"""Unit tests for `evaluation.rts_builder.oracle_utility.config.OracleUtilitySettings`."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings


def test_default_settings_construct_without_error() -> None:
    settings = OracleUtilitySettings()
    assert settings.quality_metrics_k > 0
    assert settings.utility_latency_weight == pytest.approx(0.1)


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        OracleUtilitySettings(
            quality_recall_weight=0.5, quality_mrr_weight=0.5, quality_ndcg_weight=0.5, quality_context_precision_weight=0.5
        )


def test_valid_custom_quality_weights_are_accepted() -> None:
    settings = OracleUtilitySettings(
        quality_recall_weight=0.4, quality_mrr_weight=0.3, quality_ndcg_weight=0.2, quality_context_precision_weight=0.1
    )
    assert settings.quality_recall_weight == 0.4


def test_utility_quality_weight_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        OracleUtilitySettings(utility_quality_weight=0.0)


def test_utility_latency_weight_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        OracleUtilitySettings(utility_latency_weight=-0.1)


def test_utility_weights_are_not_required_to_sum_to_one() -> None:
    # Utility = alpha*Q - beta*L is a trade-off formula, not a convex combination -- unlike the
    # quality_*_weight group, alpha and beta are independent and need not sum to 1.
    settings = OracleUtilitySettings(utility_quality_weight=2.0, utility_latency_weight=0.5)
    assert settings.utility_quality_weight == 2.0
    assert settings.utility_latency_weight == 0.5
