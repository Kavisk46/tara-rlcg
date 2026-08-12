"""Unit tests for `evaluation.rts_builder.dataset_builder.digest`."""
from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.rts_builder.dataset_builder.digest import (
    DigestComputationError,
    compute_configuration_hash,
    compute_feature_schema_version,
    compute_input_digest,
    compute_oracle_schema_version,
    compute_pipeline_digest,
    resolve_git_commit,
)
from evaluation.rts_builder.dataset_builder.models import PipelineSettingsSnapshot
from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings


def test_compute_pipeline_digest_is_deterministic_for_identical_inputs() -> None:
    settings = PipelineSettingsSnapshot()
    first = compute_pipeline_digest(settings, git_commit="abc123")
    second = compute_pipeline_digest(settings, git_commit="abc123")
    assert first == second
    assert first.digest_hash == second.digest_hash


def test_compute_pipeline_digest_changes_when_git_commit_changes() -> None:
    settings = PipelineSettingsSnapshot()
    first = compute_pipeline_digest(settings, git_commit="commit-a")
    second = compute_pipeline_digest(settings, git_commit="commit-b")
    assert first.digest_hash != second.digest_hash
    assert first.configuration_hash == second.configuration_hash  # only git_commit differs


def test_compute_pipeline_digest_changes_when_configuration_changes() -> None:
    default = compute_pipeline_digest(PipelineSettingsSnapshot(), git_commit="fixed")
    changed = compute_pipeline_digest(
        PipelineSettingsSnapshot(oracle_utility_settings=OracleUtilitySettings(utility_latency_weight=0.9)),
        git_commit="fixed",
    )
    assert default.configuration_hash != changed.configuration_hash
    assert default.digest_hash != changed.digest_hash
    assert default.git_commit == changed.git_commit  # only configuration differs


def test_compute_configuration_hash_is_order_independent() -> None:
    # Field construction order must not affect the hash -- json.dumps(..., sort_keys=True) guarantees this.
    settings_a = PipelineSettingsSnapshot()
    settings_b = PipelineSettingsSnapshot()
    assert compute_configuration_hash(settings_a) == compute_configuration_hash(settings_b)


def test_feature_and_oracle_schema_versions_are_stable_and_distinct() -> None:
    feature_version = compute_feature_schema_version()
    oracle_version = compute_oracle_schema_version()
    assert feature_version == compute_feature_schema_version()  # deterministic
    assert oracle_version == compute_oracle_schema_version()
    assert feature_version != oracle_version  # different schemas, extremely unlikely to collide


def test_resolve_git_commit_returns_unknown_outside_a_git_repository(tmp_path: Path) -> None:
    assert resolve_git_commit(tmp_path) == "unknown"


def test_compute_input_digest_is_deterministic_for_identical_file_contents(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queries_path = tmp_path / "queries.jsonl"
    manifest_path.write_text("[]", encoding="utf-8")
    queries_path.write_text("", encoding="utf-8")

    first = compute_input_digest(manifest_path, queries_path)
    second = compute_input_digest(manifest_path, queries_path)

    assert first == second


def test_compute_input_digest_changes_when_queries_file_changes(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queries_path = tmp_path / "queries.jsonl"
    manifest_path.write_text("[]", encoding="utf-8")
    queries_path.write_text('{"a": 1}', encoding="utf-8")
    before = compute_input_digest(manifest_path, queries_path)

    queries_path.write_text('{"a": 1}\n{"b": 2}', encoding="utf-8")
    after = compute_input_digest(manifest_path, queries_path)

    assert before.queries_hash != after.queries_hash
    assert before.digest_hash != after.digest_hash
    assert before.repository_manifest_hash == after.repository_manifest_hash  # manifest untouched


def test_compute_input_digest_changes_when_manifest_changes(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    queries_path = tmp_path / "queries.jsonl"
    manifest_path.write_text("[]", encoding="utf-8")
    queries_path.write_text("stable", encoding="utf-8")
    before = compute_input_digest(manifest_path, queries_path)

    manifest_path.write_text('[{"repository_id": "x"}]', encoding="utf-8")
    after = compute_input_digest(manifest_path, queries_path)

    assert before.repository_manifest_hash != after.repository_manifest_hash
    assert before.digest_hash != after.digest_hash


def test_compute_input_digest_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DigestComputationError):
        compute_input_digest(tmp_path / "missing_manifest.json", tmp_path / "missing_queries.jsonl")
