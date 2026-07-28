"""Unit tests for `tara.routing.planner.RetrievalPlanner`."""
from __future__ import annotations

from collections.abc import Callable

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.routing.planner import RetrievalPlanner
from tara.routing.policies import RoutingDecision
from tara.routing.strategy import RoutingStrategy


def _decision(strategy: RoutingStrategy, retrievers: tuple[RetrieverKind, ...], policy_name: str = "test") -> RoutingDecision:
    return RoutingDecision(policy_name=policy_name, strategy=strategy, retrievers=retrievers, reason="test reason")


def test_single_retriever_plan_is_sequential_and_unreranked(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.LEXICAL_ONLY, (RetrieverKind.LEXICAL,))
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)

    assert plan.parallel is False
    assert plan.retrievers == [RetrieverKind.LEXICAL]
    assert plan.execution_order == [RetrieverKind.LEXICAL]
    assert plan.rerank is False
    assert plan.top_k == 10
    assert plan.candidate_limit == 10
    assert plan.graph_depth == 0
    assert plan.expand_neighbors is False


def test_semantic_only_uses_spec_top_k(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.SEMANTIC_ONLY, (RetrieverKind.DENSE,))
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)
    assert plan.top_k == 8


def test_multi_retriever_plan_is_parallel_and_reranked(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.HYBRID, (RetrieverKind.LEXICAL, RetrieverKind.DENSE))
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)

    assert plan.parallel is True
    assert plan.rerank is True
    assert plan.top_k == 15
    assert plan.candidate_limit == 45  # 15 * 3


def test_full_pipeline_top_k(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(
        RoutingStrategy.FULL_PIPELINE, (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)
    )
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)
    assert plan.top_k == 20
    assert plan.candidate_limit == 60


def test_execution_order_is_cheapest_first(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(
        RoutingStrategy.FULL_PIPELINE, (RetrieverKind.DENSE, RetrieverKind.GRAPH, RetrieverKind.LEXICAL)
    )
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)
    assert plan.execution_order == [RetrieverKind.LEXICAL, RetrieverKind.GRAPH, RetrieverKind.DENSE]


def test_duplicate_retrievers_are_removed(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.HYBRID, (RetrieverKind.LEXICAL, RetrieverKind.LEXICAL, RetrieverKind.DENSE))
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)
    assert plan.retrievers == [RetrieverKind.LEXICAL, RetrieverKind.DENSE]


def test_graph_depth_and_expand_neighbors_set_only_when_graph_involved(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.GRAPH_ONLY, (RetrieverKind.GRAPH,))
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)
    assert plan.graph_depth == 3
    assert plan.expand_neighbors is True


def test_reasoning_required_forces_rerank_even_for_single_retriever(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.SEMANTIC_ONLY, (RetrieverKind.DENSE,))
    plan = RetrievalPlanner().plan(decision, classification_factory(reasoning_required=True), rich_context)

    assert plan.rerank is True
    assert plan.parallel is False  # rerank=True doesn't imply parallel=True


def test_dense_retriever_dropped_when_context_has_no_embeddings(
    bare_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.HYBRID, (RetrieverKind.LEXICAL, RetrieverKind.DENSE))
    plan = RetrievalPlanner().plan(decision, classification_factory(), bare_context)

    assert RetrieverKind.DENSE not in plan.retrievers
    assert plan.retrievers == [RetrieverKind.LEXICAL]
    assert "Dropped DENSE" in plan.reason


def test_graph_retriever_dropped_when_context_graph_is_trivial(
    bare_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.GRAPH_ONLY, (RetrieverKind.GRAPH,))
    plan = RetrievalPlanner().plan(decision, classification_factory(), bare_context)

    assert RetrieverKind.GRAPH not in plan.retrievers
    assert plan.retrievers == [RetrieverKind.LEXICAL]  # ultimate fallback
    assert plan.graph_depth == 0
    assert "Dropped GRAPH" in plan.reason


def test_plan_falls_back_to_lexical_when_nothing_else_supported(
    bare_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.GRAPH_PLUS_SEMANTIC, (RetrieverKind.GRAPH, RetrieverKind.DENSE))
    plan = RetrievalPlanner().plan(decision, classification_factory(), bare_context)

    assert plan.retrievers == [RetrieverKind.LEXICAL]
    assert "Fell back to LEXICAL" in plan.reason


def test_rich_context_does_not_downgrade_any_retriever(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(
        RoutingStrategy.FULL_PIPELINE, (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)
    )
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)
    assert set(plan.retrievers) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH}


def test_metadata_records_policy_and_classifier_retriever_kind(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    decision = _decision(RoutingStrategy.LEXICAL_ONLY, (RetrieverKind.LEXICAL,), policy_name="lexical")
    plan = RetrievalPlanner().plan(decision, classification_factory(), rich_context)

    assert plan.metadata["policy"] == "lexical"
    assert "classifier_retriever_kind" in plan.metadata
