"""Paired comparisons: the statistical analysis layer's core.

Ties together `evaluation.statistics.descriptive` (mean/median),
`evaluation.statistics.significance` (Wilcoxon/McNemar/BCa bootstrap/
Holm-Bonferroni/rank-biserial, all already implemented and hand-verified
in M11), and `evaluation.statistics.metrics_registry` (which test
applies to which metric) into one per-metric, per-system-pair analysis,
plus per-`TaskType` and overall grouping and family-wise correction.

**Reads `QueryRunResult`s only; never mutates or rewrites them.** Every
function in this module takes already-computed results (from
`evaluation.harness.runner.write_results_jsonl`/`read_results_jsonl`)
and returns new, derived summary objects -- "do not change the
experimental data" is upheld structurally: nothing here has a code path
that writes back to a `QueryRunResult` or its source file.

**No function in this module renders a natural-language conclusion.**
`PairedComparisonResult`/`ComparisonFamily` carry numbers (means, CIs,
p-values, effect sizes) and a machine-checkable `significant` flag once
corrected -- deciding what those numbers *mean* for a paper's claims
("TARA is superior," "the difference is not meaningful") is deliberately
left to whoever reads the numbers, per this milestone's explicit
instruction not to write such a conclusion unless the actual results
support it. This module cannot make that determination reliably (no
real experiment has been run against real data at all, per M9-M12's
repeated, explicit scope boundary), and structurally never tries to.
"""
from __future__ import annotations

import statistics as _statistics
from collections.abc import Sequence
from dataclasses import dataclass

from evaluation.harness.models import QueryRunResult
from evaluation.statistics.descriptive import DescriptiveStats, compute_descriptive_stats
from evaluation.statistics.metrics_registry import MetricSpec, select_paired_test_name
from evaluation.statistics.protocol import StatisticalProtocol
from evaluation.statistics.significance import (
    BootstrapCI,
    HolmBonferroniResult,
    bca_bootstrap_ci,
    holm_bonferroni,
    mcnemar_test,
    rank_biserial_correlation,
    wilcoxon_signed_rank,
)


@dataclass(frozen=True)
class PairedSample:
    """The paired per-query values two systems share for one metric, after joining by
    `query_id` and dropping any query where the metric was unavailable for either system."""

    metric_name: str
    system_a_id: str
    system_b_id: str
    query_ids: tuple[str, ...]
    values_a: tuple[float, ...]
    values_b: tuple[float, ...]
    excluded_query_ids: tuple[str, ...]
    """Queries present in both systems' results but dropped because the metric was `None` for
    at least one of them (an errored run, or a `GroundTruth` that didn't support this metric) --
    never silently coerced to `0.0`."""

    @property
    def n(self) -> int:
        return len(self.query_ids)


def build_paired_sample(
    results_a: Sequence[QueryRunResult], results_b: Sequence[QueryRunResult], metric: MetricSpec
) -> PairedSample:
    """Join `results_a`/`results_b` by `query_id` and extract `metric` from each pair.

    Args:
        results_a: One system's results (e.g. TARA-proper).
        results_b: The other system's results (e.g. a baseline), for
            the same (or an overlapping) query set.
        metric: Which metric to extract, and how.

    Returns:
        A `PairedSample` restricted to `query_id`s present in both
        inputs *and* for which `metric.extractor` returned a non-`None`
        value on both sides, sorted by `query_id` for determinism.
        Boolean extractor values are coerced to `1.0`/`0.0`.
    """
    by_id_a = {r.query_id: r for r in results_a}
    by_id_b = {r.query_id: r for r in results_b}
    common_ids = sorted(set(by_id_a) & set(by_id_b))

    query_ids: list[str] = []
    values_a: list[float] = []
    values_b: list[float] = []
    excluded: list[str] = []

    for query_id in common_ids:
        value_a = metric.extractor(by_id_a[query_id])
        value_b = metric.extractor(by_id_b[query_id])
        if value_a is None or value_b is None:
            excluded.append(query_id)
            continue
        query_ids.append(query_id)
        values_a.append(float(value_a))
        values_b.append(float(value_b))

    system_a_id = results_a[0].variant_id if results_a else "unknown"
    system_b_id = results_b[0].variant_id if results_b else "unknown"
    return PairedSample(
        metric_name=metric.name,
        system_a_id=system_a_id,
        system_b_id=system_b_id,
        query_ids=tuple(query_ids),
        values_a=tuple(values_a),
        values_b=tuple(values_b),
        excluded_query_ids=tuple(excluded),
    )


