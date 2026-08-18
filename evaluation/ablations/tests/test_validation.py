"""Unit tests for `evaluation.ablations.validation.validate_controlled_variables`."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from evaluation.ablations.validation import (
    ControlledVariableMismatchError,
    validate_controlled_variables,
)
from evaluation.harness.models import ExperimentConfig


def _make_config(**overrides: object) -> ExperimentConfig:
    defaults: dict[str, object] = dict(
        experiment_id="exp-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        variant_ids=["TARA"],
        generation_model="fake-model",
        token_budget=4000,
        embedding_model_name="BAAI/bge-small-en-v1.5",
        prompt_template="baseline",
        k_values=[5, 10],
        repository_manifest_path="manifest.json",
        queries_path="queries.jsonl",
    )
    defaults.update(overrides)
    return ExperimentConfig(**defaults)  # type: ignore[arg-type]


# ============================================================================
# Passing cases
# ============================================================================


def test_single_config_always_passes() -> None:
    validate_controlled_variables([_make_config()])


def test_empty_list_passes() -> None:
    validate_controlled_variables([])


def test_identical_configs_pass() -> None:
    validate_controlled_variables(
        [_make_config(experiment_id="exp-1"), _make_config(experiment_id="exp-2")]
    )


def test_configs_differing_only_in_uncontrolled_fields_pass() -> None:
    # variant_ids, prompt_template, k_values, notes are not controlled fields.
    a = _make_config(experiment_id="exp-1", variant_ids=["TARA"], prompt_template="baseline")
    b = _make_config(
        experiment_id="exp-2",
        variant_ids=["A2-no-refactor-override"],
        prompt_template="with_task_classification",
    )
    validate_controlled_variables([a, b])


# ============================================================================
# Failing cases
# ============================================================================


def test_different_repository_manifest_raises() -> None:
    a = _make_config(experiment_id="exp-1", repository_manifest_path="manifest_a.json")
    b = _make_config(experiment_id="exp-2", repository_manifest_path="manifest_b.json")
    with pytest.raises(ControlledVariableMismatchError, match="repository_manifest_path"):
        validate_controlled_variables([a, b])


def test_different_queries_path_raises() -> None:
    a = _make_config(experiment_id="exp-1", queries_path="queries_a.jsonl")
    b = _make_config(experiment_id="exp-2", queries_path="queries_b.jsonl")
    with pytest.raises(ControlledVariableMismatchError, match="queries_path"):
        validate_controlled_variables([a, b])


def test_different_generation_model_raises() -> None:
    a = _make_config(experiment_id="exp-1", generation_model="model-a")
    b = _make_config(experiment_id="exp-2", generation_model="model-b")
    with pytest.raises(ControlledVariableMismatchError, match="generation_model"):
        validate_controlled_variables([a, b])


def test_different_token_budget_raises() -> None:
    a = _make_config(experiment_id="exp-1", token_budget=4000)
    b = _make_config(experiment_id="exp-2", token_budget=8000)
    with pytest.raises(ControlledVariableMismatchError, match="token_budget"):
        validate_controlled_variables([a, b])


def test_different_embedding_model_raises_by_default() -> None:
    a = _make_config(experiment_id="exp-1", embedding_model_name="model-a")
    b = _make_config(experiment_id="exp-2", embedding_model_name="model-b")
    with pytest.raises(ControlledVariableMismatchError, match="embedding_model_name"):
        validate_controlled_variables([a, b])


def test_error_message_names_every_offending_experiment_id() -> None:
    a = _make_config(experiment_id="exp-a", generation_model="model-a")
    b = _make_config(experiment_id="exp-b", generation_model="model-b")
    with pytest.raises(ControlledVariableMismatchError) as excinfo:
        validate_controlled_variables([a, b])
    assert "exp-a" in str(excinfo.value)
    assert "exp-b" in str(excinfo.value)


def test_multiple_mismatched_fields_are_all_reported() -> None:
    a = _make_config(experiment_id="exp-1", generation_model="model-a", token_budget=4000)
    b = _make_config(experiment_id="exp-2", generation_model="model-b", token_budget=8000)
    with pytest.raises(ControlledVariableMismatchError) as excinfo:
        validate_controlled_variables([a, b])
    assert "generation_model" in str(excinfo.value)
    assert "token_budget" in str(excinfo.value)


def test_third_config_matching_neither_still_flags_mismatch() -> None:
    a = _make_config(experiment_id="exp-1", token_budget=4000)
    b = _make_config(experiment_id="exp-2", token_budget=4000)
    c = _make_config(experiment_id="exp-3", token_budget=9000)
    with pytest.raises(ControlledVariableMismatchError, match="token_budget"):
        validate_controlled_variables([a, b, c])


# ============================================================================
# allowed_to_vary (the A8 exemption path)
# ============================================================================


def test_embedding_model_mismatch_passes_when_explicitly_allowed() -> None:
    a = _make_config(experiment_id="exp-1", embedding_model_name="model-a")
    b = _make_config(experiment_id="exp-2", embedding_model_name="model-b")
    validate_controlled_variables([a, b], allowed_to_vary=("embedding_model_name",))


def test_allowing_one_field_does_not_exempt_another() -> None:
    a = _make_config(
        experiment_id="exp-1", embedding_model_name="model-a", generation_model="gen-a"
    )
    b = _make_config(
        experiment_id="exp-2", embedding_model_name="model-b", generation_model="gen-b"
    )
    with pytest.raises(ControlledVariableMismatchError, match="generation_model"):
        validate_controlled_variables([a, b], allowed_to_vary=("embedding_model_name",))


def test_allowed_to_vary_with_an_unknown_field_name_is_harmless() -> None:
    a = _make_config(experiment_id="exp-1")
    b = _make_config(experiment_id="exp-2")
    validate_controlled_variables([a, b], allowed_to_vary=("not_a_real_field",))
