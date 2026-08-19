"""Shared builder helpers for the `evaluation.statistics` test suite.

All content produced here is synthetic test fixture data, mirroring
every other test package in this session (`evaluation.tiqs`,
`evaluation.baselines`, `evaluation.harness`) -- never presented as a
real experiment result.
"""
from __future__ import annotations

from evaluation.harness.models import (
    EfficiencyResult,
    GenerationMetricsResult,
    QueryRunResult,
    RetrievalMetricsResult,
)
from tara.core.types import TaskType

# The exact 5-pair example already hand-verified in
# evaluation/statistics/tests/test_significance.py: Wilcoxon statistic=4.5, p=1.0,
# rank_biserial_correlation=-0.1. Reused here so every test exercising this layer end to end
# through QueryRunResults is checked against numbers already independently confirmed.
RECIPROCAL_RANK_A_VALUES = [5.0, 8.0, 3.0, 10.0, 6.0]
RECIPROCAL_RANK_B_VALUES = [6.0, 7.0, 3.0, 8.0, 9.0]


def make_efficiency(total_latency_ms: float = 10.0) -> EfficiencyResult:
    return EfficiencyResult(
        generation_latency_ms=total_latency_ms,
        total_latency_ms=total_latency_ms,
        retriever_invocation_count=1,
        embedding_call_count=0,
        retrieved_token_count=100,
    )


def make_result(
    *,
    variant_id: str = "TARA",
    query_id: str = "q-1",
    repository_id: str = "repo-a",
    task_type: TaskType | None = TaskType.SEARCH,
    precision_at_5: float | None = None,
    recall_at_5: float | None = None,
    reciprocal_rank: float | None = None,
    plan_coverage: float | None = None,
    exact_match: bool | None = None,
    edit_similarity: float | None = None,
    syntactic_validity: bool | None = None,
    total_latency_ms: float = 10.0,
    error: str | None = None,
) -> QueryRunResult:
    has_retrieval_metrics = (
        precision_at_5 is not None
        or recall_at_5 is not None
        or reciprocal_rank is not None
        or plan_coverage is not None
    )
    retrieval_metrics = None
    if has_retrieval_metrics:
        retrieval_metrics = RetrievalMetricsResult(
            precision_at_k={5: precision_at_5} if precision_at_5 is not None else {},
            recall_at_k={5: recall_at_5} if recall_at_5 is not None else {},
            reciprocal_rank=reciprocal_rank,
            plan_coverage=plan_coverage,
        )

    has_generation_metrics = (
        exact_match is not None or edit_similarity is not None or syntactic_validity is not None
    )
    generation_metrics = None
    if has_generation_metrics:
        generation_metrics = GenerationMetricsResult(
            exact_match=exact_match,
            edit_similarity=edit_similarity,
            syntactic_validity=syntactic_validity,
        )

    return QueryRunResult(
        variant_id=variant_id,
        query_id=query_id,
        repository_id=repository_id,
        task_type=task_type,
        retrieval_metrics=retrieval_metrics,
        generation_metrics=generation_metrics,
        efficiency=make_efficiency(total_latency_ms),
        error=error,
    )


def make_reciprocal_rank_results(variant_id: str, values: list[float]) -> list[QueryRunResult]:
    return [
        make_result(variant_id=variant_id, query_id=f"q-{i}", reciprocal_rank=v)
        for i, v in enumerate(values)
    ]
