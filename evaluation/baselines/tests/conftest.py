"""Shared fixtures/helpers for the `evaluation.baselines` test suite.

No real repository, no real LLM, no real TIQS query -- every fixture
here is synthetic, mirroring the pattern already established in
`tests/routing/conftest.py` and `tests/retrieval/test_orchestrator.py`.
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
    """A minimal, controllable `Retriever`, mirroring `tests/retrieval/test_orchestrator.py`'s.

    Returns one fixed, non-empty `RetrievedChunk` tagged with its own
    `kind`, so a baseline's `fused_context.chunks` is provably non-empty
    whenever its plan actually includes that retriever.
    """

    def __init__(self, kind: RetrieverKind) -> None:
        self.kind = kind
        self.call_count = 0

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        self.call_count += 1
        chunk = RetrievedChunk(
            chunk_id=f"file::app.py::{self.kind.value}_symbol::1",
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


class _RaisingRetriever(Retriever):
    """A `Retriever` that always fails -- used to prove an unregistered/unused retriever
    (e.g. GRAPH for a lexical-only baseline) is never actually invoked."""

    def __init__(self, kind: RetrieverKind) -> None:
        self.kind = kind

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        raise RetrievalError(f"{self.kind.value} should never have been invoked by this baseline")


@pytest.fixture
def rich_context() -> RepositoryContext:
    """A `RepositoryContext` with a non-trivial graph and embeddings, so no retriever a
    baseline's fixed strategy names gets silently downgraded by `RetrievalPlanner`."""
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


def make_classification(
    *,
    task_type: TaskType = TaskType.SEARCH,
    retriever_kind: RetrievalStrategy = RetrievalStrategy.LEXICAL,
    graph_required: bool = False,
    semantic_required: bool = False,
    lexical_required: bool = False,
    reasoning_required: bool = False,
) -> TaskClassification:
    return TaskClassification(
        task_type=task_type,
        retriever_kind=retriever_kind,
        confidence=1.0,
        graph_required=graph_required,
        semantic_required=semantic_required,
        lexical_required=lexical_required,
        reasoning_required=reasoning_required,
    )


@pytest.fixture
def refactor_classification() -> TaskClassification:
    """A classification that, under TARA's real `DEFAULT_POLICIES`, would trigger
    `FullPipelinePolicy`'s REFACTOR override -- used to prove a baseline's fixed strategy does
    NOT vary with classification the way TARA's real adaptive router would."""
    return make_classification(
        task_type=TaskType.REFACTOR,
        retriever_kind=RetrievalStrategy.HYBRID,
        graph_required=True,
        semantic_required=True,
        lexical_required=True,
    )


@pytest.fixture
def search_classification() -> TaskClassification:
    """A classification with no flags set -- the opposite extreme from `refactor_classification`."""
    return make_classification(task_type=TaskType.SEARCH, retriever_kind=RetrievalStrategy.LEXICAL)


def make_orchestrator(
    *kinds: RetrieverKind,
) -> tuple[RetrievalOrchestrator, dict[RetrieverKind, _FakeRetriever]]:
    """Build a `RetrievalOrchestrator` with one `_FakeRetriever` per kind in `kinds`."""
    fakes = {kind: _FakeRetriever(kind) for kind in kinds}
    mapping: Mapping[RetrieverKind, Retriever] = fakes
    return RetrievalOrchestrator(mapping), fakes


@pytest.fixture
def full_orchestrator() -> tuple[RetrievalOrchestrator, dict[RetrieverKind, _FakeRetriever]]:
    """A `RetrievalOrchestrator` with all three retrievers a baseline might request registered."""
    return make_orchestrator(RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)
