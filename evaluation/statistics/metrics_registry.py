"""Which `QueryRunResult` metrics exist, how to extract them, and which paired test applies.

`MetricSpec.kind` is what "do not select a statistical test simply
because it gives a favorable p-value" is enforced against:
`select_paired_test_name` is a pure function of `kind` alone, fixed
before any comparison ever runs, never a function of the extracted
values themselves.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from evaluation.harness.models import QueryRunResult

MetricKind = Literal["continuous", "binary"]


@dataclass(frozen=True)
class MetricSpec:
    """One named, extractable metric, and whether it is continuous or binary.

    `extractor` returns `None` for a query/result this metric cannot be
    computed for (an errored run, or a `QueryRunResult` whose
    `retrieval_metrics`/`generation_metrics` is `None`) -- callers must
    exclude, never coerce to `0.0`, per "do not fabricate missing
    metrics" (already established in M11).
    """

    name: str
    kind: MetricKind
    extractor: Callable[[QueryRunResult], float | bool | None]


def select_paired_test_name(kind: MetricKind) -> str:
    """The fixed, pre-registered paired-test choice for a metric of this `kind`.

    Per `EXPERIMENT_PLAN.md` §6: Wilcoxon signed-rank for continuous
    paired metrics (the general case); McNemar's test for paired binary
    outcomes specifically ("appropriate for paired nominal/binary data,
    in place of Wilcoxon for this specific metric type"). This function
    reads only `kind` -- never the data -- so the same metric always
    gets the same test, every time it is analyzed, regardless of what
    the resulting p-value would be.

    Args:
        kind: `"continuous"` or `"binary"`.

    Returns:
        `"wilcoxon_signed_rank"` or `"mcnemar"`.

    Raises:
        ValueError: If `kind` is neither.
    """
    if kind == "continuous":
        return "wilcoxon_signed_rank"
    if kind == "binary":
        return "mcnemar"
    raise ValueError(f"Unknown metric kind {kind!r}; expected 'continuous' or 'binary'.")


def precision_at_k_spec(k: int) -> MetricSpec:
    """Precision@k, per `EXPERIMENT_PLAN.md` §3."""

    def extractor(result: QueryRunResult) -> float | None:
        if result.error is not None or result.retrieval_metrics is None:
            return None
        return result.retrieval_metrics.precision_at_k.get(k)

    return MetricSpec(name=f"precision_at_{k}", kind="continuous", extractor=extractor)


def recall_at_k_spec(k: int) -> MetricSpec:
    """Recall@k, per `EXPERIMENT_PLAN.md` §3."""

    def extractor(result: QueryRunResult) -> float | None:
        if result.error is not None or result.retrieval_metrics is None:
            return None
        return result.retrieval_metrics.recall_at_k.get(k)

    return MetricSpec(name=f"recall_at_{k}", kind="continuous", extractor=extractor)


def ndcg_at_k_spec(k: int) -> MetricSpec:
    """NDCG@k, per `EXPERIMENT_PLAN.md` §3. `None` per-query whenever graded relevance was not
    available for that query (`evaluation.metrics.retrieval.ndcg_at_k`'s own contract) -- such
    queries are excluded from the paired sample, same as any other missing metric."""

    def extractor(result: QueryRunResult) -> float | None:
        if result.error is not None or result.retrieval_metrics is None:
            return None
        return result.retrieval_metrics.ndcg_at_k.get(k)

    return MetricSpec(name=f"ndcg_at_{k}", kind="continuous", extractor=extractor)


def _reciprocal_rank(result: QueryRunResult) -> float | None:
    if result.error is not None or result.retrieval_metrics is None:
        return None
    return result.retrieval_metrics.reciprocal_rank


def _plan_coverage(result: QueryRunResult) -> float | None:
    if result.error is not None or result.retrieval_metrics is None:
        return None
    return result.retrieval_metrics.plan_coverage


def _exact_match(result: QueryRunResult) -> bool | None:
    if result.error is not None or result.generation_metrics is None:
        return None
    return result.generation_metrics.exact_match


def _edit_similarity(result: QueryRunResult) -> float | None:
    if result.error is not None or result.generation_metrics is None:
        return None
    return result.generation_metrics.edit_similarity


def _syntactic_validity(result: QueryRunResult) -> bool | None:
    if result.error is not None or result.generation_metrics is None:
        return None
    return result.generation_metrics.syntactic_validity


def _total_latency_ms(result: QueryRunResult) -> float | None:
    if result.error is not None:
        return None
    return result.efficiency.total_latency_ms


def _retrieved_token_count(result: QueryRunResult) -> float | None:
    if result.error is not None:
        return None
    return float(result.efficiency.retrieved_token_count)


RECIPROCAL_RANK = MetricSpec(name="reciprocal_rank", kind="continuous", extractor=_reciprocal_rank)
PLAN_COVERAGE = MetricSpec(name="plan_coverage", kind="continuous", extractor=_plan_coverage)
EXACT_MATCH = MetricSpec(name="exact_match", kind="binary", extractor=_exact_match)
EDIT_SIMILARITY = MetricSpec(name="edit_similarity", kind="continuous", extractor=_edit_similarity)
SYNTACTIC_VALIDITY = MetricSpec(
    name="syntactic_validity", kind="binary", extractor=_syntactic_validity
)
TOTAL_LATENCY_MS = MetricSpec(
    name="total_latency_ms", kind="continuous", extractor=_total_latency_ms
)
RETRIEVED_TOKEN_COUNT = MetricSpec(
    name="retrieved_token_count", kind="continuous", extractor=_retrieved_token_count
)
