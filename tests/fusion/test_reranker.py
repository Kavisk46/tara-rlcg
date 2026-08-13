"""Unit tests for `tara.fusion.reranker.BaselineReranker`.

This IS the "weighted merge of normalized per-retriever scores" baseline
PROJECT_SPEC.md §20.2 specifies -- a plain descending sort by
`fused_score`, already computed by `ScoreMerger`. No cross-encoder or
learned model is exercised or implemented here.
"""
from __future__ import annotations

from tara.fusion.models import FusedChunk
from tara.fusion.reranker import BaselineReranker
from tests.fusion.conftest import make_fused_chunk as _make_fused_chunk


def test_rerank_empty_list_returns_empty() -> None:
    assert BaselineReranker().rerank([]) == []


def test_rerank_single_chunk_returns_it_unchanged() -> None:
    chunk = _make_fused_chunk(chunk_id="a")
    assert BaselineReranker().rerank([chunk]) == [chunk]


def test_rerank_sorts_by_descending_fused_score() -> None:
    low = _make_fused_chunk(chunk_id="low", fused_score=0.2)
    high = _make_fused_chunk(chunk_id="high", fused_score=0.9)
    mid = _make_fused_chunk(chunk_id="mid", fused_score=0.5)

    result = BaselineReranker().rerank([low, high, mid])

    assert [c.chunk_id for c in result] == ["high", "mid", "low"]


def test_rerank_breaks_ties_by_ascending_chunk_id() -> None:
    b = _make_fused_chunk(chunk_id="b", fused_score=0.5)
    a = _make_fused_chunk(chunk_id="a", fused_score=0.5)

    result = BaselineReranker().rerank([b, a])

    assert [c.chunk_id for c in result] == ["a", "b"]


def test_rerank_does_not_mutate_input_list() -> None:
    low = _make_fused_chunk(chunk_id="low", fused_score=0.2)
    high = _make_fused_chunk(chunk_id="high", fused_score=0.9)
    original: list[FusedChunk] = [low, high]

    BaselineReranker().rerank(original)

    assert original == [low, high]


def test_rerank_is_deterministic_across_repeated_calls() -> None:
    chunks = [
        _make_fused_chunk(chunk_id="a", fused_score=0.3),
        _make_fused_chunk(chunk_id="b", fused_score=0.7),
        _make_fused_chunk(chunk_id="c", fused_score=0.5),
    ]
    first = [c.chunk_id for c in BaselineReranker().rerank(chunks)]
    second = [c.chunk_id for c in BaselineReranker().rerank(chunks)]
    assert first == second
