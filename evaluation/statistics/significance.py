"""Statistical-test wrappers, exactly as fixed by `EXPERIMENT_PLAN.md` §6.

Every wrapper wraps an existing `scipy.stats` implementation rather than
reimplementing a well-known test from scratch, except McNemar's test
(not in `scipy.stats`; adding `statsmodels` for one small, simple,
well-defined formula was judged unjustified, matching this project's
established "no dependency for something simple and hand-verifiable"
stance -- see `tara.retrieval.bm25_index`'s and
`tara.fusion.token_budget`'s identical reasoning) and matched-pairs
rank-biserial correlation (not directly exposed by `scipy.stats.wilcoxon`,
but trivially derived from `scipy.stats.rankdata`, which *is* used here
rather than a hand-rolled tie-breaking ranker).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class WilcoxonResult:
    """Result of a Wilcoxon signed-rank test, per `EXPERIMENT_PLAN.md` §6's primary paired test."""

    statistic: float
    p_value: float
    n: int
    """Number of paired observations the test was computed over."""


def wilcoxon_signed_rank(a: Sequence[float], b: Sequence[float]) -> WilcoxonResult:
    """Two-sided Wilcoxon signed-rank test between paired samples `a` and `b`.

    Per `EXPERIMENT_PLAN.md` §6: "Primary paired comparisons (TARA vs.
    each baseline, on the same TIQS queries): Wilcoxon signed-rank
    test... Two-sided, α = 0.05." The α threshold itself is not applied
    here -- this function returns the raw statistic and p-value; the
    caller compares `p_value` against whatever corrected threshold
    `holm_bonferroni` produces for the family this comparison belongs to.

    Args:
        a: One system's per-query metric values.
        b: The other system's per-query metric values for the *same*
            queries, in the same order as `a`.

    Returns:
        The test statistic, two-sided p-value, and `n` (paired
        observation count).

    Raises:
        ValueError: If `a` and `b` have different lengths, or fewer
            than 1 paired observation is given (delegated to
            `scipy.stats.wilcoxon`'s own validation).
    """
    if len(a) != len(b):
        raise ValueError(f"a and b must be the same length, got {len(a)} and {len(b)}.")
    result = stats.wilcoxon(a, b, alternative="two-sided")
    return WilcoxonResult(statistic=float(result.statistic), p_value=float(result.pvalue), n=len(a))


def rank_biserial_correlation(a: Sequence[float], b: Sequence[float]) -> float:
    """Matched-pairs rank-biserial correlation, the effect size `EXPERIMENT_PLAN.md` §6 requires
    be reported "alongside every Wilcoxon result (not merely the p-value)."

    Args:
        a: One system's per-query metric values.
        b: The other system's per-query metric values for the same
            queries, in the same order as `a`.

    Returns:
        `(W+ - W-) / (W+ + W-)` in `[-1.0, 1.0]`, where `W+`/`W-` are
        the rank-sums of the positive/negative `a - b` differences
        (ties in `|a - b|` broken by average rank via
        `scipy.stats.rankdata`; zero differences excluded from ranking,
        the standard Wilcoxon convention). `0.0` if every difference is
        zero (no signal either direction).

    Raises:
        ValueError: If `a` and `b` have different lengths.
    """
    if len(a) != len(b):
        raise ValueError(f"a and b must be the same length, got {len(a)} and {len(b)}.")

    differences = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    nonzero = differences[differences != 0]
    if nonzero.size == 0:
        return 0.0

    ranks = stats.rankdata(np.abs(nonzero))
    w_positive = float(ranks[nonzero > 0].sum())
    w_negative = float(ranks[nonzero < 0].sum())
    return (w_positive - w_negative) / (w_positive + w_negative)


