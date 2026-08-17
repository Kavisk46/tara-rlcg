"""Aggregation: rolls a batch of `QueryRunResult`s up overall, and per TaskType/repository/variant.

Per this milestone's instructions: "Report results: overall; per
TaskType; per repository; per baseline." `aggregate_overall`,
`aggregate_by_task_type`, `aggregate_by_repository`, and
`aggregate_by_variant` are thin, identically-shaped wrappers over
`aggregate`, grouped by the obvious key. Every mean/rate here skips
`None` values and errored records rather than treating them as zero,
per "do not fabricate missing metrics." Per `ROADMAP.md` M10's own
testing-bar note ("full unit-test coverage of orchestration/aggregation
scripts is explicitly not required"), this module is tested more lightly
than `evaluation.metrics`, whose functions it calls and which are
already independently hand-verified.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from evaluation.harness.models import QueryRunResult
from evaluation.metrics.efficiency import LatencyPercentiles, summarize_latencies


def _mean_optional(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _mean_bool(values: Iterable[bool | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(1 for v in present if v) / len(present)


def _latency_or_none(values: list[float]) -> LatencyPercentiles | None:
    if not values:
        return None
    return summarize_latencies(values)


@dataclass(frozen=True)
class AggregateReport:
    """Summary statistics for one group of `QueryRunResult`s."""

    count: int
    error_count: int
    mean_precision_at_k: dict[int, float | None]
    mean_recall_at_k: dict[int, float | None]
    mean_reciprocal_rank: float | None
    mean_ndcg_at_k: dict[int, float | None]
    mean_plan_coverage: float | None
    exact_match_rate: float | None
    mean_edit_similarity: float | None
    syntactic_validity_rate: float | None
    routing_latency_ms: LatencyPercentiles | None
    retrieval_latency_ms: LatencyPercentiles | None
    fusion_latency_ms: LatencyPercentiles | None
    generation_latency_ms: LatencyPercentiles | None
    total_latency_ms: LatencyPercentiles | None
    mean_retriever_invocation_count: float | None
    mean_retrieved_token_count: float | None
    mean_generation_prompt_tokens: float | None
    mean_generation_completion_tokens: float | None


def aggregate(results: Sequence[QueryRunResult]) -> AggregateReport:
    """Aggregate `results` into one `AggregateReport`.

    Args:
        results: Any batch of results sharing whatever grouping the
            caller cares about (e.g. already filtered to one TaskType,
            one repository, or one variant) -- this function performs
            no grouping itself, only summarization.

    Returns:
        An `AggregateReport`. Every mean/rate is computed only from
        results where `error` is `None` and the relevant metric field
        is itself non-`None`; a group where no result has a given
        metric available yields `None` for it, never a fabricated `0.0`.
    """
    successful = [r for r in results if r.error is None]

    k_values: set[int] = set()
    for r in successful:
        if r.retrieval_metrics is not None:
            k_values.update(r.retrieval_metrics.precision_at_k)
    sorted_k = sorted(k_values)

    def retrieval_field(k: int, attr: str) -> float | None:
        values = [
            getattr(r.retrieval_metrics, attr).get(k)
            for r in successful
            if r.retrieval_metrics is not None and k in getattr(r.retrieval_metrics, attr)
        ]
        return _mean_optional(values)

    retrieval_results = [
        r.retrieval_metrics for r in successful if r.retrieval_metrics is not None
    ]
    generation_results = [
        r.generation_metrics for r in successful if r.generation_metrics is not None
    ]
    efficiencies = [r.efficiency for r in successful]

    def latencies(attr: str) -> LatencyPercentiles | None:
        values = [getattr(e, attr) for e in efficiencies if getattr(e, attr) is not None]
        return _latency_or_none(values)

    return AggregateReport(
        count=len(results),
        error_count=len(results) - len(successful),
        mean_precision_at_k={k: retrieval_field(k, "precision_at_k") for k in sorted_k},
        mean_recall_at_k={k: retrieval_field(k, "recall_at_k") for k in sorted_k},
        mean_reciprocal_rank=_mean_optional(rm.reciprocal_rank for rm in retrieval_results),
        mean_ndcg_at_k={k: retrieval_field(k, "ndcg_at_k") for k in sorted_k},
        mean_plan_coverage=_mean_optional(rm.plan_coverage for rm in retrieval_results),
        exact_match_rate=_mean_bool(gm.exact_match for gm in generation_results),
        mean_edit_similarity=_mean_optional(gm.edit_similarity for gm in generation_results),
        syntactic_validity_rate=_mean_bool(gm.syntactic_validity for gm in generation_results),
        routing_latency_ms=latencies("routing_latency_ms"),
        retrieval_latency_ms=latencies("retrieval_latency_ms"),
        fusion_latency_ms=latencies("fusion_latency_ms"),
        generation_latency_ms=latencies("generation_latency_ms"),
        total_latency_ms=latencies("total_latency_ms"),
        mean_retriever_invocation_count=_mean_optional(
            e.retriever_invocation_count for e in efficiencies
        ),
        mean_retrieved_token_count=_mean_optional(e.retrieved_token_count for e in efficiencies),
        mean_generation_prompt_tokens=_mean_optional(
            e.generation_prompt_tokens for e in efficiencies
        ),
        mean_generation_completion_tokens=_mean_optional(
            e.generation_completion_tokens for e in efficiencies
        ),
    )


def _group_by(
    results: Sequence[QueryRunResult], key_fn: Callable[[QueryRunResult], str | None]
) -> dict[str, list[QueryRunResult]]:
    groups: dict[str, list[QueryRunResult]] = defaultdict(list)
    for result in results:
        key = key_fn(result)
        if key is not None:
            groups[key].append(result)
    return dict(groups)


def aggregate_overall(results: Sequence[QueryRunResult]) -> AggregateReport:
    """The single `AggregateReport` for an entire batch, across every variant/query/repository."""
    return aggregate(results)


def aggregate_by_task_type(results: Sequence[QueryRunResult]) -> dict[str, AggregateReport]:
    """One `AggregateReport` per `TaskType.value` seen in `results`.

    Results with no `task_type` set are excluded from every group (not
    silently folded into one), since a `None` task type has no group to
    belong to.
    """
    groups = _group_by(results, lambda r: r.task_type.value if r.task_type is not None else None)
    return {key: aggregate(group) for key, group in groups.items()}


def aggregate_by_repository(results: Sequence[QueryRunResult]) -> dict[str, AggregateReport]:
    """One `AggregateReport` per `repository_id` seen in `results`."""
    groups = _group_by(results, lambda r: r.repository_id)
    return {key: aggregate(group) for key, group in groups.items()}


def aggregate_by_variant(results: Sequence[QueryRunResult]) -> dict[str, AggregateReport]:
    """One `AggregateReport` per `variant_id` seen in `results` (TARA-proper and every baseline)."""
    groups = _group_by(results, lambda r: r.variant_id)
    return {key: aggregate(group) for key, group in groups.items()}
