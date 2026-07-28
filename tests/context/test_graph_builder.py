"""Unit tests for `GraphBuilder`."""
from __future__ import annotations

from pathlib import Path

from git import Repo

from tara.context.graph_builder import GraphBuilder
from tara.context.models import EdgeRelation, NodeType, build_file_node_id, build_repository_node_id
from tara.parsing.models import ParsedRepository
from tara.parsing.repository_parser import TreeSitterRepositoryParser


def test_build_creates_repository_node(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    repo_id = build_repository_node_id(parsed_sample_repository.root_path)

    assert repo_id in graph.nodes
    assert graph.nodes[repo_id]["type"] == NodeType.REPOSITORY.value


def test_build_creates_file_nodes_with_contains_edges(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    repo_id = build_repository_node_id(parsed_sample_repository.root_path)
    app_file_id = build_file_node_id("app.py")

    assert app_file_id in graph.nodes
    assert graph.nodes[app_file_id]["type"] == NodeType.FILE.value
    assert graph.nodes[app_file_id]["language"] == "python"
    assert graph.has_edge(repo_id, app_file_id)
    assert graph.edges[repo_id, app_file_id]["relation"] == EdgeRelation.CONTAINS.value


def test_build_creates_class_function_and_method_nodes(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    node_types = {data["type"] for _, data in graph.nodes(data=True)}

    assert NodeType.CLASS.value in node_types
    assert NodeType.FUNCTION.value in node_types
    assert NodeType.METHOD.value in node_types

    class_names = {d["name"] for _, d in graph.nodes(data=True) if d["type"] == NodeType.CLASS.value}
    assert "Greeter" in class_names


def test_build_creates_defines_edge_for_top_level_function(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    app_file_id = build_file_node_id("app.py")
    main_node = next(n for n, d in graph.nodes(data=True) if d["name"] == "main")

    assert graph.has_edge(app_file_id, main_node)
    assert graph.edges[app_file_id, main_node]["relation"] == EdgeRelation.DEFINES.value
    assert graph.nodes[main_node]["type"] == NodeType.FUNCTION.value


def test_build_creates_contains_edge_from_class_to_method(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    greeter_node = next(n for n, d in graph.nodes(data=True) if d["name"] == "Greeter")
    greet_node = next(n for n, d in graph.nodes(data=True) if d["name"] == "greet")

    assert graph.has_edge(greeter_node, greet_node)
    assert graph.edges[greeter_node, greet_node]["relation"] == EdgeRelation.CONTAINS.value
    assert graph.nodes[greet_node]["type"] == NodeType.METHOD.value


def test_symbol_nodes_carry_expected_metadata(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    greeter_node = next(n for n, d in graph.nodes(data=True) if d["name"] == "Greeter")
    data = graph.nodes[greeter_node]

    assert data["docstring"] == "Greets users by name."
    assert data["file_path"] == "app.py"
    assert data["language"] == "python"
    assert data["start_line"] is not None
    assert data["end_line"] is not None


def test_readme_is_not_graphed_as_a_file_node(parsed_sample_repository: ParsedRepository) -> None:
    graph = GraphBuilder().build(parsed_sample_repository)
    file_names = {d["name"] for _, d in graph.nodes(data=True) if d["type"] == NodeType.FILE.value}
    assert "README.md" not in file_names


def _init_repo(repo_path: Path) -> Repo:
    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


def test_build_resolves_relative_python_imports_to_file_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "relimport_repo"
    repo_path.mkdir()
    repo = _init_repo(repo_path)

    (repo_path / "utils.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    (repo_path / "app.py").write_text(
        "from .utils import add\n\n\ndef main() -> None:\n    add(1, 2)\n", encoding="utf-8"
    )
    repo.index.add(["utils.py", "app.py"])
    repo.index.commit("init")

    parsed = TreeSitterRepositoryParser().parse(repo_path)
    graph = GraphBuilder().build(parsed)

    app_id = build_file_node_id("app.py")
    utils_id = build_file_node_id("utils.py")
    assert graph.has_edge(app_id, utils_id)
    assert graph.edges[app_id, utils_id]["relation"] == EdgeRelation.IMPORTS.value


def test_build_does_not_link_unresolvable_imports(tmp_path: Path) -> None:
    repo_path = tmp_path / "external_import_repo"
    repo_path.mkdir()
    repo = _init_repo(repo_path)

    (repo_path / "app.py").write_text("import os\n\n\ndef main() -> None:\n    pass\n", encoding="utf-8")
    repo.index.add(["app.py"])
    repo.index.commit("init")

    parsed = TreeSitterRepositoryParser().parse(repo_path)
    graph = GraphBuilder().build(parsed)

    app_id = build_file_node_id("app.py")
    import_edges = [
        (u, v) for u, v, d in graph.out_edges(app_id, data=True) if d["relation"] == EdgeRelation.IMPORTS.value
    ]
    assert import_edges == []
