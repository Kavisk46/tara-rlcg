"""A deterministic, task-agnostic, complexity-based routing baseline (COMPLEXITY_ROUTER).

**Purpose.** TARA's central claim (`CONTRIBUTIONS.md` §1) is that
*task-type-specific* classification is a useful routing signal -- not
merely that *some* per-query adaptivity is useful. B0-B4
(`evaluation.baselines.definitions`) test task-aware routing against
*fixed*-strategy baselines, which cannot distinguish those two claims: a
positive result against B0-B4 is equally consistent with "task-type
specifically matters" and with "any adaptive per-query signal would have
done about as well." This module adds one additional comparison point --
a router that is *adaptive* (its strategy varies per query) but
*task-agnostic* (it never consults `TaskType` or any other
`TaskClassification` field derived from it) -- so a future confirmatory
run can ask "does task-aware routing beat *this*," not only "does
task-aware routing beat a fixed strategy." This is the specific,
self-identified gap named in `docs/methodology/
Adaptive_Retrieval_Definition.md` §3 and §10 (open question 3): "That
task type, specifically, is a better routing signal than generic
query-difficulty/complexity signals ... is not established ... This is
noted as a gap in the current experimental design."

This is a scoped, minimal control, not the learned-router/learned-ranker
research program described in `docs/methodology/ROUTER_DESIGN.md` /
`RANKER_DESIGN.md`: no model is trained here, no `RTS`/`TIQS` data is
required to *build* it (only, eventually, to *evaluate* it against real
queries and ground truth, exactly like every other baseline), and its
thresholds (below) are illustrative, deterministic defaults -- not
calibrated against any real dataset, and not claimed to be.

**Router isolation, identical in kind to `evaluation.baselines.
plan_builder.build_fixed_plan`.** This module never imports or
constructs `tara.routing.router.AdaptiveRouter` or any
`tara.routing.policies.RoutingPolicy`. Unlike B0-B4 (whose strategy is a
*fixed constant*, independent of the query), this baseline's strategy is
a *function of the query text*, computed by
`evaluation.baselines.complexity_features.extract_complexity_features`
-- but that function, and the strategy-selection logic below, never read
`classification.task_type`, `.graph_required`, `.semantic_required`, or
`.lexical_required`. The `classification` parameter threaded into
`build_complexity_plan` exists solely to satisfy `RetrievalPlanner.plan`'s
signature -- identical in role to `build_fixed_plan`'s own `classification`
parameter -- consulted by `RetrievalPlanner` only for
`.reasoning_required` (rerank) and `.retriever_kind` (metadata
provenance), never for strategy selection. See
`evaluation/baselines/tests/test_complexity_router_isolation.py` for the
structural (call-count spy) and behavioral proofs.

**Why not a `BaselineId` enum member.** `evaluation.baselines.definitions
.BaselineId` is used throughout this package (`BaselineDefinition`,
`RetrievalResultRecord`, the reproducibility registry) under the
assumption that every member corresponds to either a `BaselineDefinition`
(a *fixed*, query-independent `RoutingStrategy`) or an
`UnavailableBaseline`. `evaluation.baselines.registry`'s reproducibility
report and its tests iterate `BaselineId` and expect every member to
appear in one of those two tuples; adding `COMPLEXITY_ROUTER` there
without also adding it to one of those tuples would break that existing,
passing test suite, and adding it to `BASELINE_DEFINITIONS` would be
false: this baseline's strategy is not fixed. `BASELINE_ID` below is
therefore a plain string constant, deliberately outside `BaselineId`,
leaving every existing enum member, tuple, and test untouched.
"""
from __future__ import annotations

from dataclasses import dataclass

from evaluation.baselines.complexity_features import (
    QueryComplexityFeatures,
    extract_complexity_features,
)
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.fusion.models import FusedContext
from tara.generation.models import GeneratedCode
from tara.routing.models import RetrievalPlan
from tara.routing.planner import RetrievalPlanner
from tara.routing.policies import RoutingDecision
from tara.routing.strategy import STRATEGY_RETRIEVERS, RoutingStrategy

BASELINE_ID = "COMPLEXITY_ROUTER"
"""This baseline's identifier, following the project's `BaselineId`-style naming convention
(`evaluation.baselines.definitions.BaselineId`) as a plain string rather than an enum member --
see this module's docstring, "Why not a `BaselineId` enum member," for why."""

_POLICY_NAME_PREFIX = "complexity_router_"

# Deterministic, illustrative default thresholds. Not tuned or validated against any real
# dataset -- see this module's docstring. Named as constants, not inlined, so a future
# calibration pass (once real annotated data exists) has one obvious place to change them.
SHORT_QUERY_TOKEN_THRESHOLD = 6
"""At or below this token count, a query naming at least one identifier-shaped token is
treated as a short, targeted lookup (routed to LEXICAL_ONLY)."""
LONG_QUERY_TOKEN_THRESHOLD = 12
"""At or above this token count (with no multi-clause signal), a query is treated as long
enough to warrant combining lexical and semantic search (routed to HYBRID)."""
MULTI_CLAUSE_THRESHOLD = 2
"""`clause_count` at or above this value (i.e. at least one coordinating conjunction) is
treated as a multi-part request warranting the most thorough retrieval (FULL_PIPELINE)."""


