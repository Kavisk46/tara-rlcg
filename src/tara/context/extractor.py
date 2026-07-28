"""Repository Context Extractor: the second stage of the TARA pipeline.

Turns a `ParsedRepository` into a `RepositoryContext` by orchestrating
three independently testable collaborators: a `GraphBuilder`, a
`SymbolIndexBuilder`, and (optionally) a `RepositoryEmbedder`. This
module contains no graph, indexing, or embedding logic of its own -- see
`graph_builder.py`, `symbol_index.py`, and `embedder.py` for that.
"""
from __future__ import annotations

import time

from tara.context.embedder import RepositoryEmbedder
from tara.context.graph_builder import GraphBuilder
from tara.context.models import RepositoryContext
from tara.context.symbol_index import SymbolIndexBuilder
from tara.core.exceptions import ContextExtractionError
from tara.core.logging import get_logger
from tara.interfaces.context_extractor import ContextExtractor
from tara.parsing.models import ParsedRepository

logger = get_logger(__name__)

_SYMBOL_NODE_TYPES = frozenset({"class", "function", "method"})


class RepositoryContextExtractor(ContextExtractor):
    """Builds a `RepositoryContext` from a `ParsedRepository`.

    All collaborators are injected through the constructor rather than
    instantiated internally, so tests can substitute a mock embedder (to
    avoid loading a real model) or a fake graph builder without any of
    this class's own logic changing. This class itself performs no
    graph traversal, indexing, or text-assembly work -- it only calls
    its collaborators in order and assembles their outputs into a
    `RepositoryContext`.
    """

    def __init__(
        self,
        graph_builder: GraphBuilder,
        symbol_index: SymbolIndexBuilder,
        embedder: RepositoryEmbedder | None = None,
        embedding_model_name: str | None = None,
    ) -> None:
        """Construct the extractor.

        Args:
            graph_builder: Builds the structural graph from a `ParsedRepository`.
            symbol_index: Builds a `SymbolIndex` from that graph.
            embedder: Generates symbol embeddings. Pass None to build a
                `RepositoryContext` with structure and a symbol index
                but no embeddings, e.g. for fast structural-only use
                cases that don't need semantic search.
            embedding_model_name: Recorded on the resulting
                `RepositoryContext` for provenance. Has no effect on
                behavior; ignored if `embedder` is None.
        """
        self._graph_builder = graph_builder
        self._symbol_index_builder = symbol_index
        self._embedder = embedder
        self._embedding_model_name = embedding_model_name

    def extract(self, parsed_repository: ParsedRepository) -> RepositoryContext:
        """See `ContextExtractor.extract`."""
        start = time.perf_counter()
        try:
            graph = self._graph_builder.build(parsed_repository)
            symbol_index = self._symbol_index_builder.build(graph)
            embeddings = (
                self._embedder.embed_repository(parsed_repository) if self._embedder is not None else {}
            )
        except ContextExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize unexpected failures at the orchestration boundary
            raise ContextExtractionError(f"Failed to extract repository context: {exc}") from exc

        embedding_dimension = len(next(iter(embeddings.values()))) if embeddings else None
        file_count = sum(1 for _, data in graph.nodes(data=True) if data.get("type") == "file")
        symbol_count = sum(1 for _, data in graph.nodes(data=True) if data.get("type") in _SYMBOL_NODE_TYPES)

        context = RepositoryContext(
            root_path=parsed_repository.root_path,
            commit_sha=parsed_repository.commit_sha,
            graph=graph,
            symbol_index=symbol_index,
            embeddings=embeddings,
            embedding_dimension=embedding_dimension,
            embedding_model_name=self._embedding_model_name,
            file_count=file_count,
            symbol_count=symbol_count,
        )

        elapsed = time.perf_counter() - start
        logger.info(
            "Extracted repository context for %s: %s (%.3fs)",
            parsed_repository.root_path, context.graph_summary(), elapsed,
        )
        return context
