"""The normalized output contract for the Retrieval Executor subsystem.

One `StrategyResult` per strategy (Lexical, Dense, Graph, Hybrid),
composed into a `RetrievalExecutionResult` -- the object
`RetrievalExecutor.execute_all` returns. Every field is a plain,
JSON-serializable value; no strategy retains a raw vector index, BM25
index, or embedding model reference on its result.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class RetrievalStrategyName(str, Enum):
    """Which of the four independently-executed strategies produced a `StrategyResult`."""

    LEXICAL = "lexical"
    DENSE = "dense"
    GRAPH = "graph"
    HYBRID = "hybrid"


class RetrievedFile(BaseModel):
    """A single file retrieved by one strategy, ranked by that strategy's own relevance score."""

    file_path: str = Field(..., description="Repository-relative, POSIX-style path of the retrieved file.")
    score: float = Field(..., description="This file's relevance score under the producing strategy. Scale is strategy-specific -- see README.md.")
    matched_reason: str | None = Field(
        default=None, description="Optional, human-readable justification (e.g. 'exact identifier match: Dog'), "
        "for debugging and dataset-quality review; never used programmatically downstream."
    )


class StrategyResult(BaseModel):
    """One strategy's complete, independent retrieval result for one (repository, query) pair."""

    strategy_name: RetrievalStrategyName = Field(..., description="Which strategy produced this result.")
    repository_id: str = Field(..., description="The repository_id this result was computed for.")
    commit_sha: str = Field(..., description="The pinned commit this result was computed for.")
    query_text: str = Field(..., description="The raw developer query text this result was computed for.")

    retrieved_files: list[RetrievedFile] = Field(
        default_factory=list, description="Ranked (highest score first), at most top_k files. Empty is a valid, "
        "expected result -- see README.md's Failure Modes -- not an error."
    )
    retrieval_score: float = Field(
        ..., ge=0.0, description="max(f.score for f in retrieved_files), or 0.0 if retrieved_files is empty -- "
        "this strategy's confidence in its own best result."
    )
    retrieval_latency_ms: float = Field(..., ge=0.0, description="Wall-clock time this strategy took to execute, in milliseconds.")
    context_token_count: int = Field(
        ..., ge=0, description="Estimated tokens if every retrieved file's content were included as LLM context: "
        "sum(size_bytes of retrieved files) / chars_per_token_estimate."
    )

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When this result was computed. Provenance, not a feature of the result."
    )


class RetrievalExecutionResult(BaseModel):
    """All four strategies' independent results for one (repository, query) pair."""

    repository_id: str = Field(..., description="The repository_id these results were computed for.")
    commit_sha: str = Field(..., description="The pinned commit these results were computed for.")
    query_text: str = Field(..., description="The raw developer query text these results were computed for.")

    lexical: StrategyResult
    dense: StrategyResult
    graph: StrategyResult
    hybrid: StrategyResult

    def all_results(self) -> list[StrategyResult]:
        """Return all four `StrategyResult`s as a list, in a fixed, deterministic order."""
        return [self.lexical, self.dense, self.graph, self.hybrid]
