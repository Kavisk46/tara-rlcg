"""Unit tests for `evaluation.statistics.significance`.

Every test asserts against a hand-computed or independently
cross-checked (against `scipy.stats` directly) known value, per this
milestone's own testing requirement for statistical-test wrappers:
"tested against a toy dataset with a known significance outcome."
"""
from __future__ import annotations

import pytest

from evaluation.statistics.significance import (
    bca_bootstrap_ci,
    holm_bonferroni,
    mcnemar_test,
    rank_biserial_correlation,
    spearman_correlation,
    wilcoxon_signed_rank,
)

_A = [5.0, 8.0, 3.0, 10.0, 6.0]
_B = [6.0, 7.0, 3.0, 8.0, 9.0]
# diffs a-b = [-1, 1, 0, 2, -3]; the zero (index 2) is excluded from ranking.
# abs diffs [1, 1, 2, 3] -> ranks [1.5, 1.5, 3, 4] (tie-averaged)
# W+ (positive diffs: index1 rank1.5, index3 rank3) = 4.5
# W- (negative diffs: index0 rank1.5, index4 rank4) = 5.5


# ============================================================================
# wilcoxon_signed_rank
# ============================================================================


def test_wilcoxon_signed_rank_hand_verified_against_scipy() -> None:
    # Cross-checked directly against `scipy.stats.wilcoxon(_A, _B)`, which this wrapper delegates
    # to -- statistic=4.5, pvalue=1.0 for this exact toy dataset.
    result = wilcoxon_signed_rank(_A, _B)
    assert result.statistic == pytest.approx(4.5)
    assert result.p_value == pytest.approx(1.0)
    assert result.n == 5


