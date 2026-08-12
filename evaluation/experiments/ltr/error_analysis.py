"""Phase 7 -- systematic failure-mode analysis: repository, query, and confidence failures.

Given a trained model's predictions on a labeled split, breaks down
where and how it fails, along three axes:

- **Repository failures**: per-`repository_id` aggregate accuracy/NDCG,
  to spot whether the model systematically underperforms on
  particular repositories (e.g. the largest/most complex ones).
- **Query failures**: a per-query table of predicted-vs-true top file,
  sorted worst-first, so a reviewer can read the actual query text and
  judge *why* a specific ranking went wrong -- something no aggregate
  metric can show.
- **Confidence failures**: the subset of wrong predictions where the
  model was nonetheless *confident* (a large score margin between its
  top-1 and second-best candidate) -- the most concerning failure mode
  for a ranking system, since a wrong-but-confident prediction is more
  likely to mislead a downstream consumer than a wrong-but-uncertain
  one. Confidence here is a **margin proxy** (`top_1_score -
  top_2_score`), not a calibrated probability -- `LGBMRanker` scores
  are not probabilities, and this module never presents them as such.
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

from evaluation.experiments.ltr.evaluate import ndcg_at_k, top1_accuracy
from evaluation.experiments.ltr.utils import REPORTS_DIR, get_logger

logger = get_logger(__name__)


@dataclass
class QueryFailureRow:
    """One query group's outcome: enough to judge, by eye, why the model succeeded or failed."""

    query_id: str
    repository_id: str
    category: str
    difficulty: str
    n_candidates: int
    is_top1_correct: bool
    ndcg_at_5: float
    predicted_top_file: str
    predicted_top_score: float
    score_margin: float  # predicted_top_score - second_best_score (0.0 if only 1 candidate)
    true_best_file: str
    true_best_grade: int

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_queries(
    query_ids: list[str],
    repository_ids: list[str],
    categories: list[str],
    difficulties: list[str],
    file_paths: list[str],
    y_true: np.ndarray,
    y_score: np.ndarray,
    group_sizes: np.ndarray,
) -> list[QueryFailureRow]:
    """Build one `QueryFailureRow` per query group.

    Args:
        query_ids: One entry per group (length == `len(group_sizes)`).
        repository_ids: One entry per *row* of `y_true`/`y_score`
            (length == `y_true.shape[0]`) -- same convention as
            `feature_pipeline.FeatureMatrix.repository_ids`.
        categories: One entry per group.
        difficulties: One entry per group.
        file_paths: One entry per row.
        y_true: `(n_rows,)` true relevance grades.
        y_score: `(n_rows,)` model scores.
        group_sizes: `(n_groups,)` group boundaries.

    Returns:
        One row per group, in `group_sizes`' order.
    """
    if len(query_ids) != len(group_sizes):
        raise ValueError(f"query_ids has {len(query_ids)} entries but group_sizes has {len(group_sizes)}")
    if len(categories) != len(group_sizes) or len(difficulties) != len(group_sizes):
        raise ValueError("categories/difficulties must have one entry per group.")

    rows: list[QueryFailureRow] = []
    offset = 0
    for group_idx, size in enumerate(group_sizes):
        size = int(size)
        gt = y_true[offset : offset + size]
        gs = y_score[offset : offset + size]
        g_files = file_paths[offset : offset + size]
        g_repos = repository_ids[offset : offset + size]
        offset += size

        order = np.argsort(-gs, kind="stable")
        top_idx = int(order[0])
        second_score = float(gs[order[1]]) if size > 1 else float(gs[order[0]])

        true_best_local_idx = int(np.argmax(gt))

        rows.append(
            QueryFailureRow(
                query_id=query_ids[group_idx],
                repository_id=g_repos[0],
                category=categories[group_idx],
                difficulty=difficulties[group_idx],
                n_candidates=size,
                is_top1_correct=bool(top1_accuracy(gt, gs) == 1.0),
                ndcg_at_5=ndcg_at_k(gt, gs, 5),
                predicted_top_file=g_files[top_idx],
                predicted_top_score=float(gs[top_idx]),
                score_margin=float(gs[top_idx]) - second_score,
                true_best_file=g_files[true_best_local_idx],
                true_best_grade=int(gt[true_best_local_idx]),
            )
        )
    return rows


