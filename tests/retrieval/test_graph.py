"""Unit tests for `tara.retrieval.graph_retriever.GraphRetriever`.

Uses a small, hand-built synthetic graph rather than a real parsed
repository -- `GraphRetriever` needs no BM25-style corpus and no
embedding model, so there is nothing a real repository would add except
filesystem/parser overhead. Symbol nodes deliberately omit
`start_byte`/`end_byte`, so `content` falls back to `record.name` (a
well-defined, asserted-on behavior), keeping this suite fully in-memory
and deterministic.

Synthetic graph shape (all edges directed source -> target):

    repository::/repo
      --CONTAINS--> file::auth.py
      --CONTAINS--> file::utils.py
      --CONTAINS--> file::unrelated.py

    file::auth.py --DEFINES--> AuthHandler (class)
      AuthHandler --CONTAINS--> login (method)
      AuthHandler --CONTAINS--> logout (method)
    file::auth.py --IMPORTS--> file::utils.py

    file::utils.py --DEFINES--> validate_token (function)

    file::unrelated.py --DEFINES--> unrelated_func (function)

With `expand_neighbors=True` (traverses both predecessors and
successors), multi-source BFS distances from seed `AuthHandler` are:
    AuthHandler=0, auth.py=1, login=1, logout=1,
    repository_root=2, utils.py=2,
    unrelated.py=3, validate_token=3,
    unrelated_func=4
(the repository root is reachable but can never become a `RetrievedChunk`
-- it has no `file_path` -- so it never appears in any asserted result).
"""
from __future__ import annotations

import networkx as nx
import pytest

from tara.classification.features import FeatureExtractor
from tara.context.models import (
    EdgeRelation,
    NodeType,
    RepositoryContext,
    build_file_node_id,
    build_repository_node_id,
    build_symbol_node_id,
)
from tara.context.symbol_index import SymbolIndex
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.graph_retriever import GraphRetriever
from tara.retrieval.models import RetrievedContext
from tara.retrieval.ranking import RankingEngine
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy

ROOT_PATH = "/repo"
REPO_ID = build_repository_node_id(ROOT_PATH)
AUTH_FILE_ID = build_file_node_id("auth.py")
UTILS_FILE_ID = build_file_node_id("utils.py")
UNRELATED_FILE_ID = build_file_node_id("unrelated.py")
AUTH_HANDLER_ID = build_symbol_node_id("auth.py", "AuthHandler", None, 1)
LOGIN_ID = build_symbol_node_id("auth.py", "login", "AuthHandler", 3)
LOGOUT_ID = build_symbol_node_id("auth.py", "logout", "AuthHandler", 6)
VALIDATE_TOKEN_ID = build_symbol_node_id("utils.py", "validate_token", None, 1)
UNRELATED_FUNC_ID = build_symbol_node_id("unrelated.py", "unrelated_func", None, 1)

AUTH_QUERY = '"AuthHandler"'
AUTH_AND_VALIDATE_QUERY = '"AuthHandler" and "validate_token"'


def _add_file(graph: nx.DiGraph, file_id: str, path: str) -> None:
    graph.add_node(file_id, type=NodeType.FILE.value, name=path, file_path=path, docstring=None)


def _add_symbol(
    graph: nx.DiGraph,
    node_id: str,
    node_type: NodeType,
    name: str,
    file_path: str,
    parent: str | None,
) -> None:
    graph.add_node(
        node_id,
        type=node_type.value,
        name=name,
        file_path=file_path,
        docstring=f"Docstring for {name}.",
        parent=parent,
    )


