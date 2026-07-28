"""Data models and graph vocabulary for the Repository Context Extractor.

Defines the node/edge vocabulary (`NodeType`, `EdgeRelation`) and the
deterministic node-id builders shared by `GraphBuilder`, `SymbolIndex`,
and the embedding layer, plus the `RepositoryContext` aggregate returned
by `RepositoryContextExtractor`. Centralizing the id scheme here (rather
than in `graph_builder.py`) lets every collaborator depend on this one
module instead of on each other, avoiding import cycles within
`tara.context`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from tara.context.symbol_index import SymbolIndex


class NodeType(str, Enum):
    """The kind of entity a `RepositoryContext` graph node represents."""

    REPOSITORY = "repository"
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class EdgeRelation(str, Enum):
    """The kind of relationship a `RepositoryContext` graph edge represents.

    Only the structural relations (`CONTAINS`, `DEFINES`, `IMPORTS`) are
    populated by the Repository Context Extractor. The remaining members
    are reserved so later stages (call-graph analysis, inheritance
    resolution, package-level dependency analysis) can extend the same
    graph in place, instead of every stage building and merging its own
    separate graph.
    """

    CONTAINS = "contains"
    DEFINES = "defines"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"


def build_repository_node_id(root_path: str) -> str:
    """Return the deterministic node id for a repository's root node."""
    return f"repository::{root_path}"


def build_file_node_id(file_path: str) -> str:
    """Return the deterministic node id for a file, given its repository-relative path."""
    return f"file::{file_path}"


def build_symbol_node_id(file_path: str, symbol_name: str, parent: str | None, start_line: int) -> str:
    """Return a deterministic, collision-resistant node id for a symbol.

    Qualifying the id with the file path, the immediate enclosing
    symbol's name (for methods nested in a class), and the symbol's
    start line keeps ids unique even across overloaded functions or
    identically named symbols defined in different scopes of the same
    file. This function is the single source of truth for symbol
    identity across the graph, the symbol index, and the embedding
    store, so all three always agree on the same key for the same
    symbol.
    """
    qualified_name = f"{parent}.{symbol_name}" if parent else symbol_name
    return f"file::{file_path}::{qualified_name}::{start_line}"


class RepositoryContext(BaseModel):
    """The complete semantic representation of a repository.

    Aggregates the structural graph, a fast symbol lookup index, and
    per-symbol embedding vectors produced by `RepositoryContextExtractor`.
    This is the single object downstream stages (task classification,
    adaptive routing, retrieval, GraphRAG) consume; none of them need to
    re-derive it from a `ParsedRepository`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    root_path: str = Field(..., description="Absolute filesystem path to the repository root.")
    commit_sha: str | None = Field(
        default=None, description="The HEAD commit SHA the context was built from, if known."
    )
    graph: nx.DiGraph = Field(
        ..., description="Directed graph of Repository/File/Class/Function/Method nodes and their relations."
    )
    symbol_index: SymbolIndex = Field(..., description="O(1) lookup index over the graph's symbol nodes.")
    embeddings: dict[str, list[float]] = Field(
        default_factory=dict, description="Symbol node id -> dense embedding vector, for every embedded symbol."
    )
    embedding_dimension: int | None = Field(
        default=None,
        description="Dimensionality of the vectors in `embeddings`, or None if no embeddings were generated.",
    )
    embedding_model_name: str | None = Field(
        default=None, description="Identifier of the embedding model used to populate `embeddings`."
    )
    file_count: int = Field(default=0, ge=0, description="Number of files represented in the graph.")
    symbol_count: int = Field(
        default=0, ge=0, description="Number of class/function/method symbols represented in the graph."
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Timestamp this context was built."
    )

    def graph_summary(self) -> dict[str, Any]:
        """Return a small, JSON-serializable summary of the graph's shape.

        `graph` itself (a `networkx.DiGraph`) and `symbol_index` are not
        JSON-serializable through the default Pydantic encoder. Callers
        that need the full graph on the wire should use
        `networkx.node_link_data(context.graph)` directly; this summary
        is what's cheap and safe to log or return from a status
        endpoint.
        """
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "file_count": self.file_count,
            "symbol_count": self.symbol_count,
            "embedded_symbol_count": len(self.embeddings),
            "embedding_dimension": self.embedding_dimension,
        }
