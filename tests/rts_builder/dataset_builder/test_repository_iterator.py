"""Unit tests for `evaluation.rts_builder.dataset_builder.repository_iterator.RepositoryIterator`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.rts_builder.dataset_builder.exceptions import ManifestError
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_specs_in_manifest_order(tmp_path: Path) -> None:
    manifest = [
        {"repository_id": "b", "source_url": "https://example.com/b.git", "commit_sha": "b" * 40},
        {"repository_id": "a", "source_url": "https://example.com/a.git", "commit_sha": "a" * 40},
    ]
    path = _write(tmp_path / "manifest.json", manifest)

    iterator = RepositoryIterator(path)

    assert [spec.repository_id for spec in iterator] == ["b", "a"]
    assert len(iterator) == 2


def test_metadata_passthrough_is_preserved(tmp_path: Path) -> None:
    manifest = [{"repository_id": "a", "source_url": "u", "commit_sha": "a" * 40, "metadata": {"split": "train"}}]
    path = _write(tmp_path / "manifest.json", manifest)

    spec = next(iter(RepositoryIterator(path)))

    assert spec.metadata == {"split": "train"}


def test_missing_file_raises_manifest_error(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        RepositoryIterator(tmp_path / "does_not_exist.json")


def test_invalid_json_raises_manifest_error(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ManifestError):
        RepositoryIterator(path)


def test_non_array_root_raises_manifest_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "manifest.json", {"not": "an array"})
    with pytest.raises(ManifestError):
        RepositoryIterator(path)


def test_invalid_entry_raises_manifest_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "manifest.json", [{"repository_id": "a"}])  # missing source_url/commit_sha
    with pytest.raises(ManifestError):
        RepositoryIterator(path)


def test_duplicate_repository_id_raises_manifest_error(tmp_path: Path) -> None:
    manifest = [
        {"repository_id": "a", "source_url": "u1", "commit_sha": "a" * 40},
        {"repository_id": "a", "source_url": "u2", "commit_sha": "b" * 40},
    ]
    path = _write(tmp_path / "manifest.json", manifest)
    with pytest.raises(ManifestError):
        RepositoryIterator(path)
