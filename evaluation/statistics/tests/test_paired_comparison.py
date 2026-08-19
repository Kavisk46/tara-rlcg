"""Unit tests for `evaluation.statistics.paired_comparison`.

Reuses the exact hand-verified Wilcoxon/McNemar/rank-biserial examples
already established in `evaluation/statistics/tests/test_significance.py`
(M11), now exercised end to end through `QueryRunResult`-based paired
samples, so this layer's own wiring (join-by-query_id, exclusion,
descriptive stats, CI, test selection) is verified against numbers
already independently confirmed against `scipy`/hand computation, not a
fresh, unverified example.
"""
from __future__ import annotations

import pytest

from evaluation.statistics.metrics_registry import EXACT_MATCH, RECIPROCAL_RANK
from evaluation.statistics.paired_comparison import (
    build_paired_sample,
    compare_variants,
    compare_variants_by_task_type,
    correct_family,
)
from evaluation.statistics.protocol import StatisticalProtocol
from evaluation.statistics.tests.conftest import (
    RECIPROCAL_RANK_A_VALUES as _A_VALUES,
)
from evaluation.statistics.tests.conftest import (
    RECIPROCAL_RANK_B_VALUES as _B_VALUES,
)
from evaluation.statistics.tests.conftest import (
    make_reciprocal_rank_results as _reciprocal_rank_results,
)
from evaluation.statistics.tests.conftest import make_result
from tara.core.types import TaskType

_PROTOCOL = StatisticalProtocol(ci_n_resamples=200, ci_seed=42)  # small n_resamples: fast tests


# ============================================================================
# build_paired_sample
# ============================================================================


def test_build_paired_sample_joins_by_query_id_and_extracts_metric() -> None:
    results_a = _reciprocal_rank_results("TARA", _A_VALUES)
    results_b = _reciprocal_rank_results("B1", _B_VALUES)

    sample = build_paired_sample(results_a, results_b, RECIPROCAL_RANK)

    assert sample.n == 5
    assert sample.values_a == tuple(_A_VALUES)
    assert sample.values_b == tuple(_B_VALUES)
    assert sample.excluded_query_ids == ()
    assert sample.system_a_id == "TARA"
    assert sample.system_b_id == "B1"


def test_build_paired_sample_excludes_queries_missing_the_metric() -> None:
    results_a = [
        make_result(query_id="q-1", reciprocal_rank=0.5),
        make_result(query_id="q-2"),  # no retrieval metrics at all
    ]
    results_b = [
        make_result(query_id="q-1", reciprocal_rank=0.4),
        make_result(query_id="q-2", reciprocal_rank=0.9),
    ]

    sample = build_paired_sample(results_a, results_b, RECIPROCAL_RANK)

    assert sample.n == 1
    assert sample.query_ids == ("q-1",)
    assert sample.excluded_query_ids == ("q-2",)


def test_build_paired_sample_excludes_queries_only_present_in_one_system() -> None:
    results_a = [make_result(query_id="q-1", reciprocal_rank=0.5)]
    results_b = [make_result(query_id="q-2", reciprocal_rank=0.5)]

    sample = build_paired_sample(results_a, results_b, RECIPROCAL_RANK)

    assert sample.n == 0
    assert sample.query_ids == ()


def test_build_paired_sample_coerces_boolean_metric_to_float() -> None:
    results_a = [make_result(query_id="q-1", exact_match=True)]
    results_b = [make_result(query_id="q-1", exact_match=False)]

    sample = build_paired_sample(results_a, results_b, EXACT_MATCH)

    assert sample.values_a == (1.0,)
    assert sample.values_b == (0.0,)


# ============================================================================
# compare_variants: continuous metric (Wilcoxon)
# ============================================================================


def test_compare_variants_continuous_uses_wilcoxon_and_matches_hand_verified_values() -> None:
    results_a = _reciprocal_rank_results("TARA", _A_VALUES)
    results_b = _reciprocal_rank_results("B1", _B_VALUES)

    comparison = compare_variants(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)

    assert comparison.test_used == "wilcoxon_signed_rank"
    assert comparison.statistic == pytest.approx(4.5)
    assert comparison.p_value == pytest.approx(1.0)
    assert comparison.effect_size == pytest.approx(-0.1)
    assert comparison.effect_size_method == "rank_biserial_correlation"
    assert comparison.sample.n == 5


def test_compare_variants_descriptive_stats_match_direct_computation() -> None:
    results_a = _reciprocal_rank_results("TARA", _A_VALUES)
    results_b = _reciprocal_rank_results("B1", _B_VALUES)

    comparison = compare_variants(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)

    assert comparison.system_a_stats.mean == pytest.approx(sum(_A_VALUES) / len(_A_VALUES))
    assert comparison.system_b_stats.mean == pytest.approx(sum(_B_VALUES) / len(_B_VALUES))
    assert comparison.mean_difference == pytest.approx(
        comparison.system_a_stats.mean - comparison.system_b_stats.mean
    )


def test_compare_variants_ci_bounds_are_ordered() -> None:
    results_a = _reciprocal_rank_results("TARA", _A_VALUES)
    results_b = _reciprocal_rank_results("B1", _B_VALUES)

    comparison = compare_variants(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)

    assert comparison.system_a_mean_ci.lower <= comparison.system_a_mean_ci.upper
    assert comparison.system_b_mean_ci.lower <= comparison.system_b_mean_ci.upper
    assert comparison.mean_difference_ci.lower <= comparison.mean_difference_ci.upper


