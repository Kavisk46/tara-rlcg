"""Unit tests for `tara.retrieval.dense_retriever.DenseRetriever`.

All tests use `DeterministicFakeEmbedder` (see `conftest.py`) instead of
a real `sentence-transformers` model, so this suite never downloads a
model, never touches the network, and is fully deterministic. Cosine
similarity itself is exercised only through the public `retrieve`
method, matching `test_lexical.py`'s convention of testing through
public behavior rather than private helpers.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tara.context.embedder import Embedder
from tara.context.models import NodeType, RepositoryContext
from tara.core.exceptions import RetrievalError
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.dense_retriever import DenseRetriever
from tara.retrieval.ranking import RankingEngine
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy
from tests.retrieval.conftest import DENSE_TEST_VOCABULARY, DeterministicFakeEmbedder


def _make_plan(candidate_limit: int = 10, top_k: int = 10) -> RetrievalPlan:
    return RetrievalPlan(
        strategy=RoutingStrategy.SEMANTIC_ONLY,
        retrievers=[RetrieverKind.DENSE],
        execution_order=[RetrieverKind.DENSE],
        parallel=False,
        rerank=False,
        top_k=top_k,
        candidate_limit=candidate_limit,
        reason="test",
    )


@pytest.fixture
def retriever() -> DenseRetriever:
    return DenseRetriever(DeterministicFakeEmbedder(), RankingEngine())


class _FixedVectorEmbedder(Embedder):
    """An `Embedder` that always returns the same, injected vector."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed(self, text: str) -> list[float]:
        return list(self._vector)


#: A unit vector on the first axis, matching `len(DENSE_TEST_VOCABULARY)`. Used by
#: the parallel/orthogonal similarity tests below to keep long vector literals short.
_UNIT_VECTOR_AXIS_0 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


# ============================================================================
# Interface conformance
# ============================================================================


def test_dense_retriever_implements_retriever_interface(retriever: DenseRetriever) -> None:
    assert isinstance(retriever, Retriever)


# ============================================================================
# retrieve() -- correct ranking / cosine similarity behavior
# ============================================================================


