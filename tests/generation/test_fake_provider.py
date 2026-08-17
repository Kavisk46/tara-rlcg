"""Unit tests for `tara.generation.fake_provider.FakeCodeGenerator`.

Every test in this module -- and every test in this package -- runs
entirely without any external LLM or network call. That is the whole
point of `FakeCodeGenerator`.
"""
from __future__ import annotations

import pytest

from tara.core.exceptions import CodeGenerationError
from tara.generation.fake_provider import FakeCodeGenerator
from tara.generation.models import Prompt

_PROMPT = Prompt(system="be helpful", user="what does greet do?")


# ============================================================================
# Response text
# ============================================================================


def test_generate_returns_default_text_when_unconfigured() -> None:
    result = FakeCodeGenerator().generate(_PROMPT)
    assert result.text
    assert result.model == "fake-model"


def test_generate_returns_fixed_response_text() -> None:
    result = FakeCodeGenerator(response_text="def greet(): ...").generate(_PROMPT)
    assert result.text == "def greet(): ..."


def test_generate_returns_callable_derived_response_text() -> None:
    generator = FakeCodeGenerator(response_text=lambda prompt: f"echo: {prompt.user}")
    result = generator.generate(_PROMPT)
    assert result.text == "echo: what does greet do?"


def test_generate_reports_configured_model() -> None:
    result = FakeCodeGenerator(model="my-test-model").generate(_PROMPT)
    assert result.model == "my-test-model"


# ============================================================================
# Token counts
# ============================================================================


def test_generate_estimates_token_counts_by_default() -> None:
    result = FakeCodeGenerator().generate(_PROMPT)
    assert result.prompt_tokens is not None
    assert result.prompt_tokens > 0
    assert result.completion_tokens is not None
    assert result.completion_tokens > 0


def test_generate_respects_explicit_token_counts() -> None:
    result = FakeCodeGenerator(prompt_tokens=10, completion_tokens=20).generate(_PROMPT)
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20


def test_generate_reports_none_token_counts_when_estimation_disabled() -> None:
    result = FakeCodeGenerator(estimate_tokens=False).generate(_PROMPT)
    assert result.prompt_tokens is None
    assert result.completion_tokens is None


def test_generate_explicit_token_count_wins_over_disabled_estimation() -> None:
    result = FakeCodeGenerator(prompt_tokens=7, estimate_tokens=False).generate(_PROMPT)
    assert result.prompt_tokens == 7
    assert result.completion_tokens is None


# ============================================================================
# Latency
# ============================================================================


def test_generate_reports_configured_latency() -> None:
    result = FakeCodeGenerator(latency_ms=42.0).generate(_PROMPT)
    assert result.latency_ms == 42.0


def test_generate_latency_defaults_to_zero() -> None:
    result = FakeCodeGenerator().generate(_PROMPT)
    assert result.latency_ms == 0.0


# ============================================================================
# Metadata
# ============================================================================


def test_generate_metadata_defaults_to_provider_fake() -> None:
    result = FakeCodeGenerator().generate(_PROMPT)
    assert result.metadata == {"provider": "fake"}


def test_generate_respects_explicit_metadata() -> None:
    result = FakeCodeGenerator(metadata={"provider": "fake", "note": "custom"}).generate(_PROMPT)
    assert result.metadata == {"provider": "fake", "note": "custom"}


# ============================================================================
# Call tracking
# ============================================================================


def test_generate_tracks_call_count_and_last_prompt() -> None:
    generator = FakeCodeGenerator()
    assert generator.call_count == 0
    assert generator.last_prompt is None

    generator.generate(_PROMPT)
    assert generator.call_count == 1
    assert generator.last_prompt == _PROMPT

    generator.generate(_PROMPT)
    assert generator.call_count == 2


# ============================================================================
# Failure path
# ============================================================================


def test_generate_raises_configured_exception() -> None:
    generator = FakeCodeGenerator(raises=CodeGenerationError("boom"))
    with pytest.raises(CodeGenerationError, match="boom"):
        generator.generate(_PROMPT)


def test_generate_raising_still_records_call_count_and_last_prompt() -> None:
    generator = FakeCodeGenerator(raises=CodeGenerationError("boom"))
    with pytest.raises(CodeGenerationError):
        generator.generate(_PROMPT)
    assert generator.call_count == 1
    assert generator.last_prompt == _PROMPT


# ============================================================================
# Determinism
# ============================================================================


def test_generate_is_deterministic_across_repeated_calls() -> None:
    generator = FakeCodeGenerator(
        response_text="fixed", prompt_tokens=5, completion_tokens=5, latency_ms=1.0
    )
    first = generator.generate(_PROMPT)
    second = generator.generate(_PROMPT)
    assert first == second
