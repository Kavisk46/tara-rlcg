"""Unit tests for `tara.fusion.models`.

Covers `FusedChunk` and `FusedContext`: field constraints and the two
cross-field validators (`FusedChunk`'s line-span check, mirroring
`RetrievedChunk`'s, and its `found_by`/`source_scores` consistency
check). No fusion pipeline component is involved -- these are pure
data-contract tests.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tara.context.models import NodeType
from tara.core.types import RetrieverKind
from tara.fusion.models import FusedChunk, FusedContext
from tests.fusion.conftest import make_fused_chunk as _make_fused_chunk

# ============================================================================
# FusedChunk: field constraints
# ============================================================================


def test_fused_chunk_accepts_valid_line_span() -> None:
    chunk = _make_fused_chunk(start_line=5, end_line=10)
    assert chunk.start_line == 5
    assert chunk.end_line == 10


def test_fused_chunk_accepts_equal_start_and_end_line() -> None:
    chunk = _make_fused_chunk(start_line=5, end_line=5)
    assert chunk.start_line == chunk.end_line == 5


def test_fused_chunk_accepts_missing_line_span() -> None:
    chunk = _make_fused_chunk(start_line=None, end_line=None)
    assert chunk.start_line is None
    assert chunk.end_line is None


def test_fused_chunk_rejects_end_line_before_start_line() -> None:
    with pytest.raises(ValidationError, match="end_line"):
        _make_fused_chunk(start_line=10, end_line=5)


def test_fused_chunk_rejects_empty_chunk_id() -> None:
    with pytest.raises(ValidationError):
        _make_fused_chunk(chunk_id="")


def test_fused_chunk_rejects_negative_fused_score() -> None:
    with pytest.raises(ValidationError):
        _make_fused_chunk(fused_score=-0.1)


def test_fused_chunk_accepts_fused_score_above_one() -> None:
    # Not bounded to <= 1.0: a weighted-average of [0,1] inputs with weights that
    # don't sum to 1 can, by construction, exceed 1.0 (see ScoreMerger).
    chunk = _make_fused_chunk(fused_score=1.5)
    assert chunk.fused_score == 1.5


def test_fused_chunk_rejects_negative_token_count() -> None:
    with pytest.raises(ValidationError):
        _make_fused_chunk(token_count=-1)


def test_fused_chunk_rejects_empty_found_by() -> None:
    with pytest.raises(ValidationError):
        FusedChunk(
            chunk_id="c",
            node_type=NodeType.FUNCTION,
            name="greet",
            file_path="app.py",
            content="...",
            fused_score=0.5,
            found_by=(),
            source_scores={},
            token_count=1,
        )


def test_fused_chunk_metadata_defaults_to_empty_dict() -> None:
    chunk = _make_fused_chunk()
    assert chunk.metadata == {}


def test_fused_chunk_docstring_defaults_to_none() -> None:
    chunk = _make_fused_chunk()
    assert chunk.docstring is None


# ============================================================================
# FusedChunk: found_by / source_scores consistency
# ============================================================================


def test_fused_chunk_accepts_matching_found_by_and_source_scores() -> None:
    chunk = _make_fused_chunk(
        found_by=(RetrieverKind.LEXICAL, RetrieverKind.DENSE),
        source_scores={RetrieverKind.LEXICAL.value: 0.5, RetrieverKind.DENSE.value: 0.7},
    )
    assert set(chunk.found_by) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE}


def test_fused_chunk_rejects_found_by_missing_a_source_score() -> None:
    with pytest.raises(ValidationError, match="found_by"):
        _make_fused_chunk(
            found_by=(RetrieverKind.LEXICAL, RetrieverKind.DENSE),
            source_scores={RetrieverKind.LEXICAL.value: 0.5},
        )


def test_fused_chunk_rejects_source_scores_with_extra_key_not_in_found_by() -> None:
    with pytest.raises(ValidationError, match="found_by"):
        _make_fused_chunk(
            found_by=(RetrieverKind.LEXICAL,),
            source_scores={RetrieverKind.LEXICAL.value: 0.5, RetrieverKind.DENSE.value: 0.7},
        )


# ============================================================================
# FusedContext
# ============================================================================


def test_fused_context_defaults_to_empty_chunks_and_zero_totals() -> None:
    context = FusedContext(query="greet", truncated=False)
    assert context.chunks == []
    assert context.total_tokens == 0
    assert context.candidate_count == 0
    assert context.metadata == {}


def test_fused_context_rejects_negative_total_tokens() -> None:
    with pytest.raises(ValidationError):
        FusedContext(query="q", truncated=False, total_tokens=-1)


def test_fused_context_rejects_negative_candidate_count() -> None:
    with pytest.raises(ValidationError):
        FusedContext(query="q", truncated=False, candidate_count=-1)


def test_fused_context_preserves_chunk_order() -> None:
    first = _make_fused_chunk(chunk_id="file::a.py::f::1")
    second = _make_fused_chunk(chunk_id="file::a.py::g::2")
    context = FusedContext(query="q", truncated=False, chunks=[first, second])
    assert [c.chunk_id for c in context.chunks] == [first.chunk_id, second.chunk_id]


def test_fused_context_truncated_requires_explicit_value() -> None:
    with pytest.raises(ValidationError):
        FusedContext(query="q")  # type: ignore[call-arg]
