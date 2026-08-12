"""Unit tests for `evaluation.rts_builder.pilot.exporter`."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from evaluation.rts_builder.dataset_builder.models import FeatureStatistic
from evaluation.rts_builder.pilot import exporter

_SAMPLE_ROWS: list[dict[str, object]] = [
    {"repository_id": "repo-1", "utility_score": 0.5, "is_best_strategy": True},
    {"repository_id": "repo-1", "utility_score": 0.7, "is_best_strategy": False},
]


def test_write_split_jsonl_writes_one_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    exporter.write_split_jsonl(_SAMPLE_ROWS, path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["repository_id"] == "repo-1"


def test_write_split_jsonl_overwrites_existing_content(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    path.write_text("stale content\nmore stale content\n", encoding="utf-8")

    exporter.write_split_jsonl(_SAMPLE_ROWS, path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_write_split_jsonl_handles_empty_rows(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    exporter.write_split_jsonl([], path)
    assert path.read_text(encoding="utf-8") == ""


def test_write_split_parquet_round_trips_rows(tmp_path: Path) -> None:
    path = tmp_path / "out.parquet"
    schema = pa.Table.from_pylist(_SAMPLE_ROWS).schema

    exporter.write_split_parquet(_SAMPLE_ROWS, path, schema)

    table = pq.read_table(path)
    assert table.num_rows == 2
    assert table.column("repository_id").to_pylist() == ["repo-1", "repo-1"]


def test_write_split_parquet_handles_an_empty_split_with_the_shared_schema(tmp_path: Path) -> None:
    path = tmp_path / "empty.parquet"
    schema = pa.Table.from_pylist(_SAMPLE_ROWS).schema

    exporter.write_split_parquet([], path, schema)

    table = pq.read_table(path)
    assert table.num_rows == 0
    assert table.schema.names == schema.names


def test_write_feature_statistics_csv_has_expected_columns(tmp_path: Path) -> None:
    path = tmp_path / "feature_statistics.csv"
    distributions = {
        "query_length": FeatureStatistic(mean=10.0, minimum=1.0, maximum=20.0, count=24),
        "repo_file_count": FeatureStatistic(mean=5.0, minimum=2.0, maximum=8.0, count=24),
    }

    exporter.write_feature_statistics_csv(distributions, path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "column,mean,minimum,maximum,count"
    assert len(lines) == 3  # header + 2 features
    # Sorted by column name.
    assert lines[1].startswith("query_length,")
    assert lines[2].startswith("repo_file_count,")
