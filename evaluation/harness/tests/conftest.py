"""Shared fixtures/helpers for the `evaluation.harness` test suite.

No real repository, no real LLM -- mirrors
`evaluation/baselines/tests/conftest.py`'s identical synthetic-fixture
pattern, kept self-contained (not imported cross-package) so each
package's tests remain independently readable.
"""
from __future__ import annotations

from collections.abc import Mapping

import networkx as nx
import pytest

from tara.classification.models import TaskClassification
from tara.context.models import NodeType, RepositoryContext, build_repository_node_id
from tara.context.symbol_index import SymbolIndex
from tara.core.exceptions import RetrievalError
from tara.core.types import RetrievalStrategy, RetrieverKind, TaskType
from tara.interfaces.retriever import Retriever
from tara.retrieval.models import RetrievalScore, RetrievedChunk, RetrievedContext
from tara.retrieval.orchestrator import RetrievalOrchestrator
from tara.routing.models import RetrievalPlan

ROOT_PATH = "/repo"


class _FakeRetriever(Retriever):
    """Returns one fixed, non-empty chunk tagged with its own kind."""

    def __init__(self, kind: RetrieverKind, chunk_id: str | None = None) -> None:
        self.kind = kind
        self.chunk_id = chunk_id or f"file::app.py::{kind.value}_symbol::1"
        self.call_count = 0

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        self.call_count += 1
        chunk = RetrievedChunk(
            chunk_id=self.chunk_id,
            retriever_kind=self.kind,
            node_type=NodeType.FUNCTION,
            name=f"{self.kind.value}_symbol",
            file_path="app.py",
            content=f"def {self.kind.value}_symbol(): ...",
            score=RetrievalScore(raw_score=1.0, normalized_score=0.9),
        )
        return RetrievedContext(
            retriever_kind=self.kind, query=query, chunks=[chunk], total_candidates=1
        )


class _BrokenRetriever(Retriever):
    """Always raises -- used to prove per-query error isolation."""

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        raise RetrievalError("simulated retriever failure")


def make_orchestrator(
    *kinds: RetrieverKind,
) -> tuple[RetrievalOrchestrator, dict[RetrieverKind, _FakeRetriever]]:
    fakes = {kind: _FakeRetriever(kind) for kind in kinds}
    mapping: Mapping[RetrieverKind, Retriever] = fakes
    return RetrievalOrchestrator(mapping), fakes


@pytest.fixture
def rich_context() -> RepositoryContext:
    graph = nx.DiGraph()
    repo_id = build_repository_node_id(ROOT_PATH)
    graph.add_node(repo_id, type=NodeType.REPOSITORY.value, name=ROOT_PATH, file_path=None)
    graph.add_node("file::app.py", type=NodeType.FILE.value, name="app.py", file_path="app.py")
    graph.add_edge(repo_id, "file::app.py")
    return RepositoryContext(
        root_path=ROOT_PATH,
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        embeddings={"file::app.py": [0.1, 0.2, 0.3]},
        embedding_dimension=3,
        file_count=1,
        symbol_count=0,
    )


@pytest.fixture
def search_classification() -> TaskClassification:
    return TaskClassification(
        task_type=TaskType.SEARCH,
        retriever_kind=RetrievalStrategy.LEXICAL,
        confidence=1.0,
    )
