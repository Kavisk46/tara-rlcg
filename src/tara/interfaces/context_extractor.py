"""Abstract interface for the Repository Context Extractor pipeline stage.

`ContextExtractor` is the second stage of the TARA pipeline: it turns a
`ParsedRepository` into a `RepositoryContext`, the semantic fact-base
(graph, symbol index, embeddings) later stages (task classification,
adaptive routing, retrieval, GraphRAG) build on. Defining it as an ABC
lets those stages depend on "a context extractor" rather than on
`RepositoryContextExtractor` specifically, mirroring how
`tara.interfaces.repository_parser.RepositoryParser` decouples parsing
consumers from `TreeSitterRepositoryParser`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from tara.context.models import RepositoryContext
from tara.parsing.models import ParsedRepository


class ContextExtractor(ABC):
    """Contract for turning a `ParsedRepository` into a `RepositoryContext`."""

    @abstractmethod
    def extract(self, parsed_repository: ParsedRepository) -> RepositoryContext:
        """Build the semantic representation of a parsed repository.

        Args:
            parsed_repository: The structural parse produced by a
                `RepositoryParser` implementation.

        Returns:
            A `RepositoryContext` combining the structural graph, a
            symbol index, and (optionally) per-symbol embeddings.

        Raises:
            ContextExtractionError: If the context cannot be built.
        """
        raise NotImplementedError
