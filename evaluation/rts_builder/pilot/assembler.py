"""Loads the frozen Dataset Builder's grouped-format output into pilot-ready flat rows.

Reads `rts_grouped.jsonl` (not the long-format file) specifically
because the grouped format's one-record-per-query shape is exactly
what's needed to compute a single `query_id` and split assignment once
per query and stamp it onto that query's four strategy rows -- reading
the long-format file directly would require re-grouping by
`(repository_id, commit_sha, query_text)` first, which the grouped file
already gives for free.
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.rts_builder.dataset_builder.models import DatasetRow, GroupedDatasetRecord
from evaluation.rts_builder.pilot.exceptions import PilotAssemblyError
from evaluation.rts_builder.pilot.identifiers import compute_query_id
from tara.core.logging import get_logger

logger = get_logger(__name__)


def load_current_rows(
    grouped_jsonl_path: Path,
    current_pipeline_digest: str,
    current_input_digest: str,
    metadata_by_repository_id: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    """Read `grouped_jsonl_path`, keep only this run's rows, flatten to per-strategy rows.

    Dataset Builder's checkpoint invalidation is whole-file but
    non-destructive: a digest change causes every recomputed query's
    rows to be *appended* alongside a prior run's now-superseded ones,
    never deleted or rewritten (see the Dataset Builder's own
    `README.md`'s Reproducibility Guarantees). Filtering to
    `pipeline_digest == current_pipeline_digest and input_digest ==
    current_input_digest` is that subsystem's own documented way for a
    downstream consumer to recover the de-duplicated, current view --
    exactly what the pilot needs before splitting, validating, or
    exporting anything.

    Args:
        grouped_jsonl_path: Path to Dataset Builder's `rts_grouped.jsonl`
            output (its `enable_grouped_export` must be True).
        current_pipeline_digest: `PipelineDigest.digest_hash` from the
            generation run that just produced `grouped_jsonl_path`.
        current_input_digest: `InputDigest.digest_hash`, likewise.
        metadata_by_repository_id: `RepositorySpec.metadata` for every
            repository in this run's manifest, keyed by
            `repository_id` -- carried through into each row's
            `metadata` column (see Output Schema).

    Returns:
        One flat dict per `(query, strategy)` row -- `DatasetRow.to_flat_dict()`'s
        columns, plus `query_id` and `metadata`.

    Raises:
        PilotAssemblyError: If `grouped_jsonl_path` doesn't exist (e.g.
            `enable_grouped_export` was left False) or contains a line
            that isn't valid JSON / a valid `GroupedDatasetRecord`.
    """
    if not grouped_jsonl_path.is_file():
        raise PilotAssemblyError(
            f"Grouped dataset output not found at {grouped_jsonl_path} -- ensure "
            "DatasetBuilderSettings.enable_grouped_export is True."
        )

    rows: list[dict[str, object]] = []
    stale_record_count = 0

    with grouped_jsonl_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                record = GroupedDatasetRecord.model_validate(payload)
            except (json.JSONDecodeError, ValueError) as exc:
                raise PilotAssemblyError(f"{grouped_jsonl_path}:{line_number} is not a valid GroupedDatasetRecord: {exc}") from exc

            if record.pipeline_digest != current_pipeline_digest or record.input_digest != current_input_digest:
                stale_record_count += 1
                continue

            repository_id = record.oracle_result.repository_id
            commit_sha = record.oracle_result.commit_sha
            query_text = record.oracle_result.query_text
            query_id = compute_query_id(repository_id, commit_sha, query_text)
            metadata = metadata_by_repository_id.get(repository_id, {})

            for oracle_row in record.oracle_result.rows:
                flat = DatasetRow(
                    feature_vector=record.feature_vector,
                    oracle_row=oracle_row,
                    pipeline_digest=record.pipeline_digest,
                    input_digest=record.input_digest,
                ).to_flat_dict()
                flat["query_id"] = query_id
                flat["metadata"] = json.dumps(metadata, sort_keys=True)
                rows.append(flat)

    if stale_record_count:
        logger.info(
            "Skipped %d grouped record(s) from a superseded pipeline_digest/input_digest while "
            "assembling the pilot dataset from %s",
            stale_record_count, grouped_jsonl_path,
        )

    return rows
