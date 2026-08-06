"""Integration-level tests for `evaluation.rts_builder.retrieval_executor.executor.RetrievalExecutor`."""
from __future__ import annotations

import pytest

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.exceptions import InvalidQueryError, MismatchedInputsError
from evaluation.rts_builder.retrieval_executor.executor import RetrievalExecutor
from evaluation.rts_builder.retrieval_executor.models import RetrievalExecutionResult, RetrievalStrategyName


def test_execute_all_returns_all_four_strategies(
    retrieval_settings: RetrievalExecutorSettings,
    sample_repository_model: RepositoryModel,
    sample_feature_vector: FeatureVector,
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    result = executor.execute_all(sample_repository_model, sample_feature_vector, "How does Dog bark?")

    assert isinstance(result, RetrievalExecutionResult)
    assert result.repository_id == sample_repository_model.repository_id
    assert result.commit_sha == sample_repository_model.commit_sha
    names = {r.strategy_name for r in result.all_results()}
    assert names == {
        RetrievalStrategyName.LEXICAL, RetrievalStrategyName.DENSE,
        RetrievalStrategyName.GRAPH, RetrievalStrategyName.HYBRID,
    }


def test_every_strategy_result_has_latency_and_token_count(
    retrieval_settings: RetrievalExecutorSettings,
    sample_repository_model: RepositoryModel,
    sample_feature_vector: FeatureVector,
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    result = executor.execute_all(sample_repository_model, sample_feature_vector, "Dog")

    for strategy_result in result.all_results():
        assert strategy_result.retrieval_latency_ms >= 0.0
        assert strategy_result.context_token_count >= 0
        assert strategy_result.retrieval_score >= 0.0


def test_execute_all_is_deterministic_across_repeated_calls(
    retrieval_settings: RetrievalExecutorSettings,
    sample_repository_model: RepositoryModel,
    sample_feature_vector: FeatureVector,
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    first = executor.execute_all(sample_repository_model, sample_feature_vector, "Dog bark helper")
    second = executor.execute_all(sample_repository_model, sample_feature_vector, "Dog bark helper")

    for first_result, second_result in zip(first.all_results(), second.all_results()):
        assert first_result.retrieved_files == second_result.retrieved_files
        assert first_result.retrieval_score == second_result.retrieval_score


def test_execute_all_raises_for_non_string_query(
    retrieval_settings: RetrievalExecutorSettings,
    sample_repository_model: RepositoryModel,
    sample_feature_vector: FeatureVector,
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    with pytest.raises(InvalidQueryError):
        executor.execute_all(sample_repository_model, sample_feature_vector, None)  # type: ignore[arg-type]


def test_execute_all_accepts_empty_query(
    retrieval_settings: RetrievalExecutorSettings,
    sample_repository_model: RepositoryModel,
    sample_feature_vector: FeatureVector,
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    result = executor.execute_all(sample_repository_model, sample_feature_vector, "")

    assert result.lexical.retrieved_files == []
    assert result.graph.retrieved_files == []


def test_execute_all_raises_on_mismatched_repository_id(
    retrieval_settings: RetrievalExecutorSettings,
    sample_repository_model: RepositoryModel,
    empty_feature_vector: FeatureVector,
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    with pytest.raises(MismatchedInputsError):
        executor.execute_all(sample_repository_model, empty_feature_vector, "any query")


def test_execute_all_on_empty_repository_does_not_crash(
    retrieval_settings: RetrievalExecutorSettings, empty_repository_model: RepositoryModel, empty_feature_vector: FeatureVector
) -> None:
    executor = RetrievalExecutor(settings=retrieval_settings)
    result = executor.execute_all(empty_repository_model, empty_feature_vector, "any query")

    for strategy_result in result.all_results():
        assert strategy_result.retrieved_files == []
        assert strategy_result.context_token_count == 0


def test_large_repository_size_category_caps_top_k(
    sample_repository_model: RepositoryModel,
) -> None:
    settings = RetrievalExecutorSettings(top_k=10, large_repository_top_k_cap=1)
    # Force the feature vector's resource category to LARGE without needing a real 500-file repo.
    extractor = FeatureExtractor(
        settings=FeatureExtractionSettings(small_repository_file_count_threshold=1, large_repository_file_count_threshold=2)
    )
    feature_vector = extractor.extract(sample_repository_model, "Dog")

    executor = RetrievalExecutor(settings=settings)
    result = executor.execute_all(sample_repository_model, feature_vector, "module")

    assert len(result.lexical.retrieved_files) <= 1
    assert len(result.dense.retrieved_files) <= 1
    assert len(result.graph.retrieved_files) <= 1
    assert len(result.hybrid.retrieved_files) <= 1
