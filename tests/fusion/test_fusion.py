"""Unit tests for `tara.fusion.fusion.ContextFusion`, the top-level fusion pipeline.

Exercises the full pipeline (dedupe -> merge scores -> [rerank] -> top_k
cut -> token budget) end to end, plus every scenario called out
explicitly for this milestone: deterministic output, provenance
preservation, found-by preservation, dedup by node/symbol identity,
token-budget enforcement with clear truncation marking, single-retriever
input, and empty retrieval results.
"""
from __future__ import annotations

import pytest

from tara.core.exceptions import ContextFusionError
from tara.core.types import RetrieverKind
from tara.fusion.fusion import ContextFusion
from tara.fusion.token_budget import approximate_token_count
from tests.fusion.conftest import make_chunk, make_context, make_plan

DEFAULT_BUDGET = 10_000  # effectively unlimited for tests not exercising budgeting


# ============================================================================
# Empty input
# ============================================================================


def test_fuse_with_no_contexts_returns_empty_fused_context() -> None:
    result = ContextFusion().fuse("query", [], make_plan(), DEFAULT_BUDGET)

    assert result.query == "query"
    assert result.chunks == []
    assert result.total_tokens == 0
    assert result.candidate_count == 0
    assert result.truncated is False


def test_fuse_with_a_context_that_has_zero_chunks_returns_empty() -> None:
    empty_context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[])
    result = ContextFusion().fuse("q", [empty_context], make_plan(), DEFAULT_BUDGET)

    assert result.chunks == []
    assert result.candidate_count == 0


# ============================================================================
# Single retriever only
# ============================================================================


def test_fuse_single_retriever_single_chunk() -> None:
    chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.6)
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[chunk])
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL])

    result = ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    assert len(result.chunks) == 1
    fused = result.chunks[0]
    assert fused.chunk_id == "a"
    assert fused.found_by == (RetrieverKind.LEXICAL,)
    assert fused.source_scores == {"lexical": 0.6}
    assert fused.fused_score == pytest.approx(0.6)


def test_fuse_single_retriever_multiple_chunks_preserves_order_without_rerank() -> None:
    chunks = [
        make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.2),
        make_chunk(chunk_id="b", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.9),
    ]
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=chunks)
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], rerank=False)

    result = ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    # rerank=False: input order preserved, even though "b" scores higher.
    assert [c.chunk_id for c in result.chunks] == ["a", "b"]


# ============================================================================
# Deduplication by chunk_id (node/symbol identity)
# ============================================================================


def test_fuse_deduplicates_same_chunk_id_across_retrievers() -> None:
    lexical_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.4
    )
    dense_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.DENSE, normalized_score=0.8
    )
    lexical_context = make_context(
        retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[lexical_chunk]
    )
    dense_context = make_context(
        retriever_kind=RetrieverKind.DENSE, query="q", chunks=[dense_chunk]
    )
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL, RetrieverKind.DENSE])

    result = ContextFusion().fuse("q", [lexical_context, dense_context], plan, DEFAULT_BUDGET)

    assert result.candidate_count == 1
    assert len(result.chunks) == 1
    fused = result.chunks[0]
    assert fused.chunk_id == "shared"
    assert set(fused.found_by) == {RetrieverKind.LEXICAL, RetrieverKind.DENSE}
    assert fused.source_scores == {"lexical": 0.4, "dense": 0.8}
    assert fused.fused_score == pytest.approx(0.6)  # equal-weight average of 0.4 and 0.8


def test_fuse_distinct_chunk_ids_are_not_merged() -> None:
    lexical_chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    dense_chunk = make_chunk(chunk_id="b", retriever_kind=RetrieverKind.DENSE)
    lexical_context = make_context(
        retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[lexical_chunk]
    )
    dense_context = make_context(
        retriever_kind=RetrieverKind.DENSE, query="q", chunks=[dense_chunk]
    )
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL, RetrieverKind.DENSE])

    result = ContextFusion().fuse("q", [lexical_context, dense_context], plan, DEFAULT_BUDGET)

    assert result.candidate_count == 2
    assert {c.chunk_id for c in result.chunks} == {"a", "b"}


# ============================================================================
# Provenance preservation
# ============================================================================


def test_fuse_preserves_file_path_name_and_line_range() -> None:
    chunk = make_chunk(
        chunk_id="a",
        retriever_kind=RetrieverKind.LEXICAL,
        name="greet",
        file_path="app.py",
        start_line=5,
        end_line=10,
    )
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[chunk])

    result = ContextFusion().fuse("q", [context], make_plan(), DEFAULT_BUDGET)

    fused = result.chunks[0]
    assert fused.name == "greet"
    assert fused.file_path == "app.py"
    assert fused.start_line == 5
    assert fused.end_line == 10


def test_fuse_reports_contributing_retrievers_in_metadata() -> None:
    lexical_chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    dense_chunk = make_chunk(chunk_id="b", retriever_kind=RetrieverKind.DENSE)
    lexical_context = make_context(
        retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[lexical_chunk]
    )
    dense_context = make_context(
        retriever_kind=RetrieverKind.DENSE, query="q", chunks=[dense_chunk]
    )
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL, RetrieverKind.DENSE])

    result = ContextFusion().fuse("q", [lexical_context, dense_context], plan, DEFAULT_BUDGET)

    assert result.metadata["contributing_retrievers"] == ["dense", "lexical"]


