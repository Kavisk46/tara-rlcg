"""Unit tests for `evaluation.baselines.complexity_router`.

Covers strategy-selection determinism, low-vs-high-complexity variation,
real `RetrievalPlanner` reuse, and -- the central property this baseline
exists to have -- complete independence from `TaskType`/`TaskClassification`
content. Structural (call-count spy) proof that `AdaptiveRouter`/
`HeuristicTaskClassifier` are never touched lives in
`test_complexity_router_isolation.py`; this file proves isolation
*behaviorally*, mirroring `test_plan_builder.py`'s
`test_plan_ignores_classification_content_entirely` for B0-B4.
"""
from __future__ import annotations

from evaluation.baselines.complexity_router import (
    BASELINE_ID,
    LONG_QUERY_TOKEN_THRESHOLD,
    MULTI_CLAUSE_THRESHOLD,
    SHORT_QUERY_TOKEN_THRESHOLD,
    build_complexity_plan,
    select_complexity_strategy,
)
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrievalStrategy, RetrieverKind, TaskType
from tara.routing.planner import RetrievalPlanner
from tara.routing.strategy import RoutingStrategy

# `rich_context`, `search_classification`, `refactor_classification` are pytest fixtures
# auto-discovered from `evaluation/baselines/tests/conftest.py`.

_SHORT_LOOKUP_QUERY = "find parse_repository"  # 2 tokens, 1 identifier-shaped -> LEXICAL_ONLY
_MULTI_CLAUSE_QUERY = (
    "explain the parser and trace the call graph and check the symbol index"
)  # clause_count 3 -> FULL_PIPELINE
_LONG_SINGLE_CLAUSE_QUERY = (
    "describe in careful detail how the repository context extraction stage builds its "
    "internal representation of the codebase"
)  # >=12 tokens, 0 conjunctions -> HYBRID
_SHORT_GENERIC_QUERY = "what happens here"  # short, no identifiers/conjunctions -> SEMANTIC_ONLY


# ============================================================================
# Baseline identifier
# ============================================================================


def test_baseline_id_is_complexity_router() -> None:
    assert BASELINE_ID == "COMPLEXITY_ROUTER"


# ============================================================================
# Deterministic strategy selection
# ============================================================================


def test_same_query_always_yields_the_same_strategy() -> None:
    first = select_complexity_strategy(_LONG_SINGLE_CLAUSE_QUERY)
    second = select_complexity_strategy(_LONG_SINGLE_CLAUSE_QUERY)
    assert first.strategy == second.strategy
    assert first.features == second.features


def test_short_identifier_bearing_query_routes_to_lexical_only() -> None:
    decision = select_complexity_strategy(_SHORT_LOOKUP_QUERY)
    assert decision.features.token_count <= SHORT_QUERY_TOKEN_THRESHOLD
    assert decision.strategy is RoutingStrategy.LEXICAL_ONLY


def test_multi_clause_query_routes_to_full_pipeline() -> None:
    decision = select_complexity_strategy(_MULTI_CLAUSE_QUERY)
    assert decision.features.clause_count >= MULTI_CLAUSE_THRESHOLD
    assert decision.strategy is RoutingStrategy.FULL_PIPELINE


def test_long_single_clause_query_routes_to_hybrid() -> None:
    decision = select_complexity_strategy(_LONG_SINGLE_CLAUSE_QUERY)
    assert decision.features.token_count >= LONG_QUERY_TOKEN_THRESHOLD
    assert decision.features.clause_count < MULTI_CLAUSE_THRESHOLD
    assert decision.strategy is RoutingStrategy.HYBRID


def test_short_generic_query_routes_to_semantic_only_default() -> None:
    decision = select_complexity_strategy(_SHORT_GENERIC_QUERY)
    assert decision.strategy is RoutingStrategy.SEMANTIC_ONLY


def test_empty_query_falls_back_to_lexical_only() -> None:
    decision = select_complexity_strategy("")
    assert decision.strategy is RoutingStrategy.LEXICAL_ONLY


# ============================================================================
# Low complexity vs. high complexity produce different plans
# ============================================================================


def test_low_and_high_complexity_queries_yield_different_strategies() -> None:
    low = select_complexity_strategy(_SHORT_LOOKUP_QUERY)
    high = select_complexity_strategy(_MULTI_CLAUSE_QUERY)
    assert low.strategy != high.strategy