def _build_synthetic_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node(REPO_ID, type=NodeType.REPOSITORY.value, name=ROOT_PATH, file_path=None)

    files = (
        (AUTH_FILE_ID, "auth.py"),
        (UTILS_FILE_ID, "utils.py"),
        (UNRELATED_FILE_ID, "unrelated.py"),
    )
    for file_id, path in files:
        _add_file(graph, file_id, path)
        graph.add_edge(REPO_ID, file_id, relation=EdgeRelation.CONTAINS.value)

    _add_symbol(graph, AUTH_HANDLER_ID, NodeType.CLASS, "AuthHandler", "auth.py", None)
    graph.add_edge(AUTH_FILE_ID, AUTH_HANDLER_ID, relation=EdgeRelation.DEFINES.value)

    _add_symbol(graph, LOGIN_ID, NodeType.METHOD, "login", "auth.py", "AuthHandler")
    graph.add_edge(AUTH_HANDLER_ID, LOGIN_ID, relation=EdgeRelation.CONTAINS.value)

    _add_symbol(graph, LOGOUT_ID, NodeType.METHOD, "logout", "auth.py", "AuthHandler")
    graph.add_edge(AUTH_HANDLER_ID, LOGOUT_ID, relation=EdgeRelation.CONTAINS.value)

    graph.add_edge(AUTH_FILE_ID, UTILS_FILE_ID, relation=EdgeRelation.IMPORTS.value)

    _add_symbol(graph, VALIDATE_TOKEN_ID, NodeType.FUNCTION, "validate_token", "utils.py", None)
    graph.add_edge(UTILS_FILE_ID, VALIDATE_TOKEN_ID, relation=EdgeRelation.DEFINES.value)

    _add_symbol(graph, UNRELATED_FUNC_ID, NodeType.FUNCTION, "unrelated_func", "unrelated.py", None)
    graph.add_edge(UNRELATED_FILE_ID, UNRELATED_FUNC_ID, relation=EdgeRelation.DEFINES.value)

    return graph


@pytest.fixture
def synthetic_context() -> RepositoryContext:
    graph = _build_synthetic_graph()
    return RepositoryContext(
        root_path=ROOT_PATH,
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        file_count=3,
        symbol_count=5,
    )


@pytest.fixture
def empty_context() -> RepositoryContext:
    graph = nx.DiGraph()
    graph.add_node(REPO_ID, type=NodeType.REPOSITORY.value, name=ROOT_PATH, file_path=None)
    return RepositoryContext(
        root_path=ROOT_PATH,
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        file_count=0,
        symbol_count=0,
    )


@pytest.fixture
def retriever() -> GraphRetriever:
    return GraphRetriever(RankingEngine(), FeatureExtractor())


def _make_plan(
    graph_depth: int, expand_neighbors: bool = True, candidate_limit: int = 20
) -> RetrievalPlan:
    return RetrievalPlan(
        strategy=RoutingStrategy.GRAPH_ONLY,
        retrievers=[RetrieverKind.GRAPH],
        execution_order=[RetrieverKind.GRAPH],
        parallel=False,
        graph_depth=graph_depth,
        expand_neighbors=expand_neighbors,
        rerank=False,
        top_k=10,
        candidate_limit=candidate_limit,
        reason="test",
    )


def _chunk_ids(result: RetrievedContext) -> set[str]:
    return {chunk.chunk_id for chunk in result.chunks}


# ============================================================================
# Interface conformance
# ============================================================================


def test_graph_retriever_implements_retriever_interface(retriever: GraphRetriever) -> None:
    assert isinstance(retriever, Retriever)


# ============================================================================
# Direct symbol seed
# ============================================================================


