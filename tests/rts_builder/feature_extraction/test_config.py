"""Unit tests for `evaluation.rts_builder.feature_extraction.config.FeatureExtractionSettings`."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings


def test_default_settings_construct_without_error() -> None:
    settings = FeatureExtractionSettings()
    assert settings.chars_per_token_estimate > 0


def test_query_complexity_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        FeatureExtractionSettings(
            query_complexity_length_weight=0.5,
            query_complexity_identifier_weight=0.5,
            query_complexity_clause_weight=0.5,
        )


def test_repository_size_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        FeatureExtractionSettings(
            small_repository_file_count_threshold=500,
            large_repository_file_count_threshold=50,
        )


def test_equal_thresholds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FeatureExtractionSettings(
            small_repository_file_count_threshold=100,
            large_repository_file_count_threshold=100,
        )
