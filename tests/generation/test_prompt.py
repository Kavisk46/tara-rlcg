"""Unit tests for `tara.generation.prompt.PromptBuilder`.

Exercises prompt assembly in isolation: no `CodeGenerator`, no
`CodeGenerationService`, no network call.
"""
from __future__ import annotations

from tara.generation.prompt import PromptBuilder, PromptTemplate
from tests.generation.conftest import make_fused_chunk, make_fused_context, make_task_classification

# ============================================================================
# Query and empty context
# ============================================================================


def test_build_includes_query() -> None:
    prompt = PromptBuilder().build("how does greet work?", make_fused_context(chunks=[]))
    assert "how does greet work?" in prompt.user


def test_build_empty_context_says_so_explicitly() -> None:
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[]))
    assert "No repository context" in prompt.user


def test_build_system_message_is_non_empty() -> None:
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[]))
    assert prompt.system


# ============================================================================
# Chunk provenance and content
# ============================================================================


def test_build_includes_chunk_provenance_and_content() -> None:
    chunk = make_fused_chunk(
        chunk_id="a", name="greet", file_path="app.py", start_line=5, end_line=10
    )
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[chunk]))
    assert "greet" in prompt.user
    assert "app.py:5-10" in prompt.user
    assert "def greet(): ..." in prompt.user


def test_build_omits_line_range_when_missing() -> None:
    chunk = make_fused_chunk(chunk_id="a", file_path="app.py", start_line=None, end_line=None)
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[chunk]))
    assert "app.py:" not in prompt.user
    assert "app.py" in prompt.user


def test_build_includes_docstring_when_present() -> None:
    chunk = make_fused_chunk(chunk_id="a", docstring="Return a friendly greeting.")
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[chunk]))
    assert "Return a friendly greeting." in prompt.user


def test_build_omits_docstring_section_when_absent() -> None:
    chunk = make_fused_chunk(chunk_id="a", docstring=None, content="def greet(): ...")
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[chunk]))
    # No stray "None" leaking into the prompt from an unset docstring.
    assert "None" not in prompt.user


def test_build_multiple_chunks_all_included() -> None:
    first = make_fused_chunk(chunk_id="a", name="greet", file_path="app.py")
    second = make_fused_chunk(chunk_id="b", name="parse_repository", file_path="utils.py")
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[first, second]))
    assert "greet" in prompt.user
    assert "parse_repository" in prompt.user
    assert "utils.py" in prompt.user


def test_build_preserves_chunk_order() -> None:
    first = make_fused_chunk(chunk_id="a", name="alpha_symbol")
    second = make_fused_chunk(chunk_id="b", name="beta_symbol")
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[first, second]))
    assert prompt.user.index("alpha_symbol") < prompt.user.index("beta_symbol")


# ============================================================================
# Truncation footnote
# ============================================================================


def test_build_notes_truncation_when_flagged() -> None:
    chunk = make_fused_chunk(chunk_id="a")
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[chunk], truncated=True))
    assert "omitted" in prompt.user.lower()


def test_build_does_not_mention_truncation_when_not_truncated() -> None:
    chunk = make_fused_chunk(chunk_id="a")
    prompt = PromptBuilder().build("q", make_fused_context(chunks=[chunk], truncated=False))
    assert "omitted" not in prompt.user.lower()


# ============================================================================
# PromptTemplate: baseline vs. with_task_classification (ablation lever A9)
# ============================================================================


def test_baseline_template_ignores_task_classification() -> None:
    builder = PromptBuilder(template=PromptTemplate.BASELINE)
    classification = make_task_classification()
    prompt = builder.build("q", make_fused_context(chunks=[]), classification)
    assert "Task Classification" not in prompt.user


def test_with_task_classification_template_includes_it() -> None:
    builder = PromptBuilder(template=PromptTemplate.WITH_TASK_CLASSIFICATION)
    classification = make_task_classification()
    prompt = builder.build("q", make_fused_context(chunks=[]), classification)
    assert "Task Classification" in prompt.user
    assert classification.task_type.value in prompt.user
    assert classification.retriever_kind.value in prompt.user


def test_with_task_classification_template_without_classification_is_not_an_error() -> None:
    builder = PromptBuilder(template=PromptTemplate.WITH_TASK_CLASSIFICATION)
    prompt = builder.build("q", make_fused_context(chunks=[]), None)
    assert "Task Classification" not in prompt.user


def test_default_template_is_baseline() -> None:
    builder = PromptBuilder()
    classification = make_task_classification()
    prompt = builder.build("q", make_fused_context(chunks=[]), classification)
    assert "Task Classification" not in prompt.user


# ============================================================================
# Determinism
# ============================================================================


def test_build_is_deterministic_across_repeated_calls() -> None:
    chunk = make_fused_chunk(chunk_id="a")
    context = make_fused_context(chunks=[chunk])
    builder = PromptBuilder()

    first = builder.build("q", context)
    second = builder.build("q", context)

    assert first == second


def test_system_message_is_stable_across_templates() -> None:
    baseline = PromptBuilder(template=PromptTemplate.BASELINE).build(
        "q", make_fused_context(chunks=[])
    )
    with_classification = PromptBuilder(template=PromptTemplate.WITH_TASK_CLASSIFICATION).build(
        "q", make_fused_context(chunks=[])
    )
    assert baseline.system == with_classification.system
