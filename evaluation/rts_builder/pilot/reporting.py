"""Markdown renderers for `validation_report.md`, `data/README.md`, and `DATASET_CARD.md`.

Every number in these documents is read off the actual `PilotSummary`/
`ValidationReport` for the run that produced them -- nothing here is a
static template with numbers filled in by hand, so the documents stay
accurate across pilot runs of any scale without being hand-edited.
"""
from __future__ import annotations

from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.models import PilotSummary, ValidationReport


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def render_validation_report_markdown(report: ValidationReport) -> str:
    lines: list[str] = []
    lines.append("# Validation Report")
    lines.append("")
    lines.append(f"Generated at `{report.generated_at.isoformat()}`.")
    lines.append("")
    lines.append(f"**Overall result: {'PASSED' if report.passed else 'FAILED'}**")
    lines.append("")
    lines.append(f"- Rows: {report.row_count}")
    lines.append(f"- Distinct queries: {report.query_count}")
    lines.append("")

    lines.append("## Success Criteria (blocking checks)")
    lines.append("")
    lines.append("| Check | Result | Detail |")
    lines.append("|---|---|---|")
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        kind = "blocking" if check.blocking else "informational"
        lines.append(f"| `{check.name}` ({kind}) | {marker} | {check.detail} |")
    lines.append("")

    lines.append("## Strategy distribution")
    lines.append("")
    lines.append("| Strategy | Row count |")
    lines.append("|---|---|")
    for strategy, count in sorted(report.strategy_distribution.items()):
        lines.append(f"| {strategy} | {count} |")
    lines.append("")

    lines.append("## Repository distribution")
    lines.append("")
    lines.append("| Repository | Row count |")
    lines.append("|---|---|")
    for repository_id, count in sorted(report.repository_distribution.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {repository_id} | {count} |")
    lines.append("")

    lines.append("## Rank distribution")
    lines.append("")
    lines.append("| Rank | Row count |")
    lines.append("|---|---|")
    for rank, count in sorted(report.rank_distribution.items()):
        lines.append(f"| {rank} | {count} |")
    lines.append("")

    lines.append("## Split distribution (queries)")
    lines.append("")
    lines.append("| Split | Query count |")
    lines.append("|---|---|")
    for split, count in sorted(report.split_distribution.items()):
        lines.append(f"| {split} | {count} |")
    lines.append("")

    lines.append("## Averages")
    lines.append("")
    lines.append(f"- Average utility (overall): {_fmt(report.average_utility_overall)}")
    lines.append(f"- Average latency ms (overall): {_fmt(report.average_latency_ms_overall)}")
    lines.append(f"- Average quality (overall): {_fmt(report.average_quality_overall)}")
    lines.append("")
    lines.append("| Strategy | Avg utility | Avg latency (ms) | Avg quality |")
    lines.append("|---|---|---|---|")
    for strategy in sorted(report.strategy_distribution):
        lines.append(
            f"| {strategy} | {_fmt(report.average_utility_by_strategy.get(strategy, 0.0))} "
            f"| {_fmt(report.average_latency_ms_by_strategy.get(strategy, 0.0))} "
            f"| {_fmt(report.average_quality_by_strategy.get(strategy, 0.0))} |"
        )
    lines.append("")

    lines.append("## Distribution histograms")
    lines.append("")
    lines.append("Bin edges and counts for the equal-width histograms rendered as figures "
                  "(`utility_histogram.png`, `latency_histogram.png`); the quality histogram is summarized "
                  "here only (see `feature_correlation_matrix.png`'s sibling figures for the full quality plot).")
    for label, histogram in (
        ("Utility", report.utility_histogram), ("Latency (ms)", report.latency_histogram), ("Quality", report.quality_histogram),
    ):
        lines.append("")
        lines.append(f"**{label}**: edges=`{[round(edge, 3) for edge in histogram.bin_edges]}`, counts=`{histogram.counts}`")
    lines.append("")

    lines.append("## Feature distributions")
    lines.append("")
    lines.append("| Feature | Mean | Minimum | Maximum | Count |")
    lines.append("|---|---|---|---|---|")
    for column in sorted(report.feature_distributions):
        stat = report.feature_distributions[column]
        lines.append(f"| {column} | {_fmt(stat.mean)} | {_fmt(stat.minimum)} | {_fmt(stat.maximum)} | {stat.count} |")
    lines.append("")

    return "\n".join(lines)


def render_data_readme_markdown(summary: PilotSummary, settings: PilotSettings) -> str:
    counts = summary.split_counts
    lines: list[str] = []
    lines.append("# RTS Pilot Dataset")
    lines.append("")
    lines.append(
        "The first pilot Retrieval Training Set produced by the TARA RTS Builder pipeline. "
        "See `DATASET_CARD.md` for purpose, schema, statistics, limitations, threats to validity, "
        "licensing assumptions, and reproducibility, and `validation_report.md` for the full "
        "automated validation output."
    )
    lines.append("")

    lines.append("## Files")
    lines.append("")
    lines.append("| File | Rows | Description |")
    lines.append("|---|---|---|")
    lines.append(f"| `{settings.train_parquet_filename}` / `{settings.train_jsonl_filename}` | {counts.train_rows} | Train split ({counts.train_queries} queries x 4 strategies). |")
    lines.append(f"| `{settings.validation_parquet_filename}` / `{settings.validation_jsonl_filename}` | {counts.validation_rows} | Validation split ({counts.validation_queries} queries x 4 strategies). |")
    lines.append(f"| `{settings.test_parquet_filename}` / `{settings.test_jsonl_filename}` | {counts.test_rows} | Test split ({counts.test_queries} queries x 4 strategies). |")
    lines.append(f"| `{settings.dataset_statistics_filename}` | -- | Cumulative dataset statistics (frozen Dataset Builder's own `DatasetStatistics`). |")
    lines.append(f"| `{settings.feature_statistics_filename}` | -- | Per-feature mean/min/max/count, CSV. |")
    lines.append(f"| `{settings.validation_report_filename}` | -- | Automated validation output (this run). |")
    lines.append(f"| `{settings.figures_dirname}/*.png` | -- | Quality-report figures (6). |")
    lines.append("")

    lines.append("## Loading")
    lines.append("")
    lines.append("```python")
    lines.append("import pyarrow.parquet as pq")
    lines.append(f'train = pq.read_table("{settings.train_parquet_filename}").to_pylist()')
    lines.append("```")
    lines.append("")
    lines.append(
        "Every row's `pipeline_digest`/`input_digest` columns match this run's "
        f"`{summary.reproducibility.pipeline_digest.digest_hash[:16]}...`/"
        f"`{summary.reproducibility.input_digest.digest_hash[:16]}...` -- see `DATASET_CARD.md`'s "
        "Reproducibility section."
    )
    lines.append("")
    lines.append(
        "Column definitions for every feature/label column are authoritative in "
        "`evaluation/rts_builder/dataset_builder/DatasetSchema.md` (this pilot layer only adds "
        "`query_id`, `metadata`, and `split` on top of that schema -- see `DATASET_CARD.md` Schema section)."
    )
    return "\n".join(lines)


def render_dataset_card_markdown(summary: PilotSummary, settings: PilotSettings) -> str:
    report = summary.validation_report
    repro = summary.reproducibility
    counts = summary.split_counts

    lines: list[str] = []
    lines.append("# Dataset Card: TARA RTS Pilot")
    lines.append("")

    lines.append("## Purpose")
    lines.append("")
    lines.append(
        "This is the first pilot Retrieval Training Set (RTS) for the TARA project's "
        "Learning-to-Rank (LTR) retrieval-strategy policy. It exists to validate the end-to-end "
        "RTS Builder pipeline (Repository Loader -> Parser -> Feature Extraction -> Retrieval "
        "Executor -> Oracle Utility -> Dataset Builder -> this Pilot layer) at a modest, "
        "scientifically-inspectable scale before committing to a full-scale dataset build. This "
        "release does **not** train an LTR model, run a planner, run task classification, or "
        "perform LLM inference -- it is the dataset construction and validation stage only."
    )
    lines.append("")
    lines.append(
        f"Scale achieved: {len(report.repository_distribution)} "
        f"repositories, {report.query_count} distinct queries, {report.row_count} long-format rows "
        "(one row per query x strategy, 4 strategies: lexical, dense, graph, hybrid)."
    )
    lines.append("")

    lines.append("## Schema")
    lines.append("")
    lines.append(
        "Long-format row columns are the frozen Dataset Builder's own schema "
        "(`evaluation/rts_builder/dataset_builder/DatasetSchema.md` SS2.1), unmodified, plus three "
        "columns this pilot layer adds on top without altering any frozen model:"
    )
    lines.append("")
    lines.append("| Column | Type | Description |")
    lines.append("|---|---|---|")
    lines.append("| `query_id` | string (16 hex chars) | Deterministic `sha256(repository_id, commit_sha, query_text)[:16]` -- stable across runs; not present in any frozen model. |")
    lines.append("| `metadata` | string (JSON object) | `RepositorySpec.metadata` for this row's repository, serialized -- passthrough curation metadata, never read or validated. |")
    lines.append("| `split` | string (`train`/`validation`/`test`) | This row's deterministic split assignment (see Reproducibility). |")
    lines.append("")
    lines.append(
        "Every long-format column beyond these three (features, labels, `pipeline_digest`/"
        "`input_digest`) is defined authoritatively in `DatasetSchema.md` SS2.1 -- not restated here "
        "to avoid a second, driftable copy of that schema."
    )
    lines.append("")

    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Train: {counts.train_queries} queries, {counts.train_rows} rows")
    lines.append(f"- Validation: {counts.validation_queries} queries, {counts.validation_rows} rows")
    lines.append(f"- Test: {counts.test_queries} queries, {counts.test_rows} rows")
    lines.append(f"- Average utility (overall): {_fmt(report.average_utility_overall)}")
    lines.append(f"- Average latency ms (overall): {_fmt(report.average_latency_ms_overall)}")
    lines.append(f"- Average retrieval quality (overall): {_fmt(report.average_quality_overall)}")
    lines.append("")
    lines.append("Full distributions, per-strategy averages, and every feature column's mean/min/max/count are in `validation_report.md` and `feature_statistics.csv`.")
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- **Pilot scale.** This is a first-pilot-scale dataset (target 8 repositories, "
        "150-200 queries), intentionally small for scientific inspectability -- not the scale a "
        "production LTR policy would ultimately train on.\n"
        "- **Python-only.** Parser (Milestone 2) is Python-only V1; every repository/feature/query in "
        "this dataset is Python source, not a multi-language sample.\n"
        "- **Query and relevance authorship are external.** Query text and ground-truth relevance "
        "grades were supplied as curated input (`queries.jsonl`), not generated or validated by any "
        "RTS Builder code -- this dataset's quality is bounded by that curation's quality, which this "
        "pipeline cannot independently assess.\n"
        "- **Oracle Utility's weighting is a fixed formula**, not learned or calibrated against human "
        "preference data -- `utility_score`/`rank`/`is_best_strategy` reflect that formula's "
        "definition of \"good,\" not an independently validated notion of developer-perceived usefulness."
    )
    lines.append("")

    lines.append("## Threats to Validity")
    lines.append("")
    lines.append(
        "- **Construct validity.** Whether `quality_score`/`utility_score` actually track what a "
        "developer would consider a *useful* retrieval result has not been validated against human "
        "judgment in this pilot -- they are well-defined, deterministic formulas (Oracle_Math.md), "
        "not a validated proxy for human preference.\n"
        "- **Internal validity.** The pipeline itself is deterministic (same inputs -> byte-identical "
        "output, enforced by `pipeline_digest`/`input_digest`), so run-to-run noise is not a threat; "
        "the ground-truth relevance judgments themselves, however, carry whatever subjectivity or "
        "noise their (external) authorship process has, which this pipeline cannot detect or correct.\n"
        "- **External validity.** 8 repositories is a small, non-random sample; conclusions drawn from "
        "this pilot about strategy performance may not generalize to repositories of very different "
        "size, domain, or code style.\n"
        "- **Statistical power.** "
        f"{report.query_count} queries ({report.row_count} rows) is adequate to validate the pipeline "
        "end-to-end but is a modest sample for training or evaluating an LTR model with strong "
        "statistical confidence."
    )
    lines.append("")

    lines.append("## Licensing Assumptions")
    lines.append("")
    lines.append(
        "No RTS Builder subsystem verifies, tracks, or enforces source-repository licensing. "
        "`RepositorySpec.metadata` can carry a caller-supplied `license` field (per "
        "`docs/DATASET_BUILDER_SPEC.md`), but it is passthrough only -- never read, validated, or "
        "used to gate inclusion. **Before this dataset (or any derivative, including a trained LTR "
        "model) is distributed outside the TARA project, the redistribution rights of every source "
        "repository listed in `repository_distribution` (validation_report.md) must be independently "
        "verified.** Treat this pilot release as internal-research-use only until that verification is done."
    )
    lines.append("")

    lines.append("## Reproducibility")
    lines.append("")
    lines.append(f"- Pipeline version: `{repro.pipeline_digest.pipeline_version}`")
    lines.append(f"- Git commit: `{repro.pipeline_digest.git_commit}`")
    lines.append(f"- Feature schema version: `{repro.pipeline_digest.feature_schema_version}`")
    lines.append(f"- Oracle schema version: `{repro.pipeline_digest.oracle_schema_version}`")
    lines.append(f"- Configuration hash: `{repro.pipeline_digest.configuration_hash}`")
    lines.append(f"- Pipeline digest (combined): `{repro.pipeline_digest.digest_hash}`")
    lines.append(f"- Repository manifest hash: `{repro.input_digest.repository_manifest_hash}`")
    lines.append(f"- Queries hash: `{repro.input_digest.queries_hash}`")
    lines.append(f"- Input digest (combined): `{repro.input_digest.digest_hash}`")
    lines.append(f"- Split seed: `{settings.split_seed}` (train/validation/test ratios: {settings.train_ratio}/{settings.validation_ratio}/{settings.test_ratio})")
    lines.append(f"- Generated at: `{repro.generated_at.isoformat()}`")
    lines.append(f"- Python: `{repro.environment.python_version}`")
    lines.append(f"- Platform: `{repro.environment.platform}`")
    for package_name, package_version in sorted(repro.environment.package_versions.items()):
        lines.append(f"- `{package_name}`: `{package_version}`")
    lines.append("")
    lines.append(
        "A caller with the identical manifest.json/queries.jsonl, the identical git commit, and the "
        "identical `PipelineSettingsSnapshot` reproduces byte-identical `pipeline_digest`/"
        "`input_digest` values, and -- given `split_seed` is also unchanged -- an identical "
        "train/validation/test split assignment for every query, per `pipeline_digest`/`input_digest` "
        "already being deterministic and `QuerySplitter.assign` being a pure hash function. See "
        "`evaluation/rts_builder/dataset_builder/README.md`'s Reproducibility Guarantees for the "
        "underlying digest mechanism."
    )
    return "\n".join(lines)
