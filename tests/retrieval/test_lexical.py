"""Unit tests for `tara.retrieval.lexical_retriever.LexicalRetriever`.

Scope: `keyword_search`, `retrieve`, and index building/caching. Exact
symbol/file lookup (`find_symbol`, `find_function`, `find_class`,
`find_method`, `find_file`, `find_path`) is covered separately in
`test_symbol_search.py`, per this milestone's given test-file layout.
"""
from __future__ import annotations

import pytest

from tara.context.models import NodeType, RepositoryContext
from tara.core.exceptions import RetrievalError
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.lexical_retriever import LexicalRetriever
from tara.retrieval.models import MatchedField
from tara.retrieval.ranking import RankingEngine
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy


def _make_plan(top_k: int = 10, candidate_limit: int = 10) -> RetrievalPlan:
    return RetrievalPlan(
        strategy=RoutingStrategy.LEXICAL_ONLY,
        retrievers=[RetrieverKind.LEXICAL],
        execution_order=[RetrieverKind.LEXICAL],
        parallel=False,
        rerank=False,
        top_k=top_k,
        candidate_limit=candidate_limit,
        reason="test",
    )


@pytest.fixture
def retriever() -> LexicalRetriever:
    return LexicalRetriever(RankingEngine())


# ============================================================================
# Interface conformance
# ============================================================================


def test_lexical_retriever_implements_retriever_interface(retriever: LexicalRetriever) -> None:
    assert isinstance(retriever, Retriever)


# ============================================================================
# keyword_search -- exact and partial matching
# ============================================================================


