"""Computes `ResourceFeatures` from a `RepositoryModel`."""
from __future__ import annotations

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.models import RepositorySizeCategory, ResourceFeatures
from evaluation.rts_builder.parser.models import RepositoryModel


def compute_resource_features(model: RepositoryModel, settings: FeatureExtractionSettings) -> ResourceFeatures:
    """Compute every downstream-consumption-cost feature.

    Args:
        model: The parsed repository to summarize.
        settings: Controls the token-estimation ratio and the
            small/large size-category thresholds.

    Returns:
        The populated `ResourceFeatures`.
    """
    total_bytes = sum(normalized_file.size_bytes for normalized_file in model.files)
    estimated_repository_tokens = round(total_bytes / settings.chars_per_token_estimate)

    file_count = len(model.files)
    if file_count <= settings.small_repository_file_count_threshold:
        category = RepositorySizeCategory.SMALL
    elif file_count <= settings.large_repository_file_count_threshold:
        category = RepositorySizeCategory.MEDIUM
    else:
        category = RepositorySizeCategory.LARGE

    return ResourceFeatures(estimated_repository_tokens=estimated_repository_tokens, repository_size_category=category)
