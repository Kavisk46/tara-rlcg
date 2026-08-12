"""Unit tests for `evaluation.rts_builder.pilot.reporting`'s markdown renderers."""
from __future__ import annotations

from pathlib import Path

from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.dataset_generator import DatasetGenerator
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.reporting import (
    render_data_readme_markdown,
    render_dataset_card_markdown,
    render_validation_report_markdown,
)
from evaluation.rts_builder.pilot.runner import PilotRunner


def _run_pilot(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> object:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=pilot_settings, dataset_generator=generator, dataset_settings=dataset_settings)
    return runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))


def test_validation_report_markdown_contains_key_sections(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    summary = _run_pilot(dataset_settings, isolated_orchestrator, manifest_path, queries_path, pilot_settings)
    markdown = render_validation_report_markdown(summary.validation_report)  # type: ignore[attr-defined]

    assert "# Validation Report" in markdown
    assert "PASSED" in markdown
    assert "Success Criteria" in markdown
    assert "no_missing_values" in markdown
    assert "Feature distributions" in markdown


def test_data_readme_markdown_lists_every_output_file(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    summary = _run_pilot(dataset_settings, isolated_orchestrator, manifest_path, queries_path, pilot_settings)
    markdown = render_data_readme_markdown(summary, pilot_settings)  # type: ignore[arg-type]

    assert pilot_settings.train_parquet_filename in markdown
    assert pilot_settings.validation_jsonl_filename in markdown
    assert pilot_settings.test_parquet_filename in markdown
    assert summary.reproducibility.pipeline_digest.digest_hash[:16] in markdown  # type: ignore[attr-defined]


def test_dataset_card_markdown_contains_every_required_section(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    summary = _run_pilot(dataset_settings, isolated_orchestrator, manifest_path, queries_path, pilot_settings)
    markdown = render_dataset_card_markdown(summary, pilot_settings)  # type: ignore[arg-type]

    for required_section in ("## Purpose", "## Schema", "## Statistics", "## Limitations", "## Threats to Validity", "## Licensing Assumptions", "## Reproducibility"):
        assert required_section in markdown


def test_dataset_card_reproducibility_section_has_actual_digest_values(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    summary = _run_pilot(dataset_settings, isolated_orchestrator, manifest_path, queries_path, pilot_settings)
    markdown = render_dataset_card_markdown(summary, pilot_settings)  # type: ignore[arg-type]

    assert summary.reproducibility.pipeline_digest.digest_hash in markdown  # type: ignore[attr-defined]
    assert summary.reproducibility.input_digest.digest_hash in markdown  # type: ignore[attr-defined]
    assert pilot_settings.split_seed in markdown
