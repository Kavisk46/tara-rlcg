"""Configuration for the RTS Builder's Dataset Builder subsystem.

Owns only what is genuinely new at this milestone: output locations,
which export formats are enabled, and checkpoint/batching behavior.
Each of the six wrapped pipeline stages (Repository Loader through
Oracle Utility) keeps its own settings object, injected into
`PipelineOrchestrator` independently -- this milestone does not nest or
re-declare their fields, matching the constructor-injection convention
every prior RTS Builder milestone uses for its own collaborators.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatasetBuilderSettings(BaseSettings):
    """Environment-driven configuration for `DatasetGenerator`.

    Every field can be overridden by an environment variable named
    `RTS_DATASET_<FIELD_NAME>` (uppercased), or by an entry in a local
    `.env` file. See `evaluation/rts_builder/dataset_builder/.env.example`.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_DATASET_", env_file=".env", extra="ignore")

    output_dir: str = Field(
        default=".rts_cache/dataset",
        description="Directory every export file/checkpoint/statistics file is written under.",
    )
    long_format_jsonl_filename: str = Field(default="rts_long.jsonl", description="Long-format JSONL output filename.")
    long_format_csv_filename: str = Field(default="rts_long.csv", description="Long-format CSV output filename.")
    long_format_parquet_dirname: str = Field(
        default="rts_long.parquet",
        description="Long-format Parquet *directory*: one part file per DatasetGenerator run (see README.md "
        "for why Parquet cannot be safely appended to across resumed runs the way JSONL/CSV can).",
    )
    grouped_jsonl_filename: str = Field(default="rts_grouped.jsonl", description="Grouped (one query = one JSON object) output filename.")
    checkpoint_filename: str = Field(
        default="checkpoint.jsonl",
        description="Checkpoint file recording completed (repository_id, commit_sha, query_text, "
        "pipeline_digest, input_digest) entries.",
    )
    statistics_filename: str = Field(default="dataset_statistics.json", description="Where the final DatasetStatistics summary is written.")
    digest_filename: str = Field(
        default="digest.json",
        description="Where this run's PipelineDigest + InputDigest are written, for reproducibility "
        "auditing (see README.md's Reproducibility Guarantees). Overwritten each run with the latest "
        "digests; historical digests remain recoverable from individual checkpoint.jsonl entries.",
    )

    enable_jsonl_export: bool = Field(default=True, description="Write the long-format JSONL file.")
    enable_csv_export: bool = Field(default=True, description="Write the long-format CSV file.")
    enable_parquet_export: bool = Field(default=True, description="Write the long-format Parquet part file.")
    enable_grouped_export: bool = Field(default=True, description="Write the grouped JSONL file.")

    parquet_batch_size: int = Field(
        default=256, gt=0,
        description="Rows buffered in memory before being flushed as one Parquet row group -- bounds peak "
        "memory for the Parquet writer specifically, independent of total dataset size (streaming).",
    )
