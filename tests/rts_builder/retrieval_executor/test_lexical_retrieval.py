"""Unit tests for `evaluation.rts_builder.retrieval_executor.lexical_retrieval.LexicalRetriever`."""
from __future__ import annotations

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.lexical_retrieval import LexicalRetriever
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName


def test_exact_identifier_match_ranks_the_defining_file_first(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "Dog", top_k=10)

    assert result.strategy_name is RetrievalStrategyName.LEXICAL
    assert result.retrieved_files
    assert result.retrieved_files[0].file_path == "app.py"


def test_query_term_absent_from_every_document_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "noise", top_k=10)

    # 'noise' appears only inside Animal.speak's return *value*, which RepositoryModel
    # does not retain (no source text) -- this repository has no lexical match for it.
    assert result.retrieved_files == []


def test_query_matching_docstring_text_retrieves_the_right_file(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "barks", top_k=10)

    assert any(f.file_path == "app.py" for f in result.retrieved_files)


def test_empty_query_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "", top_k=10)

    assert result.retrieved_files == []
    assert result.retrieval_score == 0.0


def test_empty_repository_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, empty_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(empty_repository_model, "Dog", top_k=10)

    assert result.retrieved_files == []
    assert result.context_token_count == 0


def test_top_k_bounds_the_result_size(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "module", top_k=1)

    assert len(result.retrieved_files) <= 1


def test_context_token_count_reflects_retrieved_file_sizes(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "Dog", top_k=10)

    size_by_path = {f.path: f.size_bytes for f in sample_repository_model.files}
    expected_bytes = sum(size_by_path[f.file_path] for f in result.retrieved_files)
    expected_tokens = round(expected_bytes / retrieval_settings.chars_per_token_estimate)
    assert result.context_token_count == expected_tokens


def test_result_is_deterministic_across_repeated_calls(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = LexicalRetriever(settings=retrieval_settings)
    first = retriever.retrieve(sample_repository_model, "Dog bark helper", top_k=10)
    second = retriever.retrieve(sample_repository_model, "Dog bark helper", top_k=10)

    assert first.retrieved_files == second.retrieved_files
    assert first.retrieval_score == second.retrieval_score
