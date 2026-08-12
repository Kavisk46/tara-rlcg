"""Input specs, row/record contracts, statistics, and digest models for the Dataset Builder subsystem."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings
from evaluation.rts_builder.oracle_utility.models import OracleUtilityResult, StrategyOracleRow
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings


class RepositorySpec(BaseModel):
    """One entry in the repository manifest: everything needed to load a repository.

    Mirrors `docs/DATASET_BUILDER_SPEC.md` §3's `repository_manifest.json`
    schema, narrowed to the fields this milestone's pipeline actually
    needs to *run* (`repository_id`/`source_url`/`commit_sha`, exactly
    what `RepositoryLoader.load_repository` takes). That document's
    remaining fields (`language`, `size_bucket`, `domain`, `split`,
    `license`, `pinned_at`) describe dataset-curation decisions this
    milestone does not make (no task classifier, no language detector,
    no curation policy) -- callers that track them can pass them
    through via `metadata` for provenance, unvalidated and untouched.
    """

    repository_id: str = Field(..., min_length=1, description="Stable identifier for this repository within the RTS pipeline.")
    source_url: str = Field(..., min_length=1, description="Repository source URL, passed directly to RepositoryLoader.")
    commit_sha: str = Field(..., min_length=1, description="Pinned commit, passed directly to RepositoryLoader.")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional passthrough curation metadata (e.g. split/domain/license), carried into "
        "DatasetGenerationSummary for provenance but never read or validated by this subsystem.",
    )


class QuerySpec(BaseModel):
    """One query record: a developer query plus its ground-truth relevance judgment, for one repository.

    Mirrors `docs/DATASET_BUILDER_SPEC.md` §4's "query text records,
    keyed by repository." Query authoring and relevance annotation are
    both externally-supplied, human/LLM-driven activities per this
    project's own established design
    (`docs/PILOT_EXECUTION_PLAN.md` §4) -- this subsystem reads
    `QuerySpec` records, it does not generate them.
    """

    repository_id: str = Field(..., min_length=1, description="Which repository (by repository_id) this query belongs to.")
    query_text: str = Field(..., description="The raw developer query text.")
    relevance_grades: dict[str, float] = Field(
        default_factory=dict, description="file_path -> ground-truth relevance grade, as required by "
        "evaluation.rts_builder.oracle_utility.models.RelevanceJudgment."
    )


class PipelineSettingsSnapshot(BaseModel):
    """Every settings object that affects pipeline *output*, bundled for `pipeline_digest` purposes.

    Reviewer Minor Revision (Revision 1): the `configuration_hash`
    component of `PipelineDigest` is derived from exactly this bundle.
    Each of the five wrapped stages' settings classes is frozen,
    private-attribute-based, and exposes no public way to read back the
    settings a caller constructed it with -- so this subsystem cannot
    introspect an already-built `PipelineOrchestrator`'s effective
    configuration without reaching into another milestone's private
    internals, which it does not do. Instead, a caller that constructs
    `PipelineOrchestrator` with non-default settings for any of its five
    collaborators **must** pass the identical settings objects here too,
    for `configuration_hash` to accurately reflect what actually ran --
    see `README.md`'s "Reproducibility Guarantees".
    """

    repository_loader_settings: RepositoryLoaderSettings = Field(default_factory=RepositoryLoaderSettings)
    parser_settings: ParserSettings = Field(default_factory=ParserSettings)
    feature_extraction_settings: FeatureExtractionSettings = Field(default_factory=FeatureExtractionSettings)
    retrieval_executor_settings: RetrievalExecutorSettings = Field(default_factory=RetrievalExecutorSettings)
    oracle_utility_settings: OracleUtilitySettings = Field(default_factory=OracleUtilitySettings)
    dataset_builder_settings: DatasetBuilderSettings = Field(default_factory=DatasetBuilderSettings)


class PipelineDigest(BaseModel):
    """A deterministic fingerprint of the pipeline *code and configuration* that produced a run.

    Reviewer Minor Revision (Revision 1). Every component is
    independently inspectable (for diagnosing *why* a checkpoint
    invalidated); `digest_hash` is the single combined value actually
    used as part of the checkpoint key (Revision 3) -- see
    `digest.py` for how each field is computed and `Oracle_Math.md`
    -style precision in `DatasetSchema.md` for the exact formulas.
    """

    pipeline_version: str = Field(..., description="Dataset Builder's own orchestration-code version.")
    git_commit: str = Field(..., description="The TARA repository's own git commit SHA (suffixed '-dirty' if there are uncommitted changes), or 'unknown' if not run from a git checkout.")
    feature_schema_version: str = Field(..., description="Content hash of FeatureVector's JSON schema.")
    oracle_schema_version: str = Field(..., description="Content hash of StrategyOracleRow's JSON schema.")
    configuration_hash: str = Field(..., description="Content hash of every wrapped stage's effective settings (PipelineSettingsSnapshot).")
    digest_hash: str = Field(..., description="Content hash of the five fields above, combined -- the actual checkpoint-key component.")


class InputDigest(BaseModel):
    """A deterministic fingerprint of the externally-authored input files for one dataset build.

    Reviewer Minor Revision (Revision 2). This pipeline's actual input
    schema (Milestone 7, not redesigned by this revision) combines
    queries and their ground-truth relevance grades into one file
    (`queries.jsonl`) rather than the two separate `queries.json` /
    `relevance_judgments.json` files a from-scratch design might use --
    see `README.md`'s "Reproducibility Guarantees" for why
    `queries_hash` alone (not a third, separate relevance-judgments
    hash) already covers 100% of this pipeline's externally-supplied
    query/relevance input data.
    """

    repository_manifest_hash: str = Field(..., description="SHA-256 of the repository manifest file's raw bytes.")
    queries_hash: str = Field(..., description="SHA-256 of the queries file's raw bytes (relevance_grades included -- see class docstring).")
    digest_hash: str = Field(..., description="Content hash of the two fields above, combined -- the actual checkpoint-key component.")


class DatasetRow(BaseModel):
    """One long-format row: one `(repository, commit, query, strategy)` combination, features + label together.

    A Learning-to-Rank model trains on (features -> label) pairs; a row
    containing only the label (`StrategyOracleRow`) or only the
    features (`FeatureVector`) would not be directly usable on its own.
    `to_flat_dict` merges both `to_flat_dict` outputs -- verified
    disjoint by field-name prefix (`query_`/`repo_`/`graph_`/`structural_`/`resource_`
    vs. unprefixed label fields and `quality_*`), so the merge can never
    silently overwrite one side's column with the other's.

    `pipeline_digest`/`input_digest` (Reviewer Minor Revision) let a
    downstream consumer recover exactly which run produced this row.
    This matters specifically because `CheckpointStore` invalidation is
    whole-file and non-destructive (see its docstring): a digest change
    causes every query to be recomputed and its rows *appended*
    alongside whatever rows a prior, now-superseded run already wrote,
    so the exported long-format files can contain more than one row for
    the same `(repository_id, commit_sha, query_text, strategy_name)`
    key across a digest change. A consumer that keeps only rows whose
    `pipeline_digest`/`input_digest` match the current `digest.json`
    recovers the correct, de-duplicated, latest view.
    """

    feature_vector: FeatureVector
    oracle_row: StrategyOracleRow
    pipeline_digest: str = Field(..., description="The PipelineDigest.digest_hash of the run that produced this row.")
    input_digest: str = Field(..., description="The InputDigest.digest_hash of the run that produced this row.")

    def to_flat_dict(self) -> dict[str, int | float | bool | str]:
        """Return the merged, flat, single-row mapping this format exports."""
        merged = self.feature_vector.to_flat_dict()
        merged.update(self.oracle_row.to_flat_dict())
        merged["pipeline_digest"] = self.pipeline_digest
        merged["input_digest"] = self.input_digest
        return merged


class GroupedDatasetRecord(BaseModel):
    """One grouped-format record: one query, with all four strategies nested as `oracle_result.rows`.

    Exported as JSONL only -- see `README.md`'s Design Decisions for
    why CSV/Parquet, both fundamentally flat/tabular formats, are not
    supported for the grouped (nested) shape in this milestone.

    `pipeline_digest`/`input_digest`: see `DatasetRow`'s docstring --
    the identical reasoning applies here.
    """

    feature_vector: FeatureVector
    oracle_result: OracleUtilityResult
    pipeline_digest: str = Field(..., description="The PipelineDigest.digest_hash of the run that produced this record.")
    input_digest: str = Field(..., description="The InputDigest.digest_hash of the run that produced this record.")


class FeatureStatistic(BaseModel):
    """Streaming-computed mean/min/max for one numeric feature column, across every row processed."""

    mean: float
    minimum: float
    maximum: float
    count: int = Field(..., ge=0, description="Number of rows this statistic was computed over.")


class DatasetStatistics(BaseModel):
    """The dataset-level statistics this milestone is required to generate.

    Cumulative across every run that has ever contributed to this
    output directory, not just the most recent invocation --
    `StatisticsAccumulator` reseeds itself from a previously-written
    `dataset_statistics.json`, if one exists, before folding in newly
    -processed queries (see `statistics.py`). `repository_ids` (not
    just `repository_count`) is what makes that reseeding exact rather
    than approximate: without the actual set, a repository that was
    partially processed in one run and completed in a later resumed
    run would be double-counted.
    """

    repository_count: int = Field(..., ge=0, description="len(repository_ids).")
    repository_ids: list[str] = Field(default_factory=list, description="Every distinct repository_id represented, across every contributing run.")
    query_count: int = Field(..., ge=0, description="Number of distinct (repository, query) pairs processed.")
    row_count: int = Field(..., ge=0, description="Total long-format rows written (== query_count * 4, computed independently).")

    best_strategy_distribution: dict[str, int] = Field(
        default_factory=dict, description="strategy_name.value -> count of queries where that strategy was rank 1."
    )

    average_utility_overall: float = Field(..., description="Mean utility_score across every row.")
    average_utility_by_strategy: dict[str, float] = Field(default_factory=dict)
    average_latency_ms_overall: float = Field(..., description="Mean latency_ms across every row.")
    average_latency_ms_by_strategy: dict[str, float] = Field(default_factory=dict)
    average_quality_overall: float = Field(..., description="Mean quality.quality_score across every row.")
    average_quality_by_strategy: dict[str, float] = Field(default_factory=dict)

    feature_statistics: dict[str, FeatureStatistic] = Field(
        default_factory=dict, description="feature_vector.to_flat_dict() column name -> its FeatureStatistic, "
        "for every numeric (int/float/bool) feature column."
    )


class DatasetGenerationSummary(BaseModel):
    """The final report `DatasetGenerator.generate` returns: what ran, what was skipped, and where output landed."""

    repositories_processed: int = Field(..., ge=0)
    repositories_skipped: int = Field(..., ge=0, description="Repositories whose queries were all already checkpointed as complete.")
    repositories_failed: int = Field(
        default=0, ge=0, description="Repositories whose Repository Loader / Parser stage raised; logged and "
        "skipped, not fatal to the run. Not checkpointed, so a resumed run retries them automatically."
    )
    queries_processed: int = Field(..., ge=0)
    queries_skipped: int = Field(..., ge=0, description="Individual queries already checkpointed as complete (within an otherwise-processed repository).")
    queries_failed: int = Field(
        default=0, ge=0, description="Individual queries whose Feature Extraction / Retrieval Executor / Oracle "
        "Utility stage raised; logged and skipped, not fatal to the run. Not checkpointed, so a resumed run "
        "retries them automatically."
    )
    queries_invalidated_by_digest_change: int = Field(
        default=0, ge=0, description="Previously-checkpointed queries whose recorded pipeline_digest/input_digest "
        "no longer matches this run's -- treated as incomplete and recomputed (counted within "
        "queries_processed too). See README.md's Reproducibility Guarantees."
    )
    pipeline_digest: PipelineDigest
    input_digest: InputDigest
    statistics: DatasetStatistics
    output_paths: dict[str, str] = Field(default_factory=dict, description="Logical output name -> absolute path written.")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
