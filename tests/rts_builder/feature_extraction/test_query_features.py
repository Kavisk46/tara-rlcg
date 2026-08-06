"""Unit tests for `evaluation.rts_builder.feature_extraction.query_features`."""
from __future__ import annotations

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.query_features import compute_query_features


def test_identifier_count_matches_case_shaped_tokens(feature_settings: FeatureExtractionSettings) -> None:
    features = compute_query_features("please rename fooBar and max_size and RepositoryParser", feature_settings)
    assert features.identifier_count == 3


def test_api_token_count_matches_dotted_tokens(feature_settings: FeatureExtractionSettings) -> None:
    features = compute_query_features("use os.path.join and requests.get here", feature_settings)
    assert features.api_token_count == 2


def test_identifier_and_api_token_counts_do_not_overlap(feature_settings: FeatureExtractionSettings) -> None:
    features = compute_query_features("fooBar and self.fooBar", feature_settings)
    assert features.identifier_count == 1
    assert features.api_token_count == 1


def test_keyword_indicators_detect_their_category(feature_settings: FeatureExtractionSettings) -> None:
    assert compute_query_features("How does this work?", feature_settings).has_question_keyword is True
    assert compute_query_features("There is a bug here", feature_settings).has_bug_keyword is True
    assert compute_query_features("please add a pytest test", feature_settings).has_test_keyword is True
    assert compute_query_features("please refactor this function", feature_settings).has_refactor_keyword is True


def test_keyword_indicators_are_false_when_absent(feature_settings: FeatureExtractionSettings) -> None:
    features = compute_query_features("print the current balance", feature_settings)
    assert features.has_question_keyword is False
    assert features.has_bug_keyword is False
    assert features.has_test_keyword is False
    assert features.has_refactor_keyword is False


def test_query_complexity_is_bounded_to_unit_interval(feature_settings: FeatureExtractionSettings) -> None:
    long_query = " and ".join(f"identifier_{i}_looksLikeThis" for i in range(50))
    features = compute_query_features(long_query, feature_settings)
    assert 0.0 <= features.complexity <= 1.0


def test_query_complexity_increases_with_length_identifiers_and_clauses(
    feature_settings: FeatureExtractionSettings,
) -> None:
    simple = compute_query_features("fix this", feature_settings)
    complex_query = compute_query_features(
        "fix fooBar, and also refactor max_size, and then rename RepositoryParser, and check self.helper",
        feature_settings,
    )
    assert complex_query.complexity > simple.complexity


def test_empty_query_yields_all_zero_features(feature_settings: FeatureExtractionSettings) -> None:
    features = compute_query_features("", feature_settings)

    assert features.length == 0
    assert features.identifier_count == 0
    assert features.api_token_count == 0
    assert features.has_question_keyword is False
    assert features.has_bug_keyword is False
    assert features.has_test_keyword is False
    assert features.has_refactor_keyword is False
    assert features.complexity == 0.0


def test_query_length_is_character_count_not_token_count(feature_settings: FeatureExtractionSettings) -> None:
    features = compute_query_features("abc def", feature_settings)
    assert features.length == len("abc def")
