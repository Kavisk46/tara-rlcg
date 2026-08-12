"""Unit tests for `tara.interfaces.retriever.Retriever`.

`Retriever` has no concrete implementation yet (`LexicalRetriever` is a
planned module, not implemented as of this milestone -- see
`tara.retrieval.lexical_retriever`'s module docstring), so these tests
exercise the ABC contract itself via a minimal, test-local fake
implementation, exactly the way `tests/routing/test_router.py` verifies
`Router` via the real `AdaptiveRouter`. No BM25, embedding, or graph
logic is exercised here.
"""
from __future__ import annotations

import networkx as nx
import pytest

from tara.context.models import RepositoryContext
from tara.context.symbol_index import SymbolIndex
from tara.core.exceptions import RetrievalError
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.models import RetrievedContext
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy


def _make_plan(retrievers: list[RetrieverKind] | None = None) -> RetrievalPlan:
    retrievers = retrievers if retrievers is not None else [RetrieverKind.LEXICAL]
    return RetrievalPlan(
        strategy=RoutingStrategy.LEXICAL_ONLY,
        retrievers=retrievers,
        execution_order=retrievers,
        parallel=False,
        rerank=False,
        top_k=10,
        candidate_limit=10,
        reason="test",
    )


@pytest.fixture
def empty_context() -> RepositoryContext:
    graph = nx.DiGraph()
    graph.add_node("repository::/empty-repo", type="repository", name="/empty-repo")
    return RepositoryContext(
        root_path="/empty-repo",
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        file_count=0,
        symbol_count=0,
    )


class _StubRetriever(Retriever):
    """A minimal, fully-fake `Retriever` used only to exercise the ABC contract."""

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        return RetrievedContext(
            retriever_kind=RetrieverKind.LEXICAL, query=query, chunks=[], total_candidates=0
        )


class _BrokenRetriever(Retriever):
    """A `Retriever` whose `retrieve` always fails, to test error propagation."""

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        raise RetrievalError("stub failure")


def test_retriever_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Retriever()  # type: ignore[abstract]


def test_subclass_missing_retrieve_cannot_be_instantiated() -> None:
    class IncompleteRetriever(Retriever):
        pass

    with pytest.raises(TypeError):
        IncompleteRetriever()  # type: ignore[abstract]


def test_concrete_subclass_is_instance_of_retriever() -> None:
    retriever = _StubRetriever()
    assert isinstance(retriever, Retriever)


def test_concrete_subclass_retrieve_matches_expected_signature(
    empty_context: RepositoryContext,
) -> None:
    retriever = _StubRetriever()
    result = retriever.retrieve("find parse_repository", _make_plan(), empty_context)

    assert isinstance(result, RetrievedContext)
    assert result.retriever_kind is RetrieverKind.LEXICAL
    assert result.query == "find parse_repository"
    assert result.chunks == []
    assert result.total_candidates == 0


def test_retrieve_can_raise_retrieval_error(empty_context: RepositoryContext) -> None:
    retriever = _BrokenRetriever()
    with pytest.raises(RetrievalError, match="stub failure"):
        retriever.retrieve("anything", _make_plan(), empty_context)
