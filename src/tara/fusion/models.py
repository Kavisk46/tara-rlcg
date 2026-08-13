"""Data contracts for Context Fusion.

Defines `FusedChunk` and `FusedContext`, the shared output of merging
one or more `RetrievedContext` objects (`tara.retrieval.models`) into
the single, deduplicated, budgeted payload the (future) LLM Interface
stage consumes. Fields are copied directly from the canonical
`RetrievedChunk` a candidate was deduplicated from -- deliberately not a
nested wrapper around `RetrievedChunk` -- matching how `RetrievedChunk`
itself is a fresh, purpose-built model rather than a wrapper around
`SearchResult`, so downstream consumers (prompt assembly, §21) can read
`fused_chunk.file_path` directly instead of `fused_chunk.chunk.file_path`.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from tara.context.models import NodeType
from tara.core.types import RetrieverKind


class FusedChunk(BaseModel):
    """One deduplicated, cross-retriever-scored candidate, ready for prompt assembly.

    `found_by` and `source_scores` are this model's whole reason for
    existing beyond a plain `RetrievedChunk`: a candidate chunk
    contributed by more than one retriever is represented exactly once
    here, but with every contributing retriever's identity and original
    score preserved -- deduplication that discards *which* retrievers
    agreed on a candidate would throw away exactly the cross-retriever
    corroboration signal this stage exists to compute.
    """

    chunk_id: str = Field(
        ..., min_length=1, description="The node id this chunk corresponds to; the dedup key."
    )
    node_type: NodeType = Field(..., description="The kind of entity this chunk represents.")
    name: str = Field(
        ..., min_length=1, description="The symbol or file name this chunk represents."
    )
    file_path: str = Field(
        ..., min_length=1, description="Repository-relative path of the file this chunk belongs to."
    )
    start_line: int | None = Field(
        default=None,
        ge=0,
        description="0-indexed start line of the chunk's source span, if applicable.",
    )
    end_line: int | None = Field(
        default=None,
        ge=0,
        description="0-indexed end line of the chunk's source span, if applicable.",
    )
    content: str = Field(
        ..., description="The chunk's text content, copied from its canonical `RetrievedChunk`."
    )
    docstring: str | None = Field(
        default=None, description="The symbol's docstring, if any and if extracted."
    )
    fused_score: float = Field(
        ...,
        ge=0.0,
        description="The cross-retriever-merged relevance score (see `tara.fusion.score_merge`). "
        "Not bounded to <= 1.0: a weighted-average merge of [0,1] inputs with weights that don't "
        "sum to 1 can, by construction, exceed 1.0 -- see `ScoreMerger` for the exact formula.",
    )
    found_by: tuple[RetrieverKind, ...] = Field(
        ...,
        min_length=1,
        description="Every retriever kind that surfaced this chunk_id, sorted by "
        "RetrieverKind.value for deterministic equality/display, deduplicated even if a "
        "retriever's own output somehow listed the same chunk_id twice.",
    )
    source_scores: dict[str, float] = Field(
        ...,
        description="RetrieverKind.value -> that retriever's own normalized_score for this "
        "chunk_id, before merging. Preserves per-source provenance that `fused_score` alone "
        "collapses.",
    )
    token_count: int = Field(
        ...,
        ge=0,
        description="This chunk's own approximate token contribution "
        "(see `tara.fusion.token_budget`).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic detail; not part of the stable contract."
    )

    @model_validator(mode="after")
    def _validate_line_span(self) -> FusedChunk:
        """Ensure a partially- or fully-specified line span is internally consistent."""
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        return self

    @model_validator(mode="after")
    def _validate_found_by_matches_source_scores(self) -> FusedChunk:
        """Ensure `found_by` and `source_scores` describe the same set of retrievers."""
        found_by_values = {kind.value for kind in self.found_by}
        if found_by_values != set(self.source_scores):
            raise ValueError(
                f"found_by {sorted(found_by_values)} does not match source_scores keys "
                f"{sorted(self.source_scores)} for chunk_id {self.chunk_id!r}"
            )
        return self


class FusedContext(BaseModel):
    """The complete output of fusing one or more `RetrievedContext` objects for one query.

    Per `PROJECT_SPEC.md` §15/§20: consumed next by the (not yet
    implemented) LLM Interface stage for prompt assembly. `chunks` is
    already deduplicated, already reranked (if the originating
    `RetrievalPlan.rerank` was true), already cut to `RetrievalPlan.top_k`,
    and already truncated to fit the configured token budget -- nothing
    downstream needs to re-derive any of that.
    """

    query: str = Field(..., description="The original query text this context was fused for.")
    chunks: list[FusedChunk] = Field(
        default_factory=list, description="The final, ordered, budget-truncated candidate list."
    )
    total_tokens: int = Field(
        default=0, ge=0, description="Sum of `token_count` across every chunk actually included."
    )
    truncated: bool = Field(
        ...,
        description="True if one or more deduplicated candidates were excluded solely because "
        "including them would have exceeded the token budget -- distinct from a candidate never "
        "existing in the first place (empty retrieval) or being cut by top_k, neither of which "
        "sets this.",
    )
    candidate_count: int = Field(
        default=0,
        ge=0,
        description="Number of distinct (deduplicated) candidates that existed before "
        "top_k/token-budget truncation, for diagnosing how much was cut and why.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic detail, e.g. which retrievers contributed, whether reranking "
        "was applied; not part of the stable contract.",
    )
