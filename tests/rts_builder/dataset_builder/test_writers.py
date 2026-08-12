"""Unit tests for `evaluation.rts_builder.dataset_builder.writers`."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow.parquet as pq

from evaluation.rts_builder.dataset_builder.writers import CsvRowWriter, JsonlRowWriter, ParquetRowWriter


def test_jsonl_writer_appends_one_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    writer = JsonlRowWriter(path)
    writer.write_row({"a": 1, "b": "x"})
    writer.write_row({"a": 2, "b": "y"})
    writer.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1, "b": "x"}
    assert json.loads(lines[1]) == {"a": 2, "b": "y"}


def test_jsonl_writer_appends_across_separate_instances(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    first = JsonlRowWriter(path)
    first.write_row({"a": 1})
    first.close()

    second = JsonlRowWriter(path)
    second.write_row({"a": 2})
    second.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_csv_writer_writes_header_once(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    writer = CsvRowWriter(path)
    writer.write_row({"a": 1, "b": "x"})
    writer.write_row({"a": 2, "b": "y"})
    writer.close()

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0] == {"a": "1", "b": "x"}


def test_csv_writer_reuses_existing_header_on_resume(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    first = CsvRowWriter(path)
    first.write_row({"a": 1, "b": "x"})
    first.close()

    second = CsvRowWriter(path)
    second.write_row({"a": 2, "b": "y"})
    second.close()

    with path.open(encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines()
    # Exactly one header line, even though two CsvRowWriter instances were used.
    assert lines[0] == "a,b"
    assert len(lines) == 3


def test_parquet_writer_flushes_full_batches_and_close(tmp_path: Path) -> None:
    directory = tmp_path / "out.parquet"
    writer = ParquetRowWriter(directory, batch_size=2)
    writer.write_row({"a": 1, "b": 1.5})
    writer.write_row({"a": 2, "b": 2.5})  # triggers a flush (batch_size=2)
    writer.write_row({"a": 3, "b": 3.5})  # remains buffered until close()
    writer.close()

    table = pq.read_table(directory)
    assert table.num_rows == 3
    assert set(table.column_names) == {"a", "b"}


def test_parquet_writer_uses_a_unique_part_file_per_instance(tmp_path: Path) -> None:
    directory = tmp_path / "out.parquet"
    first = ParquetRowWriter(directory, batch_size=10)
    first.write_row({"a": 1})
    first.close()

    second = ParquetRowWriter(directory, batch_size=10)
    second.write_row({"a": 2})
    second.close()

    part_files = list(directory.glob("part-*.parquet"))
    assert len(part_files) == 2

    table = pq.read_table(directory)
    assert table.num_rows == 2


def test_parquet_writer_with_no_rows_produces_no_part_file(tmp_path: Path) -> None:
    directory = tmp_path / "out.parquet"
    writer = ParquetRowWriter(directory, batch_size=10)
    writer.close()

    assert list(directory.glob("part-*.parquet")) == []
