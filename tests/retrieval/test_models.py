"""Unit tests for `tara.retrieval.models`.

Covers `RetrievalScore`, `SearchResult`, `RetrievedChunk`, and
`RetrievedContext`: field constraints and the two cross-field
validators (`RetrievedChunk`'s line-span check and `RetrievedContext`'s
chunk/retriever-kind consistency check). No retriever, index, or
repository fixture is needed -- these are pure data-contract tests.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tara.context.models import NodeType
from tara.core.types import RetrieverKind
from tara.retrieval.models import (
    MatchedField,
    RetrievalScore,
    RetrievedChunk,
    RetrievedContext,
    SearchResult,
)


def _make_score(raw: float = 1.0, normalized: float = 0.5) -> RetrievalScore:
    return RetrievalScore(raw_score=raw, normalized_score=normalized)


def _make_chunk(
    *,
    chunk_id: str = "file::app.py::greet::5",
    retriever_kind: RetrieverKind = RetrieverKind.LEXICAL,
    start_line: int | None = 5,
    end_line: int | None = 10,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        retriever_kind=retriever_kind,
        node_type=NodeType.FUNCTION,
        name="greet",
        file_path="app.py",
        start_line=start_line,
        end_line=end_line,
        content="def greet(): ...",
        score=_make_score(),
    )


# ============================================================================
# RetrievalScore
# ============================================================================


def test_retrieval_score_accepts_boundary_normalized_values() -> None:
    assert RetrievalScore(raw_score=0.0, normalized_score=0.0).normalized_score == 0.0
    assert RetrievalScore(raw_score=0.0, normalized_score=1.0).normalized_score == 1.0


@pytest.mark.parametrize("bad_normalized", [-0.01, 1.01, -5.0, 5.0])
def test_retrieval_score_rejects_out_of_range_normalized_score(bad_normalized: float) -> None:
    with pytest.raises(ValidationError):
        RetrievalScore(raw_score=1.0, normalized_score=bad_normalized)


def test_retrieval_score_matched_terms_defaults_to_empty_tuple() -> None:
    score = _make_score()
    assert score.matched_terms == ()


def test_retrieval_score_allows_negative_raw_score() -> None:
    # raw_score is unbounded (BM25 scores can be negative); only normalized_score is constrained.
    score = RetrievalScore(raw_score=-3.5, normalized_score=0.0)
    assert score.raw_score == -3.5


# ============================================================================
# SearchResult
# ============================================================================


def test_search_result_round_trips_fields() -> None:
    result = SearchResult(
        node_id="file::utils.py::parse_repository::1",
        node_type=NodeType.FUNCTION,
        name="parse_repository",
        file_path="utils.py",
        score=_make_score(),
        matched_field=MatchedField.NAME,
    )
    assert result.node_id == "file::utils.py::parse_repository::1"
    assert result.matched_field is MatchedField.NAME


@pytest.mark.parametrize("field", ["node_id", "name", "file_path"])
def test_search_result_rejects_empty_required_strings(field: str) -> None:
    kwargs = {
        "node_id": "id",
        "node_type": NodeType.FUNCTION,
        "name": "name",
        "file_path": "path.py",
        "score": _make_score(),
        "matched_field": MatchedField.NAME,
    }
    kwargs[field] = ""
    with pytest.raises(ValidationError):
        SearchResult(**kwargs)


# ============================================================================
# RetrievedChunk
# ============================================================================


def test_retrieved_chunk_accepts_valid_line_span() -> None:
    chunk = _make_chunk(start_line=5, end_line=10)
    assert chunk.start_line == 5
    assert chunk.end_line == 10


def test_retrieved_chunk_accepts_equal_start_and_end_line() -> None:
    chunk = _make_chunk(start_line=5, end_line=5)
    assert chunk.start_line == chunk.end_line == 5


def test_retrieved_chunk_accepts_missing_line_span() -> None:
    chunk = _make_chunk(start_line=None, end_line=None)
    assert chunk.start_line is None
    assert chunk.end_line is None


def test_retrieved_chunk_accepts_partial_line_span() -> None:
    # Only one of start_line/end_line set is not itself invalid -- the validator only
    # fires the ordering check when both are present.
    chunk = _make_chunk(start_line=5, end_line=None)
    assert chunk.start_line == 5
    assert chunk.end_line is None


def test_retrieved_chunk_rejects_end_line_before_start_line() -> None:
    with pytest.raises(ValidationError, match="end_line"):
        _make_chunk(start_line=10, end_line=5)


def test_retrieved_chunk_rejects_negative_line_numbers() -> None:
    with pytest.raises(ValidationError):
        _make_chunk(start_line=-1, end_line=5)


def test_retrieved_chunk_metadata_defaults_to_empty_dict() -> None:
    chunk = _make_chunk()
    assert chunk.metadata == {}


def test_retrieved_chunk_docstring_defaults_to_none() -> None:
    chunk = _make_chunk()
    assert chunk.docstring is None


def test_retrieved_chunk_rejects_empty_chunk_id() -> None:
    with pytest.raises(ValidationError):
        _make_chunk(chunk_id="")


# ============================================================================
# RetrievedContext
# ============================================================================


def test_retrieved_context_accepts_chunks_with_matching_retriever_kind() -> None:
    chunk = _make_chunk(retriever_kind=RetrieverKind.LEXICAL)
    context = RetrievedContext(retriever_kind=RetrieverKind.LEXICAL, query="greet", chunks=[chunk])
    assert context.chunks == [chunk]


def test_retrieved_context_rejects_chunk_with_mismatched_retriever_kind() -> None:
    chunk = _make_chunk(retriever_kind=RetrieverKind.DENSE)
    with pytest.raises(ValidationError, match="retriever_kind"):
        RetrievedContext(retriever_kind=RetrieverKind.LEXICAL, query="greet", chunks=[chunk])


def test_retrieved_context_defaults_to_empty_chunks_and_zero_candidates() -> None:
    context = RetrievedContext(retriever_kind=RetrieverKind.GRAPH, query="anything")
    assert context.chunks == []
    assert context.total_candidates == 0
    assert context.metadata == {}


def test_retrieved_context_rejects_negative_total_candidates() -> None:
    with pytest.raises(ValidationError):
        RetrievedContext(retriever_kind=RetrieverKind.LEXICAL, query="q", total_candidates=-1)


def test_retrieved_context_preserves_chunk_order() -> None:
    first = _make_chunk(chunk_id="file::a.py::f::1")
    second = _make_chunk(chunk_id="file::a.py::g::2")
    context = RetrievedContext(
        retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[first, second]
    )
    assert [c.chunk_id for c in context.chunks] == [first.chunk_id, second.chunk_id]
