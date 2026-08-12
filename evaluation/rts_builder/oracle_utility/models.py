"""The normalized output contract for the Oracle Utility subsystem, plus its required ground-truth input.

`RelevanceJudgment` is this subsystem's second required input, beyond
`RetrievalExecutionResult`: computing Recall@k/MRR/NDCG/Context
Precision is impossible without a ground-truth notion of "which files
are actually relevant to this query," which no earlier, frozen
milestone produces or is asked to produce -- see `Architecture.md`'s
"Design Decisions" for why this is modeled as an externally-supplied
input rather than something this subsystem computes.

`StrategyOracleRow` is the long-format row this milestone's stated
"Output schema suitable for Learning-to-Rank" requirement asks for --
one row per `(query, strategy)` pair, matching
`docs/DATASET_BUILDER_SPEC.md` §10's long-format schema design, which
explicitly retains the full per-strategy utility vector rather than
collapsing to a single best-strategy label.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName


class RelevanceJudgment(BaseModel):
    """Ground-truth relevance grades for one (repository, commit, query) combination.

    Externally supplied (by human or LLM annotation -- see
    `docs/PILOT_EXECUTION_PLAN.md` §4, which already folds this
    annotation step into the RTS pipeline's query-authoring process,
    not a separate automated stage). Never produced by any RTS Builder
    code module, including this one.
    """

    repository_id: str = Field(..., description="The repository_id this judgment was authored for.")
    commit_sha: str = Field(..., description="The pinned commit this judgment was authored for.")
    query_text: str = Field(..., description="The exact developer query text this judgment was authored for.")
    relevance_grades: dict[str, float] = Field(
        default_factory=dict,
        description="file_path -> non-negative relevance grade. A file absent from this mapping is "
        "not relevant (grade 0). Binary relevance is grade 1.0 for relevant files; graded relevance "
        "(e.g. 0/1/2/3) is also supported and used directly by ndcg -- see Oracle_Math.md.",
    )


class QualityMetrics(BaseModel):
    """The four retrieval-quality metrics for one strategy on one query, plus their weighted composite."""

    recall_at_k: float = Field(..., ge=0.0, le=1.0, description="Fraction of relevant files found in the top-k retrieved files.")
    mrr: float = Field(..., ge=0.0, le=1.0, description="Reciprocal rank of the first relevant retrieved file, for this one query.")
    ndcg: float = Field(..., ge=0.0, le=1.0, description="Normalized Discounted Cumulative Gain at k, using graded relevance.")
    context_precision: float = Field(..., ge=0.0, le=1.0, description="Fraction of all retrieved files (not just top-k) that are relevant.")
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Weighted composite: quality_recall_weight*recall_at_k + "
        "quality_mrr_weight*mrr + quality_ndcg_weight*ndcg + quality_context_precision_weight*context_precision."
    )


class StrategyOracleRow(BaseModel):
    """One row of the long-format Oracle Utility output: one `(query, strategy)` pair.

    This is the "suitable for Learning-to-Rank" contract: every field a
    ranker needs to train on is present directly on the row (no join
    required against a separate rankings table), including
    `label_confidence` and `tied_with`, which are computed once per
    query and repeated identically across that query's four rows --
    matching `docs/DATASET_BUILDER_SPEC.md` §9's stated design for the
    same reason (self-contained rows).
    """

    repository_id: str = Field(..., description="The repository_id this row was computed for.")
    commit_sha: str = Field(..., description="The pinned commit this row was computed for.")
    query_text: str = Field(..., description="The raw developer query text this row was computed for.")
    strategy_name: RetrievalStrategyName = Field(..., description="Which of the four Retrieval Executor strategies this row describes.")

    quality: QualityMetrics
    latency_ms: float = Field(..., ge=0.0, description="This strategy's raw, unnormalized retrieval_latency_ms (frozen protocol).")
    latency_normalized: float = Field(
        ..., ge=0.0, le=1.0, description="latency_ms min-max normalized across this query's 4 strategies "
        "(tara.retrieval.utils.normalize_scores, reused unmodified)."
    )
    context_token_count: int = Field(..., ge=0, description="Carried through from StrategyResult, for LTR feature completeness.")

    utility_score: float = Field(..., description="alpha*quality.quality_score - beta*latency_normalized. Not bounded to [0,1]: can be negative.")
    rank: int = Field(..., ge=1, le=4, description="1 (best) through 4 (worst), by descending utility_score.")
    is_best_strategy: bool = Field(..., description="True iff rank == 1.")
    label_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Query-level confidence in the rank-1 label, repeated across "
        "all four of this query's rows -- see Oracle_Math.md for the exact formula."
    )
    tied_with: list[RetrievalStrategyName] = Field(
        default_factory=list, description="Other strategies whose utility_score is within tie_epsilon of "
        "this row's own -- informational; rank is always a strict total order regardless of ties."
    )

    def to_flat_dict(self) -> dict[str, int | float | bool | str]:
        """Flatten this row (including nested `quality`) into a single scalar-only mapping.

        Mirrors `FeatureVector.to_flat_dict`'s established convention:
        one key per leaf value, `quality_*`-prefixed for the nested
        group, enum fields reduced to their string `.value`, ready to
        become a training-table row.
        """
        flat: dict[str, int | float | bool | str] = {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "query_text": self.query_text,
            "strategy_name": self.strategy_name.value,
            "latency_ms": self.latency_ms,
            "latency_normalized": self.latency_normalized,
            "context_token_count": self.context_token_count,
            "utility_score": self.utility_score,
            "rank": self.rank,
            "is_best_strategy": self.is_best_strategy,
            "label_confidence": self.label_confidence,
            "tied_with": ",".join(strategy.value for strategy in self.tied_with),
        }
        for field_name, value in self.quality.model_dump().items():
            flat[f"quality_{field_name}"] = value.value if isinstance(value, Enum) else value
        return flat


class OracleUtilityResult(BaseModel):
    """All four strategies' Oracle Utility rows for one `(repository, commit, query)` combination."""

    repository_id: str = Field(..., description="The repository_id these rows were computed for.")
    commit_sha: str = Field(..., description="The pinned commit these rows were computed for.")
    query_text: str = Field(..., description="The raw developer query text these rows were computed for.")
    rows: list[StrategyOracleRow] = Field(..., description="Always exactly 4 rows, one per strategy, sorted by rank ascending (best first).")
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When this result was computed. Provenance, not a feature."
    )

    def to_long_format_rows(self) -> list[dict[str, int | float | bool | str]]:
        """Return every row flattened via `StrategyOracleRow.to_flat_dict` -- the LTR-ready table."""
        return [row.to_flat_dict() for row in self.rows]
