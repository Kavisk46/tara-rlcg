"""Baseline registry / reproducibility report.

Per this milestone's REPRODUCIBILITY REPORT requirement. Derived
entirely from `evaluation.baselines.definitions` -- never hand-duplicated
data -- so the report can never drift out of sync with what is actually
implemented.
"""
from __future__ import annotations

from dataclasses import dataclass

from evaluation.baselines.definitions import BASELINE_DEFINITIONS, UNAVAILABLE_BASELINES, BaselineId
from tara.routing.strategy import STRATEGY_RETRIEVERS


@dataclass(frozen=True)
class ReproducibilityReportRow:
    """One row of the B0-B6 reproducibility report."""

    baseline_id: BaselineId
    name: str
    strategy: str
    implementation_status: str
    retrieval_mechanisms: tuple[str, ...]
    reference: str | None
    reproducibility_status: str


def build_reproducibility_report() -> tuple[ReproducibilityReportRow, ...]:
    """Build the full B0-B6 reproducibility report, in `BaselineId` order.

    Every implemented baseline (B0-B4) is deterministic and depends on
    no external system or unverified reference -- "reproducible" here
    means exactly that, not "validated to be a good baseline." Every
    unavailable baseline (B5-B6) reports its own disclosed reason
    (`UnavailableBaseline.reason`) as its reproducibility status, never a
    fabricated one.
    """
    rows: list[ReproducibilityReportRow] = []

    for baseline in BASELINE_DEFINITIONS:
        if baseline.strategy is None:
            strategy_label = "none"
            mechanisms: tuple[str, ...] = ()
        else:
            strategy_label = baseline.strategy.value
            mechanisms = tuple(kind.value for kind in STRATEGY_RETRIEVERS[baseline.strategy])
        rows.append(
            ReproducibilityReportRow(
                baseline_id=baseline.baseline_id,
                name=baseline.name,
                strategy=strategy_label,
                implementation_status="implemented",
                retrieval_mechanisms=mechanisms,
                reference=None,
                reproducibility_status="reproducible (deterministic; no external system or "
                "unverified reference involved)",
            )
        )

    for unavailable in UNAVAILABLE_BASELINES:
        rows.append(
            ReproducibilityReportRow(
                baseline_id=unavailable.baseline_id,
                name=unavailable.name,
                strategy="n/a",
                implementation_status="not implemented",
                retrieval_mechanisms=(),
                reference=None,
                reproducibility_status=f"unavailable_reference: {unavailable.reason}",
            )
        )

    return tuple(rows)


def render_reproducibility_report_markdown() -> str:
    """Render `build_reproducibility_report()` as a Markdown table."""
    lines = [
        "| ID | Name | Strategy | Implementation status | Retrieval mechanisms | "
        "Reproducibility status |",
        "|---|---|---|---|---|---|",
    ]
    for row in build_reproducibility_report():
        mechanisms = ", ".join(row.retrieval_mechanisms) if row.retrieval_mechanisms else "-"
        lines.append(
            f"| {row.baseline_id.value} | {row.name} | {row.strategy} | "
            f"{row.implementation_status} | {mechanisms} | {row.reproducibility_status} |"
        )
    return "\n".join(lines)
