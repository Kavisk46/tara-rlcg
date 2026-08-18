"""Unit tests for `evaluation.ablations.router_wrappers` (A4, A5, A7)."""
from __future__ import annotations

import pytest

from evaluation.ablations.router_wrappers import (
    _CANDIDATE_LIMIT_MULTIPLIER_WHEN_RERANKING,
    ConfidenceThresholdFallbackRouter,
    FixedTopKRouter,
    NoRerankRouter,
)
from evaluation.ablations.tests.conftest import make_classification
from tara.context.models import RepositoryContext
from tara.core.types import TaskType
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import RoutingStrategy

# A classification guaranteed to produce a reranked (parallel, multi-retriever) plan under the
# real AdaptiveRouter, so A4/A5's candidate_limit recomputation is actually exercised.
_MULTI_RETRIEVER_CLASSIFICATION = make_classification(
    task_type=TaskType.REFACTOR, graph_required=True, semantic_required=True, lexical_required=True
)


def test_candidate_limit_multiplier_matches_the_real_planners_own_value(
    rich_context: RepositoryContext,
) -> None:
    # Pins evaluation.ablations.router_wrappers's hand-kept-in-sync multiplier constant against
    # the real RetrievalPlanner's actual behavior, so drift is caught immediately.
    real_plan = AdaptiveRouter().route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)
    assert real_plan.rerank is True
    assert real_plan.candidate_limit == real_plan.top_k * _CANDIDATE_LIMIT_MULTIPLIER_WHEN_RERANKING


# ============================================================================
# A4: FixedTopKRouter
# ============================================================================


def test_fixed_top_k_router_overrides_top_k(rich_context: RepositoryContext) -> None:
    router = FixedTopKRouter(AdaptiveRouter(), fixed_top_k=10)
    classification = make_classification()

    plan = router.route(classification, rich_context)

    assert plan.top_k == 10


def test_fixed_top_k_router_recomputes_candidate_limit_when_reranking(
    rich_context: RepositoryContext,
) -> None:
    router = FixedTopKRouter(AdaptiveRouter(), fixed_top_k=10)

    plan = router.route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    assert plan.rerank is True
    assert plan.candidate_limit == 10 * _CANDIDATE_LIMIT_MULTIPLIER_WHEN_RERANKING


def test_fixed_top_k_router_candidate_limit_equals_top_k_when_not_reranking(
    rich_context: RepositoryContext,
) -> None:
    router = FixedTopKRouter(AdaptiveRouter(), fixed_top_k=10)
    classification = make_classification()  # single-retriever -> not reranked

    plan = router.route(classification, rich_context)

    assert plan.rerank is False
    assert plan.candidate_limit == 10


def test_fixed_top_k_router_preserves_strategy_selection(rich_context: RepositoryContext) -> None:
    router = FixedTopKRouter(AdaptiveRouter(), fixed_top_k=10)
    real_plan = AdaptiveRouter().route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    plan = router.route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    assert plan.strategy == real_plan.strategy
    assert plan.retrievers == real_plan.retrievers


def test_fixed_top_k_router_uses_the_same_value_across_different_strategies(
    rich_context: RepositoryContext,
) -> None:
    router = FixedTopKRouter(AdaptiveRouter(), fixed_top_k=7)
    search = make_classification()
    refactor = _MULTI_RETRIEVER_CLASSIFICATION

    assert router.route(search, rich_context).top_k == 7
    assert router.route(refactor, rich_context).top_k == 7


# ============================================================================
# A5: NoRerankRouter
# ============================================================================


def test_no_rerank_router_forces_rerank_false(rich_context: RepositoryContext) -> None:
    router = NoRerankRouter(AdaptiveRouter())

    plan = router.route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    assert plan.rerank is False


def test_no_rerank_router_recomputes_candidate_limit_to_top_k(
    rich_context: RepositoryContext,
) -> None:
    router = NoRerankRouter(AdaptiveRouter())

    plan = router.route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    assert plan.candidate_limit == plan.top_k


def test_no_rerank_router_preserves_strategy_and_top_k(rich_context: RepositoryContext) -> None:
    router = NoRerankRouter(AdaptiveRouter())
    real_plan = AdaptiveRouter().route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    plan = router.route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)

    assert plan.strategy == real_plan.strategy
    assert plan.top_k == real_plan.top_k


def test_real_router_does_rerank_for_the_multi_retriever_classification(
    rich_context: RepositoryContext,
) -> None:
    # Sanity: proves NoRerankRouter's effect above is a genuine change, not a no-op.
    real_plan = AdaptiveRouter().route(_MULTI_RETRIEVER_CLASSIFICATION, rich_context)
    assert real_plan.rerank is True


# ============================================================================
# A7: ConfidenceThresholdFallbackRouter
# ============================================================================


def test_confidence_below_threshold_falls_back_to_semantic_only(
    rich_context: RepositoryContext,
) -> None:
    router = ConfidenceThresholdFallbackRouter(AdaptiveRouter(), confidence_threshold=0.5)
    low_confidence = make_classification(
        task_type=TaskType.REFACTOR,
        graph_required=True,
        semantic_required=True,
        lexical_required=True,
        confidence=0.2,
    )

    plan = router.route(low_confidence, rich_context)

    assert plan.strategy is RoutingStrategy.SEMANTIC_ONLY


def test_confidence_at_or_above_threshold_delegates_to_inner_router(
    rich_context: RepositoryContext,
) -> None:
    router = ConfidenceThresholdFallbackRouter(AdaptiveRouter(), confidence_threshold=0.5)
    high_confidence = make_classification(
        task_type=TaskType.REFACTOR,
        graph_required=True,
        semantic_required=True,
        lexical_required=True,
        confidence=0.9,
    )

    plan = router.route(high_confidence, rich_context)

    assert plan.strategy is RoutingStrategy.FULL_PIPELINE


def test_confidence_exactly_at_threshold_is_not_a_fallback(rich_context: RepositoryContext) -> None:
    # "below" the threshold triggers fallback; exactly-equal does not -- proven observably by
    # using a classification that would route to something other than SEMANTIC_ONLY for real.
    router = ConfidenceThresholdFallbackRouter(AdaptiveRouter(), confidence_threshold=0.5)
    classification = make_classification(
        task_type=TaskType.REFACTOR,
        graph_required=True,
        semantic_required=True,
        lexical_required=True,
        confidence=0.5,
    )

    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.FULL_PIPELINE


@pytest.mark.parametrize("threshold", [0.3, 0.4, 0.5, 0.6, 0.7])
def test_every_swept_threshold_value_is_constructible(
    threshold: float, rich_context: RepositoryContext
) -> None:
    router = ConfidenceThresholdFallbackRouter(AdaptiveRouter(), confidence_threshold=threshold)
    classification = make_classification(confidence=0.0)

    plan = router.route(classification, rich_context)

    assert plan.strategy is RoutingStrategy.SEMANTIC_ONLY


def test_rejects_threshold_outside_valid_range() -> None:
    with pytest.raises(ValueError, match="confidence_threshold"):
        ConfidenceThresholdFallbackRouter(AdaptiveRouter(), confidence_threshold=1.5)


def test_fallback_reason_names_the_threshold(rich_context: RepositoryContext) -> None:
    router = ConfidenceThresholdFallbackRouter(AdaptiveRouter(), confidence_threshold=0.5)
    classification = make_classification(confidence=0.1)

    plan = router.route(classification, rich_context)

    assert "0.10" in plan.reason
