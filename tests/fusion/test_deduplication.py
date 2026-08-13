"""Unit tests for `tara.fusion.deduplication.Deduplicator`."""
from __future__ import annotations

from tara.core.types import RetrieverKind
from tara.fusion.deduplication import Deduplicator
from tests.fusion.conftest import make_chunk, make_context


def test_deduplicate_empty_contexts_list_returns_empty() -> None:
    assert Deduplicator().deduplicate([]) == []


def test_deduplicate_single_context_with_no_chunks_returns_empty() -> None:
    context = make_context(chunks=[])
    assert Deduplicator().deduplicate([context]) == []


def test_deduplicate_single_retriever_single_chunk() -> None:
    chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.7)
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, chunks=[chunk])

    [candidate] = Deduplicator().deduplicate([context])

    assert candidate.chunk is chunk
    assert candidate.found_by == (RetrieverKind.LEXICAL,)
    assert candidate.source_scores == {"lexical": 0.7}


def test_deduplicate_preserves_first_seen_order_across_distinct_chunk_ids() -> None:
    first = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    second = make_chunk(chunk_id="b", retriever_kind=RetrieverKind.LEXICAL)
    context = make_context(retriever_kind=RetrieverKind.LEXICAL, chunks=[first, second])

    candidates = Deduplicator().deduplicate([context])

    assert [c.chunk.chunk_id for c in candidates] == ["a", "b"]


def test_deduplicate_merges_same_chunk_id_found_by_two_retrievers() -> None:
    lexical_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.LEXICAL, normalized_score=0.4
    )
    dense_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.DENSE, normalized_score=0.9
    )
    lexical_context = make_context(retriever_kind=RetrieverKind.LEXICAL, chunks=[lexical_chunk])
    dense_context = make_context(retriever_kind=RetrieverKind.DENSE, chunks=[dense_chunk])

    [candidate] = Deduplicator().deduplicate([lexical_context, dense_context])

    assert candidate.found_by == (RetrieverKind.DENSE, RetrieverKind.LEXICAL)  # sorted by .value
    assert candidate.source_scores == {"lexical": 0.4, "dense": 0.9}


def test_deduplicate_uses_first_context_chunk_as_canonical() -> None:
    lexical_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.LEXICAL, content="lexical version"
    )
    dense_chunk = make_chunk(
        chunk_id="shared", retriever_kind=RetrieverKind.DENSE, content="dense version"
    )
    lexical_context = make_context(retriever_kind=RetrieverKind.LEXICAL, chunks=[lexical_chunk])
    dense_context = make_context(retriever_kind=RetrieverKind.DENSE, chunks=[dense_chunk])

    [candidate] = Deduplicator().deduplicate([lexical_context, dense_context])
    assert candidate.chunk.content == "lexical version"

    [candidate_reordered] = Deduplicator().deduplicate([dense_context, lexical_context])
    assert candidate_reordered.chunk.content == "dense version"


def test_deduplicate_distinct_chunk_ids_across_retrievers_stay_separate() -> None:
    lexical_chunk = make_chunk(chunk_id="a", retriever_kind=RetrieverKind.LEXICAL)
    dense_chunk = make_chunk(chunk_id="b", retriever_kind=RetrieverKind.DENSE)
    lexical_context = make_context(retriever_kind=RetrieverKind.LEXICAL, chunks=[lexical_chunk])
    dense_context = make_context(retriever_kind=RetrieverKind.DENSE, chunks=[dense_chunk])

    candidates = Deduplicator().deduplicate([lexical_context, dense_context])

    assert [c.chunk.chunk_id for c in candidates] == ["a", "b"]
    assert candidates[0].found_by == (RetrieverKind.LEXICAL,)
    assert candidates[1].found_by == (RetrieverKind.DENSE,)


def test_deduplicate_three_retrievers_agreeing_on_one_chunk() -> None:
    kinds = (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)
    contexts = [
        make_context(
            retriever_kind=kind, chunks=[make_chunk(chunk_id="shared", retriever_kind=kind)]
        )
        for kind in kinds
    ]

    [candidate] = Deduplicator().deduplicate(contexts)

    assert set(candidate.found_by) == set(kinds)
    assert set(candidate.source_scores) == {kind.value for kind in kinds}


def test_deduplicate_is_deterministic_across_repeated_calls() -> None:
    lexical_chunk = make_chunk(chunk_id="shared", retriever_kind=RetrieverKind.LEXICAL)
    dense_chunk = make_chunk(chunk_id="shared", retriever_kind=RetrieverKind.DENSE)
    contexts = [
        make_context(retriever_kind=RetrieverKind.LEXICAL, chunks=[lexical_chunk]),
        make_context(retriever_kind=RetrieverKind.DENSE, chunks=[dense_chunk]),
    ]

    first = Deduplicator().deduplicate(contexts)
    second = Deduplicator().deduplicate(contexts)

    assert [c.chunk.chunk_id for c in first] == [c.chunk.chunk_id for c in second]
    assert [c.found_by for c in first] == [c.found_by for c in second]
