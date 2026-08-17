"""Unit tests for `evaluation.baselines.definitions`.

Covers this milestone's two headline correctness requirements:
- each baseline produces the intended `RetrievalPlan` (retrievers/strategy);
- no baseline accidentally uses TARA's real adaptive router (proved
  behaviorally here: a baseline's plan must not change across wildly
  different classifications, unlike `AdaptiveRouter(DEFAULT_POLICIES)`;
  proved structurally, via a call-count spy, in `test_router_isolation.py`).
"""
from __future__ import annotations

from evaluation.baselines.definitions import (
    BASELINE_DEFINITIONS,
    UNAVAILABLE_BASELINES,
    BaselineDefinition,
    BaselineId,
)
from evaluation.baselines.plan_builder import build_fixed_plan
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.routing.policies import DEFAULT_POLICIES
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import RoutingStrategy

# `rich_context`, `refactor_classification`, `search_classification` are pytest fixtures
# auto-discovered from `evaluation/baselines/tests/conftest.py`.


def _definition(baseline_id: BaselineId) -> BaselineDefinition:
    matches = [b for b in BASELINE_DEFINITIONS if b.baseline_id is baseline_id]
    assert len(matches) == 1
    return matches[0]


# ============================================================================
# Registry shape
# ============================================================================


def test_baseline_definitions_covers_b0_through_b4() -> None:
    assert [b.baseline_id for b in BASELINE_DEFINITIONS] == [
        BaselineId.B0,
        BaselineId.B1,
        BaselineId.B2,
        BaselineId.B3,
        BaselineId.B4,
    ]


def test_unavailable_baselines_covers_b5_and_b6_with_reasons() -> None:
    assert [b.baseline_id for b in UNAVAILABLE_BASELINES] == [BaselineId.B5, BaselineId.B6]
    for unavailable in UNAVAILABLE_BASELINES:
        assert unavailable.reason  # non-empty: a reason must always be given


def test_no_baseline_id_appears_in_both_available_and_unavailable_sets() -> None:
    available_ids = {b.baseline_id for b in BASELINE_DEFINITIONS}
    unavailable_ids = {b.baseline_id for b in UNAVAILABLE_BASELINES}
    assert available_ids.isdisjoint(unavailable_ids)


# ============================================================================
# B0: no retrieval
# ============================================================================


def test_b0_has_no_fixed_strategy() -> None:
    assert _definition(BaselineId.B0).strategy is None


# ============================================================================
# Each baseline produces the intended retrieval plan
# ============================================================================


def test_b1_routes_to_semantic_only(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    baseline = _definition(BaselineId.B1)
    assert baseline.strategy is not None
    plan = build_fixed_plan(baseline.strategy, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.SEMANTIC_ONLY
    assert plan.retrievers == [RetrieverKind.DENSE]


def test_b2_routes_to_lexical_only(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    baseline = _definition(BaselineId.B2)
    assert baseline.strategy is not None
    plan = build_fixed_plan(baseline.strategy, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.LEXICAL_ONLY
    assert plan.retrievers == [RetrieverKind.LEXICAL]


def test_b3_routes_to_graph_only(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    baseline = _definition(BaselineId.B3)
    assert baseline.strategy is not None
    plan = build_fixed_plan(baseline.strategy, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.GRAPH_ONLY
    assert plan.retrievers == [RetrieverKind.GRAPH]


def test_b4_routes_to_full_pipeline(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    baseline = _definition(BaselineId.B4)
    assert baseline.strategy is not None
    plan = build_fixed_plan(baseline.strategy, search_classification, rich_context)
    assert plan.strategy is RoutingStrategy.FULL_PIPELINE
    assert set(plan.retrievers) == {
        RetrieverKind.LEXICAL,
        RetrieverKind.DENSE,
        RetrieverKind.GRAPH,
    }


# ============================================================================
# No baseline accidentally uses TARA's adaptive router
# ============================================================================


def test_baselines_ignore_classification_unlike_default_policies(
    rich_context: RepositoryContext,
    refactor_classification: TaskClassification,
    search_classification: TaskClassification,
) -> None:
    """The decisive behavioral proof: under TARA's real `DEFAULT_POLICIES`, a REFACTOR
    classification with every flag set routes to FULL_PIPELINE while a bare SEARCH
    classification routes to something else entirely -- routing genuinely depends on
    classification. Every fixed baseline, run against those same two wildly different
    classifications, must produce the identical strategy both times."""
    real_router = AdaptiveRouter()  # DEFAULT_POLICIES, TARA-proper
    refactor_plan = real_router.route(refactor_classification, rich_context)
    search_plan = real_router.route(search_classification, rich_context)
    assert refactor_plan.strategy != search_plan.strategy  # sanity: the real router IS adaptive

    for baseline_id in (BaselineId.B1, BaselineId.B2, BaselineId.B3, BaselineId.B4):
        baseline = _definition(baseline_id)
        assert baseline.strategy is not None
        plan_a = build_fixed_plan(baseline.strategy, refactor_classification, rich_context)
        plan_b = build_fixed_plan(baseline.strategy, search_classification, rich_context)
        assert plan_a.strategy == plan_b.strategy, f"{baseline_id} varied with classification"
        assert plan_a.retrievers == plan_b.retrievers, f"{baseline_id} varied with classification"


def test_baseline_strategies_are_plain_data_not_policy_objects() -> None:
    """`BaselineDefinition.strategy` is a bare `RoutingStrategy` enum value -- not a
    `RoutingPolicy`, not a `Router`, not anything with `.applies()`/`.decide()`/`.route()`.
    There is no policy machinery for a baseline to accidentally share with `DEFAULT_POLICIES`."""
    for baseline in BASELINE_DEFINITIONS:
        if baseline.strategy is None:
            continue  # B0
        assert isinstance(baseline.strategy, RoutingStrategy)
        assert not hasattr(baseline.strategy, "applies")
        assert not hasattr(baseline.strategy, "decide")


def test_default_policies_has_more_than_one_policy() -> None:
    # Sanity check on the assumption `test_baselines_ignore_classification...` relies on.
    assert len(DEFAULT_POLICIES) > 1
