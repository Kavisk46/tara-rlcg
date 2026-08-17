"""Unit tests for `evaluation.harness.runner.ExperimentRunner`.

Every test uses `FakeCodeGenerator` (no network call) and synthetic
`_FakeRetriever`s (no real repository) -- no real experiment is run.
"""
from __future__ import annotations

from pathlib import Path

from evaluation.harness.models import (
    ExperimentConfig,
    GroundTruth,
    QuerySpec,
    Variant,
    tara_variant,
)
from evaluation.harness.runner import (
    ExperimentRunner,
    read_config_json,
    read_results_jsonl,
    write_config_json,
    write_results_jsonl,
)
from evaluation.harness.tests.conftest import _BrokenRetriever, make_orchestrator
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import Language, RetrieverKind, TaskType
from tara.generation.fake_provider import FakeCodeGenerator
from tara.retrieval.orchestrator import RetrievalOrchestrator
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import RoutingStrategy

_ALL_KINDS = (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)


def _make_query(
    query_id: str,
    context: RepositoryContext,
    classification: TaskClassification,
    ground_truth: GroundTruth | None = None,
) -> QuerySpec:
    return QuerySpec(
        query_id=query_id,
        repository_id="repo-a",
        query_text="how does greet work?",
        task_type=TaskType.SEARCH,
        classification=classification,
        context=context,
        ground_truth=ground_truth,
    )


# ============================================================================
# End-to-end: TARA variant
# ============================================================================


