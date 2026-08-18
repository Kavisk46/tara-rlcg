"""A4, A5, A7 -- `Router` decorators that adjust exactly one plan property post-hoc.

Each wrapper delegates the *entire* real routing decision (strategy
selection, execution order, parallelism, graph depth, and, except where
the ablation itself is about rerank/top_k, reranking) to an injected
inner `Router` -- typically a real `tara.routing.router.AdaptiveRouter()`
-- and then overrides only the one `RetrievalPlan` field its own
ablation is about, via `RetrievalPlan.model_copy(update=...)`. This is
the direct architectural analogue of `evaluation.baselines`'s own
"reuse `AdaptiveRouter`, change only the wiring" approach, applied to
ablations instead of baselines: "ensure one variable changes at a time,"
per this milestone's own instruction.
"""
from __future__ import annotations

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.interfaces.router import Router
from tara.routing.models import RetrievalPlan
from tara.routing.policies import RoutingDecision, RoutingPolicy
from tara.routing.router import AdaptiveRouter
from tara.routing.strategy import STRATEGY_RETRIEVERS, RoutingStrategy

_CANDIDATE_LIMIT_MULTIPLIER_WHEN_RERANKING = 3
"""Mirrors `tara.routing.planner._CANDIDATE_MULTIPLIER_WHEN_RERANKING` (a private module
constant, not importable) -- kept in sync by hand since the real value isn't exported; see
`tests/test_router_wrappers.py` for a test pinning this to the same value the real planner
produces for an unablated plan, so any future drift between the two is caught immediately."""


class FixedTopKRouter(Router):
    """A4 -- per-strategy top-k differentiation disabled; every plan gets the same `top_k`.

    Per `EXPERIMENT_PLAN.md` §5: "single constant top-k used across all
    strategies." `candidate_limit` is recomputed consistently with the
    real planner's own rule (`top_k * 3` when `rerank` is true, else
    `top_k`), so this ablation changes only "how many results does a
    strategy keep," never "how large a pool does reranking see relative
    to `top_k`."
    """

    def __init__(self, inner: Router, fixed_top_k: int) -> None:
        """Construct the wrapper.

        Args:
            inner: The real router to delegate strategy selection to.
                Defaults are the caller's choice -- pass `AdaptiveRouter()`
                for "TARA-proper with fixed top-k."
            fixed_top_k: The single `top_k` value every plan receives,
                regardless of strategy. Must be positive (enforced by
                `RetrievalPlan.top_k`'s own `gt=0` constraint).
        """
        self._inner = inner
        self._fixed_top_k = fixed_top_k

    def route(
        self, classification: TaskClassification, context: RepositoryContext
    ) -> RetrievalPlan:
        plan = self._inner.route(classification, context)
        candidate_limit = (
            self._fixed_top_k * _CANDIDATE_LIMIT_MULTIPLIER_WHEN_RERANKING
            if plan.rerank
            else self._fixed_top_k
        )
        return plan.model_copy(
            update={"top_k": self._fixed_top_k, "candidate_limit": candidate_limit}
        )


class NoRerankRouter(Router):
    """A5 -- reranking forced off, regardless of what the real plan would have done.

    Per `EXPERIMENT_PLAN.md` §5: "`rerank` forced false regardless of
    plan." `candidate_limit` is recomputed down to `top_k` (matching
    what the real planner itself would produce for `rerank=False`),
    since a 3x-inflated candidate pool solely exists to feed reranking
    -- keeping it inflated while reranking is off would not be "one
    variable changes at a time," it would silently change candidate
    pool size as an uncontrolled side effect.
    """

    def __init__(self, inner: Router) -> None:
        self._inner = inner

    def route(
        self, classification: TaskClassification, context: RepositoryContext
    ) -> RetrievalPlan:
        plan = self._inner.route(classification, context)
        return plan.model_copy(update={"rerank": False, "candidate_limit": plan.top_k})


class ConfidenceThresholdFallbackRouter(Router):
    """A7 -- below a confidence threshold, defer to SEMANTIC_ONLY instead of trusting the plan.

    Per `EXPERIMENT_PLAN.md` §5: "A confidence threshold... below which
    the router defers to SEMANTIC_ONLY instead of trusting a
    low-confidence classification." Per that same entry, this ablation
    "requires a small, explicitly-scoped Router extension not present
    in the current implementation" (`PROJECT_SPEC.md` §26) -- this class
    is that extension, built entirely in `evaluation/` rather than as a
    change to `tara.routing`, since nothing about it is needed by
    TARA's real, unablated routing behavior.
    """

    def __init__(self, inner: Router, confidence_threshold: float) -> None:
        """Construct the wrapper.

        Args:
            inner: The real router to delegate to when confidence meets
                the threshold.
            confidence_threshold: Below this, `SEMANTIC_ONLY` is
                returned instead of `inner`'s decision. Swept over
                `{0.3, 0.4, 0.5, 0.6, 0.7}` per `EXPERIMENT_PLAN.md` §5
                -- this class accepts any single value; the sweep
                itself is a matter of constructing one instance per
                value (see `evaluation.ablations.definitions`).
        """
        if not (0.0 <= confidence_threshold <= 1.0):
            raise ValueError(
                f"confidence_threshold must be in [0.0, 1.0], got {confidence_threshold!r}."
            )
        self._inner = inner
        self._confidence_threshold = confidence_threshold
        self._fallback_policy: RoutingPolicy = _SemanticOnlyFallbackPolicy()

    def route(
        self, classification: TaskClassification, context: RepositoryContext
    ) -> RetrievalPlan:
        if classification.confidence < self._confidence_threshold:
            fallback_router = AdaptiveRouter(policies=(self._fallback_policy,))
            return fallback_router.route(classification, context)
        return self._inner.route(classification, context)


class _SemanticOnlyFallbackPolicy(RoutingPolicy):
    """The low-confidence fallback decision: always `SEMANTIC_ONLY`.

    A private, single-purpose policy (not `evaluation.baselines.policies.FixedStrategyPolicy`,
    which is deliberately generic over any strategy) -- kept local since
    `ConfidenceThresholdFallbackRouter` is the only caller and the fallback strategy is fixed by
    `EXPERIMENT_PLAN.md` §5's own definition of this ablation, not a configurable choice.
    """

    name = "confidence_threshold_fallback"

    def applies(self, classification: TaskClassification) -> bool:
        return True

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        return RoutingDecision(
            policy_name=self.name,
            strategy=RoutingStrategy.SEMANTIC_ONLY,
            retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.SEMANTIC_ONLY],
            reason=f"Classification confidence {classification.confidence:.2f} was below the "
            f"configured threshold; deferring to SEMANTIC_ONLY rather than trusting a "
            f"low-confidence classification.",
        )
