"""Unit tests for `tara.routing.router.AdaptiveRouter`.

The five worked examples run through the *real* `HeuristicTaskClassifier`
end-to-end, so these tests double as an integration check between the
Task Classifier and the Router. No retriever, no embedding model, and no
LLM is used anywhere in this file.
"""
from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from tara.classification.classifier import HeuristicTaskClassifier
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.exceptions import PlanningError, PolicyError, RoutingError
from tara.core.types import RetrieverKind
from tara.interfaces.router import Router
from tara.routing.planner import RetrievalPlanner
from tara.routing.policies import RoutingDecision, RoutingPolicy
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import RoutingStrategy


@pytest.fixture
def router() -> AdaptiveRouter:
    return AdaptiveRouter()


@pytest.fixture
def classifier() -> HeuristicTaskClassifier:
    return HeuristicTaskClassifier()


def test_router_implements_router_interface(router: AdaptiveRouter) -> None:
    assert isinstance(router, Router)


# --- Worked examples, end-to-end through the real classifier ------------------------


def test_example_find_parse_repository_is_lexical_only(
    router: AdaptiveRouter, classifier: HeuristicTaskClassifier, rich_context: RepositoryContext
) -> None:
    classification = classifier.classify("Find parse_repository")
    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.LEXICAL_ONLY
    assert plan.retrievers == [RetrieverKind.LEXICAL]
    assert plan.top_k == 10


def test_example_explain_repositorycontextextractor_is_semantic_only(
    router: AdaptiveRouter, classifier: HeuristicTaskClassifier, rich_context: RepositoryContext
) -> None:
    classification = classifier.classify("Explain RepositoryContextExtractor")
    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.SEMANTIC_ONLY
    assert plan.retrievers == [RetrieverKind.DENSE]
    assert plan.top_k == 8


def test_example_trace_login_flow_is_graph_only(
    router: AdaptiveRouter, classifier: HeuristicTaskClassifier, rich_context: RepositoryContext
) -> None:
    classification = classifier.classify("Trace login flow")
    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.GRAPH_ONLY
    assert plan.retrievers == [RetrieverKind.GRAPH]
    assert plan.graph_depth == 3
    assert plan.expand_neighbors is True


def test_example_where_is_jwt_implemented_is_hybrid(
    router: AdaptiveRouter, classifier: HeuristicTaskClassifier, rich_context: RepositoryContext
) -> None:
    classification = classifier.classify("Where is JWT implemented?")
    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.HYBRID
    assert set(plan.retrievers) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE}
    assert plan.parallel is True
    assert plan.top_k == 15
    assert plan.rerank is True


def test_example_refactor_repositoryparser_is_full_pipeline(
    router: AdaptiveRouter, classifier: HeuristicTaskClassifier, rich_context: RepositoryContext
) -> None:
    classification = classifier.classify("Refactor RepositoryParser")
    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.FULL_PIPELINE
    assert set(plan.retrievers) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH}
    assert plan.rerank is True


# --- Dependency injection --------------------------------------------------------


def test_custom_policy_set_is_used(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    class AlwaysGraph(RoutingPolicy):
        name = "always_graph"

        def applies(self, classification: TaskClassification) -> bool:
            return True

        def decide(self, classification: TaskClassification) -> RoutingDecision:
            return RoutingDecision(
                policy_name=self.name,
                strategy=RoutingStrategy.GRAPH_ONLY,
                retrievers=(RetrieverKind.GRAPH,),
                reason="forced",
            )

    router = AdaptiveRouter(policies=(AlwaysGraph(),))
    plan = router.route(classification_factory(), rich_context)
    assert plan.strategy is RoutingStrategy.GRAPH_ONLY


def test_custom_planner_is_used(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    class FixedTopKPlanner(RetrievalPlanner):
        def plan(self, decision, classification, context):  # type: ignore[override]
            base_plan = super().plan(decision, classification, context)
            return base_plan.model_copy(update={"top_k": 999})

    router = AdaptiveRouter(planner=FixedTopKPlanner())
    plan = router.route(classification_factory(lexical_required=True), rich_context)
    assert plan.top_k == 999


def test_default_router_does_not_require_explicit_dependencies() -> None:
    # Constructing with no arguments should still work via documented defaults.
    router = AdaptiveRouter()
    assert router is not None


# --- Error propagation -----------------------------------------------------------


def test_no_applicable_policy_raises_routing_error(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    class NeverApplies(RoutingPolicy):
        name = "never"

        def applies(self, classification: TaskClassification) -> bool:
            return False

        def decide(self, classification: TaskClassification) -> RoutingDecision:
            raise AssertionError("should never be called")

    router = AdaptiveRouter(policies=(NeverApplies(),))
    with pytest.raises(RoutingError):
        router.route(classification_factory(), rich_context)


def test_broken_policy_raises_policy_error(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    class BrokenPolicy(RoutingPolicy):
        name = "broken"

        def applies(self, classification: TaskClassification) -> bool:
            raise RuntimeError("boom")

        def decide(self, classification: TaskClassification) -> RoutingDecision:
            raise AssertionError("should never be called")

    router = AdaptiveRouter(policies=(BrokenPolicy(),))
    with pytest.raises(PolicyError, match="broken"):
        router.route(classification_factory(), rich_context)


def test_broken_planner_raises_planning_error(
    rich_context: RepositoryContext, classification_factory: Callable[..., TaskClassification]
) -> None:
    class BrokenPlanner(RetrievalPlanner):
        def plan(self, decision, classification, context):  # type: ignore[override]
            raise RuntimeError("boom")

    router = AdaptiveRouter(planner=BrokenPlanner())
    with pytest.raises(PlanningError):
        router.route(classification_factory(lexical_required=True), rich_context)


def test_policy_error_and_planning_error_are_routing_errors() -> None:
    assert issubclass(PolicyError, RoutingError)
    assert issubclass(PlanningError, RoutingError)


# --- Performance ---------------------------------------------------------------------


def test_routing_completes_within_2ms(
    router: AdaptiveRouter, classifier: HeuristicTaskClassifier, rich_context: RepositoryContext
) -> None:
    classification = classifier.classify("Where is JWT implemented?")

    start = time.perf_counter()
    router.route(classification, rich_context)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.002