def test_compare_variants_rejects_fewer_than_two_paired_observations() -> None:
    results_a = [make_result(query_id="q-1", reciprocal_rank=0.5)]
    results_b = [make_result(query_id="q-1", reciprocal_rank=0.4)]

    with pytest.raises(ValueError, match="at least 2 paired observations"):
        compare_variants(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)


# ============================================================================
# compare_variants: binary metric (McNemar)
# ============================================================================


def test_compare_variants_binary_uses_mcnemar_and_matches_hand_verified_values() -> None:
    # 10 pairs where A passes and B fails, 2 pairs where A fails and B passes.
    results_a = [make_result(query_id=f"q-{i}", exact_match=True) for i in range(10)] + [
        make_result(query_id=f"q-{i}", exact_match=False) for i in range(10, 12)
    ]
    results_b = [make_result(query_id=f"q-{i}", exact_match=False) for i in range(10)] + [
        make_result(query_id=f"q-{i}", exact_match=True) for i in range(10, 12)
    ]

    comparison = compare_variants(results_a, results_b, EXACT_MATCH, _PROTOCOL)

    assert comparison.test_used == "mcnemar"
    assert comparison.statistic == pytest.approx(49 / 12)
    assert comparison.p_value == pytest.approx(0.04330814281079206)
    assert comparison.effect_size is None
    assert comparison.effect_size_method is None


# ============================================================================
# compare_variants_by_task_type
# ============================================================================


def test_compare_variants_by_task_type_groups_correctly() -> None:
    results_a = [
        make_result(query_id="q-1", task_type=TaskType.SEARCH, reciprocal_rank=1.0),
        make_result(query_id="q-2", task_type=TaskType.SEARCH, reciprocal_rank=0.5),
        make_result(query_id="q-3", task_type=TaskType.DEBUG, reciprocal_rank=0.8),
        make_result(query_id="q-4", task_type=TaskType.DEBUG, reciprocal_rank=0.2),
    ]
    results_b = [
        make_result(query_id="q-1", task_type=TaskType.SEARCH, reciprocal_rank=0.9),
        make_result(query_id="q-2", task_type=TaskType.SEARCH, reciprocal_rank=0.4),
        make_result(query_id="q-3", task_type=TaskType.DEBUG, reciprocal_rank=0.7),
        make_result(query_id="q-4", task_type=TaskType.DEBUG, reciprocal_rank=0.1),
    ]

    per_task = compare_variants_by_task_type(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)

    assert set(per_task) == {"search", "debug"}
    assert per_task["search"].sample.n == 2
    assert per_task["debug"].sample.n == 2


def test_compare_variants_by_task_type_omits_task_types_with_too_few_observations() -> None:
    results_a = [make_result(query_id="q-1", task_type=TaskType.SEARCH, reciprocal_rank=1.0)]
    results_b = [make_result(query_id="q-1", task_type=TaskType.SEARCH, reciprocal_rank=0.5)]

    per_task = compare_variants_by_task_type(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)

    assert per_task == {}


def test_compare_variants_by_task_type_excludes_results_with_no_task_type() -> None:
    results_a = [
        make_result(query_id="q-1", task_type=None, reciprocal_rank=1.0),
        make_result(query_id="q-2", task_type=None, reciprocal_rank=0.5),
    ]
    results_b = [
        make_result(query_id="q-1", task_type=None, reciprocal_rank=0.9),
        make_result(query_id="q-2", task_type=None, reciprocal_rank=0.4),
    ]

    per_task = compare_variants_by_task_type(results_a, results_b, RECIPROCAL_RANK, _PROTOCOL)

    assert per_task == {}


# ============================================================================
# correct_family
# ============================================================================


def test_correct_family_applies_holm_bonferroni_across_comparisons() -> None:
    # Three comparisons against the same metric; only the third has any real signal.
    results_a = _reciprocal_rank_results("TARA", _A_VALUES)
    weak_signal = compare_variants(
        results_a, _reciprocal_rank_results("B1", _B_VALUES), RECIPROCAL_RANK, _PROTOCOL
    )
    same_again = compare_variants(
        results_a, _reciprocal_rank_results("B2", _B_VALUES), RECIPROCAL_RANK, _PROTOCOL
    )
    strong_signal = compare_variants(
        results_a,
        _reciprocal_rank_results("B3", [0.01, 0.02, 0.01, 0.02, 0.01]),
        RECIPROCAL_RANK,
        _PROTOCOL,
    )

    family = correct_family(
        "TARA vs. baselines, reciprocal_rank",
        [weak_signal, same_again, strong_signal],
        _PROTOCOL,
    )

    assert family.family_name == "TARA vs. baselines, reciprocal_rank"
    assert len(family.holm_bonferroni.rejected) == 3
    assert len(family.holm_bonferroni.thresholds) == 3


def test_correct_family_rejects_empty_comparisons() -> None:
    with pytest.raises(ValueError, match="empty"):
        correct_family("empty family", [], _PROTOCOL)
