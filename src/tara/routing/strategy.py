"""Routing strategy vocabulary for the Task-Guided Adaptive Router.

Purely declarative: the `RoutingStrategy` enum, which `RetrieverKind`s
each strategy implies, and a fixed cost-ordering of retriever kinds.
No decision-making logic lives here -- `tara.routing.policies` decides
*which* strategy applies to a query, and `tara.routing.planner` decides
*how* to execute it; this module is the shared vocabulary both depend on.
"""
from __future__ import annotations

from enum import Enum

from tara.core.types import RetrieverKind


class RoutingStrategy(str, Enum):
    """The retrieval strategy the router selects for a `RetrievalPlan`.

    A strict refinement of `tara.core.types.RetrievalStrategy` (the Task
    Classifier's coarser LEXICAL/SEMANTIC/GRAPH/HYBRID recommendation):
    the router additionally distinguishes which *pair* of signals drove
    a HYBRID-shaped decision (`GRAPH_PLUS_SEMANTIC` vs
    `LEXICAL_PLUS_GRAPH` vs plain `HYBRID`) and adds `FULL_PIPELINE` for
    when all three retrieval modes are warranted at once.
    """

    LEXICAL_ONLY = "lexical_only"
    SEMANTIC_ONLY = "semantic_only"
    GRAPH_ONLY = "graph_only"
    HYBRID = "hybrid"
    GRAPH_PLUS_SEMANTIC = "graph_plus_semantic"
    LEXICAL_PLUS_GRAPH = "lexical_plus_graph"
    FULL_PIPELINE = "full_pipeline"


STRATEGY_RETRIEVERS: dict[RoutingStrategy, tuple[RetrieverKind, ...]] = {
    RoutingStrategy.LEXICAL_ONLY: (RetrieverKind.LEXICAL,),
    RoutingStrategy.SEMANTIC_ONLY: (RetrieverKind.DENSE,),
    RoutingStrategy.GRAPH_ONLY: (RetrieverKind.GRAPH,),
    RoutingStrategy.HYBRID: (RetrieverKind.LEXICAL, RetrieverKind.DENSE),
    RoutingStrategy.GRAPH_PLUS_SEMANTIC: (RetrieverKind.GRAPH, RetrieverKind.DENSE),
    RoutingStrategy.LEXICAL_PLUS_GRAPH: (RetrieverKind.LEXICAL, RetrieverKind.GRAPH),
    RoutingStrategy.FULL_PIPELINE: (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH),
}
"""Which `RetrieverKind`s a given `RoutingStrategy` implies.

The single source of truth for strategy/retriever membership: every
`RoutingPolicy` looks up its retriever set here rather than listing
`RetrieverKind`s inline, so the mapping can never drift out of sync
across policies.
"""

RETRIEVER_EXECUTION_PRIORITY: tuple[RetrieverKind, ...] = (
    RetrieverKind.LEXICAL,
    RetrieverKind.GRAPH,
    RetrieverKind.DENSE,
    RetrieverKind.API,
    RetrieverKind.STATIC_ANALYSIS,
)
"""Cheapest/fastest first. Used by `RetrievalPlanner` to order a plan's
`execution_order`: lexical/keyword lookups are near-free, graph
traversal over an already-built graph is cheap, dense/semantic search
is the most expensive per-query step (query embedding + similarity
search), and API/static-analysis retrievers (not yet implemented) are
assumed costliest.
"""
