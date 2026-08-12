"""Configuration for the RTS Builder's Pilot subsystem.

Owns only what is genuinely new at this stage: split ratios/seed,
output locations under `data/`, figure rendering options, and the
validation success-criteria toggle. The underlying dataset generation
itself is entirely owned and configured by the frozen Dataset Builder
subsystem's own `DatasetBuilderSettings` -- not re-declared here, same
convention `DatasetBuilderSettings` itself established relative to the
five stages it wraps.
"""
from __future__ import annotations

import math

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_RATIO_SUM_TOLERANCE = 1e-6


class PilotSettings(BaseSettings):
    """Environment-driven configuration for `PilotRunner`.

    Every field can be overridden by an environment variable named
    `RTS_PILOT_<FIELD_NAME>` (uppercased), or by an entry in a local
    `.env` file. See `evaluation/rts_builder/pilot/.env.example`.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_PILOT_", env_file=".env", extra="ignore")

    data_dir: str = Field(default="data", description="Directory every pilot dataset/report/figure artifact is written under.")
    figures_dirname: str = Field(default="figures", description="Subdirectory of data_dir the quality-report figures are written to.")

    train_ratio: float = Field(default=0.70, gt=0.0, lt=1.0, description="Fraction of distinct queries assigned to the train split.")
    validation_ratio: float = Field(default=0.15, gt=0.0, lt=1.0, description="Fraction of distinct queries assigned to the validation split.")
    test_ratio: float = Field(default=0.15, gt=0.0, lt=1.0, description="Fraction of distinct queries assigned to the test split.")
    split_seed: str = Field(
        default="tara-rts-pilot-v1",
        description="Salt mixed into the deterministic, per-query hash-based split assignment (see splitter.py). "
        "Changing this reshuffles every query's split assignment; keep it fixed across a pilot's lifetime "
        "for a stable, reproducible split.",
    )

    train_parquet_filename: str = Field(default="train.parquet")
    validation_parquet_filename: str = Field(default="validation.parquet")
    test_parquet_filename: str = Field(default="test.parquet")
    train_jsonl_filename: str = Field(default="train.jsonl")
    validation_jsonl_filename: str = Field(default="validation.jsonl")
    test_jsonl_filename: str = Field(default="test.jsonl")

    dataset_statistics_filename: str = Field(default="dataset_statistics.json")
    feature_statistics_filename: str = Field(default="feature_statistics.csv")
    validation_report_filename: str = Field(default="validation_report.md")
    dataset_readme_filename: str = Field(default="README.md")
    dataset_card_filename: str = Field(default="DATASET_CARD.md")

    expected_strategy_count: int = Field(
        default=4, gt=0,
        description="How many strategy rows every query must have for the "
        "'every query has exactly four strategy rows' Success Criterion. 4 because Retrieval "
        "Executor (frozen) always runs exactly Lexical/Dense/Graph/Hybrid.",
    )
    histogram_bin_count: int = Field(default=10, gt=0, description="Bin count for the utility/latency/quality distribution histograms.")
    fail_on_validation_error: bool = Field(
        default=True,
        description="If True (default), PilotRunner.run raises PilotValidationError when any blocking "
        "Success Criterion fails, and does not proceed to write split files/figures/docs over "
        "known-bad data. If False, the run proceeds anyway and the failure is only visible in "
        "validation_report.md's checks -- useful for inspecting a failing pilot's data during debugging.",
    )

    figure_dpi: int = Field(default=150, gt=0, description="Resolution (dots per inch) figures are rendered at.")

    @model_validator(mode="after")
    def _ratios_sum_to_one(self) -> "PilotSettings":
        total = self.train_ratio + self.validation_ratio + self.test_ratio
        if not math.isclose(total, 1.0, abs_tol=_RATIO_SUM_TOLERANCE):
            raise ValueError(f"train_ratio + validation_ratio + test_ratio must sum to 1.0, got {total!r}.")
        return self
