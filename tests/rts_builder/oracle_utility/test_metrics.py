"""Unit tests for `evaluation.rts_builder.oracle_utility.metrics` (pure functions)."""
from __future__ import annotations

import pytest

from evaluation.rts_builder.oracle_utility.metrics import context_precision, ndcg_at_k, reciprocal_rank, recall_at_k

# ---------------------------------------------------------------------------
# recall_at_k
# ---------------------------------------------------------------------------


def test_recall_at_k_perfect_recall() -> None:
    assert recall_at_k(["a", "b"], {"a", "b"}, k=10) == 1.0


def test_recall_at_k_partial_recall() -> None:
    assert recall_at_k(["a", "c"], {"a", "b"}, k=10) == pytest.approx(0.5)


def test_recall_at_k_zero_recall() -> None:
    assert recall_at_k(["c", "d"], {"a", "b"}, k=10) == 0.0


def test_recall_at_k_respects_cutoff() -> None:
    assert recall_at_k(["c", "a"], {"a"}, k=1) == 0.0
    assert recall_at_k(["c", "a"], {"a"}, k=2) == 1.0


def test_recall_at_k_empty_relevant_set_is_zero() -> None:
    assert recall_at_k(["a", "b"], set(), k=10) == 0.0


def test_recall_at_k_empty_retrieved_is_zero() -> None:
    assert recall_at_k([], {"a"}, k=10) == 0.0


# ---------------------------------------------------------------------------
# reciprocal_rank
# ---------------------------------------------------------------------------


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank(["a", "b"], {"a"}) == 1.0


def test_reciprocal_rank_third_position() -> None:
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_reciprocal_rank_no_relevant_result_is_zero() -> None:
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_reciprocal_rank_empty_retrieved_is_zero() -> None:
    assert reciprocal_rank([], {"a"}) == 0.0


def test_reciprocal_rank_uses_the_first_match_not_the_best() -> None:
    # 'b' appears before 'a' in the ranking, even though both are relevant.
    assert reciprocal_rank(["x", "b", "a"], {"a", "b"}) == pytest.approx(1 / 2)


# ---------------------------------------------------------------------------
# ndcg_at_k
# ---------------------------------------------------------------------------


def test_ndcg_at_k_perfect_ordering_is_one() -> None:
    grades = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert ndcg_at_k(["a", "b", "c"], grades, k=3) == pytest.approx(1.0)


def test_ndcg_at_k_reversed_ordering_is_less_than_one() -> None:
    grades = {"a": 3.0, "b": 2.0, "c": 1.0}
    reversed_ndcg = ndcg_at_k(["c", "b", "a"], grades, k=3)
    assert 0.0 < reversed_ndcg < 1.0


def test_ndcg_at_k_no_relevant_documents_is_zero() -> None:
    assert ndcg_at_k(["a", "b"], {}, k=10) == 0.0


def test_ndcg_at_k_respects_cutoff() -> None:
    grades = {"a": 1.0}
    # 'a' is outside the top-1 cutoff -- actual DCG@1 sees no relevant document.
    assert ndcg_at_k(["x", "a"], grades, k=1) == 0.0


def test_ndcg_at_k_unjudged_documents_contribute_zero_gain() -> None:
    grades = {"a": 1.0}
    # 'x' and 'y' are unjudged (absent from grades) -- treated as relevance 0, not excluded.
    assert ndcg_at_k(["a", "x", "y"], grades, k=3) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# context_precision
# ---------------------------------------------------------------------------


def test_context_precision_all_relevant() -> None:
    assert context_precision(["a", "b"], {"a", "b"}) == 1.0


def test_context_precision_half_relevant() -> None:
    assert context_precision(["a", "c"], {"a"}) == pytest.approx(0.5)


def test_context_precision_none_relevant() -> None:
    assert context_precision(["c", "d"], {"a", "b"}) == 0.0


def test_context_precision_empty_retrieved_is_zero() -> None:
    assert context_precision([], {"a"}) == 0.0


def test_context_precision_is_not_truncated_by_any_k() -> None:
    # Unlike recall/ndcg, context_precision has no k parameter -- it considers everything retrieved.
    retrieved = ["a"] + [f"irrelevant_{i}" for i in range(20)]
    assert context_precision(retrieved, {"a"}) == pytest.approx(1 / 21)
