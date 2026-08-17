"""Unit tests for `evaluation.baselines.plan_builder.build_fixed_plan`.

Inspects the actual `RetrievalPlan` produced, not just a status string --
per this milestone's "RETRIEVAL PLAN TESTS" requirement, including the
explicit negative assertions (e.g. B1 must not contain lexical or graph).
"""
from __future__ import annotations

from evaluation.baselines.plan_builder import build_fixed_plan
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.routing.strategy import RoutingStrategy


def test_b1_semantic_only_plan_contains_only_dense(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    plan = build_fixed_plan(RoutingStrategy.SEMANTIC_ONLY, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.SEMANTIC_ONLY
    assert RetrieverKind.DENSE in plan.retrievers
    assert RetrieverKind.LEXICAL not in plan.retrievers
    assert RetrieverKind.GRAPH not in plan.retrievers


def test_b2_lexical_only_plan_contains_only_lexical(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    plan = build_fixed_plan(RoutingStrategy.LEXICAL_ONLY, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.LEXICAL_ONLY
    assert RetrieverKind.LEXICAL in plan.retrievers
    assert RetrieverKind.DENSE not in plan.retrievers
    assert RetrieverKind.GRAPH not in plan.retrievers


def test_b3_graph_only_plan_contains_only_graph(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    plan = build_fixed_plan(RoutingStrategy.GRAPH_ONLY, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.GRAPH_ONLY
    assert RetrieverKind.GRAPH in plan.retrievers
    assert RetrieverKind.LEXICAL not in plan.retrievers
    assert RetrieverKind.DENSE not in plan.retrievers


def test_b4_full_pipeline_plan_contains_exactly_the_three_fixed_mechanisms(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    plan = build_fixed_plan(RoutingStrategy.FULL_PIPELINE, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.FULL_PIPELINE
    assert set(plan.retrievers) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH}


def test_plan_ignores_classification_content_entirely(
    rich_context: RepositoryContext,
    search_classification: TaskClassification,
    refactor_classification: TaskClassification,
) -> None:
    plan_a = build_fixed_plan(RoutingStrategy.LEXICAL_ONLY, search_classification, rich_context)
    plan_b = build_fixed_plan(RoutingStrategy.LEXICAL_ONLY, refactor_classification, rich_context)
    assert plan_a.strategy == plan_b.strategy
    assert plan_a.retrievers == plan_b.retrievers


def test_plan_reason_discloses_no_adaptive_routing_was_performed(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    plan = build_fixed_plan(RoutingStrategy.GRAPH_ONLY, search_classification, rich_context)
    assert "graph_only" in plan.reason
    assert "No adaptive routing decision was made" in plan.reason
