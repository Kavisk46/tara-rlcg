"""Data contracts for the Lexical Retrieval module.

Defines the value objects the BM25 index, the symbol/file search
helpers, and the ranking engine produce and consume: a normalized
`RetrievalScore`, a raw `SearchResult` returned by low-level search
functions, and the retriever-facing `RetrievedChunk` / `RetrievedContext`
pair that is this module's actual output. `RetrievedChunk.chunk_id`
reuses the exact node-id scheme already established by
`tara.context.models` (`build_file_node_id` / `build_symbol_node_id`),
so a chunk retrieved lexically can always be correlated back to the
repository graph, the symbol index, and, once Dense Retrieval exists,
an embedding vector for the same node -- with no translation step.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from tara.context.models import NodeType
from tara.core.types import RetrieverKind


class MatchedField(str, Enum):
    """Which indexed field a search match was found in.

    Kept as a closed enum rather than a free string, consistent with
    how the rest of TARA represents closed vocabularies (e.g.
    `tara.context.models.NodeType`), so a typo in a field name fails at
    construction time rather than silently producing an unrecognized
    diagnostic value.
    """

    NAME = "name"
    DOCSTRING = "docstring"
    SOURCE = "source"
    PATH = "path"


class RetrievalScore(BaseModel):
    """A single match's relevance score, in both raw and normalized form.

    `raw_score` is whatever scale the underlying ranking function
    produces (BM25 scores are unbounded, not comparable across queries
    or corpora, and can occasionally be negative for very common terms).
    `normalized_score` rescales it into a fixed `[0.0, 1.0]` range so
    scores from different queries -- or, once Dense/Graph Retrieval
    exist, from different retrievers entirely -- can be compared or
    merged by Context Fusion without every caller re-deriving its own
    normalization.
    """

    raw_score: float = Field(
        ..., description="The unnormalized score as produced by the ranking function (e.g. a raw BM25 score)."
    )
    normalized_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="`raw_score` rescaled into a fixed [0.0, 1.0] range for cross-query/cross-retriever comparison.",
    )
    matched_terms: tuple[str, ...] = Field(
        default=(), description="Query terms that contributed to this score, for debugging and explainability."
    )


class SearchResult(BaseModel):
    """A single raw match returned by a low-level search function.

    This is the intermediate representation the BM25 index and the
    symbol/file search helpers (`find_function`, `find_file`, ...)
    return; the ranking engine consumes a list of these to produce the
    final, ordered `RetrievedChunk` list. Kept distinct from
    `RetrievedChunk`: a `SearchResult` is retriever-internal and
    index-facing, while a `RetrievedChunk` is this stage's public,
    cross-stage output handed to Context Fusion.
    """

    node_id: str = Field(
        ...,
        min_length=1,
        description="The graph/symbol-index node id this result matches, per "
        "`tara.context.models.build_symbol_node_id` / `build_file_node_id`.",
    )
    node_type: NodeType = Field(..., description="The kind of entity matched (file, class, function, or method).")
    name: str = Field(..., min_length=1, description="The matched symbol or file name.")
    file_path: str = Field(..., min_length=1, description="Repository-relative path of the file the match belongs to.")
    score: RetrievalScore = Field(..., description="The relevance score for this match.")
    matched_field: MatchedField = Field(..., description="Which indexed field the match was found in.")


class RetrievedChunk(BaseModel):
    """A single piece of retrieved context, ready to hand to Context Fusion.

    The public, cross-stage unit of retrieval output. `chunk_id` is the
    same node id used throughout `tara.context`, so a chunk retrieved
    here can be directly correlated with the repository graph, the
    symbol index, and (once Dense Retrieval exists) an embedding vector
    for the same node.
    """

    chunk_id: str = Field(
        ..., min_length=1, description="The node id this chunk corresponds to; consistent with `tara.context`'s id scheme."
    )
    retriever_kind: RetrieverKind = Field(..., description="Which retriever produced this chunk.")
    node_type: NodeType = Field(..., description="The kind of entity this chunk represents.")
    name: str = Field(..., min_length=1, description="The symbol or file name this chunk represents.")
    file_path: str = Field(..., min_length=1, description="Repository-relative path of the file this chunk belongs to.")
    start_line: int | None = Field(
        default=None, ge=0, description="0-indexed start line of the chunk's source span, if applicable."
    )
    end_line: int | None = Field(
        default=None, ge=0, description="0-indexed end line of the chunk's source span, if applicable."
    )
    content: str = Field(
        ..., description="The chunk's text content: source code for a symbol, or a path/name summary for a file-level chunk."
    )
    docstring: str | None = Field(default=None, description="The symbol's docstring, if any and if extracted.")
    score: RetrievalScore = Field(..., description="The relevance score that ranked this chunk.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic detail, e.g. matched terms; not part of the stable contract."
    )

    @model_validator(mode="after")
    def _validate_line_span(self) -> "RetrievedChunk":
        """Ensure a partially- or fully-specified line span is internally consistent."""
        if self.start_line is not None and self.end_line is not None and self.end_line < self.start_line:
            raise ValueError(f"end_line ({self.end_line}) must be >= start_line ({self.start_line})")
        return self


class RetrievedContext(BaseModel):
    """The complete output of a single retriever's invocation for one query.

    One `RetrievedContext` is produced per retriever kind that runs for
    a query (`tara.routing.models.RetrievalPlan.retrievers`); Context
    Fusion later merges one or more of these into a single fused
    context. `chunks` is expected to already be sorted by descending
    relevance and already truncated to the requesting plan's `top_k`.
    """

    retriever_kind: RetrieverKind = Field(..., description="Which retriever produced this context.")
    query: str = Field(..., description="The original query text this context was retrieved for.")
    chunks: list[RetrievedChunk] = Field(
        default_factory=list, description="Retrieved chunks, sorted by descending relevance, truncated to the requested top_k."
    )
    total_candidates: int = Field(
        default=0, ge=0, description="Number of candidates considered before ranking/truncation, for diagnostics."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic detail; not part of the stable contract."
    )

    @model_validator(mode="after")
    def _validate_chunk_retriever_consistency(self) -> "RetrievedContext":
        """Ensure every chunk in this context reports the same retriever that produced it."""
        for chunk in self.chunks:
            if chunk.retriever_kind is not self.retriever_kind:
                raise ValueError(
                    f"chunk {chunk.chunk_id!r} reports retriever_kind={chunk.retriever_kind!r}, "
                    f"expected {self.retriever_kind!r}"
                )
        return self
