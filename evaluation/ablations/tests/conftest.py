"""Shared fixtures/helpers for the `evaluation.ablations` test suite."""
from __future__ import annotations

import networkx as nx
import pytest

from tara.classification.models import TaskClassification
from tara.context.models import NodeType, RepositoryContext, build_repository_node_id
from tara.context.symbol_index import SymbolIndex
from tara.core.types import RetrievalStrategy, TaskType

ROOT_PATH = "/repo"


def make_classification(
    *,
    task_type: TaskType = TaskType.SEARCH,
    retriever_kind: RetrievalStrategy = RetrievalStrategy.LEXICAL,
    graph_required: bool = False,
    semantic_required: bool = False,
    lexical_required: bool = False,
    reasoning_required: bool = False,
    confidence: float = 1.0,
) -> TaskClassification:
    return TaskClassification(
        task_type=task_type,
        retriever_kind=retriever_kind,
        confidence=confidence,
        graph_required=graph_required,
        semantic_required=semantic_required,
        lexical_required=lexical_required,
        reasoning_required=reasoning_required,
    )


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
