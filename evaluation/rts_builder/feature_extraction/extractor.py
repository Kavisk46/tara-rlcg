"""`FeatureExtractor`: the Feature Extraction subsystem's single public entry point.

Turns a `(RepositoryModel, developer query)` pair into a `FeatureVector`,
computing each of the five feature groups via its own module and
assembling the result. Stateless and deterministic: the same inputs and
`FeatureExtractionSettings` always produce the same feature values (see
`README.md`); it holds no cache and mutates nothing it's given.
"""
from __future__ import annotations

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.exceptions import InvalidQueryError
from evaluation.rts_builder.feature_extraction.graph_features import compute_graph_features
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.feature_extraction.query_features import compute_query_features
from evaluation.rts_builder.feature_extraction.repository_features import compute_repository_features
from evaluation.rts_builder.feature_extraction.resource_features import compute_resource_features
from evaluation.rts_builder.feature_extraction.structural_features import compute_structural_features
from evaluation.rts_builder.parser.models import RepositoryModel
from tara.core.logging import get_logger

logger = get_logger(__name__)


class FeatureExtractor:
    """Computes a normalized `FeatureVector` for one `(RepositoryModel, query)` pair."""

    def __init__(self, settings: FeatureExtractionSettings | None = None) -> None:
        """Construct the extractor.

        Args:
            settings: Configuration for every group's tunable constants
                (thresholds, weights, the token-estimation ratio).
                Defaults to `FeatureExtractionSettings()` (environment
                defaults) when omitted.
        """
        self._settings = settings or FeatureExtractionSettings()

    def extract(self, repository_model: RepositoryModel, query_text: str) -> FeatureVector:
        """Compute the full `FeatureVector` for `repository_model` and `query_text`.

        Args:
            repository_model: The Parser subsystem's normalized output
                for the repository this feature vector describes.
            query_text: The raw developer query. An empty string is
                valid and yields all-zero/False query features.

        Returns:
            The populated `FeatureVector`.

        Raises:
            InvalidQueryError: If `query_text` is not a `str` (e.g. `None`).
        """
        if not isinstance(query_text, str):
            raise InvalidQueryError(f"query_text must be a str, got {type(query_text).__name__}.")

        vector = FeatureVector(
            repository_id=repository_model.repository_id,
            commit_sha=repository_model.commit_sha,
            query_text=query_text,
            query=compute_query_features(query_text, self._settings),
            repository=compute_repository_features(repository_model),
            graph=compute_graph_features(repository_model),
            structural=compute_structural_features(repository_model, self._settings),
            resource=compute_resource_features(repository_model, self._settings),
        )

        logger.info(
            "Extracted feature vector for %s@%s (query length %d chars)",
            repository_model.repository_id, repository_model.commit_sha[:8], len(query_text),
        )
        return vector
