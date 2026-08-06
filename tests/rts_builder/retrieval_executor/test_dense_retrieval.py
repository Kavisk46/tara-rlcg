"""Unit tests for `dense_retrieval.DenseRetriever`, `embedding_backend.HashingEmbedder`, and `vector_index.InMemoryVectorIndex`."""
from __future__ import annotations

import pytest

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.dense_retrieval import DenseRetriever
from evaluation.rts_builder.retrieval_executor.embedding_backend import HashingEmbedder
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName
from evaluation.rts_builder.retrieval_executor.vector_index import InMemoryVectorIndex

# ---------------------------------------------------------------------------
# HashingEmbedder
# ---------------------------------------------------------------------------


def test_hashing_embedder_is_deterministic_across_instances() -> None:
    vector_a = HashingEmbedder(dimensions=64).embed("parse the repository")
    vector_b = HashingEmbedder(dimensions=64).embed("parse the repository")
    assert vector_a == vector_b


def test_hashing_embedder_produces_the_configured_dimensionality() -> None:
    embedder = HashingEmbedder(dimensions=32)
    assert len(embedder.embed("anything")) == 32


def test_hashing_embedder_empty_text_yields_zero_vector() -> None:
    embedder = HashingEmbedder(dimensions=16)
    assert embedder.embed("") == [0.0] * 16


def test_hashing_embedder_output_is_unit_normalized_when_nonzero() -> None:
    import math

    embedder = HashingEmbedder(dimensions=64)
    vector = embedder.embed("a repository full of python files and classes")
    norm = math.sqrt(sum(component * component for component in vector))
    assert norm == pytest.approx(1.0)


def test_hashing_embedder_rejects_nonpositive_dimensions() -> None:
    with pytest.raises(ValueError):
        HashingEmbedder(dimensions=0)


def test_hashing_embedder_embed_batch_matches_embed_per_item() -> None:
    embedder = HashingEmbedder(dimensions=32)
    texts = ["alpha function", "beta class", "gamma module"]
    assert embedder.embed_batch(texts) == [embedder.embed(text) for text in texts]


# ---------------------------------------------------------------------------
# InMemoryVectorIndex
# ---------------------------------------------------------------------------


def test_vector_index_search_ranks_by_cosine_similarity() -> None:
    index = InMemoryVectorIndex()
    index.build({"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [0.9, 0.1]})

    results = index.search([1.0, 0.0], top_k=3)

    assert [doc_id for doc_id, _ in results] == ["a", "c", "b"]


def test_vector_index_search_breaks_ties_by_id_ascending() -> None:
    index = InMemoryVectorIndex()
    index.build({"z": [1.0, 0.0], "a": [1.0, 0.0]})

    results = index.search([1.0, 0.0], top_k=2)

    assert [doc_id for doc_id, _ in results] == ["a", "z"]


def test_vector_index_search_respects_top_k() -> None:
    index = InMemoryVectorIndex()
    index.build({"a": [1.0], "b": [1.0], "c": [1.0]})
    assert len(index.search([1.0], top_k=2)) == 2


def test_vector_index_search_on_empty_index_returns_empty() -> None:
    index = InMemoryVectorIndex()
    assert index.search([1.0, 0.0], top_k=5) == []


def test_vector_index_zero_query_vector_yields_zero_similarity_for_everything() -> None:
    index = InMemoryVectorIndex()
    index.build({"a": [1.0, 0.0]})
    results = index.search([0.0, 0.0], top_k=1)
    assert results == [("a", 0.0)]


# ---------------------------------------------------------------------------
# DenseRetriever
# ---------------------------------------------------------------------------


def test_dense_retriever_ranks_the_most_textually_similar_file_first(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = DenseRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "Dog bark helper", top_k=10)

    assert result.strategy_name is RetrievalStrategyName.DENSE
    assert result.retrieved_files
    assert result.retrieved_files[0].file_path == "app.py"


def test_dense_retriever_returns_every_file_when_top_k_is_large_enough(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = DenseRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "anything", top_k=10)

    assert len(result.retrieved_files) == len(sample_repository_model.files)


def test_dense_retriever_empty_repository_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, empty_repository_model: RepositoryModel
) -> None:
    retriever = DenseRetriever(settings=retrieval_settings)
    result = retriever.retrieve(empty_repository_model, "anything", top_k=10)

    assert result.retrieved_files == []


def test_dense_retriever_is_deterministic_across_repeated_calls(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = DenseRetriever(settings=retrieval_settings)
    first = retriever.retrieve(sample_repository_model, "Dog bark helper", top_k=10)
    second = retriever.retrieve(sample_repository_model, "Dog bark helper", top_k=10)

    assert first.retrieved_files == second.retrieved_files
