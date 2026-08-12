"""Integration tests for `evaluation.rts_builder.dataset_builder.dataset_generator.DatasetGenerator`."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.dataset_generator import DatasetGenerator
from evaluation.rts_builder.dataset_builder.models import PipelineSettingsSnapshot
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings


def test_generate_produces_expected_row_and_query_counts(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)

    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    assert summary.repositories_processed == 1
    assert summary.repositories_skipped == 0
    assert summary.repositories_failed == 0
    assert summary.queries_processed == 2
    assert summary.statistics.query_count == 2
    assert summary.statistics.row_count == 8  # 2 queries x 4 strategies


def test_generate_writes_all_enabled_export_formats(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    output_dir = Path(dataset_settings.output_dir)
    jsonl_lines = (output_dir / dataset_settings.long_format_jsonl_filename).read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == 8

    csv_lines = (output_dir / dataset_settings.long_format_csv_filename).read_text(encoding="utf-8").splitlines()
    assert len(csv_lines) == 9  # header + 8 rows

    table = pq.read_table(output_dir / dataset_settings.long_format_parquet_dirname)
    assert table.num_rows == 8

    grouped_lines = (output_dir / dataset_settings.grouped_jsonl_filename).read_text(encoding="utf-8").splitlines()
    assert len(grouped_lines) == 2  # one per query


def test_long_format_rows_contain_both_features_and_labels(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    jsonl_path = Path(dataset_settings.output_dir) / dataset_settings.long_format_jsonl_filename
    first_row = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])

    # Feature side.
    assert "repo_file_count" in first_row
    assert "query_length" in first_row
    # Label side.
    assert "utility_score" in first_row
    assert "rank" in first_row
    assert "quality_recall_at_k" in first_row
    assert first_row["repository_id"] == "test-repo"


def test_grouped_records_nest_all_four_strategies(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    grouped_path = Path(dataset_settings.output_dir) / dataset_settings.grouped_jsonl_filename
    record = json.loads(grouped_path.read_text(encoding="utf-8").splitlines()[0])

    assert len(record["oracle_result"]["rows"]) == 4
    assert "feature_vector" in record


def test_resume_skips_already_checkpointed_queries_and_avoids_duplicate_rows(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    first_generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    first_generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    second_generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = second_generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    assert summary.repositories_processed == 0
    assert summary.repositories_skipped == 1
    assert summary.queries_processed == 0
    assert summary.queries_skipped == 2
    assert summary.queries_invalidated_by_digest_change == 0
    # Cumulative statistics remain correct and stable across a no-op resume (same digests throughout).
    assert summary.statistics.query_count == 2
    assert summary.statistics.row_count == 8

    jsonl_path = Path(dataset_settings.output_dir) / dataset_settings.long_format_jsonl_filename
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 8  # unchanged, no duplicates


def test_changing_the_queries_file_invalidates_the_whole_checkpoint_and_recomputes_everything(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, tmp_path: Path,
) -> None:
    # input_digest hashes the *entire* queries file -- adding one new query changes the file's
    # bytes, and therefore its hash, invalidating every previously-checkpointed entry from that
    # file, not just the new query's. This is Revision 2's literal "any change invalidates
    # checkpoints," and it means q1 (unchanged in content) is *recomputed*, not skipped -- see
    # README.md's Reproducibility Guarantees for why this is correct, not a bug.
    first_queries_path = tmp_path / "queries_first.jsonl"
    first_queries_path.write_text(json.dumps({"repository_id": "test-repo", "query_text": "q1", "relevance_grades": {"app.py": 1.0}}), encoding="utf-8")

    first_summary = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator).generate(
        RepositoryIterator(manifest_path), QueryIterator(first_queries_path)
    )
    assert first_summary.statistics.query_count == 1

    both_queries_path = tmp_path / "queries_both.jsonl"
    both_queries_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"repository_id": "test-repo", "query_text": "q1", "relevance_grades": {"app.py": 1.0}},
                {"repository_id": "test-repo", "query_text": "q2", "relevance_grades": {"pkg/base.py": 1.0}},
            ]
        ),
        encoding="utf-8",
    )

    summary = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator).generate(
        RepositoryIterator(manifest_path), QueryIterator(both_queries_path)
    )

    assert summary.queries_processed == 2  # both q1 and q2 recomputed, not just the new q2
    assert summary.queries_skipped == 0
    assert summary.queries_invalidated_by_digest_change == 1  # the one prior entry (q1) that was found stale
    # Statistics reflect only this run's full, fresh recomputation -- NOT the old run's stats plus
    # this run's (which would double-count q1's contribution). See dataset_generator.py.
    assert summary.statistics.query_count == 2
    assert summary.statistics.row_count == 8

    # q1's rows exist twice in the raw long-format file (once from each run, non-destructively
    # appended) -- callers distinguish the current, valid rows via the pipeline_digest/input_digest
    # columns, which match the just-written digest.json for the newer set only.
    jsonl_path = Path(dataset_settings.output_dir) / dataset_settings.long_format_jsonl_filename
    all_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert len(all_rows) == 12  # 4 (run 1, q1) + 4 (run 2, q1 again) + 4 (run 2, q2)
    current_input_digest = summary.input_digest.digest_hash
    current_rows = [row for row in all_rows if row["input_digest"] == current_input_digest]
    assert len(current_rows) == 8  # exactly this run's fresh q1 + q2 rows


def test_changing_pipeline_settings_invalidates_the_checkpoint(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    default_settings = PipelineSettingsSnapshot()
    DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator, pipeline_settings=default_settings).generate(
        RepositoryIterator(manifest_path), QueryIterator(queries_path)
    )

    changed_settings = PipelineSettingsSnapshot(oracle_utility_settings=OracleUtilitySettings(utility_latency_weight=0.5))
    summary = DatasetGenerator(
        settings=dataset_settings, orchestrator=isolated_orchestrator, pipeline_settings=changed_settings
    ).generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    assert summary.queries_processed == 2  # both recomputed under the new configuration_hash
    assert summary.queries_invalidated_by_digest_change == 2


def test_digest_file_is_written_and_matches_the_summary(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    digest_path = Path(dataset_settings.output_dir) / dataset_settings.digest_filename
    on_disk = json.loads(digest_path.read_text(encoding="utf-8"))

    assert on_disk["pipeline_digest"]["digest_hash"] == summary.pipeline_digest.digest_hash
    assert on_disk["input_digest"]["digest_hash"] == summary.input_digest.digest_hash


def test_export_format_toggles_are_respected(
    isolated_orchestrator: PipelineOrchestrator, manifest_path: Path, queries_path: Path, tmp_path: Path
) -> None:
    settings = DatasetBuilderSettings(
        output_dir=str(tmp_path / "dataset_out"),
        enable_csv_export=False,
        enable_parquet_export=False,
        enable_grouped_export=False,
    )
    generator = DatasetGenerator(settings=settings, orchestrator=isolated_orchestrator)
    generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    output_dir = Path(settings.output_dir)
    assert (output_dir / settings.long_format_jsonl_filename).exists()
    assert not (output_dir / settings.long_format_csv_filename).exists()
    assert not (output_dir / settings.long_format_parquet_dirname).exists()
    assert not (output_dir / settings.grouped_jsonl_filename).exists()


def test_repository_failure_is_isolated_and_does_not_abort_the_run(
    isolated_orchestrator: PipelineOrchestrator, tmp_path: Path, sample_repository_source: tuple
) -> None:
    source_path, commit_sha = sample_repository_source
    manifest = [
        {"repository_id": "broken-repo", "source_url": str(tmp_path / "does_not_exist"), "commit_sha": "a" * 40},
        {"repository_id": "test-repo", "source_url": str(source_path), "commit_sha": commit_sha},
    ]
    manifest_with_failure_path = tmp_path / "manifest_with_failure.json"
    manifest_with_failure_path.write_text(json.dumps(manifest), encoding="utf-8")

    # broken-repo needs at least one pending query, or the generator correctly never attempts to
    # load it at all (no point loading a repository with nothing to process) -- that's the "skipped"
    # path, not the "failed" path this test targets.
    queries = [
        {"repository_id": "broken-repo", "query_text": "anything", "relevance_grades": {}},
        {"repository_id": "test-repo", "query_text": "q1", "relevance_grades": {"app.py": 1.0}},
        {"repository_id": "test-repo", "query_text": "q2", "relevance_grades": {"pkg/base.py": 1.0}},
    ]
    queries_with_failure_path = tmp_path / "queries_with_failure.jsonl"
    queries_with_failure_path.write_text("\n".join(json.dumps(q) for q in queries), encoding="utf-8")

    settings = DatasetBuilderSettings(output_dir=str(tmp_path / "dataset_out"))
    generator = DatasetGenerator(settings=settings, orchestrator=isolated_orchestrator)

    summary = generator.generate(RepositoryIterator(manifest_with_failure_path), QueryIterator(queries_with_failure_path))

    assert summary.repositories_failed == 1
    assert summary.repositories_processed == 1  # test-repo still succeeded
    assert summary.queries_processed == 2


def test_statistics_file_is_written_and_matches_the_summary(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> None:
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    statistics_path = Path(dataset_settings.output_dir) / dataset_settings.statistics_filename
    on_disk = json.loads(statistics_path.read_text(encoding="utf-8"))

    assert on_disk["query_count"] == summary.statistics.query_count
    assert on_disk["row_count"] == summary.statistics.row_count