def summarize_by_repository(rows: list[QueryFailureRow]) -> dict[str, dict[str, float]]:
    """Per-`repository_id` mean `is_top1_correct` and `ndcg_at_5`, plus query count."""
    by_repo: dict[str, list[QueryFailureRow]] = {}
    for r in rows:
        by_repo.setdefault(r.repository_id, []).append(r)
    return {
        repo: {
            "n_queries": len(repo_rows),
            "top1_accuracy": float(np.mean([r.is_top1_correct for r in repo_rows])),
            "mean_ndcg_at_5": float(np.mean([r.ndcg_at_5 for r in repo_rows])),
        }
        for repo, repo_rows in sorted(by_repo.items())
    }


def summarize_by_category(rows: list[QueryFailureRow]) -> dict[str, dict[str, float]]:
    """Per-`category` mean `is_top1_correct` and `ndcg_at_5`, plus query count."""
    by_cat: dict[str, list[QueryFailureRow]] = {}
    for r in rows:
        by_cat.setdefault(r.category, []).append(r)
    return {
        cat: {
            "n_queries": len(cat_rows),
            "top1_accuracy": float(np.mean([r.is_top1_correct for r in cat_rows])),
            "mean_ndcg_at_5": float(np.mean([r.ndcg_at_5 for r in cat_rows])),
        }
        for cat, cat_rows in sorted(by_cat.items())
    }


def find_confidence_failures(rows: list[QueryFailureRow], margin_threshold: float) -> list[QueryFailureRow]:
    """Wrong predictions (`is_top1_correct is False`) with `score_margin >= margin_threshold`.

    Args:
        rows: Query failure rows, as produced by `analyze_queries`.
        margin_threshold: Minimum score margin to count as "confident".
            There is no universal correct value for this -- it depends
            on the trained model's score scale -- so callers should set
            it relative to the *observed* margin distribution (e.g. its
            75th percentile among all queries), not a hardcoded
            constant; `main` does exactly this by default.

    Returns:
        The matching rows, sorted by `score_margin` descending (most
        confidently wrong first).
    """
    failures = [r for r in rows if not r.is_top1_correct and r.score_margin >= margin_threshold]
    return sorted(failures, key=lambda r: -r.score_margin)


