"""Unit tests for `evaluation.metrics.efficiency`."""
from __future__ import annotations

import pytest

from evaluation.metrics.efficiency import (
    embedding_call_count,
    estimate_cost,
    percentile,
    retriever_invocation_count,
    summarize_latencies,
)
from tara.core.types import RetrieverKind
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy

_VALUES = [10.0, 20.0, 30.0, 40.0, 50.0]


def _make_plan(retrievers: list[RetrieverKind]) -> RetrievalPlan:
    return RetrievalPlan(
        strategy=RoutingStrategy.HYBRID,
        retrievers=retrievers,
        execution_order=retrievers,
        parallel=len(retrievers) > 1,
        rerank=False,
        top_k=10,
        candidate_limit=10,
        reason="test",
    )


# ============================================================================
# percentile
# ============================================================================


def test_percentile_50_hand_computed() -> None:
    assert percentile(_VALUES, 50) == 30.0


def test_percentile_95_hand_computed() -> None:
    assert percentile(_VALUES, 95) == 50.0


def test_percentile_99_hand_computed() -> None:
    assert percentile(_VALUES, 99) == 50.0


def test_percentile_0_is_minimum() -> None:
    assert percentile(_VALUES, 0) == 10.0


def test_percentile_100_is_maximum() -> None:
    assert percentile(_VALUES, 100) == 50.0


def test_percentile_single_value() -> None:
    assert percentile([42.0], 50) == 42.0


def test_percentile_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="empty"):
        percentile([], 50)


def test_percentile_rejects_out_of_range_p() -> None:
    with pytest.raises(ValueError, match=r"\[0, 100\]"):
        percentile(_VALUES, 150)


# ============================================================================
# summarize_latencies
# ============================================================================


def test_summarize_latencies_hand_computed() -> None:
    summary = summarize_latencies(_VALUES)
    assert summary.p50 == 30.0
    assert summary.p95 == 50.0
    assert summary.p99 == 50.0
    assert summary.count == 5


def test_summarize_latencies_rejects_empty() -> None:
    with pytest.raises(ValueError):
        summarize_latencies([])


# ============================================================================
# retriever_invocation_count / embedding_call_count
# ============================================================================


def test_retriever_invocation_count_none_plan_is_zero() -> None:
    assert retriever_invocation_count(None) == 0


def test_retriever_invocation_count_matches_retriever_list_length() -> None:
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH])
    assert retriever_invocation_count(plan) == 3


def test_embedding_call_count_none_plan_is_zero() -> None:
    assert embedding_call_count(None) == 0


def test_embedding_call_count_one_when_dense_present() -> None:
    plan = _make_plan([RetrieverKind.DENSE])
    assert embedding_call_count(plan) == 1


def test_embedding_call_count_zero_when_dense_absent() -> None:
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.GRAPH])
    assert embedding_call_count(plan) == 0


# ============================================================================
# estimate_cost
# ============================================================================


def test_estimate_cost_returns_none_without_price_table() -> None:
    assert estimate_cost(1, 100, 50) is None


def test_estimate_cost_hand_computed_with_price_table() -> None:
    price_table = {"embedding_call": 0.001, "prompt_token": 0.0001, "completion_token": 0.0002}
    # 2 * 0.001 + 100 * 0.0001 + 50 * 0.0002 = 0.002 + 0.01 + 0.01 = 0.022
    assert estimate_cost(2, 100, 50, price_table=price_table) == pytest.approx(0.022)


def test_estimate_cost_missing_price_key_treated_as_zero() -> None:
    assert estimate_cost(5, 0, 0, price_table={}) == 0.0
