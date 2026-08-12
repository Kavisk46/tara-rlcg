"""Abstract interface for a single retrieval-stage retriever.

`Retriever` is the shared contract every concrete retriever kind
(`LexicalRetriever`, `DenseRetriever`, `GraphRetriever`, and any future
`APIRetriever` / `StaticAnalyzer`) implements, per `RetrieverKind`
(`tara.core.types`). Defining it as an ABC lets the (future) retrieval
orchestrator depend on "a retriever" rather than on any concrete
retriever class, mirroring `RepositoryParser`, `ContextExtractor`,
`TaskClassifier`, and `Router`.

This module defines the contract only. No concrete retriever is
implemented here, and this module has no knowledge of BM25, embeddings,
or graph traversal -- see `tara.retrieval` for concrete implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from tara.context.models import RepositoryContext
from tara.retrieval.models import RetrievedContext
from tara.routing.models import RetrievalPlan


class Retriever(ABC):
    """Contract for executing one retriever kind against a `RetrievalPlan`."""

    @abstractmethod
    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        """Fetch candidate context chunks for `query`, per `plan`.

        A concrete `Retriever` performs no strategy selection of its
        own: whether this retriever should run at all, and with what
        `top_k`/`candidate_limit`, was already decided upstream by the
        Task-Guided Adaptive Router and is handed down via `plan`. This
        method's only job is to execute that decision against `context`
        and return a ranked, deduplicated `RetrievedContext`.

        Args:
            query: The original developer query text. Concrete
                retrievers may prefer a derived signal (e.g. extracted
                keywords or detected symbols) over this raw string where
                appropriate, but `query` is always the fallback input.
            plan: The executable retrieval plan produced by the Router,
                e.g. `plan.top_k`, `plan.candidate_limit`,
                `plan.graph_depth`. A retriever must not exceed
                `plan.candidate_limit` results in the returned
                `RetrievedContext` -- this is the pre-fusion candidate
                pool `RetrievalPlan.candidate_limit` is defined to hold;
                final reranking and truncation down to `plan.top_k` is
                Context Fusion's responsibility (a later pipeline
                stage), not an individual retriever's. This is the
                convention `LexicalRetriever` already establishes.
            context: The repository's semantic context (graph, symbol
                index, embeddings) this retriever searches over.

        Returns:
            A `RetrievedContext` tagged with this retriever's
            `RetrieverKind`, containing zero or more ranked
            `RetrievedChunk` results truncated to `plan.candidate_limit`.

        Raises:
            RetrievalError: If retrieval cannot be completed, e.g. an
                index fails to build or a required `context` capability
                is missing in a way the caller (the retrieval
                orchestrator) did not already guard against.
        """
        raise NotImplementedError
