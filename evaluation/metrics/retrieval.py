"""Retrieval-quality metrics, per `EXPERIMENT_PLAN.md` §3.

Every function here is a pure, per-query score: `retrieved` is an
ordered sequence of node ids (e.g. `FusedChunk.chunk_id` values, already
sorted by relevance -- the ranking a fused, top_k-cut `FusedContext`
already produces), `relevant` is the query's TIQS ground-truth
relevant-context set (`evaluation.tiqs.models.RelevantContextEntry.node_id`
values). Aggregating per-query scores into a mean (e.g. "MRR" is itself
defined as *the mean* of per-query reciprocal rank, per §3) is the
harness/aggregation layer's job, not this module's -- keeping these
functions single-query, hand-computable, and directly unit-testable
against known values, per this milestone's mandatory
hand-computed-example testing requirement.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k!r}.")


def _validate_relevant(relevant: set[str]) -> None:
    if not relevant:
        raise ValueError(
            "relevant is empty -- Precision@k/Recall@k/reciprocal_rank are undefined for a "
            "query with no ground-truth relevant items. Skip metric computation for this query "
            "(do not call with an empty relevant set) rather than silently reporting a "
            "fabricated 0.0."
        )


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Precision@k = (relevant items in top-k) / k, per `EXPERIMENT_PLAN.md` §3.

    Args:
        retrieved: Retrieved node ids, ordered by descending relevance.
        relevant: The query's ground-truth relevant node ids. Must be
            non-empty.
        k: The cutoff. The denominator is always `k` itself (the
            standard TREC-style convention), even when `len(retrieved)
            < k` -- a retriever returning fewer than `k` results is not
            given a smaller, more forgiving denominator.

    Returns:
        A value in `[0.0, 1.0]`.

    Raises:
        ValueError: If `k <= 0` or `relevant` is empty.
    """
    _validate_k(k)
    _validate_relevant(relevant)
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / k


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Recall@k = (relevant items in top-k) / (total relevant items), per `EXPERIMENT_PLAN.md` §3.

    Args:
        retrieved: Retrieved node ids, ordered by descending relevance.
        relevant: The query's ground-truth relevant node ids. Must be
            non-empty.
        k: The cutoff.

    Returns:
        A value in `[0.0, 1.0]`.

    Raises:
        ValueError: If `k <= 0` or `relevant` is empty.
    """
    _validate_k(k)
    _validate_relevant(relevant)
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    """`1 / rank` of the first relevant item in `retrieved`, or `0.0` if none is found.

    The per-query value `EXPERIMENT_PLAN.md` §3 defines MRR as the mean
    of, across the queries in a run: "MRR = mean over queries of `1 /
    rank of first relevant item` (0 if none retrieved within the
    evaluated cutoff)." No cutoff is applied within this function
    itself -- pass an already-cut (e.g. top_k-truncated) `retrieved`
    sequence if a cutoff should apply.

    Args:
        retrieved: Retrieved node ids, ordered by descending relevance.
        relevant: The query's ground-truth relevant node ids. Must be
            non-empty.

    Returns:
        `1.0 / rank` (1-indexed) of the first hit, or `0.0` if no item
        in `retrieved` is relevant.

    Raises:
        ValueError: If `relevant` is empty.
    """
    _validate_relevant(relevant)
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved: Sequence[str], relevance_grades: Mapping[str, float] | None, k: int
) -> float | None:
    """NDCG@k, computed only when graded relevance judgments are available.

    Per `EXPERIMENT_PLAN.md` §3: "computed only if TIQS annotation
    captures graded (not merely binary) relevance... if only binary
    relevance is captured, NDCG@k is reported as not applicable rather
    than computed from an artificially graded proxy." This function
    honors that directly: it returns `None`, not `0.0` or an exception,
    when no graded judgment is available -- `None` is the "not
    applicable" signal the harness/aggregation layer must propagate
    (e.g. by omitting NDCG@k from a report) rather than average away.

    Args:
        retrieved: Retrieved node ids, ordered by descending relevance.
        relevance_grades: `node_id -> graded relevance score` (e.g.
            `evaluation.tiqs.models.RelevanceTier` mapped to a numeric
            scale), or `None`/empty if this dataset version only
            recorded binary relevance.
        k: The cutoff.

    Returns:
        DCG@k / IDCG@k in `[0.0, 1.0]`, or `None` if `relevance_grades`
        is `None` or empty. `0.0` (not `None`) when `relevance_grades`
        is non-empty but every graded item has grade 0 or none appears
        in `retrieved` -- a real, computed score of "no gain achieved,"
        distinct from "not applicable."

    Raises:
        ValueError: If `k <= 0`.
    """
    _validate_k(k)
    if not relevance_grades:
        return None

    top_k = retrieved[:k]
    dcg = sum(
        relevance_grades.get(item, 0.0) / math.log2(rank + 1)
        for rank, item in enumerate(top_k, start=1)
    )
    ideal_grades = sorted(relevance_grades.values(), reverse=True)[:k]
    idcg = sum(grade / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def plan_coverage(candidates: Sequence[str] | set[str], relevant: set[str]) -> float:
    """Fraction of ground-truth relevant items that appear anywhere in the full candidate pool.

    **Not defined in `PROJECT_SPEC.md`/`EXPERIMENT_PLAN.md`** -- this
    milestone's own instructions name "plan coverage" as a required
    retrieval metric without specifying a formula, so this is this
    implementation's own reasoned design choice, documented as such
    rather than presented as an already-agreed-upon definition.

    Rationale: Precision@k/Recall@k/MRR/NDCG@k all measure *ranking*
    quality within an already-cut top-k result. None of them
    distinguishes "the right retriever ran and found the relevant item,
    but ranked it too low to survive the top-k cut" from "no retriever
    the plan selected was ever capable of finding it at all" -- two
    completely different failure modes with different fixes (better
    reranking vs. a different `RetrievalPlan.retrievers` selection).
    `plan_coverage` isolates the second: it is Recall computed against
    the *entire* pre-top-k candidate pool (e.g. every deduplicated
    candidate `ContextFusion` saw before its `plan.top_k` cut), not
    against the top-k cut ranking. A `plan_coverage` of 1.0 with a low
    Recall@k means reranking/fusion is the bottleneck; a `plan_coverage`
    below 1.0 means the plan's retriever *selection* itself is the
    ceiling -- exactly the distinction task-aware routing (RQ2) is
    meant to improve.

    Args:
        candidates: Every node id retrieved by the plan, before any
            top-k truncation (e.g. `chunk_id` for every
            `evaluation.tiqs.models.RelevantContextEntry`-comparable
            candidate `ContextFusion.fuse` deduplicated, prior to its
            own `plan.top_k` slice).
        relevant: The query's ground-truth relevant node ids. Must be
            non-empty.

    Returns:
        A value in `[0.0, 1.0]`.

    Raises:
        ValueError: If `relevant` is empty.
    """
    _validate_relevant(relevant)
    candidate_set = candidates if isinstance(candidates, set) else set(candidates)
    hits = len(candidate_set & relevant)
    return hits / len(relevant)
