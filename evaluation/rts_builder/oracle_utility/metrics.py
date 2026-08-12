"""Pure, standalone retrieval-quality metric functions.

Each function takes a ranked list of retrieved file paths and a
ground-truth relevance judgment, and returns a single float in
`[0, 1]`. None of these depend on `RetrievalExecutionResult`,
`RelevanceJudgment`, or any other Oracle Utility model -- domain wiring
lives in `computer.py`, not here -- so each is independently
unit-testable against plain lists/dicts, mirroring the
"corpus-agnostic" design already established by
`tara.retrieval.bm25_index.BM25Index`.

See `Oracle_Math.md` for the full formal derivation of every formula
below.
"""
from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant files found within the top `k` retrieved files.

    Args:
        retrieved: Ranked file paths, highest-relevance-first.
        relevant: The full set of ground-truth relevant file paths.
        k: Cutoff rank.

    Returns:
        `|retrieved[:k] ∩ relevant| / |relevant|`, or `0.0` if `relevant`
        is empty (no ground truth to recall against -- not undefined,
        since a rate with a zero denominator has no meaningful value
        other than "no evidence of success").
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    """The reciprocal of the rank of the first relevant file in `retrieved`.

    Named `reciprocal_rank` (not `mrr`) because "Mean" Reciprocal Rank
    is a mean taken *across queries*; this function computes one
    query's single reciprocal-rank value, which `computer.py` reports
    as that strategy's `mrr` for this one query -- consistent with how
    an actual mean would later be computed by averaging this value
    across many queries' Oracle Utility results, a later, out-of-scope
    dataset-aggregation step.

    Args:
        retrieved: Ranked file paths, highest-relevance-first.
        relevant: The full set of ground-truth relevant file paths.

    Returns:
        `1 / rank` (1-indexed) of the first file in `retrieved` that is
        also in `relevant`, or `0.0` if none of `retrieved` is relevant
        (including when `retrieved` is empty).
    """
    for rank, file_path in enumerate(retrieved, start=1):
        if file_path in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevance_grades: dict[str, float], k: int) -> float:
    """Normalized Discounted Cumulative Gain at rank `k`, using graded relevance.

    Uses the standard exponential-gain formulation
    (`gain(rel) = 2**rel - 1`), the same convention used by the
    original NDCG papers and most IR evaluation libraries -- it
    disproportionately rewards highly-relevant results over merely
    relevant ones, which flat linear gain does not.

    Args:
        retrieved: Ranked file paths, highest-relevance-first.
        relevance_grades: `file_path -> non-negative relevance grade`.
            A file absent from this mapping is treated as grade `0`
            (not relevant).
        k: Cutoff rank, applied to both the actual and ideal orderings.

    Returns:
        `DCG@k / IDCG@k`, or `0.0` if `IDCG@k` is `0` (no relevant
        files exist in `relevance_grades` at all, so no ordering could
        possibly achieve a nonzero gain).
    """

    def gain(grade: float) -> float:
        return (2.0**grade) - 1.0

    def discount(rank_index: int) -> float:
        # rank_index is 0-based; the standard discount uses the 1-based rank + 1,
        # i.e. log2(rank_index + 2).
        return math.log2(rank_index + 2)

    dcg = sum(
        gain(relevance_grades.get(file_path, 0.0)) / discount(index)
        for index, file_path in enumerate(retrieved[:k])
    )

    ideal_grades = sorted(relevance_grades.values(), reverse=True)[:k]
    idcg = sum(gain(grade) / discount(index) for index, grade in enumerate(ideal_grades))

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def context_precision(retrieved: Sequence[str], relevant: set[str]) -> float:
    """Fraction of *all* retrieved files (not just a top-k window) that are relevant.

    Deliberately not truncated to `quality_metrics_k`, unlike
    `recall_at_k`/`ndcg_at_k`: this metric answers "of what would
    actually be handed to an LLM as context, how much of it is useful,"
    which depends on everything actually retrieved, not an arbitrary
    ranking-evaluation cutoff -- see `Oracle_Math.md`.

    Args:
        retrieved: The full retrieved file list (order does not matter
            for this metric).
        relevant: The full set of ground-truth relevant file paths.

    Returns:
        `|set(retrieved) ∩ relevant| / |retrieved|`, or `0.0` if
        `retrieved` is empty.
    """
    if not retrieved:
        return 0.0
    return len(set(retrieved) & relevant) / len(retrieved)
