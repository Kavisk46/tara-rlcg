"""Report, split, and reproducibility models for the RTS Builder's Pilot subsystem.

Deliberately reuses the frozen Dataset Builder's own models
(`DatasetGenerationSummary`, `PipelineDigest`, `InputDigest`,
`FeatureStatistic`) wherever the same information is needed, rather
than redefining parallel shapes -- one authoritative schema per
concept, consistent with every prior RTS Builder milestone's own
practice of composing rather than duplicating a frozen upstream
stage's contracts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from evaluation.rts_builder.dataset_builder.models import (
    DatasetGenerationSummary,
    FeatureStatistic,
    InputDigest,
    PipelineDigest,
)


class SplitName(str, Enum):
    """The three Learning-to-Rank dataset partitions every query is deterministically assigned to."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class Histogram(BaseModel):
    """An equal-width histogram over one numeric column -- reused for utility/latency/quality."""

    bin_edges: list[float] = Field(..., description="len(bin_edges) == len(counts) + 1; bin i covers [bin_edges[i], bin_edges[i+1]).")
    counts: list[int] = Field(..., description="Row count falling in each bin, same order as bin_edges.")


class ValidationCheck(BaseModel):
    """The outcome of one named validation check."""

    name: str = Field(..., description="Stable, snake_case identifier for this check (e.g. 'no_missing_values').")
    blocking: bool = Field(..., description="If True, a failure here fails the whole ValidationReport (a Success Criterion). If False, informational only.")
    passed: bool
    detail: str = Field(..., description="Human-readable explanation of the outcome, including counts when relevant.")


class ValidationReport(BaseModel):
    """The complete, automated validation summary for one assembled pilot dataset.

    Computed independently of (and as a cross-check against)
    `DatasetStatistics`/`StatisticsAccumulator` -- both read the same
    underlying rows, but this report is built directly from the
    assembled pilot rows rather than reusing the frozen accumulator, so
    a bug in one is unlikely to be masked by the other.
    """

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    row_count: int = Field(..., ge=0)
    query_count: int = Field(..., ge=0, description="Distinct (repository_id, commit_sha, query_text) triples.")

    checks: list[ValidationCheck] = Field(..., description="Every check run, blocking and informational, in the order evaluated.")
    passed: bool = Field(..., description="True iff every *blocking* check in `checks` passed. See Success Criteria in VALIDATION_GUIDE.md.")

    missing_value_row_count: int = Field(..., ge=0, description="Rows containing at least one None/NaN value in any column.")
    duplicate_row_count: int = Field(..., ge=0, description="Rows that are an exact duplicate of an earlier row (all columns equal).")
    duplicate_query_strategy_pair_count: int = Field(
        ..., ge=0, description="(repository_id, commit_sha, query_text, strategy_name) keys that appear more than once."
    )
    queries_with_unexpected_strategy_count: int = Field(
        ..., ge=0, description="Distinct queries whose row count != PilotSettings.expected_strategy_count."
    )

    strategy_distribution: dict[str, int] = Field(default_factory=dict, description="strategy_name -> row count.")
    repository_distribution: dict[str, int] = Field(default_factory=dict, description="repository_id -> row count.")
    rank_distribution: dict[str, int] = Field(default_factory=dict, description="rank (as string) -> row count.")
    split_distribution: dict[str, int] = Field(default_factory=dict, description="split name -> query count.")

    average_utility_overall: float
    average_utility_by_strategy: dict[str, float] = Field(default_factory=dict)
    average_latency_ms_overall: float
    average_latency_ms_by_strategy: dict[str, float] = Field(default_factory=dict)
    average_quality_overall: float
    average_quality_by_strategy: dict[str, float] = Field(default_factory=dict)

    utility_histogram: Histogram
    latency_histogram: Histogram
    quality_histogram: Histogram

    feature_distributions: dict[str, FeatureStatistic] = Field(
        default_factory=dict, description="Numeric feature column -> its FeatureStatistic, mirroring "
        "DatasetStatistics.feature_statistics's own definition of 'numeric feature column'."
    )


class SplitCounts(BaseModel):
    """How many distinct queries and long-format rows landed in each split."""

    train_queries: int = Field(..., ge=0)
    validation_queries: int = Field(..., ge=0)
    test_queries: int = Field(..., ge=0)
    train_rows: int = Field(..., ge=0)
    validation_rows: int = Field(..., ge=0)
    test_rows: int = Field(..., ge=0)


class EnvironmentInfo(BaseModel):
    """The execution environment a pilot run happened in, for reproducibility auditing."""

    python_version: str = Field(..., description="sys.version, full interpreter version string.")
    platform: str = Field(..., description="platform.platform(), the OS/architecture string.")
    package_versions: dict[str, str] = Field(
        default_factory=dict, description="Distribution name -> installed version, for every package whose "
        "version could materially affect pilot output (pydantic, pyarrow, numpy, matplotlib, gitpython).",
    )


class ReproducibilityRecord(BaseModel):
    """Everything the Reproducibility section asks to be recorded, for one pilot run.

    `pipeline_digest`/`input_digest` are reused verbatim from the
    frozen Dataset Builder's own `DatasetGenerationSummary` (which
    already includes pipeline version, git commit, and configuration
    hash -- see `PipelineDigest`) rather than recomputed independently,
    so there is exactly one source of truth for "what pipeline and
    inputs produced this data."
    """

    pipeline_digest: PipelineDigest
    input_digest: InputDigest
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    environment: EnvironmentInfo


class PilotSummary(BaseModel):
    """The final report `PilotRunner.run` returns: everything a caller needs to know about the pilot."""

    dataset_generation_summary: DatasetGenerationSummary = Field(
        ..., description="The frozen Dataset Builder's own summary for the underlying generation run, unmodified."
    )
    split_counts: SplitCounts
    validation_report: ValidationReport
    reproducibility: ReproducibilityRecord
    output_paths: dict[str, str] = Field(default_factory=dict, description="Logical output name -> absolute path written.")
    figure_paths: dict[str, str] = Field(default_factory=dict, description="Figure name -> absolute path written.")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