@dataclass(frozen=True)
class ComplexityRoutingDecision:
    """One complexity-based routing decision: the selected strategy, why, and the features
    that drove it -- mirroring `tara.routing.policies.RoutingDecision`'s `reason`-string
    convention, so this baseline's decisions are just as inspectable as TARA's real ones."""

    strategy: RoutingStrategy
    reason: str
    features: QueryComplexityFeatures


def select_complexity_strategy(query: str) -> ComplexityRoutingDecision:
    """Deterministically select a `RoutingStrategy` from `query`'s complexity features alone.

    Never consults `TaskType`, `TaskClassification`, or any repository
    state -- purely a function of `query`'s own text, via
    `extract_complexity_features`. Given the same `query` string, this
    function always returns the same `RoutingStrategy`.

    Args:
        query: The raw developer query.

    Returns:
        The selected strategy, a human-readable justification, and the
        underlying features, for inspection/testing.
    """
    features = extract_complexity_features(query)

    if features.token_count == 0:
        strategy = RoutingStrategy.LEXICAL_ONLY
        reason = (
            "Empty or unparseable query (0 tokens): falling back to LEXICAL_ONLY, the "
            "cheapest, dependency-free retrieval strategy."
        )
    elif features.clause_count >= MULTI_CLAUSE_THRESHOLD:
        strategy = RoutingStrategy.FULL_PIPELINE
        reason = (
            f"Query has {features.clause_count} clause(s) (>= {MULTI_CLAUSE_THRESHOLD}, "
            f"{features.clause_count - 1} coordinating conjunction(s) detected): routed to "
            "FULL_PIPELINE as the most thorough strategy for a multi-part request."
        )
    elif (
        features.identifier_like_count >= 1
        and features.token_count <= SHORT_QUERY_TOKEN_THRESHOLD
    ):
        strategy = RoutingStrategy.LEXICAL_ONLY
        reason = (
            f"Short query ({features.token_count} token(s) <= {SHORT_QUERY_TOKEN_THRESHOLD}) "
            f"naming {features.identifier_like_count} identifier-shaped token(s): routed to "
            "LEXICAL_ONLY as a targeted-lookup shape."
        )
    elif features.token_count >= LONG_QUERY_TOKEN_THRESHOLD:
        strategy = RoutingStrategy.HYBRID
        reason = (
            f"Long, single-clause query ({features.token_count} token(s) >= "
            f"{LONG_QUERY_TOKEN_THRESHOLD}): routed to HYBRID (lexical + semantic)."
        )
    else:
        strategy = RoutingStrategy.SEMANTIC_ONLY
        reason = (
            f"Query does not match any short-lookup, long-query, or multi-clause pattern "
            f"({features.token_count} token(s), {features.identifier_like_count} "
            f"identifier-shaped, {features.clause_count} clause(s)): SEMANTIC_ONLY is the safe "
            "general default."
        )

    return ComplexityRoutingDecision(strategy=strategy, reason=reason, features=features)


def build_complexity_plan(
    query: str,
    classification: TaskClassification,
    context: RepositoryContext,
) -> RetrievalPlan:
    """Build the `COMPLEXITY_ROUTER` baseline's `RetrievalPlan` for `query`.

    Mirrors `evaluation.baselines.plan_builder.build_fixed_plan`'s reuse
    of `RoutingDecision` + `RetrievalPlanner` exactly, with one
    difference: `strategy` is computed dynamically from `query`'s own
    text (`select_complexity_strategy`), not passed in as a fixed
    constant. `classification` is never read to make that choice --
    threaded through only because `RetrievalPlanner.plan` requires it
    for its own, unrelated `.reasoning_required`/`.retriever_kind`
    bookkeeping (see this module's docstring, and `RetrievalPlanner.plan`'s
    own docstring).

    Never constructs or calls `tara.routing.router.AdaptiveRouter` or any
    `tara.routing.policies.RoutingPolicy`.

    Args:
        query: The raw developer query -- the *only* input to strategy
            selection.
        classification: Passed through to `RetrievalPlanner.plan` only;
            never consulted to choose a strategy.
        context: The repository context the plan would run against,
            consulted only by `RetrievalPlanner`'s own cheap capability
            checks (e.g. dropping DENSE if no embeddings exist).

    Returns:
        The resulting `RetrievalPlan`, built by TARA's real, unmodified
        `RetrievalPlanner`.
    """
    decision = select_complexity_strategy(query)
    routing_decision = RoutingDecision(
        policy_name=f"{_POLICY_NAME_PREFIX}{decision.strategy.value}",
        strategy=decision.strategy,
        retrievers=STRATEGY_RETRIEVERS[decision.strategy],
        reason=f"{BASELINE_ID}: {decision.reason} Task classification was not consulted.",
    )
    return RetrievalPlanner().plan(routing_decision, classification, context)


@dataclass(frozen=True)
class ComplexityBaselineRunResult:
    """Everything one COMPLEXITY_ROUTER run produced.

    Mirrors `evaluation.baselines.runner.BaselineRunResult`'s shape
    exactly (`plan`, `fused_context`, `generated_code`), with
    `baseline_id: str` (`BASELINE_ID`) in place of `BaselineId`, since
    `COMPLEXITY_ROUTER` is deliberately not a `BaselineId` enum member
    (see this module's top-level docstring).
    """

    baseline_id: str
    plan: RetrievalPlan
    fused_context: FusedContext
    generated_code: GeneratedCode
