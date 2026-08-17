"""Builds a fixed `RetrievalPlan` for a baseline, entirely bypassing TARA's
adaptive routing layer: no `AdaptiveRouter`, no `RoutingPolicy` (fixed or
otherwise), no `TaskClassifier` call.

**This module replaces an earlier version of this package that built
baselines via `AdaptiveRouter(policies=(FixedStrategyPolicy(strategy),))`**
(see `BASELINE_DISCREPANCIES.md`, "Router isolation: why this package no
longer touches `AdaptiveRouter`," for the full history). That earlier
approach reused `AdaptiveRouter`'s policy-selection loop with a
single, always-applicable policy -- behaviorally fixed, but still, in
this milestone's own words, exactly the pattern its instructions name as
invalid: *"Even if the router happens to select semantic retrieval, that
is NOT a valid fixed semantic baseline."* A router-call-count spy proves
the distinction: the earlier approach called `AdaptiveRouter.route()`
once per baseline run; this module never does.

`RetrievalPlanner` (`tara.routing.planner`) is still reused directly, and
deliberately: it is not "the adaptive router" or "a routing policy" in
any sense the isolation requirement is about -- it performs no strategy
*selection* at all (its own docstring: "owns every numeric and ordering
decision the router itself does not"). Feeding it a hand-built
`RoutingDecision` -- a plain, frozen dataclass, i.e. inert data, never a
call to any policy's `.decide()` -- reuses TARA's real top-k /
execution-order / rerank / context-capability-downgrade logic for a
baseline's plan without involving anything that decides *which*
strategy to use. This is also what keeps this module from having to
duplicate `RetrievalPlanner`'s own numeric tables (`_DEFAULT_TOP_K`,
`RETRIEVER_EXECUTION_PRIORITY`) -- reuse, not reimplementation.
"""
from __future__ import annotations

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.routing.models import RetrievalPlan
from tara.routing.planner import RetrievalPlanner
from tara.routing.policies import RoutingDecision
from tara.routing.strategy import STRATEGY_RETRIEVERS, RoutingStrategy

_POLICY_NAME_PREFIX = "baseline_fixed_"


def build_fixed_plan(
    strategy: RoutingStrategy,
    classification: TaskClassification,
    context: RepositoryContext,
) -> RetrievalPlan:
    """Build a `RetrievalPlan` for `strategy`, unconditionally -- no routing decision is made.

    Args:
        strategy: The `RoutingStrategy` this baseline always uses,
            regardless of `classification`'s content.
        classification: Passed through only to `RetrievalPlanner.plan`,
            which reads `.reasoning_required` (for whether to rerank) and
            `.retriever_kind` (recorded in `RetrievalPlan.metadata` for
            observability only). Never inspected here, and never used to
            choose `strategy` -- `strategy` is this function's own,
            fixed argument.
        context: The repository context the plan would run against,
            consulted only for `RetrievalPlanner`'s cheap capability
            checks (e.g. dropping DENSE if no embeddings exist).

    Returns:
        The `RetrievalPlan` `RetrievalPlanner` would build for a
        `RoutingDecision` fixed to `strategy` -- identical in shape to
        what `AdaptiveRouter` would produce *if* some policy chose
        `strategy`, but built without asking anything to choose.
    """
    decision = RoutingDecision(
        policy_name=f"{_POLICY_NAME_PREFIX}{strategy.value}",
        strategy=strategy,
        retrievers=STRATEGY_RETRIEVERS[strategy],
        reason=f"Baseline: every query is routed to {strategy.value} regardless of "
        "classification. No adaptive routing decision was made -- this plan is fixed "
        "configuration, not a Router/RoutingPolicy output.",
    )
    return RetrievalPlanner().plan(decision, classification, context)
