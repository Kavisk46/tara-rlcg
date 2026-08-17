"""Unit tests for `tara.generation.models`.

Covers `Prompt` and `GeneratedCode`: field constraints only. No
`PromptBuilder`, `CodeGenerator`, or network call is involved -- these
are pure data-contract tests.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tara.generation.models import GeneratedCode, Prompt

# ============================================================================
# Prompt
# ============================================================================


def test_prompt_round_trips_fields() -> None:
    prompt = Prompt(system="be helpful", user="do the thing")
    assert prompt.system == "be helpful"
    assert prompt.user == "do the thing"


def test_prompt_rejects_empty_user() -> None:
    with pytest.raises(ValidationError):
        Prompt(system="be helpful", user="")


def test_prompt_accepts_empty_system() -> None:
    # system is not required to be non-empty -- a provider with no system-role
    # concept could reasonably be handed an empty string.
    prompt = Prompt(system="", user="query")
    assert prompt.system == ""


def test_prompt_equality_compares_by_value() -> None:
    assert Prompt(system="s", user="u") == Prompt(system="s", user="u")


# ============================================================================
# GeneratedCode
# ============================================================================


def test_generated_code_round_trips_fields() -> None:
    result = GeneratedCode(text="print('hi')", model="fake-model", latency_ms=1.5)
    assert result.text == "print('hi')"
    assert result.model == "fake-model"
    assert result.latency_ms == 1.5


def test_generated_code_allows_empty_text() -> None:
    result = GeneratedCode(text="", model="fake-model", latency_ms=0.0)
    assert result.text == ""


def test_generated_code_rejects_empty_model() -> None:
    with pytest.raises(ValidationError):
        GeneratedCode(text="x", model="", latency_ms=0.0)


def test_generated_code_token_counts_default_to_none() -> None:
    result = GeneratedCode(text="x", model="m", latency_ms=0.0)
    assert result.prompt_tokens is None
    assert result.completion_tokens is None


def test_generated_code_accepts_explicit_token_counts() -> None:
    result = GeneratedCode(
        text="x", model="m", latency_ms=0.0, prompt_tokens=10, completion_tokens=20
    )
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20


def test_generated_code_rejects_negative_prompt_tokens() -> None:
    with pytest.raises(ValidationError):
        GeneratedCode(text="x", model="m", latency_ms=0.0, prompt_tokens=-1)


def test_generated_code_rejects_negative_completion_tokens() -> None:
    with pytest.raises(ValidationError):
        GeneratedCode(text="x", model="m", latency_ms=0.0, completion_tokens=-1)


def test_generated_code_rejects_negative_latency() -> None:
    with pytest.raises(ValidationError):
        GeneratedCode(text="x", model="m", latency_ms=-0.1)


def test_generated_code_accepts_zero_latency() -> None:
    result = GeneratedCode(text="x", model="m", latency_ms=0.0)
    assert result.latency_ms == 0.0


def test_generated_code_metadata_defaults_to_empty_dict() -> None:
    result = GeneratedCode(text="x", model="m", latency_ms=0.0)
    assert result.metadata == {}


def test_generated_code_preserves_arbitrary_metadata() -> None:
    result = GeneratedCode(
        text="x", model="m", latency_ms=0.0, metadata={"provider": "fake", "temperature": 0.0}
    )
    assert result.metadata == {"provider": "fake", "temperature": 0.0}