def format_report(
    rows: list[QueryFailureRow],
    by_repo: dict[str, dict[str, float]],
    by_category: dict[str, dict[str, float]],
    confidence_failures: list[QueryFailureRow],
    margin_threshold: float,
) -> str:
    lines = ["# Phase 7 -- Error Analysis Report", ""]

    overall_acc = float(np.mean([r.is_top1_correct for r in rows])) if rows else 0.0
    lines += [f"Overall top-1 accuracy: **{overall_acc:.4f}** across **{len(rows)}** query groups.", ""]

    lines += ["## Repository failures", "", "| Repository | n queries | Top-1 accuracy | Mean NDCG@5 |", "|---|---|---|---|"]
    for repo, stats in by_repo.items():
        lines.append(f"| {repo} | {int(stats['n_queries'])} | {stats['top1_accuracy']:.4f} | {stats['mean_ndcg_at_5']:.4f} |")
    lines.append("")

    lines += ["## Category failures", "", "| Category | n queries | Top-1 accuracy | Mean NDCG@5 |", "|---|---|---|---|"]
    for cat, stats in by_category.items():
        lines.append(f"| {cat} | {int(stats['n_queries'])} | {stats['top1_accuracy']:.4f} | {stats['mean_ndcg_at_5']:.4f} |")
    lines.append("")

    lines += ["## Query failures (worst NDCG@5 first, top 20)", "", "| Query | Repo | Category | NDCG@5 | Predicted top | True best (grade) |", "|---|---|---|---|---|---|"]
    worst_first = sorted(rows, key=lambda r: r.ndcg_at_5)
    for r in worst_first[:20]:
        lines.append(
            f"| {r.query_id} | {r.repository_id} | {r.category} | {r.ndcg_at_5:.4f} | `{r.predicted_top_file}` | "
            f"`{r.true_best_file}` ({r.true_best_grade}) |"
        )
    lines.append("")

    lines += [
        f"## Confidence failures (wrong predictions with score margin >= {margin_threshold:.4f})",
        "",
        f"**{len(confidence_failures)}** of {len(rows)} queries are confidently wrong -- the model's top-1 "
        "choice was incorrect *and* scored well ahead of the runner-up, meaning it was not a near-miss.",
        "",
        "| Query | Repo | Margin | Predicted top | True best (grade) |",
        "|---|---|---|---|---|",
    ]
    for r in confidence_failures[:20]:
        lines.append(
            f"| {r.query_id} | {r.repository_id} | {r.score_margin:.4f} | `{r.predicted_top_file}` | "
            f"`{r.true_best_file}` ({r.true_best_grade}) |"
        )
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: load model predictions already computed by `evaluate.py`-style scoring and analyze them.

    Reuses `feature_pipeline`/`model` directly (same pattern as
    `evaluate.py`) rather than requiring a separate precomputed-scores
    file, so this script's inputs are exactly the same
    `--model-path`/`--encoders-path`/`--split` triple as `evaluate.py`.
    """
    from evaluation.experiments.ltr.feature_pipeline import Encoders, RetrievalFeatureProvider, build_feature_matrix, validate_labels_are_numeric
    from evaluation.experiments.ltr.model import LambdaRankModel
    from evaluation.experiments.ltr.utils import MERGED_DATASET_DIR, read_jsonl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train", "validation", "test"], default="test")
    parser.add_argument("--merged-dataset-dir", type=Path, default=MERGED_DATASET_DIR)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--encoders-path", type=Path, required=True)
    parser.add_argument("--no-retrieval", action="store_true")
    parser.add_argument("--confidence-margin-percentile", type=float, default=75.0)
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args(argv)

    rows_raw = read_jsonl(args.merged_dataset_dir / f"{args.split}.jsonl")
    validate_labels_are_numeric(rows_raw, split_name=args.split)

    encoders = Encoders.load(args.encoders_path)
    provider = None if args.no_retrieval else RetrievalFeatureProvider()
    matrix = build_feature_matrix(rows_raw, encoders=encoders, retrieval_provider=provider, require_numeric_labels=True)

    model = LambdaRankModel.load(args.model_path)
    scores = model.predict(matrix.X)

    # Per-group category/difficulty, in matrix.query_ids' exact order -- looked up by query_id
    # rather than zipped positionally, since build_feature_matrix may have dropped a query
    # entirely (if every one of its candidates lacked a real label), which would silently
    # misalign a positional zip against rows_raw.
    row_by_qid = {r["query_id"]: r for r in rows_raw}
    categories = [row_by_qid[qid]["category"] for qid in matrix.query_ids]
    difficulties = [row_by_qid[qid]["difficulty"] for qid in matrix.query_ids]

    failure_rows = analyze_queries(
        matrix.query_ids, matrix.repository_ids, categories, difficulties, matrix.file_paths,
        matrix.y, scores, matrix.group_sizes,
    )
    by_repo = summarize_by_repository(failure_rows)
    by_category = summarize_by_category(failure_rows)

    margins = np.array([r.score_margin for r in failure_rows if not r.is_top1_correct])
    margin_threshold = float(np.percentile(margins, args.confidence_margin_percentile)) if len(margins) else 0.0
    confidence_failures = find_confidence_failures(failure_rows, margin_threshold)

    report = format_report(failure_rows, by_repo, by_category, confidence_failures, margin_threshold)
    print(report)

    report_path = args.report_path or (REPORTS_DIR / f"phase7_error_analysis_{args.split}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    (report_path.with_suffix(".json")).write_text(
        json.dumps(
            {
                "by_repository": by_repo,
                "by_category": by_category,
                "confidence_margin_threshold": margin_threshold,
                "n_confidence_failures": len(confidence_failures),
                "queries": [r.to_dict() for r in failure_rows],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Wrote %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
