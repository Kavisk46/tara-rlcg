"""Integration-level tests for `FeatureExtractor.extract`, against a real parsed repository."""
from __future__ import annotations

import json

import pytest

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.exceptions import InvalidQueryError
from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
from evaluation.rts_builder.feature_extraction.models import FeatureVector, RepositorySizeCategory
from evaluation.rts_builder.parser.models import RepositoryModel
from tara.core.types import Language


def test_extract_returns_a_fully_populated_feature_vector(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "How do I fix the bug in Dog.bark()?")

    assert isinstance(vector, FeatureVector)
    assert vector.repository_id == sample_repository_model.repository_id
    assert vector.commit_sha == sample_repository_model.commit_sha
    assert vector.query_text == "How do I fix the bug in Dog.bark()?"


def test_extract_query_features_reflect_the_query_text(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "How do I fix the bug in Dog.bark()?")

    assert vector.query.length == len("How do I fix the bug in Dog.bark()?")
    assert vector.query.has_question_keyword is True
    assert vector.query.has_bug_keyword is True
    assert vector.query.has_test_keyword is False
    assert vector.query.api_token_count >= 1  # 'Dog.bark' is a dotted token


def test_extract_repository_features_reflect_the_repository(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "any query")

    assert vector.repository.file_count == 3
    assert vector.repository.function_count == 4  # helper, main, speak, bark
    assert vector.repository.class_count == 2  # Animal, Dog
    assert vector.repository.module_count == 2  # 'app' and 'pkg'
    assert vector.repository.dominant_language is Language.PYTHON


def test_extract_graph_features_are_internally_consistent(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "any query")

    assert vector.graph.import_density == len(sample_repository_model.import_graph) / 3
    assert vector.graph.call_density == len(sample_repository_model.call_graph) / 4
    assert vector.graph.inheritance_density == len(sample_repository_model.inheritance_graph) / 2
    assert vector.graph.connected_components >= 1
    assert vector.graph.avg_degree >= 0.0


def test_extract_structural_features_docstring_and_comment_coverage(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "any query")

    # Only Animal has a docstring, out of 4 functions + 2 classes = 6 documentable symbols.
    assert vector.structural.docstring_coverage_ratio == pytest.approx(1 / 6)
    assert vector.structural.comment_coverage_ratio > 0.0


def test_extract_resource_features_are_positive_and_categorized(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "any query")

    assert vector.resource.estimated_repository_tokens > 0
    assert vector.resource.repository_size_category is RepositorySizeCategory.SMALL


def test_extract_is_deterministic_across_repeated_calls(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    first = extractor.extract(sample_repository_model, "How do I fix the bug in Dog.bark()?")
    second = extractor.extract(sample_repository_model, "How do I fix the bug in Dog.bark()?")

    assert first.query == second.query
    assert first.repository == second.repository
    assert first.graph == second.graph
    assert first.structural == second.structural
    assert first.resource == second.resource


def test_extract_raises_invalid_query_error_for_non_string_query(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    with pytest.raises(InvalidQueryError):
        extractor.extract(sample_repository_model, None)  # type: ignore[arg-type]


def test_extract_accepts_empty_query_string(extractor: FeatureExtractor, sample_repository_model: RepositoryModel) -> None:
    vector = extractor.extract(sample_repository_model, "")

    assert vector.query.length == 0
    assert vector.query.identifier_count == 0
    assert vector.query.complexity == 0.0
    assert vector.query.has_question_keyword is False


def test_to_flat_dict_contains_every_leaf_feature_with_group_prefixes(
    extractor: FeatureExtractor, sample_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(sample_repository_model, "fix the bug")
    flat = vector.to_flat_dict()

    expected_keys = {
        "query_length", "query_identifier_count", "query_api_token_count", "query_has_question_keyword",
        "query_has_bug_keyword", "query_has_test_keyword", "query_has_refactor_keyword", "query_complexity",
        "repo_file_count", "repo_function_count", "repo_class_count", "repo_module_count",
        "repo_avg_file_size_bytes", "repo_dominant_language",
        "graph_import_density", "graph_call_density", "graph_inheritance_density",
        "graph_connected_components", "graph_avg_degree",
        "structural_avg_functions_per_file", "structural_avg_classes_per_file",
        "structural_docstring_coverage_ratio", "structural_comment_coverage_ratio",
        "resource_estimated_repository_tokens", "resource_repository_size_category",
    }
    assert set(flat.keys()) == expected_keys
    assert flat["repo_dominant_language"] == "python"
    assert flat["resource_repository_size_category"] == "small"
    # Provenance fields must not leak into the ML-facing flat row.
    assert "repository_id" not in flat
    assert "commit_sha" not in flat
    assert "query_text" not in flat
    assert "computed_at" not in flat


def test_feature_vector_json_round_trip(extractor: FeatureExtractor, sample_repository_model: RepositoryModel) -> None:
    vector = extractor.extract(sample_repository_model, "fix the bug")

    payload = vector.model_dump_json()
    reloaded = FeatureVector.model_validate(json.loads(payload))

    assert reloaded.query == vector.query
    assert reloaded.repository == vector.repository
    assert reloaded.graph == vector.graph
    assert reloaded.structural == vector.structural
    assert reloaded.resource == vector.resource


def test_extract_on_empty_repository_does_not_divide_by_zero(
    extractor: FeatureExtractor, empty_repository_model: RepositoryModel
) -> None:
    vector = extractor.extract(empty_repository_model, "any query")

    assert vector.repository.file_count == 0
    assert vector.repository.avg_file_size_bytes == 0.0
    assert vector.repository.dominant_language is Language.UNKNOWN
    assert vector.graph.import_density == 0.0
    assert vector.graph.connected_components == 0
    assert vector.graph.avg_degree == 0.0
    assert vector.structural.avg_functions_per_file == 0.0
    assert vector.structural.docstring_coverage_ratio == 0.0
    assert vector.structural.comment_coverage_ratio == 0.0
    assert vector.resource.estimated_repository_tokens == 0
    assert vector.resource.repository_size_category is RepositorySizeCategory.SMALL


def test_comment_coverage_disabled_via_settings_is_always_zero(
    sample_repository_model: RepositoryModel,
) -> None:
    settings = FeatureExtractionSettings(enable_comment_coverage=False)
    extractor = FeatureExtractor(settings=settings)

    vector = extractor.extract(sample_repository_model, "any query")

    assert vector.structural.comment_coverage_ratio == 0.0