def test_run_query_tara_variant_end_to_end(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator(response_text="ok", model="fake-model")
    runner = ExperimentRunner(orchestrator, generator)
    query = _make_query("q-1", rich_context, search_classification)

    result = runner.run_query(tara_variant(), query)

    assert result.error is None
    assert result.variant_id == "TARA"
    assert result.plan_strategy is not None
    assert result.efficiency.routing_latency_ms is not None
    assert result.efficiency.retrieval_latency_ms is not None
    assert result.efficiency.fusion_latency_ms is not None
    assert result.efficiency.generation_latency_ms >= 0.0
    assert result.efficiency.total_latency_ms >= 0.0
    assert result.generated_text == "ok"


def test_run_query_tara_variant_uses_default_policies_not_fixed(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    # Sanity: tara_variant() genuinely uses AdaptiveRouter's real policy chain.
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator)
    query = _make_query("q-1", rich_context, search_classification)

    result = runner.run_query(tara_variant(), query)

    reference_router = AdaptiveRouter()
    reference_plan = reference_router.route(search_classification, rich_context)
    assert result.plan_strategy == reference_plan.strategy.value


# ============================================================================
# No-retrieval variant (B0-equivalent)
# ============================================================================


def test_run_query_no_strategy_skips_retrieval(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator(response_text="ok")
    runner = ExperimentRunner(orchestrator, generator)
    no_retrieval_variant = Variant(variant_id="B0")
    query = _make_query("q-1", rich_context, search_classification)

    result = runner.run_query(no_retrieval_variant, query)

    assert result.error is None
    assert result.plan_strategy is None
    assert result.plan_retrievers == []
    assert result.efficiency.routing_latency_ms is None
    assert result.efficiency.retrieval_latency_ms is None
    assert result.efficiency.fusion_latency_ms is None
    assert result.efficiency.retriever_invocation_count == 0
    assert all(fake.call_count == 0 for fake in fakes.values())


# ============================================================================
# Retrieval metrics
# ============================================================================


def test_run_query_computes_retrieval_metrics_when_ground_truth_present(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(RetrieverKind.LEXICAL)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator, k_values=(1, 5))
    variant = Variant(variant_id="lexical-only", strategy=RoutingStrategy.LEXICAL_ONLY)
    ground_truth = GroundTruth(
        query_id="q-1", relevant_node_ids={"file::app.py::lexical_symbol::1"}
    )
    query = _make_query("q-1", rich_context, search_classification, ground_truth)

    result = runner.run_query(variant, query)

    assert result.error is None
    assert result.retrieval_metrics is not None
    assert result.retrieval_metrics.precision_at_k[1] == 1.0
    assert result.retrieval_metrics.recall_at_k[1] == 1.0
    assert result.retrieval_metrics.reciprocal_rank == 1.0
    assert result.retrieval_metrics.plan_coverage == 1.0


def test_run_query_retrieval_metrics_none_without_ground_truth(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator)
    query = _make_query("q-1", rich_context, search_classification, ground_truth=None)

    result = runner.run_query(tara_variant(), query)

    assert result.retrieval_metrics is None


def test_run_query_retrieval_metrics_none_when_ground_truth_has_no_relevant_ids(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator)
    ground_truth = GroundTruth(query_id="q-1", relevant_node_ids=None)
    query = _make_query("q-1", rich_context, search_classification, ground_truth)

    result = runner.run_query(tara_variant(), query)

    assert result.retrieval_metrics is None


# ============================================================================
# Generation metrics
# ============================================================================


def test_run_query_computes_generation_metrics_with_reference_and_language(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator(response_text="def f(): return 1")
    runner = ExperimentRunner(orchestrator, generator)
    ground_truth = GroundTruth(
        query_id="q-1", reference_text="def f(): return 1", language=Language.PYTHON
    )
    query = _make_query("q-1", rich_context, search_classification, ground_truth)

    result = runner.run_query(tara_variant(), query)

    assert result.generation_metrics is not None
    assert result.generation_metrics.exact_match is True
    assert result.generation_metrics.edit_similarity == 1.0
    assert result.generation_metrics.syntactic_validity is True


def test_run_query_generation_metrics_none_without_ground_truth(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator)
    query = _make_query("q-1", rich_context, search_classification, ground_truth=None)

    result = runner.run_query(tara_variant(), query)

    assert result.generation_metrics is None


# ============================================================================
# Error isolation
# ============================================================================


def test_run_query_isolates_a_generation_failure(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    # RetrievalOrchestrator already isolates a single retriever's own failure internally (skips
    # it, logs a warning -- established M6 behavior), so it cannot demonstrate this runner's own
    # error isolation. A CodeGenerator failure, by contrast, is not caught by any lower layer --
    # exactly what ExperimentRunner.run_query's own try/except must catch.
    from tara.core.exceptions import CodeGenerationError

    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator(raises=CodeGenerationError("simulated generation failure"))
    runner = ExperimentRunner(orchestrator, generator)
    query = _make_query("q-1", rich_context, search_classification)

    result = runner.run_query(tara_variant(), query)

    assert result.error is not None
    assert "simulated generation failure" in result.error
    assert result.generated_text == ""
    assert result.efficiency.total_latency_ms >= 0.0


def test_run_query_broken_single_retriever_does_not_error_the_query(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    # The orchestrator's own established skip-and-log behavior: a broken retriever degrades the
    # result (empty FusedContext), it does not raise up to the harness.
    broken_orchestrator = RetrievalOrchestrator({RetrieverKind.LEXICAL: _BrokenRetriever()})
    generator = FakeCodeGenerator(response_text="ok")
    runner = ExperimentRunner(broken_orchestrator, generator)
    variant = Variant(variant_id="lexical-only", strategy=RoutingStrategy.LEXICAL_ONLY)
    query = _make_query("q-1", rich_context, search_classification)

    result = runner.run_query(variant, query)

    assert result.error is None
    assert result.generated_text == "ok"
    assert result.efficiency.retriever_invocation_count == 1


# ============================================================================
# run_batch
# ============================================================================


def test_run_batch_order_is_outer_queries_inner_variants(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator)
    variants = [tara_variant(), Variant(variant_id="B0")]
    queries = [
        _make_query("q-1", rich_context, search_classification),
        _make_query("q-2", rich_context, search_classification),
    ]

    results = runner.run_batch(variants, queries)

    assert [(r.query_id, r.variant_id) for r in results] == [
        ("q-1", "TARA"),
        ("q-1", "B0"),
        ("q-2", "TARA"),
        ("q-2", "B0"),
    ]


# ============================================================================
# JSONL / config round trip
# ============================================================================


def test_results_jsonl_round_trip(
    tmp_path: Path, rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    generator = FakeCodeGenerator()
    runner = ExperimentRunner(orchestrator, generator, k_values=(5,))
    ground_truth = GroundTruth(
        query_id="q-1", relevant_node_ids={"file::app.py::lexical_symbol::1"}
    )
    query = _make_query("q-1", rich_context, search_classification, ground_truth)
    results = [runner.run_query(tara_variant(), query)]

    path = tmp_path / "results.jsonl"
    write_results_jsonl(results, path)
    loaded = read_results_jsonl(path)

    assert loaded == results


def test_config_json_round_trip(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    config = ExperimentConfig(
        experiment_id="exp-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        variant_ids=["TARA", "B0", "B1"],
        generation_model="fake-model",
        token_budget=4000,
        prompt_template="baseline",
        k_values=[5, 10],
    )
    path = tmp_path / "config.json"
    write_config_json(config, path)
    loaded = read_config_json(path)

    assert loaded == config
