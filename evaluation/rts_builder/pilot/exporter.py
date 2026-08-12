"""Write-once export of the finished train/validation/test splits and `feature_statistics.csv`.

Unlike the frozen Dataset Builder's own writers (`writers.py`), these
are not streaming/resumable: by the time `PilotRunner` calls into this
module, the complete, validated, in-memory row set for one split is
already known, so each split is written as a single, whole file rather
than incrementally appended to -- there is no crash-resume story to
support at this layer, since a failed pilot run is simply re-run from
Dataset Builder's own checkpoint forward.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from evaluation.rts_builder.dataset_builder.models import FeatureStatistic
from evaluation.rts_builder.pilot.exceptions import PilotError


def write_split_jsonl(rows: list[dict[str, object]], path: Path) -> None:
    """Write `rows` as one JSON object per line, overwriting any existing file at `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError as exc:
        raise PilotError(f"Could not write split JSONL to {path}: {exc}") from exc


def write_split_parquet(rows: list[dict[str, object]], path: Path, schema: pa.Schema) -> None:
    """Write `rows` as a single Parquet file at `path`, cast to `schema`.

    `schema` is always derived from the *full* (train + validation +
    test) row set by the caller -- not from `rows` alone -- so an
    empty split (possible on a tiny/unbalanced pilot) still produces a
    validly-typed, zero-row Parquet file instead of failing on missing
    columns.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        table = pa.Table.from_pylist(rows, schema=schema) if rows else schema.empty_table()
        pq.write_table(table, str(path))
    except (OSError, pa.ArrowException) as exc:
        raise PilotError(f"Could not write split Parquet to {path}: {exc}") from exc


def write_feature_statistics_csv(feature_distributions: dict[str, FeatureStatistic], path: Path) -> None:
    """Write one row per feature column: `column,mean,minimum,maximum,count`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["column", "mean", "minimum", "maximum", "count"])
            for column in sorted(feature_distributions):
                stat = feature_distributions[column]
                writer.writerow([column, stat.mean, stat.minimum, stat.maximum, stat.count])
    except OSError as exc:
        raise PilotError(f"Could not write feature statistics CSV to {path}: {exc}") from exc