def test_keyword_search_exact_compound_token(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.keyword_search("parse_repository", retrieval_context, top_k=5)
    assert results
    assert results[0].name == "parse_repository"


def test_keyword_search_partial_subidentifier_match(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    """The core partial-search case: a bare sub-identifier finds the compound identifier."""
    results = retriever.keyword_search("parse", retrieval_context, top_k=5)
    names = {result.name for result in results}
    assert "parse_repository" in names


def test_keyword_search_exact_query_ranks_above_partial_query_for_the_same_document(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    """An exact compound-token query should score its target higher than a partial one does."""
    exact = retriever.keyword_search("parse_repository", retrieval_context, top_k=5)
    partial = retriever.keyword_search("parse", retrieval_context, top_k=5)

    exact_score = next(r.score.raw_score for r in exact if r.name == "parse_repository")
    partial_score = next(r.score.raw_score for r in partial if r.name == "parse_repository")
    assert exact_score > partial_score


# ============================================================================
# keyword_search -- multiple keywords, unknown query, empty query
# ============================================================================


def test_keyword_search_multiple_keywords(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.keyword_search("greet name", retrieval_context, top_k=5)
    names = {result.name for result in results}
    assert names & {"greet", "Greeter"}


def test_keyword_search_unknown_query_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.keyword_search("zzz_totally_unknown_xyz", retrieval_context, top_k=5) == []


def test_keyword_search_empty_query_string_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.keyword_search("", retrieval_context, top_k=5) == []


def test_keyword_search_whitespace_only_query_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.keyword_search("   ", retrieval_context, top_k=5) == []


@pytest.mark.parametrize("bad_top_k", [0, -1, -50])
def test_keyword_search_rejects_non_positive_top_k(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext, bad_top_k: int
) -> None:
    with pytest.raises(RetrievalError):
        retriever.keyword_search("greet", retrieval_context, top_k=bad_top_k)


# ============================================================================
# keyword_search -- field weighting and matched_field attribution
# ============================================================================


def test_keyword_search_name_match_outranks_source_only_match(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    """`add`'s name matches the query directly; `main`'s body merely constructs a `Greeter`.

    Querying "greeter" should rank the `Greeter` class (a name match)
    above `main` (whose body only mentions "greeter" as a local variable
    and a call), reflecting the configured name-field weighting.
    """
    results = retriever.keyword_search("greeter", retrieval_context, top_k=10)
    names_in_order = [r.name for r in results]
    assert "Greeter" in names_in_order
    if "main" in names_in_order:
        assert names_in_order.index("Greeter") < names_in_order.index("main")


def test_keyword_search_matched_field_is_name_for_an_exact_name_match(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    results = retriever.keyword_search("parse_repository", retrieval_context, top_k=5)
    top = next(r for r in results if r.name == "parse_repository")
    assert top.matched_field == MatchedField.NAME


def test_keyword_search_matched_field_is_docstring_for_a_docstring_only_match(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    """"metadata" appears only in `parse_repository`'s docstring, not its name or body."""
    results = retriever.keyword_search("metadata", retrieval_context, top_k=5)
    assert results
    top = results[0]
    assert top.name == "parse_repository"
    assert top.matched_field == MatchedField.DOCSTRING


# ============================================================================
# keyword_search -- top-k behavior and ranking correctness
# ============================================================================


def test_keyword_search_respects_top_k(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.keyword_search("repository path", retrieval_context, top_k=1)
    assert len(results) <= 1


def test_keyword_search_results_sorted_by_descending_normalized_score(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    results = retriever.keyword_search("greet", retrieval_context, top_k=10)
    scores = [r.score.normalized_score for r in results]
    assert scores == sorted(scores, reverse=True)


# ============================================================================
# keyword_search -- empty and large repositories
# ============================================================================


def test_keyword_search_on_empty_repository_returns_empty(
    retriever: LexicalRetriever, empty_context: RepositoryContext
) -> None:
    assert retriever.keyword_search("anything", empty_context, top_k=5) == []


def test_keyword_search_on_large_repository_finds_the_correct_symbol(
    retriever: LexicalRetriever, large_retrieval_context: RepositoryContext
) -> None:
    results = retriever.keyword_search("generated_function_150", large_retrieval_context, top_k=5)
    assert results
    assert results[0].name == "generated_function_150"


def test_keyword_search_on_large_repository_respects_top_k(
    retriever: LexicalRetriever, large_retrieval_context: RepositoryContext
) -> None:
    results = retriever.keyword_search("generated transformation item", large_retrieval_context, top_k=10)
    assert len(results) <= 10


# ============================================================================
# retrieve() -- the RetrievalPlan-driven entry point
# ============================================================================


def test_retrieve_returns_context_tagged_with_lexical_retriever_kind(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    result = retriever.retrieve("parse_repository", _make_plan(), retrieval_context)
    assert result.retriever_kind is RetrieverKind.LEXICAL
    assert result.query == "parse_repository"


def test_retrieve_populates_chunk_content_and_docstring(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    result = retriever.retrieve("parse_repository", _make_plan(), retrieval_context)
    assert result.chunks
    top_chunk = result.chunks[0]

    assert top_chunk.name == "parse_repository"
    assert "def parse_repository" in top_chunk.content
    assert top_chunk.docstring == "Parse a repository at the given path and return its metadata."
    assert top_chunk.file_path == "utils.py"
    assert top_chunk.start_line is not None
    assert top_chunk.end_line is not None
    assert top_chunk.retriever_kind is RetrieverKind.LEXICAL
    assert top_chunk.node_type is NodeType.FUNCTION


def test_retrieve_respects_plan_candidate_limit(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    result = retriever.retrieve("repository path metadata", _make_plan(candidate_limit=1), retrieval_context)
    assert len(result.chunks) <= 1


def test_retrieve_total_candidates_matches_chunk_count(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    result = retriever.retrieve("parse_repository", _make_plan(candidate_limit=10), retrieval_context)
    assert result.total_candidates == len(result.chunks)


def test_retrieve_on_empty_repository_returns_empty_context(
    retriever: LexicalRetriever, empty_context: RepositoryContext
) -> None:
    result = retriever.retrieve("anything", _make_plan(), empty_context)
    assert result.chunks == []
    assert result.total_candidates == 0
    assert result.retriever_kind is RetrieverKind.LEXICAL


def test_retrieve_unknown_query_returns_empty_context(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    result = retriever.retrieve("zzz_totally_unknown_xyz", _make_plan(), retrieval_context)
    assert result.chunks == []


# ============================================================================
# Index caching
# ============================================================================


def test_index_is_cached_across_repeated_calls_against_the_same_context(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    retriever.keyword_search("parse_repository", retrieval_context, top_k=5)
    signature_after_first_call = retriever._indexed_signature

    retriever.keyword_search("greet", retrieval_context, top_k=5)
    signature_after_second_call = retriever._indexed_signature

    assert signature_after_first_call == signature_after_second_call


def test_index_rebuilds_for_a_different_context(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext, empty_context: RepositoryContext
) -> None:
    retriever.keyword_search("parse_repository", retrieval_context, top_k=5)
    signature_for_first_context = retriever._indexed_signature

    retriever.keyword_search("anything", empty_context, top_k=5)
    signature_for_second_context = retriever._indexed_signature

    assert signature_for_first_context != signature_for_second_context

    # And searching the first context again still finds its content --
    # confirms the rebuild for empty_context didn't corrupt shared state.
    results = retriever.keyword_search("parse_repository", retrieval_context, top_k=5)
    assert results
