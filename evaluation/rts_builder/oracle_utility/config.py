"""Configuration for the RTS Builder's Oracle Utility subsystem.

Every coefficient in the Utility formula and its supporting metrics is
a setting here, not a hardcoded literal -- required both by this
milestone's own "Configuration-driven weights" requirement and by
`docs/DATASET_BUILDER_SPEC.md` §8-9's explicit framing of several of
these exact constants (`lambda`, `epsilon`) as **proposed defaults
requiring pilot calibration**, not settled values. See `Oracle_Math.md`
for the full derivation each field corresponds to.
"""
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OracleUtilitySettings(BaseSettings):
    """Environment-driven configuration for `OracleUtilityComputer`.

    Every field can be overridden by an environment variable named
    `RTS_ORACLE_<FIELD_NAME>` (uppercased), or by an entry in a local
    `.env` file. See `evaluation/rts_builder/oracle_utility/.env.example`.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_ORACLE_", env_file=".env", extra="ignore")

    # --- Retrieval quality metrics ---
    quality_metrics_k: int = Field(
        default=10, gt=0,
        description="k for Recall@k and NDCG@k. Context precision is computed over the full "
        "retrieved set, not this k -- see Oracle_Math.md.",
    )
    quality_recall_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight of Recall@k in the composite Quality score.")
    quality_mrr_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight of MRR in the composite Quality score.")
    quality_ndcg_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight of NDCG@k in the composite Quality score.")
    quality_context_precision_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight of Context Precision in the composite Quality score.")

    # --- Utility formula: Utility = alpha * Quality - beta * Latency_normalized ---
    utility_quality_weight: float = Field(
        default=1.0, gt=0.0,
        description="alpha in Utility = alpha*Quality - beta*Latency_normalized.",
    )
    utility_latency_weight: float = Field(
        default=0.1, ge=0.0,
        description="beta in Utility = alpha*Quality - beta*Latency_normalized. Proposed default "
        "0.1, mirroring docs/DATASET_BUILDER_SPEC.md §8's lambda=0.1 proposed default (alpha=1 "
        "recovers that original formula exactly) -- not a validated constant; that document's §14 "
        "sensitivity-sweep requirement applies equally here.",
    )

    # --- Ranking: tie handling and confidence ---
    tie_epsilon: float = Field(
        default=0.02, ge=0.0,
        description="Two strategies are considered tied if |Utility(a) - Utility(b)| < tie_epsilon. "
        "Proposed default per docs/DATASET_BUILDER_SPEC.md §9, pilot-calibrated, not fixed in advance.",
    )
    confidence_epsilon: float = Field(
        default=1e-6, gt=0.0,
        description="epsilon_0 in the label_confidence formula (Oracle_Math.md); prevents division "
        "by zero when the top-ranked strategy's utility is itself near zero.",
    )

    @model_validator(mode="after")
    def _validate_quality_weights_sum_to_one(self) -> "OracleUtilitySettings":
        """Ensure the four quality sub-metric weights combine into a properly bounded [0, 1] score."""
        total = (
            self.quality_recall_weight
            + self.quality_mrr_weight
            + self.quality_ndcg_weight
            + self.quality_context_precision_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"quality_*_weight fields must sum to 1.0 (got {total!r}).")
        return self
