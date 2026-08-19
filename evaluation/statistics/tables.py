"""Markdown tables suitable for insertion into the research paper.

Maps onto `EXPERIMENT_PLAN.md` §11's Table 3 ("Main results"), Table 4
("Per-task-type breakdown"), and Table 5 ("Ablation results") shapes:
each is, at its core, one row per `PairedComparisonResult` in a
`ComparisonFamily`, with significance marked post-correction and effect
size shown alongside. `render_comparison_family_table` is deliberately
generic over what varies row-to-row (a metric, a `TaskType`, or an
ablation) rather than three hard-coded renderers, since all three
tables share the same underlying shape.

**Two columns named in `EXPERIMENT_PLAN.md` §11 Table 3 are not
produced by this milestone and are never fabricated here**: "generation
composite score" (no composite-score formula has been fixed anywhere in
this project's specification) and "pass@k" (requires an execution
harness this project does not have, per `PROJECT_SPEC.md` §8). A table
rendered by this module simply does not include a row/column for a
metric nobody computed -- it is not padded with placeholder values.

**No function in this module writes a narrative conclusion** -- see
`evaluation.statistics.paired_comparison`'s module docstring for why.
"""
from __future__ import annotations

from evaluation.statistics.paired_comparison import ComparisonFamily, PairedComparisonResult


def _format_ci(lower: float, upper: float, precision: int) -> str:
    return f"[{lower:.{precision}f}, {upper:.{precision}f}]"


def _format_effect_size(comparison: PairedComparisonResult, precision: int) -> str:
    if comparison.effect_size is None:
        return "n/a"
    return f"{comparison.effect_size:.{precision}f} ({comparison.effect_size_method})"


def render_comparison_family_table(
    family: ComparisonFamily,
    *,
    row_label: str = "Metric",
    row_names: list[str] | None = None,
    precision: int = 3,
) -> str:
    """Render `family` as a Markdown table: one row per `PairedComparisonResult`.

    Args:
        family: The `ComparisonFamily` to render -- e.g. one metric per
            row (Table 3's shape: system A vs. system B across several
            metrics), or one `TaskType` per row (Table 4's shape: a
            fixed metric, one row per task type), or one ablation per
            row (Table 5's shape, if `family.comparisons` holds one
            ablation-vs-full-TARA comparison per row).
        row_label: The header for the leftmost, row-identifying column.
            Defaults to `"Metric"`; pass `"TaskType"` or `"Ablation"`
            for the other two table shapes.
        row_names: Row labels, in the same order as
            `family.comparisons`. Defaults to each comparison's own
            `sample.metric_name` if omitted.
        precision: Decimal places for every rendered number.

    Returns:
        A GitHub-Flavored-Markdown table (a header, a caption line
        naming `family.family_name` and every system id / query count
        involved, and one data row per comparison), directly pasteable
        into a paper draft. Significance is `family`'s own
        Holm-Bonferroni-*corrected* decision (`family.holm_bonferroni.rejected`),
        never each comparison's raw, uncorrected `p_value` alone --
        the per-hypothesis corrected threshold is shown alongside the
        raw p-value for transparency.
    """
    if row_names is not None:
        names = row_names
    else:
        names = [c.sample.metric_name for c in family.comparisons]
    if len(names) != len(family.comparisons):
        raise ValueError(
            f"row_names has {len(names)} entries but family has {len(family.comparisons)} "
            f"comparisons; they must match 1:1."
        )

    lines = [
        f"**{family.family_name}**",
        "",
        f"| {row_label} | n | System A mean [CI] | System B mean [CI] | Δ (A−B) [CI] | Test | "
        "p (α threshold) | Significant | Effect size |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    rows = zip(
        names,
        family.comparisons,
        family.holm_bonferroni.rejected,
        family.holm_bonferroni.thresholds,
        strict=True,
    )
    for name, comparison, rejected, threshold in rows:
        a_ci = _format_ci(
            comparison.system_a_mean_ci.lower, comparison.system_a_mean_ci.upper, precision
        )
        b_ci = _format_ci(
            comparison.system_b_mean_ci.lower, comparison.system_b_mean_ci.upper, precision
        )
        diff_ci = _format_ci(
            comparison.mean_difference_ci.lower, comparison.mean_difference_ci.upper, precision
        )
        lines.append(
            f"| {name} | {comparison.sample.n} | "
            f"{comparison.system_a_stats.mean:.{precision}f} {a_ci} | "
            f"{comparison.system_b_stats.mean:.{precision}f} {b_ci} | "
            f"{comparison.mean_difference:+.{precision}f} {diff_ci} | "
            f"{comparison.test_used} | "
            f"{comparison.p_value:.4f} ({threshold:.4f}) | "
            f"{'yes' if rejected else 'no'} | "
            f"{_format_effect_size(comparison, precision)} |"
        )

    if family.comparisons:
        first = family.comparisons[0]
        lines.append("")
        lines.append(
            f"*System A: `{first.sample.system_a_id}`. System B: `{first.sample.system_b_id}`. "
            f"CIs are {_ci_label(first)}. Corrected via Holm-Bonferroni within this family "
            f"({len(family.comparisons)} comparisons). Every number above is computed from "
            f"paired `QueryRunResult`s joined by `query_id`; excluded-query counts per row are "
            f"available on each `PairedComparisonResult.sample.excluded_query_ids`.*"
        )

    return "\n".join(lines)


def _ci_label(comparison: PairedComparisonResult) -> str:
    return (
        f"{comparison.system_a_mean_ci.confidence_level:.0%} BCa bootstrap "
        f"({comparison.system_a_mean_ci.n_resamples} resamples)"
    )
