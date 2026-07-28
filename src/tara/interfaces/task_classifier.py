"""Abstract interface for the Task Classifier pipeline stage.

`TaskClassifier` is the third stage of the TARA pipeline: it turns a
raw developer query into a `TaskClassification`, the signal set the
Task-Guided Adaptive Router and every retriever (graph, dense, API,
static analysis) will use to decide what and how to retrieve. Defining
it as an ABC lets those stages depend on "a task classifier" rather than
on `HeuristicTaskClassifier` specifically, mirroring
`tara.interfaces.repository_parser.RepositoryParser` and
`tara.interfaces.context_extractor.ContextExtractor`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from tara.classification.models import TaskClassification


class TaskClassifier(ABC):
    """Contract for turning a raw developer query into a `TaskClassification`."""

    @abstractmethod
    def classify(self, query: str) -> TaskClassification:
        """Classify a developer query.

        Args:
            query: The raw natural-language query. Implementations must
                handle empty, whitespace-only, or punctuation-only input
                without raising -- an underspecified query is valid
                input, not an error.

        Returns:
            A `TaskClassification` describing the task type, recommended
            retrieval strategy, and every signal that recommendation was
            derived from.

        Raises:
            TaskClassificationError: If classification cannot complete.
        """
        raise NotImplementedError
