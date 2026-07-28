"""Shared fixtures for the `tara.routing` test suite."""
from __future__ import annotations

from collections.abc import Callable

import networkx as nx
import pytest

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.context.symbol_index import SymbolIndex
from tara.core.types import RetrievalStrategy, TaskType


def _make_graph(file_count: int) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node("repository::/repo", type="repository", name="/repo")
    for i in range(file_count):
        graph.add_node(f"file::file{i}.py", type="file", name=f"file{i}.py", file_path=f"file{i}.py")
    return graph


@pytest.fixture
def rich_context() -> RepositoryContext:
    """A `RepositoryContext` with both a non-trivial graph and embeddings -- nothing gets downgraded."""
    graph = _make_graph(5)
    return RepositoryContext(
        root_path="/repo",
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        embeddings={"file::file0.py": [0.1, 0.2, 0.3]},
        embedding_dimension=3,
        file_count=5,
        symbol_count=0,
    )


@pytest.fixture
def bare_context() -> RepositoryContext:
    """A `RepositoryContext` with only the repository root node and no embeddings."""
    graph = nx.DiGraph()
    graph.add_node("repository::/repo", type="repository", name="/repo")
    return RepositoryContext(
        root_path="/repo",
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        embeddings={},
        file_count=0,
        symbol_count=0,
    )


@pytest.fixture
def classification_factory() -> Callable[..., TaskClassification]:
    """Build a `TaskClassification` directly, without running the real classifier."""

    def _make(
        task_type: TaskType = TaskType.UNKNOWN,
        retriever_kind: RetrievalStrategy = RetrievalStrategy.SEMANTIC,
        graph_required: bool = False,
        semantic_required: bool = False,
        lexical_required: bool = False,
        reasoning_required: bool = False,
        detected_symbols: list[str] | None = None,
    ) -> TaskClassification:
        return TaskClassification(
            task_type=task_type,
            retriever_kind=retriever_kind,
            confidence=1.0,
            graph_required=graph_required,
            semantic_required=semantic_required,
            lexical_required=lexical_required,
            reasoning_required=reasoning_required,
            detected_symbols=detected_symbols or [],
        )

    return _make