@dataclass(frozen=True)
class PairedComparisonResult:
    """The complete statistical comparison of two systems on one metric.

    Every field traces back to `sample`'s own `query_ids` -- this result
    carries `sample` itself specifically so a reader can verify, for any
    number reported here, exactly which queries (and which excluded
    queries) it was computed from, per this milestone's "every reported
    number must trace back to a machine-readable experiment result"
    instruction.
    """

    sample: PairedSample
    system_a_stats: DescriptiveStats
    system_b_stats: DescriptiveStats
    system_a_mean_ci: BootstrapCI
    system_b_mean_ci: BootstrapCI
    mean_difference: float
    mean_difference_ci: BootstrapCI
    test_used: str
    statistic: float
    p_value: float
    effect_size: float | None
    effect_size_method: str | None


def compare_variants(
    results_a: Sequence[QueryRunResult],
    results_b: Sequence[QueryRunResult],
    metric: MetricSpec,
    protocol: StatisticalProtocol,
) -> PairedComparisonResult:
    """Run the complete, pre-registered paired analysis of `metric` between two systems.

    Args:
        results_a: One system's results.
        results_b: The other system's results.
        metric: Which metric to compare.
        protocol: The fixed statistical protocol (α, bootstrap
            settings) -- see `evaluation.statistics.protocol`.

    Returns:
        A `PairedComparisonResult` covering descriptive statistics
        (mean/median/std), BCa bootstrap confidence intervals for each
        system's mean and for the paired mean difference, and the
        pre-registered paired significance test
        (`evaluation.statistics.metrics_registry.select_paired_test_name`
        -- Wilcoxon signed-rank for a continuous metric, McNemar for a
        binary one) with its matching effect size (rank-biserial
        correlation, continuous metrics only; McNemar has no
        `EXPERIMENT_PLAN.md`-specified effect size and none is invented
        here).

    Raises:
        ValueError: If fewer than 2 paired observations remain after
            joining and excluding queries with a missing metric value.
    """
    sample = build_paired_sample(results_a, results_b, metric)
    if sample.n < 2:
        raise ValueError(
            f"Need at least 2 paired observations for metric {metric.name!r} between "
            f"{sample.system_a_id!r} and {sample.system_b_id!r}; got {sample.n} (after "
            f"excluding {len(sample.excluded_query_ids)} of "
            f"{sample.n + len(sample.excluded_query_ids)} common queries missing this metric)."
        )

    system_a_stats = compute_descriptive_stats(sample.values_a)
    system_b_stats = compute_descriptive_stats(sample.values_b)
    system_a_ci = bca_bootstrap_ci(
        sample.values_a,
        confidence_level=protocol.ci_confidence_level,
        n_resamples=protocol.ci_n_resamples,
        seed=protocol.ci_seed,
    )
    system_b_ci = bca_bootstrap_ci(
        sample.values_b,
        confidence_level=protocol.ci_confidence_level,
        n_resamples=protocol.ci_n_resamples,
        seed=protocol.ci_seed,
    )

    differences = [a - b for a, b in zip(sample.values_a, sample.values_b, strict=True)]
    mean_difference = _statistics.fmean(differences)
    mean_difference_ci = bca_bootstrap_ci(
        differences,
        confidence_level=protocol.ci_confidence_level,
        n_resamples=protocol.ci_n_resamples,
        seed=protocol.ci_seed,
    )

    test_name = select_paired_test_name(metric.kind)
    effect_size: float | None = None
    effect_size_method: str | None = None
    if test_name == "wilcoxon_signed_rank":
        wilcoxon_result = wilcoxon_signed_rank(sample.values_a, sample.values_b)
        statistic, p_value = wilcoxon_result.statistic, wilcoxon_result.p_value
        effect_size = rank_biserial_correlation(sample.values_a, sample.values_b)
        effect_size_method = "rank_biserial_correlation"
    else:  # "mcnemar" -- the only other value select_paired_test_name can return
        mcnemar_result = mcnemar_test(
            [bool(v) for v in sample.values_a], [bool(v) for v in sample.values_b]
        )
        statistic, p_value = mcnemar_result.statistic, mcnemar_result.p_value

    return PairedComparisonResult(
        sample=sample,
        system_a_stats=system_a_stats,
        system_b_stats=system_b_stats,
        system_a_mean_ci=system_a_ci,
        system_b_mean_ci=system_b_ci,
        mean_difference=mean_difference,
        mean_difference_ci=mean_difference_ci,
        test_used=test_name,
        statistic=statistic,
        p_value=p_value,
        effect_size=effect_size,
        effect_size_method=effect_size_method,
    )