@dataclass(frozen=True)
class HolmBonferroniResult:
    """Per-hypothesis outcome of a Holm-Bonferroni step-down correction.

    Every list is in the *original* input order (not sorted by
    p-value), so a caller can zip it directly against the comparisons
    it corrected without needing to track a sort permutation.
    """

    rejected: list[bool]
    thresholds: list[float]
    """The α threshold each hypothesis was actually compared against, in original input order --
    disclosed for transparency, since Holm-Bonferroni's per-hypothesis threshold depends on every
    other p-value's rank, not on a single fixed α."""


def holm_bonferroni(p_values: Sequence[float], alpha: float = 0.05) -> HolmBonferroniResult:
    """Holm-Bonferroni step-down multiple-comparisons correction.

    Per `EXPERIMENT_PLAN.md` §6: "applied within each family of
    comparisons... chosen over plain Bonferroni for its uniformly higher
    power at equivalent family-wise error control." Sort p-values
    ascending; reject `H_(i)` iff `p_(i) <= alpha / (m - i + 1)`
    (1-indexed) for every hypothesis up to and including the first
    non-rejection -- once one hypothesis in the sorted order fails to
    clear its threshold, every later (larger-p) hypothesis is not
    rejected either, per the step-down procedure's own definition.

    Args:
        p_values: Raw (uncorrected) p-values for one family of comparisons.
        alpha: Family-wise significance level. Defaults to 0.05, per
            `EXPERIMENT_PLAN.md` §6.

    Returns:
        A `HolmBonferroniResult` in original input order.

    Raises:
        ValueError: If `p_values` is empty, or `alpha` is not in `(0, 1]`.
    """
    if not p_values:
        raise ValueError("p_values is empty -- nothing to correct.")
    if not (0 < alpha <= 1):
        raise ValueError(f"alpha must be in (0, 1], got {alpha!r}.")

    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])

    rejected = [False] * m
    thresholds = [0.0] * m
    still_rejecting = True
    for step, original_index in enumerate(order):  # step is 0-indexed
        threshold = alpha / (m - step)
        thresholds[original_index] = threshold
        if still_rejecting and p_values[original_index] <= threshold:
            rejected[original_index] = True
        else:
            still_rejecting = False

    return HolmBonferroniResult(rejected=rejected, thresholds=thresholds)


@dataclass(frozen=True)
class BootstrapCI:
    """A bias-corrected and accelerated (BCa) bootstrap confidence interval."""

    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    n_resamples: int


def bca_bootstrap_ci(
    data: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    *,
    confidence_level: float = 0.95,
    n_resamples: int = 10_000,
    seed: int | None = None,
) -> BootstrapCI:
    """BCa bootstrap confidence interval, per `EXPERIMENT_PLAN.md` §6's fixed procedure.

    Per §6: "bias-corrected and accelerated (BCa) bootstrap, 10,000
    resamples, for every point estimate reported in Tables 3-5,
    including metrics not directly amenable to a closed-form CI (e.g.
    macro-F1, ECE)." Wraps `scipy.stats.bootstrap` (`method="BCa"`)
    rather than implementing BCa's jackknife/bias-correction/acceleration
    machinery by hand.

    Args:
        data: The sample to bootstrap.
        statistic: A function `data -> point estimate`, applied along
            the last axis (matching `scipy.stats.bootstrap`'s own
            convention). Defaults to the mean.
        confidence_level: Defaults to `0.95`.
        n_resamples: Defaults to `10_000`, per §6.
        seed: Optional seed for reproducibility. `None` (the default)
            uses `numpy`'s default, non-reproducible entropy source --
            pass a fixed seed for a reproducible experiment run.

    Returns:
        A `BootstrapCI` with the point estimate (computed directly from
        `data`, not from the bootstrap distribution) and the BCa
        interval bounds.

    Raises:
        ValueError: If `data` has fewer than 2 observations (delegated
            to `scipy.stats.bootstrap`'s own validation).
    """
    data_array = np.asarray(data, dtype=float)
    point_estimate = float(statistic(data_array))

    rng = np.random.default_rng(seed)
    result = stats.bootstrap(
        (data_array,),
        statistic,
        confidence_level=confidence_level,
        n_resamples=n_resamples,
        method="BCa",
        random_state=rng,
    )
    return BootstrapCI(
        point_estimate=point_estimate,
        lower=float(result.confidence_interval.low),
        upper=float(result.confidence_interval.high),
        confidence_level=confidence_level,
        n_resamples=n_resamples,
    )


