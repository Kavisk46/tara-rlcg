"""Unit tests for `evaluate.py`'s ranking metrics against hand-computable synthetic examples.

None of these values are experiment results -- every input here is a
small, fabricated array chosen specifically because its correct metric
value can be computed by hand and checked against. See each test's
inline arithmetic for the expected-value derivation.
"""
from __future__ import annotations

import numpy as np
import pytest

from evaluation.experiments.ltr.evaluate import (
    evaluate_split, mean_reciprocal_rank_one_group, ndcg_at_k, precision_at_1, recall_at_1, top1_accuracy,
)


class TestNdcgAtK:
    def test_perfect_ranking_is_1(self) -> None:
        # Scores already in true-relevance order -> DCG == IDCG -> NDCG == 1.0 for any k.
        y_true = np.array([3, 1, 0])
        y_score = np.array([3.0, 2.0, 1.0])
        assert ndcg_at_k(y_true, y_score, 3) == pytest.approx(1.0)

    def test_worst_ranking_below_1(self) -> None:
        # Scores in exactly reversed order relative to relevance.
        y_true = np.array([3, 1, 0])
        y_score = np.array([1.0, 2.0, 3.0])  # ranks index2 (rel=0) first, index1 (rel=1) second, index0 (rel=3) last
        # DCG@3 = (2^0-1)/log2(2) + (2^1-1)/log2(3) + (2^3-1)/log2(4) = 0 + 0.6309 + 3.5 = 4.1309
        # IDCG@3 = (2^3-1)/log2(2) + (2^1-1)/log2(3) + (2^0-1)/log2(4) = 7 + 0.6309 + 0 = 7.6309
        expected = (0 + (2**1 - 1) / np.log2(3) + (2**3 - 1) / np.log2(4)) / (
            (2**3 - 1) / np.log2(2) + (2**1 - 1) / np.log2(3) + 0
        )
        assert ndcg_at_k(y_true, y_score, 3) == pytest.approx(expected)

    def test_no_relevant_items_is_0(self) -> None:
        y_true = np.array([0, 0, 0])
        y_score = np.array([1.0, 2.0, 3.0])
        assert ndcg_at_k(y_true, y_score, 3) == 0.0

    def test_k_larger_than_group_uses_whole_group(self) -> None:
        y_true = np.array([1, 0])
        y_score = np.array([1.0, 0.0])
        # k=10 should behave identically to k=2 for a 2-item group.
        assert ndcg_at_k(y_true, y_score, 10) == ndcg_at_k(y_true, y_score, 2)

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ValueError):
            ndcg_at_k(np.array([1, 2]), np.array([1.0]), 1)

    def test_empty_group_raises(self) -> None:
        with pytest.raises(ValueError):
            ndcg_at_k(np.array([]), np.array([]), 1)


class TestMeanReciprocalRank:
    def test_first_ranked_item_is_relevant(self) -> None:
        y_true = np.array([1, 0, 0])
        y_score = np.array([3.0, 2.0, 1.0])
        assert mean_reciprocal_rank_one_group(y_true, y_score) == pytest.approx(1.0)

    def test_relevant_item_at_rank_3(self) -> None:
        y_true = np.array([0, 0, 1])
        y_score = np.array([3.0, 2.0, 1.0])  # true rank order matches score order -> relevant item ranked 3rd
        assert mean_reciprocal_rank_one_group(y_true, y_score) == pytest.approx(1.0 / 3.0)

    def test_no_relevant_item_is_0(self) -> None:
        y_true = np.array([0, 0, 0])
        y_score = np.array([3.0, 2.0, 1.0])
        assert mean_reciprocal_rank_one_group(y_true, y_score) == 0.0


class TestPrecisionRecallTop1:
    def test_precision_at_1_true_when_top_relevant(self) -> None:
        assert precision_at_1(np.array([0, 2]), np.array([1.0, 2.0])) == 1.0

    def test_precision_at_1_false_when_top_irrelevant(self) -> None:
        assert precision_at_1(np.array([2, 0]), np.array([1.0, 2.0])) == 0.0

    def test_recall_at_1_divides_by_total_relevant(self) -> None:
        # 2 relevant items in the group; top-1 prediction captures exactly one of them.
        y_true = np.array([1, 1, 0])
        y_score = np.array([3.0, 1.0, 2.0])  # top-1 is index0 (relevant)
        assert recall_at_1(y_true, y_score) == pytest.approx(0.5)

    def test_recall_at_1_none_when_no_relevant_items(self) -> None:
        assert recall_at_1(np.array([0, 0]), np.array([1.0, 2.0])) is None

    def test_top1_accuracy_requires_the_single_best_item(self) -> None:
        # grades [0, 1, 3]: ranking the grade-1 item first is "relevant" (precision_at_1=1)
        # but not "the best" (top1_accuracy=0).
        y_true = np.array([0, 1, 3])
        y_score = np.array([1.0, 3.0, 2.0])  # top-1 predicted is index1 (grade=1), not index2 (grade=3, the true best)
        assert precision_at_1(y_true, y_score) == 1.0
        assert top1_accuracy(y_true, y_score) == 0.0

    def test_top1_accuracy_true_when_best_item_ranked_first(self) -> None:
        y_true = np.array([0, 1, 3])
        y_score = np.array([1.0, 2.0, 3.0])  # top-1 predicted is index2 (grade=3, the true best)
        assert top1_accuracy(y_true, y_score) == 1.0


class TestEvaluateSplit:
    def test_two_perfect_groups_give_all_metrics_equal_1(self) -> None:
        y_true = np.array([3, 1, 3, 0])
        y_score = np.array([3.0, 1.0, 3.0, 1.0])  # both 2-item groups perfectly ranked
        group_sizes = np.array([2, 2])
        metrics = evaluate_split(y_true, y_score, group_sizes)
        assert metrics.n_groups == 2
        assert metrics.ndcg_at_1 == pytest.approx(1.0)
        assert metrics.ndcg_at_3 == pytest.approx(1.0)
        assert metrics.mrr == pytest.approx(1.0)
        assert metrics.precision_at_1 == pytest.approx(1.0)
        assert metrics.top1_accuracy == pytest.approx(1.0)

    def test_group_sizes_mismatch_raises(self) -> None:
        with pytest.raises(ValueError):
            evaluate_split(np.array([1, 2, 3]), np.array([1.0, 2.0, 3.0]), np.array([2, 2]))

    def test_recall_at_1_averages_only_over_groups_with_relevant_items(self) -> None:
        # Group 1 has a relevant item (recall defined); group 2 has none (recall undefined, excluded).
        y_true = np.array([1, 0, 0, 0])
        y_score = np.array([2.0, 1.0, 2.0, 1.0])
        group_sizes = np.array([2, 2])
        metrics = evaluate_split(y_true, y_score, group_sizes)
        # Group 1: top-1 is index0 (relevant), 1 relevant item total -> recall = 1.0.
        # Group 2: excluded from the recall average.
        assert metrics.recall_at_1 == pytest.approx(1.0)
