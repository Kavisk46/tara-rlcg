"""Integration tests for `evaluation.rts_builder.pilot.runner.PilotRunner`."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.dataset_generator import DatasetGenerator
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.exceptions import PilotValidationError
from evaluation.rts_builder.pilot.runner import PilotRunner


def test_run_produces_every_declared_output_file(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=pilot_settings, dataset_generator=generator, dataset_settings=dataset_settings)

    summary = runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    data_dir = Path(pilot_settings.data_dir)
    for filename in (
        pilot_settings.train_parquet_filename, pilot_settings.validation_parquet_filename, pilot_settings.test_parquet_filename,
        pilot_settings.train_jsonl_filename, pilot_settings.validation_jsonl_filename, pilot_settings.test_jsonl_filename,
        pilot_settings.dataset_statistics_filename, pilot_settings.feature_statistics_filename,
        pilot_settings.validation_report_filename, pilot_settings.dataset_readme_filename, pilot_settings.dataset_card_filename,
    ):
        assert (data_dir / filename).is_file(), f"missing {filename}"

    figures_dir = data_dir / pilot_settings.figures_dirname
    assert len(list(figures_dir.glob("*.png"))) == 6
    assert summary.validation_report.passed is True


def test_every_query_has_exactly_four_rows_across_all_splits(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=pilot_settings, dataset_generator=generator, dataset_settings=dataset_settings)
    summary = runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    total_rows = summary.split_counts.train_rows + summary.split_counts.validation_rows + summary.split_counts.test_rows
    total_queries = summary.split_counts.train_queries + summary.split_counts.validation_queries + summary.split_counts.test_queries
    assert total_rows == total_queries * 4
    assert total_queries == 6  # 2 repos x 3 queries


def test_a_query_never_splits_across_train_and_validation(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=pilot_settings, dataset_generator=generator, dataset_settings=dataset_settings)
    runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    data_dir = Path(pilot_settings.data_dir)
    train_query_ids = {json.loads(line)["query_id"] for line in (data_dir / pilot_settings.train_jsonl_filename).read_text(encoding="utf-8").splitlines()}
    validation_query_ids = {json.loads(line)["query_id"] for line in (data_dir / pilot_settings.validation_jsonl_filename).read_text(encoding="utf-8").splitlines()}
    test_query_ids = {json.loads(line)["query_id"] for line in (data_dir / pilot_settings.test_jsonl_filename).read_text(encoding="utf-8").splitlines()}

    assert train_query_ids.isdisjoint(validation_query_ids)
    assert train_query_ids.isdisjoint(test_query_ids)
    assert validation_query_ids.isdisjoint(test_query_ids)


def test_split_assignment_is_stable_across_two_independent_runs(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, tmp_path: Path,
) -> None:
    first_settings = PilotSettings(data_dir=str(tmp_path / "data_first"), split_seed="stable-seed")
    second_settings = PilotSettings(data_dir=str(tmp_path / "data_second"), split_seed="stable-seed")

    first_generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    PilotRunner(settings=first_settings, dataset_generator=first_generator, dataset_settings=dataset_settings).run(
        RepositoryIterator(manifest_path), QueryIterator(queries_path)
    )

    second_dataset_settings = DatasetBuilderSettings(output_dir=str(tmp_path / "dsout2"), enable_grouped_export=True)
    second_generator = DatasetGenerator(settings=second_dataset_settings, orchestrator=isolated_orchestrator)
    PilotRunner(settings=second_settings, dataset_generator=second_generator, dataset_settings=second_dataset_settings).run(
        RepositoryIterator(manifest_path), QueryIterator(queries_path)
    )

    first_train_ids = {
        json.loads(line)["query_id"]
        for line in (Path(first_settings.data_dir) / first_settings.train_jsonl_filename).read_text(encoding="utf-8").splitlines()
    }
    second_train_ids = {
        json.loads(line)["query_id"]
        for line in (Path(second_settings.data_dir) / second_settings.train_jsonl_filename).read_text(encoding="utf-8").splitlines()
    }
    assert first_train_ids == second_train_ids


def test_validation_failure_raises_by_default(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, tmp_path: Path,
) -> None:
    # expected_strategy_count=99 guarantees every_query_has_expected_strategy_rows fails,
    # deterministically, without needing to hand-corrupt the pipeline's own output.
    failing_settings = PilotSettings(data_dir=str(tmp_path / "data"), expected_strategy_count=99)
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=failing_settings, dataset_generator=generator, dataset_settings=dataset_settings)

    with pytest.raises(PilotValidationError) as excinfo:
        runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    assert excinfo.value.report.passed is False
    # Split files must NOT be written over a dataset known to have failed validation.
    assert not (tmp_path / "data" / failing_settings.train_parquet_filename).exists()


def test_validation_failure_does_not_raise_when_disabled(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, tmp_path: Path,
) -> None:
    lenient_settings = PilotSettings(data_dir=str(tmp_path / "data"), expected_strategy_count=99, fail_on_validation_error=False)
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=lenient_settings, dataset_generator=generator, dataset_settings=dataset_settings)

    summary = runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    assert summary.validation_report.passed is False
    assert (tmp_path / "data" / lenient_settings.train_parquet_filename).exists()


def test_reproducibility_record_matches_the_generation_summarys_digests(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=pilot_settings, dataset_generator=generator, dataset_settings=dataset_settings)
    summary = runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    assert summary.reproducibility.pipeline_digest.digest_hash == summary.dataset_generation_summary.pipeline_digest.digest_hash
    assert summary.reproducibility.input_digest.digest_hash == summary.dataset_generation_summary.input_digest.digest_hash


def test_parquet_and_jsonl_splits_agree_on_row_counts(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path, pilot_settings: PilotSettings,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    runner = PilotRunner(settings=pilot_settings, dataset_generator=generator, dataset_settings=dataset_settings)
    runner.run(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    data_dir = Path(pilot_settings.data_dir)
    for parquet_filename, jsonl_filename in (
        (pilot_settings.train_parquet_filename, pilot_settings.train_jsonl_filename),
        (pilot_settings.validation_parquet_filename, pilot_settings.validation_jsonl_filename),
        (pilot_settings.test_parquet_filename, pilot_settings.test_jsonl_filename),
    ):
        parquet_rows = pq.read_table(data_dir / parquet_filename).num_rows
        jsonl_rows = len((data_dir / jsonl_filename).read_text(encoding="utf-8").splitlines())
        assert parquet_rows == jsonl_rows