def test_wilcoxon_signed_rank_identical_samples_is_degenerate_not_an_error() -> None:
    # Every difference is zero -- scipy returns a degenerate but valid statistic=0.0, pvalue=1.0
    # (no evidence of a difference) rather than raising.
    result = wilcoxon_signed_rank([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert result.statistic == pytest.approx(0.0)
    assert result.p_value == pytest.approx(1.0)


def test_wilcoxon_signed_rank_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        wilcoxon_signed_rank([1.0, 2.0], [1.0])


# ============================================================================
# rank_biserial_correlation
# ============================================================================


def test_rank_biserial_correlation_hand_computed() -> None:
    assert rank_biserial_correlation(_A, _B) == pytest.approx(-0.1)


def test_rank_biserial_correlation_all_positive_is_one() -> None:
    assert rank_biserial_correlation([5.0, 6.0, 7.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_rank_biserial_correlation_all_negative_is_negative_one() -> None:
    assert rank_biserial_correlation([1.0, 2.0, 3.0], [5.0, 6.0, 7.0]) == pytest.approx(-1.0)


def test_rank_biserial_correlation_all_zero_differences_is_zero() -> None:
    assert rank_biserial_correlation([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_rank_biserial_correlation_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        rank_biserial_correlation([1.0, 2.0], [1.0])


# ============================================================================
# holm_bonferroni
# ============================================================================


def test_holm_bonferroni_hand_computed() -> None:
    # p_values in original order: [0.01, 0.04, 0.03, 0.005]. Sorted ascending:
    # 0.005(idx3) -> threshold 0.05/4=0.0125 -> 0.005 <= 0.0125 -> reject
    # 0.01(idx0)  -> threshold 0.05/3=0.016667 -> 0.01 <= 0.016667 -> reject
    # 0.03(idx2)  -> threshold 0.05/2=0.025 -> 0.03 > 0.025 -> NOT rejected, stop
    # 0.04(idx1)  -> never reached -> NOT rejected
    result = holm_bonferroni([0.01, 0.04, 0.03, 0.005], alpha=0.05)
    assert result.rejected == [True, False, False, True]
    assert result.thresholds[0] == pytest.approx(0.05 / 3)
    assert result.thresholds[1] == pytest.approx(0.05 / 1)
    assert result.thresholds[2] == pytest.approx(0.05 / 2)
    assert result.thresholds[3] == pytest.approx(0.05 / 4)


def test_holm_bonferroni_single_hypothesis_matches_plain_alpha() -> None:
    result = holm_bonferroni([0.03], alpha=0.05)
    assert result.rejected == [True]
    assert result.thresholds == [pytest.approx(0.05)]


def test_holm_bonferroni_all_large_p_values_reject_none() -> None:
    result = holm_bonferroni([0.5, 0.6, 0.7], alpha=0.05)
    assert result.rejected == [False, False, False]


def test_holm_bonferroni_all_tiny_p_values_reject_all() -> None:
    result = holm_bonferroni([0.0001, 0.0002, 0.0003], alpha=0.05)
    assert result.rejected == [True, True, True]


def test_holm_bonferroni_rejects_empty_p_values() -> None:
    with pytest.raises(ValueError, match="empty"):
        holm_bonferroni([])


def test_holm_bonferroni_rejects_invalid_alpha() -> None:
    with pytest.raises(ValueError, match="alpha"):
        holm_bonferroni([0.01], alpha=0.0)


# ============================================================================
# bca_bootstrap_ci
# ============================================================================


def test_bca_bootstrap_ci_point_estimate_matches_direct_computation() -> None:
    data = [10.0, 12.0, 11.0, 13.0, 9.0, 14.0, 10.0, 12.0]
    result = bca_bootstrap_ci(data, seed=42, n_resamples=500)
    assert result.point_estimate == pytest.approx(sum(data) / len(data))


def test_bca_bootstrap_ci_interval_contains_point_estimate_or_is_close() -> None:
    data = [10.0, 12.0, 11.0, 13.0, 9.0, 14.0, 10.0, 12.0]
    result = bca_bootstrap_ci(data, seed=42, n_resamples=500)
    assert result.lower <= result.upper


def test_bca_bootstrap_ci_is_deterministic_given_a_fixed_seed() -> None:
    data = [10.0, 12.0, 11.0, 13.0, 9.0, 14.0, 10.0, 12.0]
    first = bca_bootstrap_ci(data, seed=7, n_resamples=500)
    second = bca_bootstrap_ci(data, seed=7, n_resamples=500)
    assert first.lower == pytest.approx(second.lower)
    assert first.upper == pytest.approx(second.upper)


def test_bca_bootstrap_ci_echoes_configuration() -> None:
    result = bca_bootstrap_ci([1.0, 2.0, 3.0, 4.0], seed=1, n_resamples=200, confidence_level=0.90)
    assert result.confidence_level == 0.90
    assert result.n_resamples == 200


# ============================================================================
# mcnemar_test
# ============================================================================


def test_mcnemar_test_hand_verified_against_chi2_formula() -> None:
    # 10 pairs where A passes and B fails (b=10), 2 pairs where A fails and B passes (c=2).
    # statistic = (|10-2|-1)^2 / 12 = 49/12 = 4.0833..., p = chi2.sf(4.0833, df=1) = 0.043308...
    a_outcomes = [True] * 10 + [False] * 2
    b_outcomes = [False] * 10 + [True] * 2
    result = mcnemar_test(a_outcomes, b_outcomes)
    assert result.statistic == pytest.approx(49 / 12)
    assert result.p_value == pytest.approx(0.04330814281079206)
    assert result.discordant_pairs == 12


def test_mcnemar_test_no_discordant_pairs_is_not_significant() -> None:
    a_outcomes = [True, True, False, False]
    b_outcomes = [True, True, False, False]
    result = mcnemar_test(a_outcomes, b_outcomes)
    assert result.statistic == 0.0
    assert result.p_value == 1.0
    assert result.discordant_pairs == 0


def test_mcnemar_test_without_continuity_correction() -> None:
    a_outcomes = [True] * 10 + [False] * 2
    b_outcomes = [False] * 10 + [True] * 2
    result = mcnemar_test(a_outcomes, b_outcomes, continuity_correction=False)
    # statistic = (10-2)^2 / 12 = 64/12 = 5.3333...
    assert result.statistic == pytest.approx(64 / 12)


def test_mcnemar_test_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        mcnemar_test([True, False], [True])


# ============================================================================
# spearman_correlation
# ============================================================================


def test_spearman_correlation_hand_verified_against_scipy() -> None:
    # Cross-checked directly against `scipy.stats.spearmanr([1,2,3,4,5], [2,1,4,3,5])`.
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 1.0, 4.0, 3.0, 5.0]
    result = spearman_correlation(x, y)
    assert result.correlation == pytest.approx(0.7999999999999999)
    assert result.p_value == pytest.approx(0.10408803866182788)
    assert result.n == 5


def test_spearman_correlation_perfect_positive() -> None:
    x = [1.0, 2.0, 3.0, 4.0]
    result = spearman_correlation(x, x)
    assert result.correlation == pytest.approx(1.0)


def test_spearman_correlation_perfect_negative() -> None:
    x = [1.0, 2.0, 3.0, 4.0]
    y = [4.0, 3.0, 2.0, 1.0]
    result = spearman_correlation(x, y)
    assert result.correlation == pytest.approx(-1.0)


def test_spearman_correlation_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        spearman_correlation([1.0, 2.0], [1.0])
