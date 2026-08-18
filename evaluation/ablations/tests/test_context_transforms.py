"""Unit tests for `evaluation.ablations.context_transforms` (A3 -- graph retrieval disabled)."""
from __future__ import annotations

from evaluation.ablations.context_transforms import disable_graph_retrieval
from evaluation.ablations.tests.conftest import make_classification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.routing.planner import RetrievalPlanner
from tara.routing.policies import RoutingDecision
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import STRATEGY_RETRIEVERS, RoutingStrategy


def test_disabled_context_has_empty_graph(rich_context: RepositoryContext) -> None:
    assert rich_context.graph.number_of_nodes() > 1  # sanity: the real fixture has real content

    ablated = disable_graph_retrieval(rich_context)

    assert ablated.graph.number_of_nodes() == 0


def test_disabled_context_preserves_every_other_field(rich_context: RepositoryContext) -> None:
    ablated = disable_graph_retrieval(rich_context)

    assert ablated.root_path == rich_context.root_path
    assert ablated.symbol_index is rich_context.symbol_index
    assert ablated.embeddings == rich_context.embeddings
    assert ablated.file_count == rich_context.file_count


def test_planner_drops_graph_from_a_graph_only_decision_against_the_ablated_context(
    rich_context: RepositoryContext,
) -> None:
    ablated = disable_graph_retrieval(rich_context)
    decision = RoutingDecision(
        policy_name="test",
        strategy=RoutingStrategy.GRAPH_ONLY,
        retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.GRAPH_ONLY],
        reason="test",
    )
    classification = make_classification()

    plan = RetrievalPlanner().plan(decision, classification, ablated)

    # GRAPH is unsupported and was the only retriever requested -> falls back to LEXICAL,
    # exactly RetrievalPlanner's own existing context-capability-downgrade behavior.
    assert RetrieverKind.GRAPH not in plan.retrievers
    assert plan.retrievers == [RetrieverKind.LEXICAL]


def test_planner_keeps_graph_for_the_real_unablated_context(
    rich_context: RepositoryContext,
) -> None:
    # Sanity: the real, non-ablated context does NOT trigger the downgrade (it has real graph
    # content), proving the ablation above is what caused the fallback.
    decision = RoutingDecision(
        policy_name="test",
        strategy=RoutingStrategy.GRAPH_ONLY,
        retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.GRAPH_ONLY],
        reason="test",
    )
    classification = make_classification()

    plan = RetrievalPlanner().plan(decision, classification, rich_context)

    assert plan.retrievers == [RetrieverKind.GRAPH]


def test_full_pipeline_strategy_drops_only_graph_from_the_ablated_context(
    rich_context: RepositoryContext,
) -> None:
    ablated = disable_graph_retrieval(rich_context)
    decision = RoutingDecision(
        policy_name="test",
        strategy=RoutingStrategy.FULL_PIPELINE,
        retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.FULL_PIPELINE],
        reason="test",
    )
    classification = make_classification()

    plan = RetrievalPlanner().plan(decision, classification, ablated)

    assert RetrieverKind.GRAPH not in plan.retrievers
    assert RetrieverKind.LEXICAL in plan.retrievers
    assert RetrieverKind.DENSE in plan.retrievers


def test_adaptive_router_never_selects_graph_against_the_ablated_context(
    rich_context: RepositoryContext,
) -> None:
    ablated = disable_graph_retrieval(rich_context)
    router = AdaptiveRouter()
    classification = make_classification(graph_required=True)

    plan = router.route(classification, ablated)

    assert RetrieverKind.GRAPH not in plan.retrievers