def test_retrieve_ranks_the_semantically_closest_symbol_first(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    """"greet" and "friendly" only co-occur with the `greet` symbol in the fixture repo."""
    result = retriever.retrieve("a friendly way to greet someone", _make_plan(), dense_context)

    assert result.chunks
    assert result.chunks[0].name == "greet"


def test_retrieve_tags_result_with_dense_retriever_kind_and_query(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    result = retriever.retrieve("parse a repository", _make_plan(), dense_context)
    assert result.retriever_kind is RetrieverKind.DENSE
    assert result.query == "parse a repository"


def test_retrieve_matching_symbol_scores_strictly_higher_than_unrelated_symbols(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    result = retriever.retrieve("add two integers together", _make_plan(), dense_context)
    scores_by_name = {chunk.name: chunk.score.raw_score for chunk in result.chunks}

    assert scores_by_name["add"] > scores_by_name["greet"]
    assert scores_by_name["add"] > scores_by_name["parse_repository"]


def test_retrieve_completely_unrelated_query_still_returns_every_candidate(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    """Dense retrieval is dense: unlike BM25's sparse matching, every embedded
    symbol has *some* cosine similarity (here, exactly 0.0) to any query, so
    nothing is dropped for "no shared vocabulary" the way LexicalRetriever
    would drop it for "no shared token"."""
    result = retriever.retrieve("zzz_totally_unrelated_query_xyz", _make_plan(), dense_context)
    assert len(result.chunks) == 3
    assert all(chunk.score.raw_score == 0.0 for chunk in result.chunks)


def test_retrieve_parallel_query_and_document_vectors_score_maximal_similarity(
    dense_context: RepositoryContext,
) -> None:
    # Precisely controlled, rather than relying on hand-counting DeterministicFakeEmbedder's
    # output over a real symbol's assembled embedding text (fragile: the docstring is
    # duplicated inside the embedded source code, so word ratios are not obvious by
    # inspection). Overriding one embedding to an exact known vector and querying with
    # an exactly parallel vector directly proves cosine similarity reaches its 1.0 maximum
    # for parallel vectors, and that DenseRetriever surfaces that score unmodified.
    node_id = next(iter(dense_context.embeddings))
    fixed_vector = [3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    single_embedding_context = dense_context.model_copy(
        update={"embeddings": {node_id: fixed_vector}}
    )
    retriever = DenseRetriever(_FixedVectorEmbedder(_UNIT_VECTOR_AXIS_0), RankingEngine())

    result = retriever.retrieve(
        "irrelevant text -- embedder ignores it", _make_plan(), single_embedding_context
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].score.raw_score == pytest.approx(1.0)


def test_retrieve_orthogonal_query_and_document_vectors_score_zero_similarity(
    dense_context: RepositoryContext,
) -> None:
    node_id = next(iter(dense_context.embeddings))
    orthogonal_vector = [0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    single_embedding_context = dense_context.model_copy(
        update={"embeddings": {node_id: orthogonal_vector}}
    )
    retriever = DenseRetriever(_FixedVectorEmbedder(_UNIT_VECTOR_AXIS_0), RankingEngine())

    result = retriever.retrieve(
        "irrelevant text -- embedder ignores it", _make_plan(), single_embedding_context
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].score.raw_score == pytest.approx(0.0)


# ============================================================================
# retrieve() -- chunk content / metadata traceability
# ============================================================================


def test_retrieve_populates_chunk_content_and_metadata(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    result = retriever.retrieve("parse a repository and its metadata", _make_plan(), dense_context)
    top = next(c for c in result.chunks if c.name == "parse_repository")

    assert "def parse_repository" in top.content
    assert top.docstring == "Parse a repository at the given path and return its metadata."
    assert top.file_path == "utils.py"
    assert top.start_line is not None
    assert top.end_line is not None
    assert top.retriever_kind is RetrieverKind.DENSE
    assert top.node_type is NodeType.FUNCTION
    assert top.chunk_id  # the shared tara.context node id -- traces back to the graph/symbol index


# ============================================================================
# retrieve() -- top_k / candidate_limit
# ============================================================================


def test_retrieve_respects_candidate_limit(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    result = retriever.retrieve("greet parse add", _make_plan(candidate_limit=1), dense_context)
    assert len(result.chunks) <= 1


def test_retrieve_total_candidates_matches_chunk_count(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    result = retriever.retrieve("greet parse add", _make_plan(candidate_limit=10), dense_context)
    assert result.total_candidates == len(result.chunks)


def test_retrieve_candidate_limit_larger_than_corpus_returns_everything(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    result = retriever.retrieve("greet", _make_plan(candidate_limit=1000), dense_context)
    assert len(result.chunks) == 3


# ============================================================================
# retrieve() -- missing embeddings / empty repository
# ============================================================================


def test_retrieve_with_no_embeddings_computed_returns_empty_context_cleanly(
    retriever: DenseRetriever, dense_context_no_embeddings: RepositoryContext
) -> None:
    result = retriever.retrieve("greet", _make_plan(), dense_context_no_embeddings)
    assert result.chunks == []
    assert result.total_candidates == 0
    assert result.retriever_kind is RetrieverKind.DENSE


def test_retrieve_on_empty_repository_returns_empty_context(
    retriever: DenseRetriever, empty_context: RepositoryContext
) -> None:
    result = retriever.retrieve("anything", _make_plan(), empty_context)
    assert result.chunks == []
    assert result.total_candidates == 0


def test_retrieve_with_no_embeddings_does_not_call_the_embedder(
    dense_context_no_embeddings: RepositoryContext,
) -> None:
    """The empty-embeddings short-circuit must happen before embedding the
    query -- there's nothing to compare it against, so embedding it would be
    wasted work (and, for a real model, wasted latency/cost)."""

    class _ExplodingEmbedder(Embedder):
        def embed(self, text: str) -> list[float]:
            raise AssertionError("embed() should not be called when context.embeddings is empty")

    retriever = DenseRetriever(_ExplodingEmbedder(), RankingEngine())
    result = retriever.retrieve("greet", _make_plan(), dense_context_no_embeddings)
    assert result.chunks == []


# ============================================================================
# retrieve() -- determinism
# ============================================================================


def test_retrieve_is_deterministic_across_repeated_calls(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    first = retriever.retrieve("parse a repository", _make_plan(), dense_context)
    second = retriever.retrieve("parse a repository", _make_plan(), dense_context)

    first_ids = [c.chunk_id for c in first.chunks]
    second_ids = [c.chunk_id for c in second.chunks]
    assert first_ids == second_ids

    first_scores = [c.score.raw_score for c in first.chunks]
    second_scores = [c.score.raw_score for c in second.chunks]
    assert first_scores == second_scores


def test_retrieve_ties_are_broken_deterministically_by_chunk_id(
    retriever: DenseRetriever, dense_context: RepositoryContext
) -> None:
    # "zzz_..." scores 0.0 against every symbol (see the unrelated-query test
    # above), so this exercises RankingEngine's ascending-document-id tiebreak.
    first = retriever.retrieve("zzz_totally_unrelated_query_xyz", _make_plan(), dense_context)
    second = retriever.retrieve("zzz_totally_unrelated_query_xyz", _make_plan(), dense_context)
    assert [c.chunk_id for c in first.chunks] == [c.chunk_id for c in second.chunks]
    assert [c.chunk_id for c in first.chunks] == sorted(c.chunk_id for c in first.chunks)


# ============================================================================
# retrieve() -- dimension mismatch handling
# ============================================================================


def test_retrieve_raises_when_query_embedding_dimension_mismatches_context(
    dense_context: RepositoryContext,
) -> None:
    # dense_context expects len(DENSE_TEST_VOCABULARY) == 8, not 3.
    wrong_dimension_embedder = _FixedVectorEmbedder([0.1, 0.2, 0.3])
    retriever = DenseRetriever(wrong_dimension_embedder, RankingEngine())

    with pytest.raises(RetrievalError, match="dimension"):
        retriever.retrieve("greet", _make_plan(), dense_context)


def test_retrieve_dimension_mismatch_error_names_both_dimensions(
    dense_context: RepositoryContext,
) -> None:
    wrong_dimension_embedder = _FixedVectorEmbedder([0.0] * 3)
    retriever = DenseRetriever(wrong_dimension_embedder, RankingEngine())

    with pytest.raises(RetrievalError, match=r"3.*8|8.*3"):
        retriever.retrieve("greet", _make_plan(), dense_context)


def test_retrieve_does_not_raise_when_context_has_no_declared_dimension(
    dense_context_no_embeddings: RepositoryContext,
) -> None:
    # embedding_dimension is None here (no embeddings computed at all), and
    # embeddings is also empty, so the empty-context short-circuit applies
    # before dimension validation would even run -- confirms no false-positive
    # dimension error is raised for a context that simply has nothing embedded.
    retriever = DenseRetriever(_FixedVectorEmbedder([0.0] * 3), RankingEngine())
    result = retriever.retrieve("greet", _make_plan(), dense_context_no_embeddings)
    assert result.chunks == []


def test_retrieve_skips_a_single_malformed_document_embedding_without_raising(
    dense_repository: Path,
) -> None:
    """A per-document dimension mismatch (isolated bad data) must not abort
    the whole query the way a query/context-wide mismatch does."""
    from tara.context.graph_builder import GraphBuilder
    from tara.context.symbol_index import SymbolIndexBuilder
    from tara.parsing.repository_parser import TreeSitterRepositoryParser

    parsed = TreeSitterRepositoryParser().parse(dense_repository)
    graph = GraphBuilder().build(parsed)
    symbol_index = SymbolIndexBuilder().build(graph)
    embeddings = {
        node.node_id: [0.0] * len(DENSE_TEST_VOCABULARY)
        for node in symbol_index
        if node.node_type in {"function", "method", "class"}
    }
    # Corrupt exactly one entry with the wrong dimension.
    corrupted_id = next(iter(embeddings))
    embeddings[corrupted_id] = [0.0, 0.0]  # wrong length

    context = RepositoryContext(
        root_path=str(dense_repository),
        commit_sha=parsed.commit_sha,
        graph=graph,
        symbol_index=symbol_index,
        embeddings=embeddings,
        embedding_dimension=len(DENSE_TEST_VOCABULARY),
        file_count=len(parsed.files),
        symbol_count=sum(len(f.symbols) for f in parsed.files),
    )

    retriever = DenseRetriever(DeterministicFakeEmbedder(), RankingEngine())
    result = retriever.retrieve("greet", _make_plan(), context)

    # The corrupted entry is silently skipped; the other two are still scored.
    assert len(result.chunks) == 2
    assert corrupted_id not in {c.chunk_id for c in result.chunks}