def test_direct_symbol_seed_is_included_at_zero_distance(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    result = retriever.retrieve('Find "AuthHandler"', _make_plan(graph_depth=0), synthetic_context)

    assert AUTH_HANDLER_ID in _chunk_ids(result)
    seed_chunk = next(c for c in result.chunks if c.chunk_id == AUTH_HANDLER_ID)
    assert seed_chunk.score.raw_score == pytest.approx(1.0)  # distance 0 -> 1/(1+0)
    assert seed_chunk.retriever_kind is RetrieverKind.GRAPH
    assert seed_chunk.node_type is NodeType.CLASS


def test_direct_file_path_seed_is_included(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    result = retriever.retrieve("Show utils.py", _make_plan(graph_depth=0), synthetic_context)
    assert UTILS_FILE_ID in _chunk_ids(result)


def test_graph_depth_zero_returns_only_the_seed(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    result = retriever.retrieve(AUTH_QUERY, _make_plan(graph_depth=0), synthetic_context)
    assert _chunk_ids(result) == {AUTH_HANDLER_ID}


# ============================================================================
# One-hop traversal
# ============================================================================


def test_one_hop_traversal_reaches_immediate_neighbors_only(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=1, expand_neighbors=True)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    ids = _chunk_ids(result)

    assert ids == {AUTH_HANDLER_ID, AUTH_FILE_ID, LOGIN_ID, LOGOUT_ID}
    assert VALIDATE_TOKEN_ID not in ids
    assert UNRELATED_FUNC_ID not in ids


def test_one_hop_traversal_with_expand_neighbors_false_is_successors_only(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=1, expand_neighbors=False)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    ids = _chunk_ids(result)

    # auth.py is a *predecessor* of AuthHandler (DEFINES), not a successor,
    # so it must be excluded when expand_neighbors=False.
    assert ids == {AUTH_HANDLER_ID, LOGIN_ID, LOGOUT_ID}
    assert AUTH_FILE_ID not in ids


# ============================================================================
# Multi-hop traversal / graph depth limit
# ============================================================================


def test_multi_hop_traversal_reaches_a_three_hop_symbol(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=3, expand_neighbors=True)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    ids = _chunk_ids(result)

    assert VALIDATE_TOKEN_ID in ids  # AuthHandler -> auth.py -> utils.py -> validate_token (3 hops)
    assert UNRELATED_FUNC_ID not in ids  # 4 hops away, beyond this depth


def test_graph_depth_limit_excludes_nodes_beyond_the_limit(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    shallow_plan = _make_plan(graph_depth=2, expand_neighbors=True)
    deep_plan = _make_plan(graph_depth=4, expand_neighbors=True)
    shallow = retriever.retrieve(AUTH_QUERY, shallow_plan, synthetic_context)
    deep = retriever.retrieve(AUTH_QUERY, deep_plan, synthetic_context)

    assert UNRELATED_FUNC_ID not in _chunk_ids(shallow)
    assert UNRELATED_FUNC_ID in _chunk_ids(deep)


def test_graph_depth_limit_score_reflects_hop_distance(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=3, expand_neighbors=True)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    scores_by_id = {c.chunk_id: c.score.raw_score for c in result.chunks}

    assert scores_by_id[AUTH_HANDLER_ID] == pytest.approx(1.0)  # distance 0
    assert scores_by_id[AUTH_FILE_ID] == pytest.approx(0.5)  # distance 1
    assert scores_by_id[VALIDATE_TOKEN_ID] == pytest.approx(0.25)  # distance 3 (via utils.py)
    assert scores_by_id[AUTH_HANDLER_ID] > scores_by_id[AUTH_FILE_ID]
    assert scores_by_id[AUTH_FILE_ID] > scores_by_id[VALIDATE_TOKEN_ID]


# ============================================================================
# Multiple seeds / duplicate suppression
# ============================================================================


def test_multiple_seeds_are_all_included_at_distance_zero(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=0)
    result = retriever.retrieve(AUTH_AND_VALIDATE_QUERY, plan, synthetic_context)
    ids = _chunk_ids(result)

    assert AUTH_HANDLER_ID in ids
    assert VALIDATE_TOKEN_ID in ids
    scores_by_id = {c.chunk_id: c.score.raw_score for c in result.chunks}
    assert scores_by_id[AUTH_HANDLER_ID] == pytest.approx(1.0)
    assert scores_by_id[VALIDATE_TOKEN_ID] == pytest.approx(1.0)


def test_duplicate_node_reached_from_multiple_seeds_appears_exactly_once(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    # utils.py is reachable from AuthHandler at distance 2 (via auth.py's IMPORTS
    # edge) AND from validate_token at distance 1 (its DEFINES predecessor).
    # The nearer distance (1) must win, and utils.py must appear only once.
    plan = _make_plan(graph_depth=2, expand_neighbors=True)
    result = retriever.retrieve(AUTH_AND_VALIDATE_QUERY, plan, synthetic_context)

    matches = [c for c in result.chunks if c.chunk_id == UTILS_FILE_ID]
    assert len(matches) == 1
    assert matches[0].score.raw_score == pytest.approx(0.5)  # 1 / (1 + 1), the nearer distance


# ============================================================================
# Missing seed / empty graph
# ============================================================================


def test_missing_seed_returns_empty_context_cleanly(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    result = retriever.retrieve('"NonexistentClass"', _make_plan(graph_depth=3), synthetic_context)

    assert result.chunks == []
    assert result.total_candidates == 0
    assert result.retriever_kind is RetrieverKind.GRAPH


def test_empty_graph_returns_empty_context_cleanly(
    retriever: GraphRetriever, empty_context: RepositoryContext
) -> None:
    result = retriever.retrieve(AUTH_QUERY, _make_plan(graph_depth=3), empty_context)

    assert result.chunks == []
    assert result.total_candidates == 0


def test_query_with_no_detectable_symbols_or_paths_returns_empty_context(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=3)
    result = retriever.retrieve("hello there general question", plan, synthetic_context)
    assert result.chunks == []


# ============================================================================
# Deterministic ordering
# ============================================================================


def test_retrieve_is_deterministic_across_repeated_calls(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=3, expand_neighbors=True)
    first = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    second = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)

    assert [c.chunk_id for c in first.chunks] == [c.chunk_id for c in second.chunks]
    assert [c.score.raw_score for c in first.chunks] == [c.score.raw_score for c in second.chunks]


def test_retrieve_orders_chunks_by_descending_score(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=3, expand_neighbors=True)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    scores = [c.score.normalized_score for c in result.chunks]
    assert scores == sorted(scores, reverse=True)


# ============================================================================
# candidate_limit / content population
# ============================================================================


def test_retrieve_respects_candidate_limit(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    plan = _make_plan(graph_depth=3, expand_neighbors=True, candidate_limit=1)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    assert len(result.chunks) <= 1


def test_retrieve_populates_chunk_metadata_and_docstring(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    result = retriever.retrieve(AUTH_QUERY, _make_plan(graph_depth=0), synthetic_context)
    chunk = result.chunks[0]

    assert chunk.name == "AuthHandler"
    assert chunk.file_path == "auth.py"
    assert chunk.docstring == "Docstring for AuthHandler."
    # No byte span in this synthetic graph, so content falls back to record.name.
    assert chunk.content == "AuthHandler"


def test_retrieve_file_node_content_is_its_path(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    result = retriever.retrieve("utils.py", _make_plan(graph_depth=0), synthetic_context)
    chunk = next(c for c in result.chunks if c.chunk_id == UTILS_FILE_ID)
    assert chunk.content == "utils.py"
    assert chunk.node_type is NodeType.FILE


def test_repository_root_node_never_appears_in_results(
    retriever: GraphRetriever, synthetic_context: RepositoryContext
) -> None:
    # Depth 2 from AuthHandler reaches the repository root (a genuine graph
    # neighbor at that distance), but it must never surface as a chunk --
    # RetrievedChunk.file_path is required and the root node has none.
    plan = _make_plan(graph_depth=2, expand_neighbors=True)
    result = retriever.retrieve(AUTH_QUERY, plan, synthetic_context)
    assert REPO_ID not in _chunk_ids(result)
