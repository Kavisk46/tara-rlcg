"""Unit tests for `evaluation.harness.models`."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from evaluation.baselines.definitions import (
    BASELINE_DEFINITIONS as _BASELINE_DEFINITIONS,
)
from evaluation.baselines.definitions import BaselineId
from evaluation.harness.models import (
    TARA_VARIANT_ID,
    EfficiencyResult,
    ExperimentConfig,
    QueryRunResult,
    tara_variant,
    variant_from_baseline,
)


def test_tara_variant_id_is_reserved_constant() -> None:
    assert tara_variant().variant_id == TARA_VARIANT_ID


def test_tara_variant_id_is_not_a_baseline_id() -> None:
    baseline_ids = {b.value for b in BaselineId}
    assert TARA_VARIANT_ID not in baseline_ids


def test_tara_variant_is_adaptive_with_no_fixed_strategy() -> None:
    variant = tara_variant()
    assert variant.is_adaptive is True
    assert variant.strategy is None


def test_variant_from_baseline_preserves_id_and_strategy() -> None:
    b1 = next(b for b in _BASELINE_DEFINITIONS if b.baseline_id is BaselineId.B1)
    variant = variant_from_baseline(b1)
    assert variant.variant_id == "B1"
    assert variant.strategy is b1.strategy
    assert variant.is_adaptive is False


def test_variant_from_baseline_b0_has_no_strategy() -> None:
    b0 = next(b for b in _BASELINE_DEFINITIONS if b.baseline_id is BaselineId.B0)
    variant = variant_from_baseline(b0)
    assert variant.strategy is None
    assert variant.is_adaptive is False


def test_experiment_config_round_trips() -> None:
    config = ExperimentConfig(
        experiment_id="exp-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        variant_ids=["TARA", "B0"],
        generation_model="fake-model",
        token_budget=1000,
        embedding_model_name="fake-embedding-model",
        prompt_template="baseline",
        k_values=[5],
    )
    assert config.experiment_id == "exp-1"


def test_experiment_config_rejects_zero_token_budget() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_id="exp-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            variant_ids=["TARA"],
            generation_model="fake-model",
            token_budget=0,
            embedding_model_name="fake-embedding-model",
            prompt_template="baseline",
            k_values=[5],
        )


def test_experiment_config_rejects_empty_k_values() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_id="exp-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            variant_ids=["TARA"],
            generation_model="fake-model",
            token_budget=1000,
            embedding_model_name="fake-embedding-model",
            prompt_template="baseline",
            k_values=[],
        )


def test_experiment_config_rejects_empty_embedding_model_name() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            experiment_id="exp-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            variant_ids=["TARA"],
            generation_model="fake-model",
            token_budget=1000,
            embedding_model_name="",
            prompt_template="baseline",
            k_values=[5],
        )


def test_query_run_result_requires_efficiency() -> None:
    with pytest.raises(ValidationError):
        QueryRunResult(variant_id="TARA", query_id="q-1", repository_id="repo-a")  # type: ignore[call-arg]


def test_efficiency_result_rejects_negative_token_count() -> None:
    with pytest.raises(ValidationError):
        EfficiencyResult(
            generation_latency_ms=1.0,
            total_latency_ms=1.0,
            retriever_invocation_count=0,
            embedding_call_count=0,
            retrieved_token_count=-1,
        )
