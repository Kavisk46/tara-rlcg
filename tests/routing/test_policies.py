"""Unit tests for `tara.routing.policies`."""
from __future__ import annotations

from collections.abc import Callable

import pytest

from tara.classification.models import TaskClassification
from tara.core.types import RetrieverKind, TaskType
from tara.routing.policies import (
    DEFAULT_POLICIES,
    FullPipelinePolicy,
    GraphPolicy,
    HybridPolicy,
    LexicalPolicy,
    RoutingPolicy,
    SemanticPolicy,
)
from tara.routing.strategy import RoutingStrategy


def _first_applicable(classification: TaskClassification) -> RoutingPolicy | None:
    for policy in DEFAULT_POLICIES:
        if policy.applies(classification):
            return policy
    return None


@pytest.mark.parametrize(
    ("flags", "expected_strategy"),
    [
        ({}, RoutingStrategy.SEMANTIC_ONLY),
        ({"lexical_required": True}, RoutingStrategy.LEXICAL_ONLY),
        ({"semantic_required": True}, RoutingStrategy.SEMANTIC_ONLY),
        ({"graph_required": True}, RoutingStrategy.GRAPH_ONLY),
        ({"lexical_required": True, "semantic_required": True}, RoutingStrategy.HYBRID),
        ({"semantic_required": True, "graph_required": True}, RoutingStrategy.GRAPH_PLUS_SEMANTIC),
        ({"lexical_required": True, "graph_required": True}, RoutingStrategy.LEXICAL_PLUS_GRAPH),
        (
            {"lexical_required": True, "semantic_required": True, "graph_required": True},
            RoutingStrategy.FULL_PIPELINE,
        ),
    ],
)
def test_default_policy_chain_covers_every_flag_combination(
    flags: dict[str, bool], expected_strategy: RoutingStrategy, classification_factory: Callable[..., TaskClassification]
) -> None:
    classification = classification_factory(**flags)
    policy = _first_applicable(classification)
    assert policy is not None

    decision = policy.decide(classification)
    assert decision.strategy is expected_strategy


def test_refactor_task_type_forces_full_pipeline_regardless_of_flags(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    classification = classification_factory(task_type=TaskType.REFACTOR, semantic_required=True)
    policy = _first_applicable(classification)

    assert isinstance(policy, FullPipelinePolicy)
    decision = policy.decide(classification)
    assert decision.strategy is RoutingStrategy.FULL_PIPELINE
    assert set(decision.retrievers) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH}
    assert "REFACTOR" in decision.reason


def test_refactor_with_all_flags_also_reports_flag_based_reason(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    classification = classification_factory(
        task_type=TaskType.REFACTOR, graph_required=True, semantic_required=True, lexical_required=True
    )
    decision = FullPipelinePolicy().decide(classification)
    assert "all required" in decision.reason


def test_semantic_policy_is_universal_fallback(classification_factory: Callable[..., TaskClassification]) -> None:
    assert SemanticPolicy().applies(classification_factory()) is True


def test_lexical_policy_does_not_apply_when_semantic_also_required(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    classification = classification_factory(lexical_required=True, semantic_required=True)
    assert LexicalPolicy().applies(classification) is False


def test_hybrid_policy_does_not_apply_when_graph_also_required(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    classification = classification_factory(lexical_required=True, semantic_required=True, graph_required=True)
    assert HybridPolicy().applies(classification) is False


def test_graph_policy_applies_whenever_graph_required(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    classification = classification_factory(graph_required=True, semantic_required=True, lexical_required=True)
    assert GraphPolicy().applies(classification) is True


def test_default_policies_ordered_most_specific_first() -> None:
    names = [policy.name for policy in DEFAULT_POLICIES]
    assert names == ["full_pipeline", "graph", "hybrid", "lexical", "semantic"]


def test_default_policies_always_produce_a_decision(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    for lexical in (False, True):
        for semantic in (False, True):
            for graph in (False, True):
                classification = classification_factory(
                    lexical_required=lexical, semantic_required=semantic, graph_required=graph
                )
                assert _first_applicable(classification) is not None


def test_every_decision_reports_its_own_policy_name(
    classification_factory: Callable[..., TaskClassification]
) -> None:
    # decide() doesn't consult applies() internally, so any classification works here.
    classification = classification_factory(lexical_required=True, semantic_required=True, graph_required=True)
    for policy in DEFAULT_POLICIES:
        decision = policy.decide(classification)
        assert decision.policy_name == policy.name
