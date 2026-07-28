"""Abstract interface for the Task-Guided Adaptive Router pipeline stage.

`Router` is the fourth stage of the TARA pipeline: it turns a
`TaskClassification` plus a `RepositoryContext` into a `RetrievalPlan`,
the execution recipe the (future) retrieval stage will run. Defining it
as an ABC lets that future stage depend on "a router" rather than on
`AdaptiveRouter` specifically, mirroring `RepositoryParser`,
`ContextExtractor`, and `TaskClassifier`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.routing.models import RetrievalPlan


class Router(ABC):
    """Contract for turning a `TaskClassification` into a `RetrievalPlan`."""

    @abstractmethod
    def route(self, classification: TaskClassification, context: RepositoryContext) -> RetrievalPlan:
        """Decide which retriever(s) to run, and how, for a classified query.

        This stage never performs retrieval itself: no repository
        traversal, no embedding generation, no network call. `context`
        is consulted only for cheap, already-computed capability checks
        (e.g. whether embeddings exist yet).

        Args:
            classification: The Task Classifier's analysis of the query.
            context: The repository's semantic context, used only to
                confirm a recommended retriever is actually supported.

        Returns:
            A `RetrievalPlan` describing what to retrieve with and how.

        Raises:
            RoutingError: If no plan can be produced.
        """
        raise NotImplementedError