# ============================================================================
# Reranking baseline (weighted score merge, not a cross-encoder)
# ============================================================================


def test_fuse_with_rerank_true_sorts_by_fused_score() -> None:
    chunks = [
        make_chunk(chunk_id="low", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.1),
        make_chunk(chunk_id="high", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.9),
    ]
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=chunks)
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], rerank=True)

    result = ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    assert [c.chunk_id for c in result.chunks] == ["high", "low"]
    assert result.metadata["reranked"] is True


def test_fuse_with_rerank_false_preserves_dedup_order() -> None:
    chunks = [
        make_chunk(chunk_id="low", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.1),
        make_chunk(chunk_id="high", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.9),
    ]
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=chunks)
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], rerank=False)

    result = ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    assert [c.chunk_id for c in result.chunks] == ["low", "high"]
    assert result.metadata["reranked"] is False


# ============================================================================
# top_k truncation
# ============================================================================


def test_fuse_cuts_to_top_k_after_reranking() -> None:
    chunks = [
        make_chunk(chunk_id=f"c{i}", retriever_kind=RetrieverKind.LEXICAL, normalized_score=i / 10)
        for i in range(5)
    ]
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=chunks)
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], rerank=True, top_k=2)

    result = ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    assert [c.chunk_id for c in result.chunks] == ["c4", "c3"]  # two highest-scored
    assert result.candidate_count == 5  # pre-truncation candidate count is still reported


def test_fuse_top_k_larger_than_candidate_pool_keeps_everything() -> None:
    chunks = [make_chunk(chunk_id="a"), ]
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=chunks)
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], top_k=100)

    result = ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    assert len(result.chunks) == 1


# ============================================================================
# Token budgeting and truncation marking
# ============================================================================


def test_fuse_enforces_token_budget() -> None:
    long_content = "x" * 400  # ~100 tokens at char/4
    short_content = "y" * 40  # ~10 tokens
    chunks = [
        make_chunk(chunk_id="a", content=long_content, normalized_score=0.9),
        make_chunk(chunk_id="b", content=short_content, normalized_score=0.1),
    ]
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=chunks)
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], top_k=10)

    budget = approximate_token_count(long_content)  # only the first chunk fits
    result = ContextFusion().fuse("q", [context], plan, budget)

    assert [c.chunk_id for c in result.chunks] == ["a"]
    assert result.truncated is True
    assert result.total_tokens == approximate_token_count(long_content)


def test_fuse_within_budget_is_not_marked_truncated() -> None:
    chunk = make_chunk(chunk_id="a", content="short")
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[chunk])

    result = ContextFusion().fuse("q", [context], make_plan(), DEFAULT_BUDGET)

    assert result.truncated is False


def test_fuse_reports_token_budget_in_metadata() -> None:
    chunk = make_chunk(chunk_id="a", content="short")
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[chunk])

    result = ContextFusion().fuse("q", [context], make_plan(), 42)

    assert result.metadata["token_budget"] == 42


# ============================================================================
# Query consistency validation
# ============================================================================


def test_fuse_raises_when_a_context_query_does_not_match() -> None:
    chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    context = make_context(
        retriever_kind=RetrieverKind.LEXICAL, query="other query", chunks=[chunk]
    )

    with pytest.raises(ContextFusionError):
        ContextFusion().fuse("original query", [context], make_plan(), DEFAULT_BUDGET)


def test_fuse_mismatched_query_does_not_dispatch_any_pipeline_work() -> None:
    # A validation failure should fail fast, before any dedup/merge/rerank work happens --
    # verified indirectly by confirming the raised error names the offending context.
    chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    context = make_context(
        retriever_kind=RetrieverKind.LEXICAL, query="other query", chunks=[chunk]
    )

    with pytest.raises(ContextFusionError, match="other query"):
        ContextFusion().fuse("original query", [context], make_plan(), DEFAULT_BUDGET)


# ============================================================================
# Determinism
# ============================================================================


def test_fuse_is_deterministic_across_repeated_calls() -> None:
    lexical_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.4
    )
    dense_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.DENSE, normalized_score=0.9
    )
    other_chunk = make_chunk(
        chunk_id="only-dense", retriever_kind=RetrieverKind.DENSE, normalized_score=0.2
    )
    lexical_context = make_context(
        retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[lexical_chunk]
    )
    dense_context = make_context(
        retriever_kind=RetrieverKind.DENSE, query="q", chunks=[dense_chunk, other_chunk]
    )
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL, RetrieverKind.DENSE], rerank=True, top_k=5)

    fusion = ContextFusion()
    first = fusion.fuse("q", [lexical_context, dense_context], plan, DEFAULT_BUDGET)
    second = fusion.fuse("q", [lexical_context, dense_context], plan, DEFAULT_BUDGET)

    assert [c.chunk_id for c in first.chunks] == [c.chunk_id for c in second.chunks]
    assert [c.fused_score for c in first.chunks] == [c.fused_score for c in second.chunks]
    assert first.total_tokens == second.total_tokens
    assert first.truncated == second.truncated


# ============================================================================
# Plan is not mutated
# ============================================================================


def test_fuse_does_not_mutate_the_plan() -> None:
    chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, query="q", chunks=[chunk])
    plan = make_plan(retrievers=[RetrieverKind.LEXICAL], rerank=True, top_k=3)
    snapshot = plan.model_copy(deep=True)

    ContextFusion().fuse("q", [context], plan, DEFAULT_BUDGET)

    assert plan == snapshot