@dataclass(frozen=True)
class McNemarResult:
    """Result of McNemar's test for paired binary outcomes."""

    statistic: float
    p_value: float
    discordant_pairs: int
    """`b + c`: pairs where the two systems disagreed. McNemar's test is computed entirely from
    these -- concordant pairs (both right or both wrong) carry no information about which system
    is better and are correctly ignored."""


def mcnemar_test(
    a_outcomes: Sequence[bool], b_outcomes: Sequence[bool], *, continuity_correction: bool = True
) -> McNemarResult:
    """McNemar's test for paired binary outcomes, per `EXPERIMENT_PLAN.md` §6.

    Per §6: "Paired binary outcomes (e.g. per-query pass@1
    success/failure...): McNemar's test, appropriate for paired
    nominal/binary data, in place of Wilcoxon for this specific metric
    type." Not in `scipy.stats`; implemented directly here (see module
    docstring) as `statistic = (|b - c| - 1)^2 / (b + c)` (continuity-
    corrected) or `(b - c)^2 / (b + c)` (uncorrected), a chi-square
    statistic with 1 degree of freedom, where `b`/`c` are the two
    discordant-pair counts.

    Args:
        a_outcomes: System A's per-query pass/fail outcomes.
        b_outcomes: System B's per-query pass/fail outcomes, for the
            same queries in the same order.
        continuity_correction: Apply Yates' continuity correction
            (the standard default for McNemar's test on small samples).

    Returns:
        The chi-square statistic, its p-value (`scipy.stats.chi2.sf`
        with 1 degree of freedom), and the discordant-pair count.
        `statistic=0.0, p_value=1.0` when there are zero discordant
        pairs (the two systems never disagreed -- no evidence of a
        difference, not an error).

    Raises:
        ValueError: If `a_outcomes` and `b_outcomes` have different lengths.
    """
    if len(a_outcomes) != len(b_outcomes):
        raise ValueError(
            f"a_outcomes and b_outcomes must be the same length, got {len(a_outcomes)} and "
            f"{len(b_outcomes)}."
        )

    b = sum(1 for a, bb in zip(a_outcomes, b_outcomes, strict=True) if a and not bb)
    c = sum(1 for a, bb in zip(a_outcomes, b_outcomes, strict=True) if not a and bb)
    discordant = b + c

    if discordant == 0:
        return McNemarResult(statistic=0.0, p_value=1.0, discordant_pairs=0)

    if continuity_correction:
        statistic = (abs(b - c) - 1) ** 2 / discordant
    else:
        statistic = (b - c) ** 2 / discordant

    p_value = float(stats.chi2.sf(statistic, df=1))
    return McNemarResult(statistic=statistic, p_value=p_value, discordant_pairs=discordant)


@dataclass(frozen=True)
class SpearmanResult:
    """Result of a Spearman rank correlation test."""

    correlation: float
    p_value: float
    n: int


def spearman_correlation(a: Sequence[float], b: Sequence[float]) -> SpearmanResult:
    """Spearman rank correlation, per `EXPERIMENT_PLAN.md` §6 (H1: confidence vs. correctness).

    Args:
        a: First variable's per-query values (e.g. classifier `confidence`).
        b: Second variable's per-query values, same order as `a` (e.g.
            a binary per-query correctness indicator).

    Returns:
        The Spearman ρ, its two-sided p-value, and `n`.

    Raises:
        ValueError: If `a` and `b` have different lengths.
    """
    if len(a) != len(b):
        raise ValueError(f"a and b must be the same length, got {len(a)} and {len(b)}.")
    result = stats.spearmanr(a, b)
    return SpearmanResult(
        correlation=float(result.statistic), p_value=float(result.pvalue), n=len(a)
    )
