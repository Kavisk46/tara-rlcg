"""Streaming, resume-safe export writers for the long-format and grouped RTS datasets.

Every writer appends rather than rewrites-from-scratch, and flushes
after each write, so a crash leaves whatever was durably written before
it (plus, in the worst case, one incomplete trailing entry -- see
`README.md`'s Failure Modes) rather than losing the whole run's output.

JSONL and CSV are both line-oriented and safely appendable across
separate process runs; Parquet is not (see `ParquetRowWriter`'s
docstring) and uses a different, still-streaming-safe strategy.
"""
from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import Protocol

import pyarrow as pa
import pyarrow.parquet as pq

from evaluation.rts_builder.dataset_builder.exceptions import DatasetWriteError
from evaluation.rts_builder.dataset_builder.models import GroupedDatasetRecord
from tara.core.logging import get_logger

logger = get_logger(__name__)


class RowWriter(Protocol):
    """Structural contract for a long-format row writer."""

    def write_row(self, row: dict[str, int | float | bool | str]) -> None:
        """Write one flat row."""
        ...

    def close(self) -> None:
        """Flush and release any open resources."""
        ...


class JsonlRowWriter:
    """Appends one JSON object per line. The simplest, most directly resumable writer."""

    def __init__(self, path: Path) -> None:
        """Open `path` for appending, creating its parent directory if needed.

        Raises:
            DatasetWriteError: If the file cannot be opened.
        """
        self._path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = path.open("a", encoding="utf-8")
        except OSError as exc:
            raise DatasetWriteError(f"Could not open {path} for JSONL writing: {exc}") from exc

    def write_row(self, row: dict[str, int | float | bool | str]) -> None:
        """See `RowWriter.write_row`."""
        try:
            self._handle.write(json.dumps(row, sort_keys=True) + "\n")
            self._handle.flush()
        except OSError as exc:
            raise DatasetWriteError(f"Could not write a row to {self._path}: {exc}") from exc

    def close(self) -> None:
        """See `RowWriter.close`."""
        self._handle.close()


class CsvRowWriter:
    """Appends rows to a CSV file, writing the header only once (on first write to a new/empty file).

    Column order is taken from the first row's own key order (stable
    and deterministic across every row, since every row comes from the
    same fixed Pydantic schemas -- see `models.DatasetRow.to_flat_dict`)
    if the file is new, or from the existing file's own header if
    resuming -- so a resumed run's newly-appended rows always align
    with the columns already on disk.
    """

    def __init__(self, path: Path) -> None:
        """Open `path` for appending, reusing its existing header if present.

        Raises:
            DatasetWriteError: If the file cannot be read (to check for
                an existing header) or opened for appending.
        """
        self._path = path
        self._fieldnames: list[str] | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > 0:
                with path.open("r", encoding="utf-8", newline="") as handle:
                    self._fieldnames = next(csv.reader(handle), None)
            self._handle = path.open("a", encoding="utf-8", newline="")
        except OSError as exc:
            raise DatasetWriteError(f"Could not open {path} for CSV writing: {exc}") from exc
        self._writer: csv.DictWriter[str] | None = (
            csv.DictWriter(self._handle, fieldnames=self._fieldnames) if self._fieldnames else None
        )

    def write_row(self, row: dict[str, int | float | bool | str]) -> None:
        """See `RowWriter.write_row`."""
        try:
            if self._writer is None:
                self._fieldnames = list(row.keys())
                self._writer = csv.DictWriter(self._handle, fieldnames=self._fieldnames)
                self._writer.writeheader()
            self._writer.writerow(row)
            self._handle.flush()
        except OSError as exc:
            raise DatasetWriteError(f"Could not write a row to {self._path}: {exc}") from exc

    def close(self) -> None:
        """See `RowWriter.close`."""
        self._handle.close()


class ParquetRowWriter:
    """Buffers rows into batches and writes them as Parquet row groups, one part file per run.

    Parquet cannot be safely appended to the way JSONL/CSV can: a
    `.parquet` file's footer (row-group index, schema) is written once,
    at `close()`, and reopening a previously-closed file to add more
    row groups is not a supported operation in `pyarrow`. Resumability
    is achieved the standard way real Parquet-producing systems (Spark,
    Dask) handle incremental writes: each run writes its own uniquely
    -named part file into a shared output *directory*
    (`<long_format_parquet_dirname>/part-<uuid>.parquet`); a downstream
    reader loads the whole directory as one logical dataset
    (`pyarrow.parquet.read_table(directory)` or
    `pandas.read_parquet(directory)` both do this natively). A resumed
    run never needs to touch, rewrite, or validate any prior run's part
    file.
    """

    def __init__(self, directory: Path, batch_size: int) -> None:
        """Create a new part file in `directory`.

        Args:
            directory: The shared Parquet dataset directory. Created if
                it doesn't exist.
            batch_size: Rows buffered in memory before being flushed as
                one row group -- bounds this writer's peak memory
                independent of total row count.

        Raises:
            DatasetWriteError: If `directory` cannot be created.
        """
        self._batch_size = batch_size
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DatasetWriteError(f"Could not create Parquet output directory {directory}: {exc}") from exc

        self._part_path = directory / f"part-{uuid.uuid4().hex}.parquet"
        self._buffer: list[dict[str, int | float | bool | str]] = []
        self._writer: pq.ParquetWriter | None = None
        self._schema: pa.Schema | None = None

    def write_row(self, row: dict[str, int | float | bool | str]) -> None:
        """See `RowWriter.write_row`."""
        self._buffer.append(row)
        if len(self._buffer) >= self._batch_size:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        try:
            table = pa.Table.from_pylist(self._buffer)
            if self._writer is None:
                self._schema = table.schema
                self._writer = pq.ParquetWriter(str(self._part_path), self._schema)
            else:
                table = table.cast(self._schema)
            self._writer.write_table(table)
        except (OSError, pa.ArrowException) as exc:
            raise DatasetWriteError(f"Could not write a Parquet batch to {self._part_path}: {exc}") from exc
        self._buffer.clear()

    def close(self) -> None:
        """See `RowWriter.close`. Flushes any buffered rows before closing."""
        self._flush()
        if self._writer is not None:
            self._writer.close()


class GroupedJsonlWriter:
    """Appends one JSON object per *query* (not per strategy) -- the grouped/nested format."""

    def __init__(self, path: Path) -> None:
        """Open `path` for appending.

        Raises:
            DatasetWriteError: If the file cannot be opened.
        """
        self._path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = path.open("a", encoding="utf-8")
        except OSError as exc:
            raise DatasetWriteError(f"Could not open {path} for grouped JSONL writing: {exc}") from exc

    def write_record(self, record: GroupedDatasetRecord) -> None:
        """Write one grouped record as a single JSON line."""
        try:
            self._handle.write(record.model_dump_json() + "\n")
            self._handle.flush()
        except OSError as exc:
            raise DatasetWriteError(f"Could not write a record to {self._path}: {exc}") from exc

    def close(self) -> None:
        """See `RowWriter.close`."""
        self._handle.close()
