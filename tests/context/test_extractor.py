"""Unit tests for `RepositoryContextExtractor`. No real embedding model is loaded."""
from __future__ import annotations

import networkx as nx
import pytest

from tara.context.embedder import Embedder, RepositoryEmbedder
from tara.context.extractor import RepositoryContextExtractor
from tara.context.graph_builder import GraphBuilder
from tara.context.symbol_index import SymbolIndex, SymbolIndexBuilder
from tara.core.exceptions import ContextExtractionError, GraphBuildError
from tara.parsing.models import ParsedRepository


class FakeEmbedder(Embedder):
    def embed(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class FailingGraphBuilder(GraphBuilder):
    def build(self, parsed_repository: ParsedRepository) -> nx.DiGraph:
        raise GraphBuildError("boom")


class ExplodingSymbolIndexBuilder(SymbolIndexBuilder):
    def build(self, graph: nx.DiGraph) -> SymbolIndex:
        raise RuntimeError("unexpected")


def test_extract_builds_full_context_with_embeddings(parsed_sample_repository: ParsedRepository) -> None:
    extractor = RepositoryContextExtractor(
        graph_builder=GraphBuilder(),
        symbol_index=SymbolIndexBuilder(),
        embedder=RepositoryEmbedder(FakeEmbedder(), batch_size=2),
        embedding_model_name="fake-model",
    )

    context = extractor.extract(parsed_sample_repository)

    assert context.graph.number_of_nodes() > 0
    assert context.symbol_count == 4  # Greeter, greet, main, add
    assert context.file_count == 2  # app.py, utils.py
    assert context.embedding_dimension == 2
    assert context.embedding_model_name == "fake-model"
    assert len(context.embeddings) == context.symbol_count

    for symbol_id in context.embeddings:
        assert context.symbol_index.get_by_id(symbol_id) is not None


def test_extract_without_embedder_returns_empty_embeddings(parsed_sample_repository: ParsedRepository) -> None:
    extractor = RepositoryContextExtractor(
        graph_builder=GraphBuilder(),
        symbol_index=SymbolIndexBuilder(),
        embedder=None,
    )

    context = extractor.extract(parsed_sample_repository)

    assert context.embeddings == {}
    assert context.embedding_dimension is None
    assert context.graph.number_of_nodes() > 0


def test_extract_propagates_typed_errors_from_collaborators(parsed_sample_repository: ParsedRepository) -> None:
    extractor = RepositoryContextExtractor(
        graph_builder=FailingGraphBuilder(),
        symbol_index=SymbolIndexBuilder(),
        embedder=None,
    )

    with pytest.raises(GraphBuildError):
        extractor.extract(parsed_sample_repository)


def test_extract_wraps_unexpected_errors_as_context_extraction_error(
    parsed_sample_repository: ParsedRepository,
) -> None:
    extractor = RepositoryContextExtractor(
        graph_builder=GraphBuilder(),
        symbol_index=ExplodingSymbolIndexBuilder(),
        embedder=None,
    )

    with pytest.raises(ContextExtractionError):
        extractor.extract(parsed_sample_repository)
