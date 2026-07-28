"""Task-Guided Adaptive Router: the fourth stage of the TARA pipeline.

`AdaptiveRouter` decides WHAT to retrieve with and HOW -- never
retrieval itself. It orchestrates two injected collaborators: an
ordered set of `RoutingPolicy`s (WHAT: which strategy and retriever
kinds -- the first applicable policy wins) and a `RetrievalPlanner`
(HOW: ordering, parallelism, top-k, graph depth, reranking, and
context-capability downgrades). This class contains no policy or
planning logic of its own.
"""
from __future__ import annotations

import time

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.exceptions import PlanningError, PolicyError, RoutingError
from tara.core.logging import get_logger
from tara.interfaces.router import Router
from tara.routing.models import RetrievalPlan
from tara.routing.planner import RetrievalPlanner
from tara.routing.policies import DEFAULT_POLICIES, RoutingDecision, RoutingPolicy

logger = get_logger(__name__)


class AdaptiveRouter(Router):
    """Deterministic, policy-driven `Router`.

    Every collaborator is injected through the constructor rather than
    instantiated internally, so a caller can supply an extended or
    reordered policy set, or a customized planner, without changing this
    class.
    """

    def __init__(
        self,
        policies: tuple[RoutingPolicy, ...] = DEFAULT_POLICIES,
        planner: RetrievalPlanner | None = None,
    ) -> None:
        """Construct the router.

        Args:
            policies: Ordered policies to evaluate; the first whose
                `applies()` returns True decides the routing. Defaults
                to `DEFAULT_POLICIES`.
            planner: Turns the winning policy's `RoutingDecision` into a
                `RetrievalPlan`. Defaults to a plain `RetrievalPlanner()`.
        """
        self._policies = policies
        self._planner = planner or RetrievalPlanner()

    def route(self, classification: TaskClassification, context: RepositoryContext) -> RetrievalPlan:
        """See `Router.route`."""
        start = time.perf_counter()
        decision = self._select_policy(classification)

        try:
            plan = self._planner.plan(decision, classification, context)
        except RoutingError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize unexpected planner failures
            raise PlanningError(f"Failed to build a retrieval plan: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Routed task_type=%s -> strategy=%s retrievers=%s parallel=%s graph_depth=%d "
            "rerank=%s reason=%r (%.3fms)",
            classification.task_type.value,
            plan.strategy.value,
            [r.value for r in plan.retrievers],
            plan.parallel,
            plan.graph_depth,
            plan.rerank,
            plan.reason,
            elapsed_ms,
        )
        return plan

    def _select_policy(self, classification: TaskClassification) -> RoutingDecision:
        """Return the first applicable policy's `RoutingDecision`.

        Raises:
            PolicyError: If a policy's `applies` or `decide` raises.
            RoutingError: If no policy in `self._policies` applies.
        """
        for policy in self._policies:
            try:
                applies = policy.applies(classification)
            except Exception as exc:  # noqa: BLE001 - identify the culprit policy
                raise PolicyError(f"Policy '{policy.name}' failed to evaluate: {exc}") from exc

            if not applies:
                continue

            logger.debug("Policy %r applied for task_type=%s", policy.name, classification.task_type.value)
            try:
                return policy.decide(classification)
            except Exception as exc:  # noqa: BLE001 - identify the culprit policy
                raise PolicyError(f"Policy '{policy.name}' failed to decide: {exc}") from exc

        raise RoutingError(
            "No routing policy applied to this classification; ensure a catch-all policy is registered."
        )
