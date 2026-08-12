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

from tara.context.embedder import Embedder, RepositoryEmbedder
from tara.context.graph_builder import GraphBuilder
from tara.context.models import RepositoryContext
from tara.context.symbol_index import SymbolIndex, SymbolIndexBuilder
from tara.parsing.repository_parser import TreeSitterRepositoryParser

#: Fixed vocabulary `DeterministicFakeEmbedder` counts occurrences of. Chosen to
#: appear distinctly across `dense_repository`'s three symbols (see that fixture's
#: docstring) so cosine similarity between a query and each symbol is predictable
#: and independently hand-verifiable in tests, without loading a real model.
DENSE_TEST_VOCABULARY: tuple[str, ...] = (
    "greet",
    "hello",
    "friendly",
    "parse",
    "repository",
    "metadata",
    "add",
    "integers",
)


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


class DeterministicFakeEmbedder(Embedder):
    """A tiny, fully deterministic `Embedder` for `DenseRetriever` tests.

    Not a real semantic model: encodes text as a fixed-length vector of
    `DENSE_TEST_VOCABULARY` word-occurrence counts (case-insensitive
    substring counting, not tokenization). This makes cosine similarity
    between any two embedded texts a direct, hand-verifiable function of
    shared vocabulary terms -- exactly what deterministic, network-free,
    model-free tests need, per this module's design (mirrors why
    `tara.retrieval.bm25_index.BM25Index` is hand-rolled rather than
    pulled from a third-party ranking library).

    Every vector has the same fixed dimension (`len(DENSE_TEST_VOCABULARY)`),
    matching a real embedding model's behavior of always producing
    same-dimension output regardless of input text.
    """

    def embed(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float(lowered.count(word)) for word in DENSE_TEST_VOCABULARY]


@pytest.fixture(scope="module")
def dense_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small, real Git repository tailored for `DenseRetriever` tests.

    Three symbols, each dominated by a disjoint subset of
    `DENSE_TEST_VOCABULARY`, so a query embedding built from the same
    vocabulary ranks them predictably: `greet` and `hello`/`friendly`
    only appear in `greet`; `parse`/`repository`/`metadata` only in
    `parse_repository`; `add`/`integers` only in `add`.
    """
    repo_path = tmp_path_factory.mktemp("dense_repo") / "sample_repo"
    repo = _init_repo(repo_path)

    (repo_path / "app.py").write_text(
        '''def greet(name: str) -> str:
    """Return a friendly greeting for name."""
    return f"Hello, {name}!"
''',
        encoding="utf-8",
    )

    (repo_path / "utils.py").write_text(
        '''def parse_repository(path: str) -> dict:
    """Parse a repository at the given path and return its metadata."""
    return {"path": path}


def add(a: int, b: int) -> int:
    """Add two integers together."""
    return a + b
''',
        encoding="utf-8",
    )

    repo.index.add(["app.py", "utils.py"])
    repo.index.commit("Initial commit")
    return repo_path


def _build_dense_context(repo_path: Path, embedder: Embedder) -> RepositoryContext:
    """Build a `RepositoryContext` with real embeddings, via the real `RepositoryEmbedder`.

    Reuses the exact production wiring (`RepositoryEmbedder.embed_repository`)
    with `embedder` swapped for a deterministic fake, so these fixtures
    exercise the same embedding-population code path `DenseRetriever`'s
    real callers would use, not a hand-assembled shortcut.
    """
    parsed = TreeSitterRepositoryParser().parse(repo_path)
    graph = GraphBuilder().build(parsed)
    symbol_index = SymbolIndexBuilder().build(graph)
    embeddings = RepositoryEmbedder(embedder).embed_repository(parsed)
    return RepositoryContext(
        root_path=str(repo_path),
        commit_sha=parsed.commit_sha,
        graph=graph,
        symbol_index=symbol_index,
        embeddings=embeddings,
        embedding_dimension=len(DENSE_TEST_VOCABULARY),
        embedding_model_name="deterministic-fake-test-embedder",
        file_count=len(parsed.files),
        symbol_count=sum(len(f.symbols) for f in parsed.files),
    )


@pytest.fixture(scope="module")
def dense_context(dense_repository: Path) -> RepositoryContext:
    """A `RepositoryContext` for `dense_repository`, with real (fake-model) embeddings populated."""
    return _build_dense_context(dense_repository, DeterministicFakeEmbedder())


@pytest.fixture(scope="module")
def dense_context_no_embeddings(dense_repository: Path) -> RepositoryContext:
    """The same repository as `dense_context`, but with no embeddings computed.

    Distinct from `empty_context` (which has zero files/symbols at all):
    this represents a repository with real, parsed content whose
    `RepositoryContextExtractor` simply never ran the embedding step --
    the specific "missing embeddings" scenario `DenseRetriever` must
    handle cleanly.
    """
    parsed = TreeSitterRepositoryParser().parse(dense_repository)
    graph = GraphBuilder().build(parsed)
    symbol_index = SymbolIndexBuilder().build(graph)
    return RepositoryContext(
        root_path=str(dense_repository),
        commit_sha=parsed.commit_sha,
        graph=graph,
        symbol_index=symbol_index,
        embeddings={},
        file_count=len(parsed.files),
        symbol_count=sum(len(f.symbols) for f in parsed.files),
    )
