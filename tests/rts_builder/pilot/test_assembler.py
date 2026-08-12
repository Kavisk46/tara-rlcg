"""Unit/integration tests for `evaluation.rts_builder.pilot.assembler.load_current_rows`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.dataset_generator import DatasetGenerator
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.pilot.assembler import load_current_rows
from evaluation.rts_builder.pilot.exceptions import PilotAssemblyError


def test_raises_when_grouped_output_is_missing(tmp_path: Path) -> None:
    with pytest.raises(PilotAssemblyError):
        load_current_rows(tmp_path / "does_not_exist.jsonl", "digest-a", "digest-b", {})


def test_loaded_rows_have_query_id_and_metadata(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    metadata_by_repository_id = {spec.repository_id: spec.metadata for spec in RepositoryIterator(manifest_path)}
    grouped_path = Path(dataset_settings.output_dir) / dataset_settings.grouped_jsonl_filename

    rows = load_current_rows(
        grouped_path, summary.pipeline_digest.digest_hash, summary.input_digest.digest_hash, metadata_by_repository_id
    )

    assert len(rows) == 24  # 2 repos x 3 queries x 4 strategies
    assert all("query_id" in row and len(str(row["query_id"])) == 16 for row in rows)
    assert all("metadata" in row for row in rows)


def test_rows_from_a_superseded_digest_are_excluded(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    grouped_path = Path(dataset_settings.output_dir) / dataset_settings.grouped_jsonl_filename
    metadata_by_repository_id = {spec.repository_id: spec.metadata for spec in RepositoryIterator(manifest_path)}

    # A digest that does not match anything on disk -- every record must be treated as stale.
    rows = load_current_rows(grouped_path, "some-other-pipeline-digest", "some-other-input-digest", metadata_by_repository_id)
    assert rows == []


def test_metadata_is_populated_per_repository(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    metadata_by_repository_id = {spec.repository_id: spec.metadata for spec in RepositoryIterator(manifest_path)}
    grouped_path = Path(dataset_settings.output_dir) / dataset_settings.grouped_jsonl_filename
    rows = load_current_rows(
        grouped_path, summary.pipeline_digest.digest_hash, summary.input_digest.digest_hash, metadata_by_repository_id
    )

    for row in rows:
        metadata = json.loads(str(row["metadata"]))
        assert metadata == {"license": f"license-{row['repository_id']}"}