def test_low_and_high_complexity_queries_yield_different_plans(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    low_plan = build_complexity_plan(_SHORT_LOOKUP_QUERY, search_classification, rich_context)
    high_plan = build_complexity_plan(_MULTI_CLAUSE_QUERY, search_classification, rich_context)
    assert low_plan.strategy != high_plan.strategy
    assert low_plan.retrievers != high_plan.retrievers


# ============================================================================
# Reason strings are inspectable, like every other TARA/baseline routing decision
# ============================================================================


def test_reason_discloses_baseline_identity_and_that_classification_was_not_consulted() -> None:
    decision = select_complexity_strategy(_MULTI_CLAUSE_QUERY)
    assert "clause" in decision.reason.lower()


def test_plan_reason_discloses_task_classification_was_not_consulted(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    plan = build_complexity_plan(_MULTI_CLAUSE_QUERY, search_classification, rich_context)
    assert BASELINE_ID in plan.reason
    assert "Task classification was not consulted" in plan.reason


# ============================================================================
# TaskType / TaskClassification independence (behavioral proof)
# ============================================================================


def test_plan_is_identical_across_wildly_different_classifications(
    rich_context: RepositoryContext,
    search_classification: TaskClassification,
    refactor_classification: TaskClassification,
) -> None:
    """The decisive behavioral proof for this baseline, mirroring
    `test_plan_builder.test_plan_ignores_classification_content_entirely`: a bare SEARCH
    classification and a REFACTOR classification with every flag set (which, under TARA's
    real `DEFAULT_POLICIES`, would route to two different strategies) must produce the exact
    same COMPLEXITY_ROUTER plan for the same query text, since only the query text may
    influence this baseline's strategy."""
    plan_a = build_complexity_plan(_MULTI_CLAUSE_QUERY, search_classification, rich_context)
    plan_b = build_complexity_plan(_MULTI_CLAUSE_QUERY, refactor_classification, rich_context)
    assert plan_a.strategy == plan_b.strategy
    assert plan_a.retrievers == plan_b.retrievers


def test_strategy_selection_function_does_not_accept_a_classification_argument() -> None:
    """Structural guarantee, not just a behavioral one: `select_complexity_strategy`'s own
    signature has no `classification`/`TaskClassification` parameter at all -- there is no
    argument through which a caller could even attempt to pass task-type information in."""
    import inspect

    signature = inspect.signature(select_complexity_strategy)
    assert list(signature.parameters) == ["query"]


# ============================================================================
# Uses the real RetrievalPlanner
# ============================================================================


def test_plan_builder_delegates_to_the_real_retrieval_planner(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    """Cross-checks `build_complexity_plan`'s output against `RetrievalPlanner` invoked
    directly with an equivalent hand-built `RoutingDecision` -- if COMPLEXITY_ROUTER used its
    own, separate planning logic instead of reusing `RetrievalPlanner`, this would diverge
    (different top_k table, different execution-order rule, different rerank/candidate-limit
    logic, different context-capability-downgrade behavior)."""
    from tara.routing.policies import RoutingDecision
    from tara.routing.strategy import STRATEGY_RETRIEVERS

    decision = select_complexity_strategy(_LONG_SINGLE_CLAUSE_QUERY)
    plan = build_complexity_plan(_LONG_SINGLE_CLAUSE_QUERY, search_classification, rich_context)

    expected = RetrievalPlanner().plan(
        RoutingDecision(
            policy_name="irrelevant-for-this-comparison",
            strategy=decision.strategy,
            retrievers=STRATEGY_RETRIEVERS[decision.strategy],
            reason="irrelevant-for-this-comparison",
        ),
        search_classification,
        rich_context,
    )

    assert plan.strategy == expected.strategy
    assert plan.retrievers == expected.retrievers
    assert plan.execution_order == expected.execution_order
    assert plan.parallel == expected.parallel
    assert plan.top_k == expected.top_k
    assert plan.candidate_limit == expected.candidate_limit
    assert plan.graph_depth == expected.graph_depth


def test_plan_respects_retrieval_planners_context_capability_downgrade() -> None:
    """A repository context with no embeddings and a trivial graph must still cause
    `RetrievalPlanner`'s own capability-downgrade logic to fire for COMPLEXITY_ROUTER exactly
    as it would for any other plan -- proving this baseline gets no special-cased treatment
    from the planner."""
    import networkx as nx

    from tara.context.models import NodeType, RepositoryContext, build_repository_node_id
    from tara.context.symbol_index import SymbolIndex

    graph = nx.DiGraph()
    repo_id = build_repository_node_id("/repo")
    graph.add_node(repo_id, type=NodeType.REPOSITORY.value, name="/repo", file_path=None)
    bare_context = RepositoryContext(
        root_path="/repo",
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        embeddings={},
        embedding_dimension=None,
        file_count=0,
        symbol_count=0,
    )
    classification = TaskClassification(
        task_type=TaskType.SEARCH,
        retriever_kind=RetrievalStrategy.LEXICAL,
        confidence=1.0,
    )

    plan = build_complexity_plan(_MULTI_CLAUSE_QUERY, classification, bare_context)
    # _MULTI_CLAUSE_QUERY selects FULL_PIPELINE (lexical+dense+graph), but this bare context
    # supports neither dense (no embeddings) nor graph (trivial graph) -- RetrievalPlanner
    # must downgrade both, leaving only lexical.
    assert plan.retrievers == [RetrieverKind.LEXICAL]
    assert "Dropped DENSE" in plan.reason
    assert "Dropped GRAPH" in plan.reason
