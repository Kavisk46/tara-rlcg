"""Retrieval planner: turns a `RoutingDecision` into an executable `RetrievalPlan`.

`RetrievalPlanner` owns every numeric and ordering decision the router
itself does not: deduplication, execution order, parallel execution,
reranking, top-k, candidate pool size, and graph traversal depth. It
also downgrades a `RoutingDecision` when the concrete `RepositoryContext`
can't actually support one of its retrievers (e.g. no embeddings
computed yet) -- a cheap, O(1) metadata check (dict truthiness,
`DiGraph.number_of_nodes()`), never a repository traversal or embedding
computation, keeping this stage within its <2ms budget.
"""
from __future__ import annotations

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.routing.models import RetrievalPlan
from tara.routing.policies import RoutingDecision
from tara.routing.strategy import RETRIEVER_EXECUTION_PRIORITY

_DEFAULT_TOP_K: dict[str, int] = {
    "lexical_only": 10,
    "semantic_only": 8,
    "graph_only": 10,
    "hybrid": 15,
    "graph_plus_semantic": 12,
    "lexical_plus_graph": 12,
    "full_pipeline": 20,
}
"""Keyed by `RoutingStrategy.value` rather than the enum itself so a
custom/extended `RoutingStrategy` still gets a sane fallback via
`.get(strategy.value, _FALLBACK_TOP_K)` instead of a `KeyError`.
"""

_FALLBACK_TOP_K = 10
_DEFAULT_GRAPH_DEPTH = 3
_CANDIDATE_MULTIPLIER_WHEN_RERANKING = 3


class RetrievalPlanner:
    """Turns a `RoutingDecision` into a concrete, executable `RetrievalPlan`."""

    def plan(
        self,
        decision: RoutingDecision,
        classification: TaskClassification,
        context: RepositoryContext,
    ) -> RetrievalPlan:
        """Build the final `RetrievalPlan` for a policy's `RoutingDecision`.

        Args:
            decision: The winning policy's opinion of what to retrieve with.
            classification: The classification the decision was derived
                from; consulted here only for `reasoning_required` (to
                decide reranking) and for provenance in `metadata`.
            context: The concrete repository context the plan will run
                against; consulted only for cheap capability checks
                (are embeddings present? is the graph non-trivial?).

        Returns:
            The fully configured `RetrievalPlan`.
        """
        retrievers, adjustment_note = self._apply_context_constraints(decision.retrievers, context)
        execution_order = self._order(retrievers)
        parallel = len(retrievers) > 1
        rerank = parallel or classification.reasoning_required
        top_k = _DEFAULT_TOP_K.get(decision.strategy.value, _FALLBACK_TOP_K)
        candidate_limit = top_k * _CANDIDATE_MULTIPLIER_WHEN_RERANKING if rerank else top_k
        graph_involved = RetrieverKind.GRAPH in retrievers
        graph_depth = _DEFAULT_GRAPH_DEPTH if graph_involved else 0

        reason = f"{decision.reason} {adjustment_note}".strip()

        return RetrievalPlan(
            strategy=decision.strategy,
            retrievers=list(retrievers),
            execution_order=execution_order,
            parallel=parallel,
            graph_depth=graph_depth,
            expand_neighbors=graph_involved,
            rerank=rerank,
            top_k=top_k,
            candidate_limit=candidate_limit,
            reason=reason,
            metadata={
                "policy": decision.policy_name,
                "classifier_retriever_kind": classification.retriever_kind.value,
            },
        )

    @staticmethod
    def _apply_context_constraints(
        retrievers: tuple[RetrieverKind, ...], context: RepositoryContext
    ) -> tuple[tuple[RetrieverKind, ...], str]:
        """Drop retrievers the concrete `RepositoryContext` cannot actually support.

        Falls back to `LEXICAL` if every retriever a policy asked for
        turns out to be unsupported, since lexical/keyword search over
        raw source text has no dependency on embeddings or a populated
        graph and is always the safest retriever to attempt.
        """
        adjusted = list(dict.fromkeys(retrievers))  # de-duplicate, preserve order
        notes: list[str] = []

        if RetrieverKind.DENSE in adjusted and not context.embeddings:
            adjusted.remove(RetrieverKind.DENSE)
            notes.append("Dropped DENSE: the repository context has no embeddings yet.")

        if RetrieverKind.GRAPH in adjusted and context.graph.number_of_nodes() <= 1:
            adjusted.remove(RetrieverKind.GRAPH)
            notes.append("Dropped GRAPH: the repository context graph has no files indexed.")

        if not adjusted:
            adjusted = [RetrieverKind.LEXICAL]
            notes.append("Fell back to LEXICAL: no other retriever was supported by this context.")

        return tuple(adjusted), " ".join(notes)

    @staticmethod
    def _order(retrievers: tuple[RetrieverKind, ...]) -> list[RetrieverKind]:
        """Order `retrievers` cheapest/fastest first, for sequential execution."""
        return sorted(retrievers, key=RETRIEVER_EXECUTION_PRIORITY.index)
