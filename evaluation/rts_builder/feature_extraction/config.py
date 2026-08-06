"""Configuration for the RTS Builder's Feature Extraction subsystem.

Every heuristic constant with more than one reasonable value (bucket
thresholds, the token-estimation ratio, the query-complexity weights)
is a setting here, not a hardcoded literal in a compute module --
required so a later pilot-calibration pass (mirroring
`docs/DATASET_BUILDER_SPEC.md`'s own "proposed default requiring pilot
calibration" discipline for its Utility formula's `lambda`) can retune
these without touching feature-computation code, and so two pipeline
runs using different settings are distinguishable, not silently
divergent.
"""
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureExtractionSettings(BaseSettings):
    """Environment-driven configuration for `FeatureExtractor`.

    Every field can be overridden by an environment variable named
    `RTS_FEATURES_<FIELD_NAME>` (uppercased), or by an entry in a local
    `.env` file. See `evaluation/rts_builder/feature_extraction/.env.example`.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_FEATURES_", env_file=".env", extra="ignore")

    # --- Resource features ---
    chars_per_token_estimate: float = Field(
        default=4.0,
        gt=0,
        description="Approximate characters-per-token ratio used to estimate repository token count "
        "from total source size, without depending on any specific LLM tokenizer.",
    )
    small_repository_file_count_threshold: int = Field(
        default=50,
        gt=0,
        description="Repositories with at most this many files are categorized 'small'.",
    )
    large_repository_file_count_threshold: int = Field(
        default=500,
        gt=0,
        description="Repositories with more than this many files are categorized 'large'; "
        "repositories in between are 'medium'.",
    )

    # --- Query complexity ---
    query_complexity_length_weight: float = Field(
        default=0.4, ge=0.0, le=1.0, description="Weight of normalized word count in query_complexity."
    )
    query_complexity_identifier_weight: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Weight of normalized identifier density in query_complexity."
    )
    query_complexity_clause_weight: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Weight of normalized clause count in query_complexity."
    )
    query_complexity_length_norm: int = Field(
        default=25, gt=0, description="Word count treated as 'maximally long' (clamped to 1.0 above this) when normalizing."
    )
    query_complexity_identifier_norm: int = Field(
        default=5, gt=0, description="Identifier count treated as 'maximally identifier-dense' when normalizing."
    )
    query_complexity_clause_norm: int = Field(
        default=3, gt=0, description="Clause count treated as 'maximally multi-clause' when normalizing."
    )

    # --- Structural features ---
    enable_comment_coverage: bool = Field(
        default=True,
        description="If True, re-read each source file from disk (via RepositoryModel.root_path) to "
        "compute comment_coverage_ratio -- the one feature in this subsystem that reads outside "
        "RepositoryModel's own data (see README.md). If False, comment_coverage_ratio is always 0.0 "
        "and no filesystem access is performed.",
    )

    @model_validator(mode="after")
    def _validate_query_complexity_weights_sum_to_one(self) -> "FeatureExtractionSettings":
        """Ensure the three query_complexity weights combine into a properly bounded [0, 1] score."""
        total = (
            self.query_complexity_length_weight
            + self.query_complexity_identifier_weight
            + self.query_complexity_clause_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"query_complexity_*_weight fields must sum to 1.0 (got {total!r}); otherwise "
                "query_complexity would not be boundable to [0, 1]."
            )
        return self

    @model_validator(mode="after")
    def _validate_repository_size_thresholds_are_ordered(self) -> "FeatureExtractionSettings":
        """Ensure the small/large thresholds define a non-empty 'medium' band."""
        if self.small_repository_file_count_threshold >= self.large_repository_file_count_threshold:
            raise ValueError(
                "small_repository_file_count_threshold must be less than "
                "large_repository_file_count_threshold."
            )
        return self
