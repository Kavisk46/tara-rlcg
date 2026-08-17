"""Unit tests for `evaluation.harness.aggregation`.

Per `ROADMAP.md` M10's own note, aggregation/orchestration code carries
a lighter test bar than metric functions (already independently
hand-verified in `evaluation.metrics`'s own tests) -- these tests focus
on the two properties that matter most for this module's honesty
guarantee: means skip `None`/errored values rather than treating them
as zero, and grouping puts each result in the right bucket.
"""
from __future__ import annotations

from evaluation.harness.aggregation import (
    aggregate_by_repository,
    aggregate_by_task_type,
    aggregate_by_variant,
    aggregate_overall,
)
from evaluation.harness.models import (
    EfficiencyResult,
    GenerationMetricsResult,
    QueryRunResult,
    RetrievalMetricsResult,
)
from tara.core.types import TaskType


def _result(
    *,
    variant_id: str = "TARA",
    query_id: str,
    repository_id: str = "repo-a",
    task_type: TaskType | None = TaskType.SEARCH,
    error: str | None = None,
    precision_at_5: float | None = None,
    plan_coverage: float | None = None,
    exact_match: bool | None = None,
    routing_latency_ms: float | None = 1.0,
    retriever_invocation_count: int = 1,
    retrieved_token_count: int = 10,
) -> QueryRunResult:
    retrieval_metrics = None
    if precision_at_5 is not None or plan_coverage is not None:
        retrieval_metrics = RetrievalMetricsResult(
            precision_at_k={5: precision_at_5} if precision_at_5 is not None else {},
            plan_coverage=plan_coverage,
        )
    generation_metrics = None
    if exact_match is not None:
        generation_metrics = GenerationMetricsResult(exact_match=exact_match)

    return QueryRunResult(
        variant_id=variant_id,
        query_id=query_id,
        repository_id=repository_id,
        task_type=task_type,
        retrieval_metrics=retrieval_metrics,
        generation_metrics=generation_metrics,
        efficiency=EfficiencyResult(
            routing_latency_ms=routing_latency_ms,
            generation_latency_ms=1.0,
            total_latency_ms=2.0,
            retriever_invocation_count=retriever_invocation_count,
            embedding_call_count=0,
            retrieved_token_count=retrieved_token_count,
        ),
        error=error,
    )


# ============================================================================
# aggregate_overall: means skip None / errored results
# ============================================================================


def test_aggregate_overall_hand_computed_means() -> None:
    results = [
        _result(query_id="q-1", precision_at_5=0.4, plan_coverage=0.6, exact_match=True),
        _result(query_id="q-2", precision_at_5=0.6, plan_coverage=0.8, exact_match=False),
    ]
    report = aggregate_overall(results)

    assert report.count == 2
    assert report.error_count == 0
    assert report.mean_precision_at_k[5] == 0.5
    assert report.mean_plan_coverage == 0.7
    assert report.exact_match_rate == 0.5


def test_aggregate_overall_excludes_errored_results_from_means() -> None:
    results = [
        _result(query_id="q-1", precision_at_5=1.0, plan_coverage=1.0, exact_match=True),
        _result(
            query_id="q-2",
            precision_at_5=0.0,
            plan_coverage=0.0,
            exact_match=False,
            error="boom",
        ),
    ]
    report = aggregate_overall(results)

    assert report.count == 2
    assert report.error_count == 1
    # If the errored result's 0.0 leaked into the mean, this would be 0.5, not 1.0.
    assert report.mean_precision_at_k[5] == 1.0
    assert report.mean_plan_coverage == 1.0
    assert report.exact_match_rate == 1.0


def test_aggregate_overall_skips_none_metric_values_not_treated_as_zero() -> None:
    results = [
        _result(query_id="q-1", precision_at_5=1.0, plan_coverage=None, exact_match=None),
        _result(query_id="q-2", precision_at_5=None, plan_coverage=None, exact_match=None),
    ]
    report = aggregate_overall(results)

    # Only q-1 has a retrieval_metrics object with a precision_at_5 value; q-2 contributes nothing.
    assert report.mean_precision_at_k[5] == 1.0
    assert report.mean_plan_coverage is None
    assert report.exact_match_rate is None


def test_aggregate_overall_skips_none_latency_values() -> None:
    results = [
        _result(query_id="q-1", routing_latency_ms=2.0),
        _result(query_id="q-2", routing_latency_ms=None),
    ]
    report = aggregate_overall(results)

    assert report.routing_latency_ms is not None
    assert report.routing_latency_ms.count == 1


def test_aggregate_overall_empty_results_has_zero_count() -> None:
    report = aggregate_overall([])
    assert report.count == 0
    assert report.error_count == 0
    assert report.mean_plan_coverage is None


# ============================================================================
# Grouping
# ============================================================================


def test_aggregate_by_task_type_groups_correctly() -> None:
    results = [
        _result(query_id="q-1", task_type=TaskType.SEARCH, precision_at_5=1.0),
        _result(query_id="q-2", task_type=TaskType.BUG_FIX, precision_at_5=0.0),
        _result(query_id="q-3", task_type=TaskType.SEARCH, precision_at_5=0.5),
    ]
    grouped = aggregate_by_task_type(results)

    assert set(grouped) == {"search", "bug_fix"}
    assert grouped["search"].count == 2
    assert grouped["search"].mean_precision_at_k[5] == 0.75
    assert grouped["bug_fix"].count == 1


def test_aggregate_by_task_type_excludes_results_with_no_task_type() -> None:
    results = [_result(query_id="q-1", task_type=None)]
    grouped = aggregate_by_task_type(results)
    assert grouped == {}


def test_aggregate_by_repository_groups_correctly() -> None:
    results = [
        _result(query_id="q-1", repository_id="repo-a"),
        _result(query_id="q-2", repository_id="repo-b"),
        _result(query_id="q-3", repository_id="repo-a"),
    ]
    grouped = aggregate_by_repository(results)

    assert set(grouped) == {"repo-a", "repo-b"}
    assert grouped["repo-a"].count == 2
    assert grouped["repo-b"].count == 1


def test_aggregate_by_variant_groups_correctly() -> None:
    results = [
        _result(query_id="q-1", variant_id="TARA"),
        _result(query_id="q-2", variant_id="B1"),
        _result(query_id="q-3", variant_id="TARA"),
    ]
    grouped = aggregate_by_variant(results)

    assert set(grouped) == {"TARA", "B1"}
    assert grouped["TARA"].count == 2
    assert grouped["B1"].count == 1
