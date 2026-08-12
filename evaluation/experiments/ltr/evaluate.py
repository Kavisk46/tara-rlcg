"""Phase 5 -- ranking-quality evaluation metrics for the LTR model.

Implements NDCG@1/3/5, MRR, Precision@1, Recall@1, and Top-1 Accuracy
as pure, independently-testable functions operating on one query
group's true relevance grades and predicted scores (`tests/test_evaluate.py`
checks each against hand-computed values), plus a CLI that loads a
saved model (`model.LambdaRankModel.load`), scores a split, and reports
these metrics averaged across that split's query groups.

Metric definitions (standard IR conventions -- see each function's
docstring for the exact formula used):

- **NDCG@k**: normalized discounted cumulative gain of the top-`k`
  predicted ranking, using the standard `(2^rel - 1) / log2(rank + 1)`
  gain, normalized by the ideal (true-relevance-sorted) DCG@k. `0.0`
  for a group with no relevant (`grade > 0`) items (IDCG@k == 0).
- **MRR**: mean reciprocal rank of the first relevant (`grade > 0`)
  item in the predicted ranking. `0.0` for a group with no relevant
  items (a query contributes 0, it is not excluded from the mean --
  see `mean_reciprocal_rank`'s docstring for why).
- **Precision@1**: fraction of groups whose top-predicted item is
  relevant (`grade > 0`).
- **Recall@1**: mean, across groups with >=1 relevant item, of
  (1 if the top-predicted item is relevant else 0) / (number of
  relevant items in that group) -- i.e. what fraction of a group's
  relevant items are captured by taking only the top-1 prediction.
- **Top-1 Accuracy**: fraction of groups whose top-predicted item is
  *the single highest-graded* item in that group (ties broken by "any
  item achieving the group's max grade counts as correct") --
  deliberately distinct from Precision@1, which only asks whether the
  top item is relevant *at all*, not whether it is the *best* one.

As with every other module in this package, evaluation against the
current RTS Dataset v1.0 will raise `feature_pipeline.UnlabeledDatasetError`
before computing anything, since every grade in the shipped dataset is
still the placeholder `"TO_BE_ASSIGNED"` -- see `main`'s first step.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

if __package__ in (None, ""):  # pragma: no cover - direct-execution convenience
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evaluation.experiments.ltr.feature_pipeline import (
    Encoders, RetrievalFeatureProvider, build_feature_matrix, validate_labels_are_numeric,
)
from evaluation.experiments.ltr.model import LambdaRankModel
from evaluation.experiments.ltr.utils import MERGED_DATASET_DIR, REPORTS_DIR, get_logger, read_jsonl

logger = get_logger(__name__)

DEFAULT_K_VALUES: tuple[int, ...] = (1, 3, 5)


def _dcg_at_k(relevance_in_rank_order: np.ndarray, k: int) -> float:
    """Discounted cumulative gain of the first `k` items of an already-ranked relevance sequence.

    Formula: `sum_{i=1}^{min(k, len)} (2**rel_i - 1) / log2(i + 1)`,
    with `i` 1-indexed rank position.

    Args:
        relevance_in_rank_order: Relevance grades, already ordered by
            descending predicted score (index 0 = top-ranked item).
        k: Cutoff. If `k > len(relevance_in_rank_order)`, all items are used.

    Returns:
        The DCG@k value (`>= 0`).
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    top_k = relevance_in_rank_order[:k]
    ranks = np.arange(1, len(top_k) + 1)
    gains = np.power(2.0, top_k.astype(np.float64)) - 1.0
    discounts = np.log2(ranks + 1)
    return float(np.sum(gains / discounts))


