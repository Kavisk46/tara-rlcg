"""Configuration for the RTS Builder's Retrieval Executor subsystem.

Every tunable constant (BM25 parameters, per-signal and per-strategy
combination weights, graph hop budget, token-estimation ratio,
size-based caps) is a setting here, not a hardcoded literal in a
retriever module -- consistent with every prior RTS Builder milestone's
own configuration discipline, and required for the weighted
combinations (`LexicalRetriever`'s three internal signals,
`HybridRetriever`'s three strategy scores) to be retunable without
touching retrieval logic.
"""
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalExecutorSettings(BaseSettings):
    """Environment-driven configuration for `RetrievalExecutor` and its four strategies.

    Every field can be overridden by an environment variable named
    `RTS_RETRIEVAL_<FIELD_NAME>` (uppercased), or by an entry in a local
    `.env` file. See `evaluation/rts_builder/retrieval_executor/.env.example`.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_RETRIEVAL_", env_file=".env", extra="ignore")

    # --- Shared ---
    top_k: int = Field(default=10, gt=0, description="Maximum files returned by each strategy.")
    chars_per_token_estimate: float = Field(
        default=4.0, gt=0, description="Characters-per-token ratio used for context_token_count, "
        "matching the convention already established by Feature Extraction's own resource features."
    )

    # --- Lexical Retrieval ---
    bm25_k1: float = Field(default=1.5, gt=0, description="BM25 term-frequency saturation parameter.")
    bm25_b: float = Field(default=0.75, ge=0.0, le=1.0, description="BM25 document-length normalization parameter.")
    lexical_bm25_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Weight of the BM25 signal in the combined lexical score.")
    lexical_identifier_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight of the exact-identifier-match signal.")
    lexical_keyword_overlap_weight: float = Field(default=0.2, ge=0.0, le=1.0, description="Weight of the raw keyword-overlap signal.")

    # --- Dense Retrieval ---
    embedding_dimensions: int = Field(default=128, gt=0, description="Vector dimensionality for the default HashingEmbedder.")

    # --- Graph Retrieval ---
    max_graph_hops: int = Field(default=2, gt=0, description="Maximum BFS hop distance from a seed file during graph expansion.")

    # --- Hybrid Retrieval ---
    hybrid_lexical_weight: float = Field(default=1 / 3, ge=0.0, le=1.0, description="Weight of the (normalized) lexical score in the hybrid combination.")
    hybrid_dense_weight: float = Field(default=1 / 3, ge=0.0, le=1.0, description="Weight of the (normalized) dense score in the hybrid combination.")
    hybrid_graph_weight: float = Field(default=1 / 3, ge=0.0, le=1.0, description="Weight of the (normalized) graph score in the hybrid combination.")

    # --- Latency budget scaling (uses FeatureVector.resource, see README.md) ---
    large_repository_top_k_cap: int = Field(
        default=5, gt=0, description="top_k is capped to this value when "
        "FeatureVector.resource.repository_size_category is LARGE, to bound latency on large repositories."
    )

    @model_validator(mode="after")
    def _validate_lexical_weights_sum_to_one(self) -> "RetrievalExecutorSettings":
        """Ensure the three lexical sub-signal weights combine predictably."""
        total = self.lexical_bm25_weight + self.lexical_identifier_weight + self.lexical_keyword_overlap_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"lexical_*_weight fields must sum to 1.0 (got {total!r}).")
        return self

    @model_validator(mode="after")
    def _validate_hybrid_weights_sum_to_one(self) -> "RetrievalExecutorSettings":
        """Ensure the three hybrid strategy weights combine predictably."""
        total = self.hybrid_lexical_weight + self.hybrid_dense_weight + self.hybrid_graph_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"hybrid_*_weight fields must sum to 1.0 (got {total!r}).")
        return self
