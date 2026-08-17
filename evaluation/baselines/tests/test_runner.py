"""Unit tests for `evaluation.baselines.runner.BaselineRunner`.

Every test uses `FakeCodeGenerator` (no network call) and synthetic
`_FakeRetriever`s (no real repository) -- this milestone explicitly does
not run any real experiment.
"""
from __future__ import annotations

from evaluation.baselines.definitions import BASELINE_DEFINITIONS, BaselineDefinition, BaselineId
from evaluation.baselines.runner import BaselineRunner
from evaluation.baselines.tests.conftest import make_orchestrator
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.config import TaraSettings
from tara.core.types import RetrieverKind
from tara.generation.fake_provider import FakeCodeGenerator

_ALL_KINDS = (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)

# `rich_context`, `search_classification` are pytest fixtures auto-discovered from
# `evaluation/baselines/tests/conftest.py`.


def _definition(baseline_id: BaselineId) -> BaselineDefinition:
    return next(b for b in BASELINE_DEFINITIONS if b.baseline_id is baseline_id)


def _runner(token_budget: int = 10_000) -> tuple[BaselineRunner, FakeCodeGenerator]:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator(response_text="ok", model="fake-model")
    settings = TaraSettings(fusion_token_budget=token_budget)
    runner = BaselineRunner(orchestrator, generator, settings=settings)
    return runner, generator


# ============================================================================
# B0: no retrieval
# ============================================================================


def test_b0_run_produces_no_plan_and_empty_fused_context(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    runner, _generator = _runner()
    result = runner.run(
        _definition(BaselineId.B0), "how does greet work?", search_classification, rich_context
    )

    assert result.plan is None
    assert result.fused_context.chunks == []
    assert result.fused_context.candidate_count == 0


def test_b0_run_never_invokes_any_retriever(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = BaselineRunner(orchestrator, generator)

    runner.run(_definition(BaselineId.B0), "q", search_classification, rich_context)

    assert all(fake.call_count == 0 for fake in fakes.values())


def test_b0_run_still_calls_the_generator_with_no_context_note(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    runner, generator = _runner()
    result = runner.run(_definition(BaselineId.B0), "q", search_classification, rich_context)

    assert generator.call_count == 1
    assert generator.last_prompt is not None
    assert "No repository context" in generator.last_prompt.user
    assert result.generated_code.text == "ok"


# ============================================================================
# B1-B4: plan + retrieval + fusion + generation, end to end
# ============================================================================


def test_b1_run_invokes_only_dense_retriever(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = BaselineRunner(orchestrator, generator)

    result = runner.run(_definition(BaselineId.B1), "q", search_classification, rich_context)

    assert fakes[RetrieverKind.DENSE].call_count == 1
    assert fakes[RetrieverKind.LEXICAL].call_count == 0
    assert fakes[RetrieverKind.GRAPH].call_count == 0
    assert len(result.fused_context.chunks) == 1
    assert result.fused_context.chunks[0].found_by == (RetrieverKind.DENSE,)


def test_b2_run_invokes_only_lexical_retriever(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = BaselineRunner(orchestrator, generator)

    runner.run(_definition(BaselineId.B2), "q", search_classification, rich_context)

    assert fakes[RetrieverKind.LEXICAL].call_count == 1
    assert fakes[RetrieverKind.DENSE].call_count == 0
    assert fakes[RetrieverKind.GRAPH].call_count == 0


def test_b3_run_invokes_only_graph_retriever(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = BaselineRunner(orchestrator, generator)

    runner.run(_definition(BaselineId.B3), "q", search_classification, rich_context)

    assert fakes[RetrieverKind.GRAPH].call_count == 1
    assert fakes[RetrieverKind.LEXICAL].call_count == 0
    assert fakes[RetrieverKind.DENSE].call_count == 0


def test_b4_run_invokes_every_retriever(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = BaselineRunner(orchestrator, generator)

    result = runner.run(_definition(BaselineId.B4), "q", search_classification, rich_context)

    assert fakes[RetrieverKind.LEXICAL].call_count == 1
    assert fakes[RetrieverKind.DENSE].call_count == 1
    assert fakes[RetrieverKind.GRAPH].call_count == 1
    assert len(result.fused_context.chunks) == 3


# ============================================================================
# Common generation settings are preserved across every baseline
# ============================================================================


def test_every_baseline_uses_the_same_token_budget(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    runner, _generator = _runner(token_budget=4321)

    for baseline in BASELINE_DEFINITIONS:
        if baseline.baseline_id is BaselineId.B0:
            continue  # B0 never calls ContextFusion.fuse; no token_budget metadata to check
        result = runner.run(baseline, "q", search_classification, rich_context)
        assert result.fused_context.metadata["token_budget"] == 4321


def test_every_baseline_receives_the_identical_corpus_instance(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    """Fairness invariant: same repository corpus for every baseline. Proved by passing the
    exact same `RepositoryContext` object to every call and observing every fused chunk's
    file_path traces back to that one context's own graph (`app.py`, per `rich_context`)."""
    runner, _generator = _runner()

    for baseline in BASELINE_DEFINITIONS:
        result = runner.run(baseline, "q", search_classification, rich_context)
        for chunk in result.fused_context.chunks:
            assert chunk.file_path == "app.py"  # the only file rich_context defines


def test_every_baseline_receives_the_identical_query_text(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    """Fairness invariant: same query set for every baseline. Proved by passing the same query
    string to every baseline and observing it reflected in fused_context.query and, for the
    baselines that ran retrieval, in the generator's assembled prompt."""
    runner, generator = _runner()
    query = "how does the greet function work?"

    for baseline in BASELINE_DEFINITIONS:
        result = runner.run(baseline, query, search_classification, rich_context)
        assert result.fused_context.query == query
        assert generator.last_prompt is not None
        assert query in generator.last_prompt.user


def test_every_baseline_uses_the_same_code_generator_instance(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    runner, generator = _runner()

    for baseline in BASELINE_DEFINITIONS:
        runner.run(baseline, "q", search_classification, rich_context)

    assert generator.call_count == len(BASELINE_DEFINITIONS)


def test_every_baseline_uses_the_baseline_prompt_template_never_task_classification(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    runner, generator = _runner()

    for baseline in BASELINE_DEFINITIONS:
        runner.run(baseline, "q", search_classification, rich_context)
        assert generator.last_prompt is not None
        assert "Task Classification" not in generator.last_prompt.user


def test_every_baseline_reports_the_same_model_identifier(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    runner, _generator = _runner()

    reported_models = set()
    for baseline in BASELINE_DEFINITIONS:
        result = runner.run(baseline, "q", search_classification, rich_context)
        reported_models.add(result.generated_code.model)

    assert reported_models == {"fake-model"}


# ============================================================================
# build_plan: the smaller, directly-testable unit
# ============================================================================


def test_build_plan_matches_run_for_every_baseline(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = BaselineRunner(orchestrator, generator)

    for baseline in BASELINE_DEFINITIONS:
        plan_only = runner.build_plan(baseline, search_classification, rich_context)
        result = runner.run(baseline, "q", search_classification, rich_context)
        assert plan_only == result.plan
