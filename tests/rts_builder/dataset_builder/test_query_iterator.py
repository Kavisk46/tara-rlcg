"""Unit tests for `evaluation.rts_builder.dataset_builder.query_iterator.QueryIterator`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.rts_builder.dataset_builder.exceptions import ManifestError
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator


def _write_jsonl(path: Path, records: list[object]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return path


def test_queries_for_returns_only_the_matching_repository_in_file_order(tmp_path: Path) -> None:
    records = [
        {"repository_id": "a", "query_text": "a1"},
        {"repository_id": "b", "query_text": "b1"},
        {"repository_id": "a", "query_text": "a2"},
    ]
    path = _write_jsonl(tmp_path / "queries.jsonl", records)

    iterator = QueryIterator(path)

    assert [q.query_text for q in iterator.queries_for("a")] == ["a1", "a2"]
    assert [q.query_text for q in iterator.queries_for("b")] == ["b1"]
    assert iterator.queries_for("c") == []


def test_iteration_covers_every_repository_in_file_order(tmp_path: Path) -> None:
    records = [{"repository_id": "a", "query_text": "a1"}, {"repository_id": "b", "query_text": "b1"}]
    path = _write_jsonl(tmp_path / "queries.jsonl", records)

    iterator = QueryIterator(path)

    assert [q.query_text for q in iterator] == ["a1", "b1"]
    assert len(iterator) == 2


def test_relevance_grades_default_to_empty(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "queries.jsonl", [{"repository_id": "a", "query_text": "a1"}])
    spec = next(iter(QueryIterator(path)))
    assert spec.relevance_grades == {}


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    path.write_text('{"repository_id": "a", "query_text": "a1"}\n\n\n{"repository_id": "a", "query_text": "a2"}\n', encoding="utf-8")

    iterator = QueryIterator(path)

    assert len(iterator) == 2


def test_missing_file_raises_manifest_error(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        QueryIterator(tmp_path / "does_not_exist.jsonl")


def test_malformed_json_line_raises_manifest_error(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    path.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        QueryIterator(path)


def test_invalid_record_raises_manifest_error(tmp_path: Path) -> None:
    path = tmp_path / "queries.jsonl"
    path.write_text(json.dumps({"repository_id": "a"}) + "\n", encoding="utf-8")  # missing query_text
    with pytest.raises(ManifestError):
        QueryIterator(path)