def ndcg_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """Normalized DCG@k for one query group.

    Args:
        y_true: `(n_candidates,)` true relevance grades for this group
            (any order -- this function does the sorting).
        y_score: `(n_candidates,)` predicted scores, same order as `y_true`.
        k: Cutoff.

    Returns:
        NDCG@k in `[0, 1]`. `0.0` if no candidate in this group has a
        positive relevance grade (the ideal ranking's DCG@k, the
        denominator, is 0 in that case -- avoided by returning 0
        directly rather than dividing by zero).
    """
    if len(y_true) != len(y_score):
        raise ValueError(f"y_true and y_score must have the same length, got {len(y_true)} vs {len(y_score)}")
    if len(y_true) == 0:
        raise ValueError("Cannot compute NDCG for an empty group.")

    predicted_order = np.argsort(-y_score, kind="stable")
    ideal_order = np.argsort(-y_true, kind="stable")

    dcg = _dcg_at_k(y_true[predicted_order], k)
    idcg = _dcg_at_k(y_true[ideal_order], k)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def mean_reciprocal_rank_one_group(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Reciprocal rank of the first relevant (`grade > 0`) item in the predicted ranking.

    Args:
        y_true: `(n_candidates,)` true relevance grades.
        y_score: `(n_candidates,)` predicted scores, same order.

    Returns:
        `1 / rank` of the first relevant item (1-indexed rank in the
        predicted ordering), or `0.0` if no item in this group is
        relevant. Returning `0.0` (rather than excluding the query
        from the caller's average) matches this dataset's use case: a
        query with zero relevant *candidates* is itself informative
        (a candidate-generation gap -- see `error_analysis.py`), and
        should pull the aggregate MRR down rather than be silently
        dropped from it.
    """
    if len(y_true) != len(y_score):
        raise ValueError(f"y_true and y_score must have the same length, got {len(y_true)} vs {len(y_score)}")
    predicted_order = np.argsort(-y_score, kind="stable")
    ranked_relevance = y_true[predicted_order]
    relevant_positions = np.flatnonzero(ranked_relevance > 0)
    if relevant_positions.size == 0:
        return 0.0
    first_relevant_rank = int(relevant_positions[0]) + 1  # 1-indexed
    return 1.0 / first_relevant_rank


def precision_at_1(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """`1.0` if the top-predicted item is relevant (`grade > 0`), else `0.0`."""
    top_index = int(np.argmax(y_score))
    return 1.0 if y_true[top_index] > 0 else 0.0


def recall_at_1(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """Fraction of this group's relevant items captured by the top-1 prediction.

    Returns:
        `(1 if top-1 is relevant else 0) / n_relevant`, or `None` if
        this group has zero relevant items (recall is undefined, not
        zero, in that case -- callers computing a dataset-wide average
        must exclude `None` results, see `evaluate_split`).
    """
    n_relevant = int(np.sum(y_true > 0))
    if n_relevant == 0:
        return None
    return precision_at_1(y_true, y_score) / n_relevant


def top1_accuracy(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """`1.0` if the top-predicted item achieves this group's maximum relevance grade, else `0.0`.

    Distinct from `precision_at_1`: a group with grades `[0, 1, 3]`
    scores `precision_at_1 = 1.0` if the model ranks *either* the
    grade-1 *or* grade-3 item first (both are "relevant"), but
    `top1_accuracy = 1.0` only if it ranks the grade-3 item first
    specifically.
    """
    top_index = int(np.argmax(y_score))
    return 1.0 if y_true[top_index] == np.max(y_true) else 0.0


@dataclass
class SplitMetrics:
    """Aggregate metrics for one split, each averaged across that split's query groups."""

    n_groups: int
    n_groups_with_relevant_item: int
    ndcg_at_1: float
    ndcg_at_3: float
    ndcg_at_5: float
    mrr: float
    precision_at_1: float
    recall_at_1: float
    top1_accuracy: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def evaluate_split(y_true: np.ndarray, y_score: np.ndarray, group_sizes: np.ndarray) -> SplitMetrics:
    """Compute every metric in this module, averaged across `group_sizes`' query groups.

    Args:
        y_true: `(n_rows,)` true relevance grades, `feature_pipeline.FeatureMatrix`-ordered.
        y_score: `(n_rows,)` model scores, same row order.
        group_sizes: `(n_groups,)` group boundaries, same convention
            as `feature_pipeline.FeatureMatrix.group_sizes`.

    Returns:
        A `SplitMetrics` with every metric averaged over the
        `n_groups` query groups (Recall@1 averaged only over groups
        with at least one relevant item -- see `recall_at_1`).
    """
    if y_true.shape != y_score.shape:
        raise ValueError(f"y_true and y_score must have the same shape, got {y_true.shape} vs {y_score.shape}")
    if int(np.sum(group_sizes)) != len(y_true):
        raise ValueError(f"group_sizes sums to {int(np.sum(group_sizes))} but y_true has {len(y_true)} rows.")

    ndcg1_vals: list[float] = []
    ndcg3_vals: list[float] = []
    ndcg5_vals: list[float] = []
    mrr_vals: list[float] = []
    p1_vals: list[float] = []
    r1_vals: list[float] = []
    top1_vals: list[float] = []
    n_with_relevant = 0

    offset = 0
    for size in group_sizes:
        size = int(size)
        gt = y_true[offset : offset + size]
        gs = y_score[offset : offset + size]
        offset += size

        ndcg1_vals.append(ndcg_at_k(gt, gs, 1))
        ndcg3_vals.append(ndcg_at_k(gt, gs, 3))
        ndcg5_vals.append(ndcg_at_k(gt, gs, 5))
        mrr_vals.append(mean_reciprocal_rank_one_group(gt, gs))
        p1_vals.append(precision_at_1(gt, gs))
        top1_vals.append(top1_accuracy(gt, gs))

        r1 = recall_at_1(gt, gs)
        if r1 is not None:
            r1_vals.append(r1)
            n_with_relevant += 1

    n_groups = len(group_sizes)
    return SplitMetrics(
        n_groups=n_groups,
        n_groups_with_relevant_item=n_with_relevant,
        ndcg_at_1=float(np.mean(ndcg1_vals)) if n_groups else 0.0,
        ndcg_at_3=float(np.mean(ndcg3_vals)) if n_groups else 0.0,
        ndcg_at_5=float(np.mean(ndcg5_vals)) if n_groups else 0.0,
        mrr=float(np.mean(mrr_vals)) if n_groups else 0.0,
        precision_at_1=float(np.mean(p1_vals)) if n_groups else 0.0,
        recall_at_1=float(np.mean(r1_vals)) if r1_vals else 0.0,
        top1_accuracy=float(np.mean(top1_vals)) if n_groups else 0.0,
    )


def format_report(split_name: str, metrics: SplitMetrics, model_path: Path) -> str:
    """Render one split's `SplitMetrics` as a Markdown report section."""
    lines = [
        f"# Phase 5 -- Evaluation Report: `{split_name}`",
        "",
        f"Model: `{model_path}`",
        f"Query groups evaluated: **{metrics.n_groups}** ({metrics.n_groups_with_relevant_item} with >=1 relevant candidate)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| NDCG@1 | {metrics.ndcg_at_1:.4f} |",
        f"| NDCG@3 | {metrics.ndcg_at_3:.4f} |",
        f"| NDCG@5 | {metrics.ndcg_at_5:.4f} |",
        f"| MRR | {metrics.mrr:.4f} |",
        f"| Precision@1 | {metrics.precision_at_1:.4f} |",
        f"| Recall@1 | {metrics.recall_at_1:.4f} |",
        f"| Top-1 Accuracy | {metrics.top1_accuracy:.4f} |",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: load a trained model, evaluate it on a split, write a report.

    Fails fast (does not compute anything) if the requested split has
    no real relevance grades -- see module docstring.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train", "validation", "test"], default="test")
    parser.add_argument("--merged-dataset-dir", type=Path, default=MERGED_DATASET_DIR)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--encoders-path", type=Path, required=True)
    parser.add_argument("--no-retrieval", action="store_true", help="Skip real retrieval features (must match how the model was trained).")
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args(argv)

    rows = read_jsonl(args.merged_dataset_dir / f"{args.split}.jsonl")
    validate_labels_are_numeric(rows, split_name=args.split)  # raises UnlabeledDatasetError if unlabeled

    encoders = Encoders.load(args.encoders_path)
    provider = None if args.no_retrieval else RetrievalFeatureProvider()
    matrix = build_feature_matrix(rows, encoders=encoders, retrieval_provider=provider, require_numeric_labels=True)

    model = LambdaRankModel.load(args.model_path)
    scores = model.predict(matrix.X)
    metrics = evaluate_split(matrix.y, scores, matrix.group_sizes)

    report = format_report(args.split, metrics, args.model_path)
    print(report)

    report_path = args.report_path or (REPORTS_DIR / f"phase5_evaluation_{args.split}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    (report_path.with_suffix(".json")).write_text(json.dumps(metrics.to_dict(), indent=2), encoding="utf-8")
    logger.info("Wrote %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
