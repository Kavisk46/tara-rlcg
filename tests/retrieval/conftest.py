"""Shared fixtures for the `tara.retrieval` test suite.

Deliberately does not reuse the root-level `sample_repository` fixture
(shared by `tests/parsing`, `tests/context`, `tests/classification`, and
`tests/routing`): its content has no compound snake_case identifiers,
which lexical-retrieval tests specifically need to exercise partial
search. Defining a separate fixture here avoids any risk of a
retrieval-motivated change to shared fixture content rippling into
unrelated, already-passing test suites.
"""
from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest
from git import Repo

from tara.context.graph_builder import GraphBuilder
from tara.context.models import RepositoryContext
from tara.context.symbol_index import SymbolIndex, SymbolIndexBuilder
from tara.parsing.repository_parser import TreeSitterRepositoryParser


def _init_repo(repo_path: Path) -> Repo:
    repo_path.mkdir()
    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


def _build_context(repo_path: Path) -> RepositoryContext:
    parsed = TreeSitterRepositoryParser().parse(repo_path)
    graph = GraphBuilder().build(parsed)
    symbol_index = SymbolIndexBuilder().build(graph)
    return RepositoryContext(
        root_path=str(repo_path),
        commit_sha=parsed.commit_sha,
        graph=graph,
        symbol_index=symbol_index,
        file_count=len(parsed.files),
        symbol_count=sum(len(f.symbols) for f in parsed.files),
    )


@pytest.fixture(scope="module")
def retrieval_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small, real Git repository tailored for lexical-retrieval tests.

    Content is deliberately chosen to exercise BM25 keyword search:
    compound snake_case identifiers (`parse_repository`), docstrings on
    some symbols but not others, a class with a method, and multiple
    files.
    """
    repo_path = tmp_path_factory.mktemp("retrieval_repo") / "sample_repo"
    repo = _init_repo(repo_path)

    (repo_path / "app.py").write_text(
        '''"""Application entry point."""


class Greeter:
    """Greets users by name."""

    def greet(self, name: str) -> str:
        """Return a greeting for `name`."""
        return f"Hello, {name}!"


def main() -> None:
    """Run the application."""
    greeter = Greeter()
    print(greeter.greet("World"))
''',
        encoding="utf-8",
    )

    (repo_path / "utils.py").write_text(
        '''def parse_repository(path: str) -> dict:
    """Parse a repository at the given path and return its metadata."""
    return {"path": path}


def add(a: int, b: int) -> int:
    return a + b
''',
        encoding="utf-8",
    )

    repo.index.add(["app.py", "utils.py"])
    repo.index.commit("Initial commit")
    return repo_path


@pytest.fixture(scope="module")
def retrieval_context(retrieval_repository: Path) -> RepositoryContext:
    """A `RepositoryContext` built from `retrieval_repository` via the real pipeline.

    No embeddings are generated -- `LexicalRetriever` doesn't need them
    -- keeping this fixture fast and free of any model dependency.
    """
    return _build_context(retrieval_repository)


@pytest.fixture
def empty_context() -> RepositoryContext:
    """A `RepositoryContext` for a repository with zero files or symbols.

    Built directly (bypassing the parser entirely) since there is
    nothing real to parse for this case; matches the `bare_context`
    pattern already used in `tests/routing/conftest.py`.
    """
    graph = nx.DiGraph()
    graph.add_node("repository::/empty-repo", type="repository", name="/empty-repo")
    return RepositoryContext(
        root_path="/empty-repo",
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        file_count=0,
        symbol_count=0,
    )


@pytest.fixture(scope="module")
def large_retrieval_context(tmp_path_factory: pytest.TempPathFactory) -> RepositoryContext:
    """A `RepositoryContext` with a large, programmatically generated symbol corpus.

    Stands in for the 'large repository' test scenario for
    `LexicalRetriever` specifically -- `BM25Index` itself is already
    exercised at a larger (5,000-document) scale directly in
    `test_bm25.py`; this fixture verifies the retriever's own
    corpus-building and search path at a meaningful, still-fast-to-parse
    scale.
    """
    repo_path = tmp_path_factory.mktemp("large_retrieval_repo") / "large_repo"
    repo = _init_repo(repo_path)

    lines = ['"""Generated large module for retrieval scale testing."""', ""]
    for i in range(300):
        lines.append(f"def generated_function_{i}(value: int) -> int:")
        lines.append(f'    """Compute a transformation for generated item {i}."""')
        lines.append(f"    return value + {i}")
        lines.append("")
    (repo_path / "generated.py").write_text("\n".join(lines), encoding="utf-8")

    repo.index.add(["generated.py"])
    repo.index.commit("Generated large module")

    return _build_context(repo_path)