def _group_by_task_type(results: Sequence[QueryRunResult]) -> dict[str, list[QueryRunResult]]:
    groups: dict[str, list[QueryRunResult]] = {}
    for result in results:
        if result.task_type is None:
            continue
        groups.setdefault(result.task_type.value, []).append(result)
    return groups


def compare_variants_by_task_type(
    results_a: Sequence[QueryRunResult],
    results_b: Sequence[QueryRunResult],
    metric: MetricSpec,
    protocol: StatisticalProtocol,
) -> dict[str, PairedComparisonResult]:
    """`compare_variants`, run independently within each `TaskType` both systems share.

    Args:
        results_a: One system's results, spanning one or more `TaskType`s.
        results_b: The other system's results.
        metric: Which metric to compare.
        protocol: The fixed statistical protocol.

    Returns:
        `{task_type_value: PairedComparisonResult}`, one entry per
        `TaskType` value present in both `results_a` and `results_b`
        with at least 2 paired observations for `metric` -- a
        `TaskType` with too few paired observations is *omitted*, not
        reported with a fabricated or degenerate result (per
        `EXPERIMENT_PLAN.md` §6's own subgroup-power caveat: small-n
        subgroup results must be disclosed with their `n`, and a `n < 2`
        subgroup cannot even produce a test statistic to disclose).
        Results with no `task_type` set are excluded from every group.
    """
    groups_a = _group_by_task_type(results_a)
    groups_b = _group_by_task_type(results_b)
    common_task_types = sorted(set(groups_a) & set(groups_b))

    output: dict[str, PairedComparisonResult] = {}
    for task_type in common_task_types:
        try:
            output[task_type] = compare_variants(
                groups_a[task_type], groups_b[task_type], metric, protocol
            )
        except ValueError:
            continue
    return output


@dataclass(frozen=True)
class ComparisonFamily:
    """A family of `PairedComparisonResult`s, jointly corrected for multiple comparisons.

    Per `EXPERIMENT_PLAN.md` §6: "Multiple-comparisons correction:
    Holm-Bonferroni, applied within each family of comparisons (e.g. the
    family 'TARA vs. {B0, B1, B2, B3}' is one family... corrected
    separately" from any other family. `family_name` documents which
    family this is, so two `ComparisonFamily` results can never be
    silently conflated.
    """

    family_name: str
    comparisons: tuple[PairedComparisonResult, ...]
    holm_bonferroni: HolmBonferroniResult


def correct_family(
    family_name: str, comparisons: Sequence[PairedComparisonResult], protocol: StatisticalProtocol
) -> ComparisonFamily:
    """Apply Holm-Bonferroni correction across `comparisons`' p-values, as one family.

    Args:
        family_name: A human-readable name for this family (e.g.
            `"TARA vs. baselines, Recall@10"`), carried through to
            table rendering for provenance.
        comparisons: The `PairedComparisonResult`s that make up this
            family -- e.g. one `compare_variants` call per baseline,
            all for the same metric, all against TARA-proper.
        protocol: Supplies `alpha`.

    Returns:
        A `ComparisonFamily` pairing `comparisons` (original order)
        with the `HolmBonferroniResult` correcting them jointly.

    Raises:
        ValueError: If `comparisons` is empty.
    """
    if not comparisons:
        raise ValueError(f"comparisons is empty for family {family_name!r} -- nothing to correct.")
    p_values = [c.p_value for c in comparisons]
    result = holm_bonferroni(p_values, alpha=protocol.alpha)
    return ComparisonFamily(
        family_name=family_name, comparisons=tuple(comparisons), holm_bonferroni=result
    )
