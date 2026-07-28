"""Fast, read-only lookup index over a repository context graph's nodes.

`SymbolIndex` wraps three dictionaries (by node id, by symbol name, by
file path) behind a small query API so callers never touch raw graph
internals directly. All lookups are O(1) average case; the index is
built once, in a single pass over the graph's nodes.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass(frozen=True)
class SymbolRecord:
    """A single indexed node: its id plus its graph attributes.

    `attributes` is a live reference to the underlying graph node's
    attribute dict rather than a copy, so indexing a graph with 100,000+
    nodes does not pay for 100,000+ dict copies. Callers that need an
    isolated snapshot can take `dict(record.attributes)` themselves.
    """

    node_id: str
    node_type: str
    name: str
    file_path: str | None
    attributes: dict[str, Any]


class SymbolIndex:
    """O(1) average-case lookup by node id, by symbol name, and by file path.

    Built once from a `networkx.DiGraph` produced by `GraphBuilder` via
    `SymbolIndex.from_graph`. Backed by plain dicts internally, but those
    dicts are never exposed directly -- every access goes through
    `get_by_id` / `get_by_name` / `get_by_file`, so the storage strategy
    can change later (e.g. to back onto a persistent store for very
    large monorepos) without touching call sites.
    """

    def __init__(self) -> None:
        """Construct an empty index; populate it via `add` or `from_graph`."""
        self._by_id: dict[str, SymbolRecord] = {}
        self._by_name: dict[str, list[SymbolRecord]] = defaultdict(list)
        self._by_file: dict[str, list[SymbolRecord]] = defaultdict(list)

    @classmethod
    def from_graph(cls, graph: nx.DiGraph) -> "SymbolIndex":
        """Build an index by scanning every node in `graph` exactly once.

        Args:
            graph: A repository context graph, typically produced by
                `GraphBuilder.build`.

        Returns:
            A fully populated `SymbolIndex`.
        """
        index = cls()
        for node_id, attributes in graph.nodes(data=True):
            index.add(
                SymbolRecord(
                    node_id=node_id,
                    node_type=attributes.get("type", "unknown"),
                    name=attributes.get("name", node_id),
                    file_path=attributes.get("file_path"),
                    attributes=attributes,
                )
            )
        return index

    def add(self, record: SymbolRecord) -> None:
        """Insert a single record into the index.

        Args:
            record: The record to index. Re-adding a record with an
                already-indexed `node_id` overwrites the id-keyed entry
                but appends an additional name/file entry; callers
                should only add each node once.
        """
        self._by_id[record.node_id] = record
        self._by_name[record.name].append(record)
        if record.file_path is not None:
            self._by_file[record.file_path].append(record)

    def get_by_id(self, node_id: str) -> SymbolRecord | None:
        """Return the record for `node_id`, or None if it isn't indexed."""
        return self._by_id.get(node_id)

    def get_by_name(self, name: str) -> list[SymbolRecord]:
        """Return every record whose symbol name equals `name`.

        Multiple records can share a name (e.g. the same function name
        defined in different files, or overloaded methods), so this
        always returns a list, even when exactly one record matches.
        """
        return list(self._by_name.get(name, ()))

    def get_by_file(self, file_path: str) -> list[SymbolRecord]:
        """Return every record defined in `file_path`, including the file node itself."""
        return list(self._by_file.get(file_path, ()))

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._by_id

    def __iter__(self) -> Iterator[SymbolRecord]:
        return iter(self._by_id.values())


class SymbolIndexBuilder:
    """Builds a `SymbolIndex` from a repository context graph.

    Kept as its own injectable component -- rather than folding
    `SymbolIndex.from_graph` directly into `RepositoryContextExtractor`
    -- so the indexing strategy can be swapped later (e.g. for an index
    backed by a persistent store) without changing the extractor or any
    of its other collaborators.
    """

    def build(self, graph: nx.DiGraph) -> SymbolIndex:
        """Return a `SymbolIndex` covering every node in `graph`."""
        return SymbolIndex.from_graph(graph)
