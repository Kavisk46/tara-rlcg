"""Unit tests for `evaluation.metrics.retrieval`.

Every test asserts against a hand-computed value, per this milestone's
own explicit requirement that a metric-implementation bug "would
silently invalidate reported results."
"""
from __future__ import annotations

import pytest

from evaluation.metrics.retrieval import (
    ndcg_at_k,
    plan_coverage,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

_RETRIEVED = ["a", "b", "c", "d", "e"]
_RELEVANT = {"b", "d", "f"}  # "f" is relevant but never retrieved


# ============================================================================
# precision_at_k
# ============================================================================


def test_precision_at_3_hand_computed() -> None:
    # top-3 = [a, b, c]; hits = {b} -> 1/3
    assert precision_at_k(_RETRIEVED, _RELEVANT, k=3) == pytest.approx(1 / 3)


def test_precision_at_5_hand_computed() -> None:
    # top-5 = [a, b, c, d, e]; hits = {b, d} -> 2/5
    assert precision_at_k(_RETRIEVED, _RELEVANT, k=5) == pytest.approx(2 / 5)


def test_precision_at_k_denominator_is_k_not_len_retrieved() -> None:
    # Only 2 items retrieved, k=5: denominator is still 5, not 2.
    assert precision_at_k(["b", "d"], _RELEVANT, k=5) == pytest.approx(2 / 5)


def test_precision_at_k_with_no_hits_is_zero() -> None:
    assert precision_at_k(["x", "y"], _RELEVANT, k=2) == 0.0


def test_precision_at_k_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="positive"):
        precision_at_k(_RETRIEVED, _RELEVANT, k=0)


def test_precision_at_k_rejects_empty_relevant() -> None:
    with pytest.raises(ValueError, match="empty"):
        precision_at_k(_RETRIEVED, set(), k=3)


# ============================================================================
# recall_at_k
# ============================================================================


def test_recall_at_3_hand_computed() -> None:
    # top-3 hits = {b} -> 1/3 of 3 relevant items
    assert recall_at_k(_RETRIEVED, _RELEVANT, k=3) == pytest.approx(1 / 3)


def test_recall_at_5_hand_computed() -> None:
    # top-5 hits = {b, d} -> 2/3 of 3 relevant items
    assert recall_at_k(_RETRIEVED, _RELEVANT, k=5) == pytest.approx(2 / 3)


def test_recall_at_k_all_relevant_found_is_one() -> None:
    assert recall_at_k(["b", "d", "f"], {"b", "d", "f"}, k=3) == 1.0


def test_recall_at_k_rejects_empty_relevant() -> None:
    with pytest.raises(ValueError, match="empty"):
        recall_at_k(_RETRIEVED, set(), k=3)


# ============================================================================
# reciprocal_rank
# ============================================================================


def test_reciprocal_rank_first_hit_at_rank_2() -> None:
    # "b" (relevant) is the first hit, at 1-indexed rank 2.
    assert reciprocal_rank(_RETRIEVED, _RELEVANT) == pytest.approx(0.5)


def test_reciprocal_rank_first_item_is_relevant() -> None:
    assert reciprocal_rank(["b", "a"], _RELEVANT) == pytest.approx(1.0)


def test_reciprocal_rank_no_hit_is_zero() -> None:
    assert reciprocal_rank(["x", "y", "z"], _RELEVANT) == 0.0


def test_reciprocal_rank_empty_retrieved_is_zero() -> None:
    assert reciprocal_rank([], _RELEVANT) == 0.0


def test_reciprocal_rank_rejects_empty_relevant() -> None:
    with pytest.raises(ValueError, match="empty"):
        reciprocal_rank(_RETRIEVED, set())


# ============================================================================
# ndcg_at_k
# ============================================================================


def test_ndcg_at_k_returns_none_when_grades_are_none() -> None:
    assert ndcg_at_k(_RETRIEVED, None, k=3) is None


def test_ndcg_at_k_returns_none_when_grades_are_empty() -> None:
    assert ndcg_at_k(_RETRIEVED, {}, k=3) is None


def test_ndcg_at_4_hand_computed() -> None:
    # DCG = 0/log2(2) + 3/log2(3) + 2/log2(4) + 1/log2(5)
    #     = 0 + 1.8927892607511... + 1.0 + 0.4306765580733...
    #     = 3.3234658187877...
    # IDCG (ideal order [3,2,1,0]) = 3/log2(2) + 2/log2(3) + 1/log2(4) + 0/log2(5)
    #     = 3.0 + 1.2618595071429... + 0.5 + 0.0 = 4.7618595071429...
    # NDCG = 3.3234658187877... / 4.7618595071429... = 0.6979344547655...
    grades = {"a": 3, "b": 2, "c": 0, "d": 1}
    retrieved = ["c", "a", "b", "d"]
    assert ndcg_at_k(retrieved, grades, k=4) == pytest.approx(0.697934454765513)


def test_ndcg_at_k_perfect_ranking_is_one() -> None:
    grades = {"a": 3, "b": 2, "c": 1}
    assert ndcg_at_k(["a", "b", "c"], grades, k=3) == pytest.approx(1.0)


def test_ndcg_at_k_all_zero_grades_is_zero_not_none() -> None:
    grades = {"a": 0, "b": 0}
    assert ndcg_at_k(["a", "b"], grades, k=2) == 0.0


def test_ndcg_at_k_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="positive"):
        ndcg_at_k(_RETRIEVED, {"a": 1}, k=0)


# ============================================================================
# plan_coverage
# ============================================================================


def test_plan_coverage_partial_hand_computed() -> None:
    # candidates has {b, d} of the 3 relevant items -> 2/3
    assert plan_coverage(["a", "b", "c", "d", "e"], _RELEVANT) == pytest.approx(2 / 3)


def test_plan_coverage_full_coverage_is_one() -> None:
    assert plan_coverage(["b", "d", "f", "z"], _RELEVANT) == 1.0


def test_plan_coverage_accepts_a_set_of_candidates() -> None:
    assert plan_coverage({"b", "d", "f"}, _RELEVANT) == 1.0


def test_plan_coverage_no_overlap_is_zero() -> None:
    assert plan_coverage(["x", "y", "z"], _RELEVANT) == 0.0


def test_plan_coverage_rejects_empty_relevant() -> None:
    with pytest.raises(ValueError, match="empty"):
        plan_coverage(_RETRIEVED, set())


def test_plan_coverage_is_at_least_recall_at_k() -> None:
    # Coverage over the full candidate pool can never be lower than recall at any k <= pool size,
    # since the top-k ranking is itself a subset of the full candidate pool.
    k = 3
    assert plan_coverage(_RETRIEVED, _RELEVANT) >= recall_at_k(_RETRIEVED, _RELEVANT, k=k)
