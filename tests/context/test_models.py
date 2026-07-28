"""Unit tests for `tara.context.models`."""
from __future__ import annotations

import networkx as nx

from tara.context.models import (
    RepositoryContext,
    build_file_node_id,
    build_repository_node_id,
    build_symbol_node_id,
)
from tara.context.symbol_index import SymbolIndex


def test_build_repository_node_id_is_deterministic() -> None:
    assert build_repository_node_id("/repo") == build_repository_node_id("/repo")


def test_build_repository_node_id_differs_by_root_path() -> None:
    assert build_repository_node_id("/repo-a") != build_repository_node_id("/repo-b")


def test_build_file_node_id_uses_relative_path() -> None:
    assert build_file_node_id("app.py") == "file::app.py"


def test_build_symbol_node_id_is_unique_per_parent_and_line() -> None:
    top_level = build_symbol_node_id("app.py", "greet", None, 5)
    nested = build_symbol_node_id("app.py", "greet", "Greeter", 10)
    assert top_level != nested


def test_build_symbol_node_id_is_deterministic() -> None:
    first = build_symbol_node_id("app.py", "greet", "Greeter", 10)
    second = build_symbol_node_id("app.py", "greet", "Greeter", 10)
    assert first == second


def test_repository_context_holds_graph_and_symbol_index() -> None:
    graph = nx.DiGraph()
    graph.add_node("file::a.py", type="file", name="a.py")
    index = SymbolIndex.from_graph(graph)

    context = RepositoryContext(
        root_path="/repo",
        commit_sha="abc123",
        graph=graph,
        symbol_index=index,
        embeddings={"file::a.py": [0.1, 0.2]},
        embedding_dimension=2,
        embedding_model_name="fake-model",
        file_count=1,
        symbol_count=0,
    )

    assert context.graph.number_of_nodes() == 1
    assert context.symbol_index.get_by_id("file::a.py") is not None
    assert context.commit_sha == "abc123"


def test_repository_context_defaults_to_empty_embeddings() -> None:
    graph = nx.DiGraph()
    context = RepositoryContext(
        root_path="/repo",
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
    )

    assert context.embeddings == {}
    assert context.embedding_dimension is None
    assert context.commit_sha is None


def test_graph_summary_is_json_serializable_shape() -> None:
    graph = nx.DiGraph()
    graph.add_node("a", type="file")
    graph.add_node("b", type="class")
    graph.add_edge("a", "b", relation="defines")
    index = SymbolIndex.from_graph(graph)

    context = RepositoryContext(
        root_path="/repo",
        graph=graph,
        symbol_index=index,
        embeddings={"b": [0.1, 0.2, 0.3]},
        embedding_dimension=3,
        file_count=1,
        symbol_count=1,
    )

    summary = context.graph_summary()
    assert summary == {
        "node_count": 2,
        "edge_count": 1,
        "file_count": 1,
        "symbol_count": 1,
        "embedded_symbol_count": 1,
        "embedding_dimension": 3,
    }
