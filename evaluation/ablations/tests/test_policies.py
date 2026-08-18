"""Unit tests for `evaluation.ablations.policies` (A2 -- no REFACTOR override)."""
from __future__ import annotations

from evaluation.ablations.policies import (
    FullPipelinePolicyWithoutRefactorOverride,
    ablated_policies,
)
from evaluation.ablations.tests.conftest import make_classification
from tara.context.models import RepositoryContext
from tara.core.types import TaskType
from tara.routing.policies import DEFAULT_POLICIES
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import RoutingStrategy


def test_applies_false_for_refactor_without_all_flags() -> None:
    policy = FullPipelinePolicyWithoutRefactorOverride()
    classification = make_classification(task_type=TaskType.REFACTOR, lexical_required=True)
    assert policy.applies(classification) is False


def test_real_full_pipeline_policy_applies_true_for_refactor_without_all_flags() -> None:
    # Sanity: proves the ablation actually changed behavior relative to the real policy.
    real_policy = DEFAULT_POLICIES[0]
    classification = make_classification(task_type=TaskType.REFACTOR, lexical_required=True)
    assert real_policy.applies(classification) is True


def test_applies_true_when_all_flags_set_regardless_of_task_type() -> None:
    policy = FullPipelinePolicyWithoutRefactorOverride()
    classification = make_classification(
        task_type=TaskType.SEARCH,
        graph_required=True,
        semantic_required=True,
        lexical_required=True,
    )
    assert policy.applies(classification) is True


def test_decide_returns_full_pipeline() -> None:
    policy = FullPipelinePolicyWithoutRefactorOverride()
    classification = make_classification(
        graph_required=True, semantic_required=True, lexical_required=True
    )
    decision = policy.decide(classification)
    assert decision.strategy is RoutingStrategy.FULL_PIPELINE


def test_ablated_policies_has_five_entries_matching_default_policies_length() -> None:
    assert len(ablated_policies()) == len(DEFAULT_POLICIES) == 5


def test_ablated_policies_swaps_only_the_first_entry() -> None:
    ablated = ablated_policies()
    assert isinstance(ablated[0], FullPipelinePolicyWithoutRefactorOverride)
    assert ablated[1:] == DEFAULT_POLICIES[1:]


def test_ablated_router_does_not_route_refactor_to_full_pipeline_without_all_flags(
    rich_context: RepositoryContext,
) -> None:
    router = AdaptiveRouter(policies=ablated_policies())
    classification = make_classification(task_type=TaskType.REFACTOR, lexical_required=True)

    plan = router.route(classification, rich_context)

    assert plan.strategy is not RoutingStrategy.FULL_PIPELINE


def test_real_router_does_route_refactor_to_full_pipeline_without_all_flags(
    rich_context: RepositoryContext,
) -> None:
    # Sanity: proves the ablated router's behavior above genuinely differs from TARA-proper's.
    router = AdaptiveRouter()
    classification = make_classification(task_type=TaskType.REFACTOR, lexical_required=True)

    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.FULL_PIPELINE


def test_ablated_router_still_routes_full_pipeline_when_all_flags_set(
    rich_context: RepositoryContext,
) -> None:
    router = AdaptiveRouter(policies=ablated_policies())
    classification = make_classification(
        graph_required=True, semantic_required=True, lexical_required=True
    )

    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.FULL_PIPELINE
