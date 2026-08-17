"""Unit tests for `tara.generation.service.CodeGenerationService`.

The top-level (query, FusedContext, TaskClassification) -> GeneratedCode
entry point. Every test here uses `FakeCodeGenerator`; none makes a
network call.
"""
from __future__ import annotations

import pytest

from tara.core.exceptions import CodeGenerationError
from tara.generation.fake_provider import FakeCodeGenerator
from tara.generation.prompt import PromptBuilder, PromptTemplate
from tara.generation.service import CodeGenerationService
from tests.generation.conftest import make_fused_chunk, make_fused_context, make_task_classification


def test_generate_calls_provider_with_built_prompt() -> None:
    generator = FakeCodeGenerator(response_text="ok")
    service = CodeGenerationService(generator)

    result = service.generate("how does greet work?", make_fused_context(chunks=[]))

    assert result.text == "ok"
    assert generator.call_count == 1
    assert generator.last_prompt is not None
    assert "how does greet work?" in generator.last_prompt.user


def test_generate_returns_the_providers_generated_code() -> None:
    generator = FakeCodeGenerator(response_text="hello", model="fake-model", latency_ms=3.0)
    service = CodeGenerationService(generator)

    result = service.generate("q", make_fused_context(chunks=[]))

    assert result.text == "hello"
    assert result.model == "fake-model"
    assert result.latency_ms == 3.0


def test_generate_with_default_prompt_builder_uses_baseline_template() -> None:
    generator = FakeCodeGenerator()
    service = CodeGenerationService(generator)
    classification = make_task_classification()

    service.generate("q", make_fused_context(chunks=[]), classification)

    assert generator.last_prompt is not None
    assert "Task Classification" not in generator.last_prompt.user


def test_generate_with_task_classification_template_surfaces_it() -> None:
    generator = FakeCodeGenerator()
    builder = PromptBuilder(template=PromptTemplate.WITH_TASK_CLASSIFICATION)
    service = CodeGenerationService(generator, prompt_builder=builder)
    classification = make_task_classification()

    service.generate("q", make_fused_context(chunks=[]), classification)

    assert generator.last_prompt is not None
    assert "Task Classification" in generator.last_prompt.user


def test_generate_includes_fused_context_chunks_in_prompt() -> None:
    generator = FakeCodeGenerator()
    service = CodeGenerationService(generator)
    chunk = make_fused_chunk(chunk_id="a", name="greet")

    service.generate("q", make_fused_context(chunks=[chunk]))

    assert generator.last_prompt is not None
    assert "greet" in generator.last_prompt.user


def test_generate_with_empty_fused_context_still_calls_provider() -> None:
    generator = FakeCodeGenerator()
    service = CodeGenerationService(generator)

    result = service.generate("q", make_fused_context(chunks=[]))

    assert generator.call_count == 1
    assert result.text


def test_generate_propagates_provider_errors() -> None:
    generator = FakeCodeGenerator(raises=CodeGenerationError("provider down"))
    service = CodeGenerationService(generator)

    with pytest.raises(CodeGenerationError, match="provider down"):
        service.generate("q", make_fused_context(chunks=[]))


def test_generate_runs_entirely_without_network() -> None:
    service = CodeGenerationService(FakeCodeGenerator())
    result = service.generate("q", make_fused_context(chunks=[]))
    assert result.text


def test_generate_is_deterministic_across_repeated_calls() -> None:
    fake_generator = FakeCodeGenerator(
        response_text="fixed", latency_ms=1.0, prompt_tokens=1, completion_tokens=1
    )
    service = CodeGenerationService(fake_generator)
    context = make_fused_context(chunks=[make_fused_chunk(chunk_id="a")])

    first = service.generate("q", context)
    second = service.generate("q", context)

    assert first == second


def test_generate_does_not_mutate_fused_context() -> None:
    generator = FakeCodeGenerator()
    service = CodeGenerationService(generator)
    context = make_fused_context(chunks=[make_fused_chunk(chunk_id="a")])
    snapshot = context.model_copy(deep=True)

    service.generate("q", context)

    assert context == snapshot
