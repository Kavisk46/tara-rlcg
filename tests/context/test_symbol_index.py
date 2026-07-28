"""Unit tests for `SymbolIndex` and `SymbolIndexBuilder`."""
from __future__ import annotations

import networkx as nx

from tara.context.symbol_index import SymbolIndex, SymbolIndexBuilder


def _sample_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node("file::app.py", type="file", name="app.py", file_path="app.py")
    graph.add_node("file::app.py::Greeter::5", type="class", name="Greeter", file_path="app.py")
    graph.add_node("file::app.py::Greeter.greet::7", type="method", name="greet", file_path="app.py")
    graph.add_node("file::utils.py::add::1", type="function", name="add", file_path="utils.py")
    return graph


def test_from_graph_indexes_every_node() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    assert len(index) == 4


def test_get_by_id_returns_matching_record() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    record = index.get_by_id("file::app.py::Greeter::5")
    assert record is not None
    assert record.name == "Greeter"
    assert record.node_type == "class"


def test_get_by_id_returns_none_for_unknown_id() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    assert index.get_by_id("does-not-exist") is None


def test_get_by_name_returns_all_matches() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    matches = index.get_by_name("greet")
    assert len(matches) == 1
    assert matches[0].file_path == "app.py"


def test_get_by_name_returns_empty_list_for_unknown_name() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    assert index.get_by_name("does-not-exist") == []


def test_get_by_file_returns_only_that_files_symbols() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    matches = index.get_by_file("app.py")
    assert {m.name for m in matches} == {"app.py", "Greeter", "greet"}


def test_contains_and_iteration() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    assert "file::utils.py::add::1" in index
    assert len(list(index)) == 4


def test_index_does_not_expose_raw_dictionaries() -> None:
    index = SymbolIndex.from_graph(_sample_graph())
    assert not hasattr(index, "by_id")
    assert not hasattr(index, "by_name")
    assert not hasattr(index, "by_file")


def test_symbol_index_builder_delegates_to_from_graph() -> None:
    graph = _sample_graph()
    index = SymbolIndexBuilder().build(graph)
    assert len(index) == graph.number_of_nodes()
