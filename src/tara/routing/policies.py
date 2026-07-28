"""Deterministic routing policies for the Task-Guided Adaptive Router.

Each `RoutingPolicy` is isolated: it only inspects a `TaskClassification`
and decides (a) whether it applies and (b) what `RoutingDecision` it
would produce. Policies never see each other, never see the
`RepositoryContext`, and never call an LLM -- context-aware adjustments
(e.g. downgrading a retriever the context can't actually support) are
`tara.routing.planner.RetrievalPlanner`'s job, not a policy's.

`AdaptiveRouter` evaluates `DEFAULT_POLICIES` in order and uses the
first applicable one, so **policy order is itself the conflict-
resolution mechanism**: more specific policies are listed first, and
`SemanticPolicy` is a universal catch-all last, mirroring the Task
Classifier's own SEMANTIC default for underspecified queries.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from tara.classification.models import TaskClassification
from tara.core.types import RetrieverKind, TaskType
from tara.routing.strategy import STRATEGY_RETRIEVERS, RoutingStrategy


@dataclass(frozen=True)
class RoutingDecision:
    """A single policy's opinion of which strategy and retrievers apply.

    Intentionally minimal: only *what* to retrieve with (`strategy`,
    `retrievers`) and *why* (`reason`). Every *how* decision (ordering,
    parallelism, top-k, rerank, graph depth, context-capability
    downgrades) is `RetrievalPlanner`'s responsibility, not a policy's.
    """

    policy_name: str
    strategy: RoutingStrategy
    retrievers: tuple[RetrieverKind, ...]
    reason: str


class RoutingPolicy(ABC):
    """A single, named, isolated routing rule."""

    name: str

    @abstractmethod
    def applies(self, classification: TaskClassification) -> bool:
        """Return whether this policy should decide the routing for `classification`."""
        raise NotImplementedError

    @abstractmethod
    def decide(self, classification: TaskClassification) -> RoutingDecision:
        """Produce this policy's `RoutingDecision`. Only called when `applies` returned True."""
        raise NotImplementedError


class FullPipelinePolicy(RoutingPolicy):
    """Routes to `FULL_PIPELINE`: lexical + semantic + graph, together.

    Fires either when the classifier flagged all three retrieval modes
    as required, or -- regardless of the raw flags -- whenever the task
    is a `REFACTOR`: safely refactoring a symbol needs to find it exactly
    (lexical), understand its purpose (semantic), and map everything
    that depends on it (graph) all at once, so a REFACTOR task always
    warrants the most thorough retrieval TARA can do.
    """

    name = "full_pipeline"

    def applies(self, classification: TaskClassification) -> bool:
        return classification.task_type is TaskType.REFACTOR or (
            classification.graph_required and classification.semantic_required and classification.lexical_required
        )

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        all_flags_required = (
            classification.graph_required and classification.semantic_required and classification.lexical_required
        )
        if classification.task_type is TaskType.REFACTOR and not all_flags_required:
            reason = (
                "Task type REFACTOR always routes to FULL_PIPELINE: finding the exact "
                "symbol (lexical), understanding it (semantic), and mapping its "
                "dependents (graph) are all needed before a safe refactor."
            )
        else:
            reason = "The classifier flagged graph, semantic, and lexical retrieval as all required."
        return RoutingDecision(
            policy_name=self.name,
            strategy=RoutingStrategy.FULL_PIPELINE,
            retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.FULL_PIPELINE],
            reason=reason,
        )


class GraphPolicy(RoutingPolicy):
    """Routes to a graph-involving strategy whenever `graph_required` is set.

    Owns all three graph-involving strategies short of `FULL_PIPELINE`
    (which `FullPipelinePolicy` claims at higher priority):
    `GRAPH_ONLY`, `GRAPH_PLUS_SEMANTIC`, and `LEXICAL_PLUS_GRAPH`,
    chosen by which of the other two flags also hold.
    """

    name = "graph"

    def applies(self, classification: TaskClassification) -> bool:
        return classification.graph_required

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        if classification.semantic_required and not classification.lexical_required:
            strategy = RoutingStrategy.GRAPH_PLUS_SEMANTIC
            reason = "Graph traversal is required and the classifier also flagged semantic search."
        elif classification.lexical_required and not classification.semantic_required:
            strategy = RoutingStrategy.LEXICAL_PLUS_GRAPH
            reason = "Graph traversal is required and the classifier also flagged lexical search."
        else:
            strategy = RoutingStrategy.GRAPH_ONLY
            reason = "Only graph traversal was flagged as required by the classifier."
        return RoutingDecision(
            policy_name=self.name, strategy=strategy, retrievers=STRATEGY_RETRIEVERS[strategy], reason=reason
        )


class HybridPolicy(RoutingPolicy):
    """Routes to `HYBRID`: lexical + semantic, with no graph signal at all."""

    name = "hybrid"

    def applies(self, classification: TaskClassification) -> bool:
        return (
            classification.lexical_required
            and classification.semantic_required
            and not classification.graph_required
        )

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        return RoutingDecision(
            policy_name=self.name,
            strategy=RoutingStrategy.HYBRID,
            retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.HYBRID],
            reason="Both lexical and semantic search were flagged as required, with no graph signal.",
        )


class LexicalPolicy(RoutingPolicy):
    """Routes to `LEXICAL_ONLY`: only exact/keyword search is warranted."""

    name = "lexical"

    def applies(self, classification: TaskClassification) -> bool:
        return (
            classification.lexical_required
            and not classification.semantic_required
            and not classification.graph_required
        )

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        return RoutingDecision(
            policy_name=self.name,
            strategy=RoutingStrategy.LEXICAL_ONLY,
            retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.LEXICAL_ONLY],
            reason="Only lexical/exact-match search was flagged as required by the classifier.",
        )


class SemanticPolicy(RoutingPolicy):
    """Routes to `SEMANTIC_ONLY`. TARA's universal fallback: applies to every classification.

    Placed last in `DEFAULT_POLICIES` so every more specific policy gets
    first refusal; semantic/embedding-based search is the safest
    general-purpose default, mirroring the Task Classifier's own
    SEMANTIC fallback for underspecified queries.
    """

    name = "semantic"

    def applies(self, classification: TaskClassification) -> bool:
        return True

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        if classification.semantic_required:
            reason = "Only semantic search was flagged as required by the classifier."
        else:
            reason = "No retrieval requirement was confidently flagged; semantic search is the safe default."
        return RoutingDecision(
            policy_name=self.name,
            strategy=RoutingStrategy.SEMANTIC_ONLY,
            retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.SEMANTIC_ONLY],
            reason=reason,
        )


DEFAULT_POLICIES: tuple[RoutingPolicy, ...] = (
    FullPipelinePolicy(),
    GraphPolicy(),
    HybridPolicy(),
    LexicalPolicy(),
    SemanticPolicy(),
)
"""Evaluated in this order by `AdaptiveRouter`; the first applicable policy wins."""
