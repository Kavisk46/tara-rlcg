"""Builds the TARA repository context graph from a `ParsedRepository`.

`GraphBuilder` is a pure, stateless transformation: `ParsedRepository`
in, `networkx.DiGraph` out. It encodes only structure directly
observable from the parse -- containment, definition, and a best-effort
resolution of same-repository imports. Richer relations (`CALLS`,
`INHERITS`, `IMPLEMENTS`, `DEPENDS_ON`) are reserved on `EdgeRelation`
for later stages to populate on this same graph, so GraphRAG traversal
never has to merge multiple graphs together.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import networkx as nx

from tara.context.models import (
    EdgeRelation,
    NodeType,
    build_file_node_id,
    build_repository_node_id,
    build_symbol_node_id,
)
from tara.core.exceptions import GraphBuildError
from tara.core.logging import get_logger
from tara.core.types import Language
from tara.parsing.models import CodeSymbol, ParsedFile, ParsedRepository, SymbolKind

logger = get_logger(__name__)


def _python_import_target(text: str) -> str | None:
    """Extract the module path from a Python `import`/`from ... import` statement."""
    match = re.search(r"from\s+([.\w]+)\s+import|import\s+([.\w]+)", text)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _quoted_path_target(text: str) -> str | None:
    """Extract the first quoted path from an import statement (JS/TS `from '...'`, Go `"..."`)."""
    match = re.search(r"""['"]([^'"]+)['"]""", text)
    return match.group(1) if match else None


def _java_import_target(text: str) -> str | None:
    """Extract the dotted type path from a Java `import ...;` statement."""
    match = re.search(r"import\s+(?:static\s+)?([\w.]+)\s*;", text)
    return match.group(1) if match else None


def _rust_import_target(text: str) -> str | None:
    """Extract the module path from a Rust `use ...` statement."""
    match = re.search(r"use\s+([\w:]+)", text)
    return match.group(1) if match else None


def _c_family_import_target(text: str) -> str | None:
    """Extract the header path from a C/C++ `#include` directive."""
    match = re.search(r'#include\s*[<"]([^>"]+)[>"]', text)
    return match.group(1) if match else None


_IMPORT_TARGET_EXTRACTORS: dict[Language, Callable[[str], str | None]] = {
    Language.PYTHON: _python_import_target,
    Language.JAVASCRIPT: _quoted_path_target,
    Language.TYPESCRIPT: _quoted_path_target,
    Language.GO: _quoted_path_target,
    Language.JAVA: _java_import_target,
    Language.RUST: _rust_import_target,
    Language.C: _c_family_import_target,
    Language.CPP: _c_family_import_target,
}


def _module_stem(raw_target: str) -> str | None:
    """Reduce a raw import target (a path, dotted name, or `::` path) to its final segment."""
    cleaned = raw_target.strip(".")
    if not cleaned:
        return None
    segment = re.split(r"[./\\:]+", cleaned)[-1]
    return segment or None


class GraphBuilder:
    """Builds a `networkx.DiGraph` of Repository/File/Class/Function/Method nodes."""

    def build(self, parsed_repository: ParsedRepository) -> nx.DiGraph:
        """Construct the full repository graph.

        Args:
            parsed_repository: The structural parse produced by a
                `RepositoryParser` implementation.

        Returns:
            A `networkx.DiGraph` with one node per repository/file/class/
            function/method, and `contains`, `defines`, and `imports`
            edges recording their relationships.

        Raises:
            GraphBuildError: If the graph cannot be constructed.
        """
        start = time.perf_counter()
        try:
            graph = nx.DiGraph()
            repository_id = self._add_repository_node(graph, parsed_repository)

            path_to_file_id: dict[str, str] = {}
            for parsed_file in parsed_repository.files:
                file_id = self._add_file_node(graph, parsed_file)
                path_to_file_id[parsed_file.path] = file_id
                graph.add_edge(repository_id, file_id, relation=EdgeRelation.CONTAINS.value)
                self._add_symbol_nodes(graph, parsed_file, file_id)

            stems = self._build_stem_index(path_to_file_id)
            for parsed_file in parsed_repository.files:
                self._add_import_edges(graph, parsed_file, path_to_file_id, stems)
        except Exception as exc:  # noqa: BLE001 - normalize to a typed context-extraction error
            raise GraphBuildError(f"Failed to build repository graph: {exc}") from exc

        elapsed = time.perf_counter() - start
        logger.info(
            "Built repository graph: %d nodes, %d edges (%.3fs)",
            graph.number_of_nodes(), graph.number_of_edges(), elapsed,
        )
        return graph

    def _add_repository_node(self, graph: nx.DiGraph, parsed_repository: ParsedRepository) -> str:
        """Add the single root `Repository` node and return its id."""
        repository_id = build_repository_node_id(parsed_repository.root_path)
        graph.add_node(
            repository_id,
            id=repository_id,
            type=NodeType.REPOSITORY.value,
            name=parsed_repository.root_path,
            file_path=None,
            language=None,
            docstring=None,
            start_line=None,
            end_line=None,
            commit_sha=parsed_repository.commit_sha,
        )
        return repository_id

    def _add_file_node(self, graph: nx.DiGraph, parsed_file: ParsedFile) -> str:
        """Add a `File` node for `parsed_file` and return its id."""
        file_id = build_file_node_id(parsed_file.path)
        graph.add_node(
            file_id,
            id=file_id,
            type=NodeType.FILE.value,
            name=parsed_file.path,
            file_path=parsed_file.path,
            language=parsed_file.language.value,
            docstring=None,
            start_line=None,
            end_line=None,
            size_bytes=parsed_file.size_bytes,
            content_hash=parsed_file.content_hash,
        )
        return file_id

    def _add_symbol_nodes(self, graph: nx.DiGraph, parsed_file: ParsedFile, file_id: str) -> None:
        """Add Class/Function/Method nodes for every symbol in `parsed_file`.

        `parsed_file.symbols` is a pre-order flattening of the syntax
        tree (see `TreeSitterRepositoryParser`), so a symbol's parent
        always appears earlier in the list than the symbol itself. That
        lets this method resolve both the parent's graph node id and its
        `SymbolKind` in a single forward pass.
        """
        name_to_id: dict[str, str] = {}
        name_to_kind: dict[str, SymbolKind] = {}

        for symbol in parsed_file.symbols:
            enclosing_kind = name_to_kind.get(symbol.parent) if symbol.parent else None
            node_type = self._resolve_node_type(symbol, enclosing_kind)
            if node_type is None:
                logger.debug("Skipping unsupported symbol kind %s in %s", symbol.kind, parsed_file.path)
                continue

            symbol_id = build_symbol_node_id(parsed_file.path, symbol.name, symbol.parent, symbol.start_line)
            graph.add_node(
                symbol_id,
                id=symbol_id,
                type=node_type.value,
                name=symbol.name,
                file_path=parsed_file.path,
                language=parsed_file.language.value,
                docstring=symbol.docstring,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                start_byte=symbol.start_byte,
                end_byte=symbol.end_byte,
                parent=symbol.parent,
            )
            name_to_id[symbol.name] = symbol_id
            name_to_kind[symbol.name] = symbol.kind

            if symbol.parent is None:
                graph.add_edge(file_id, symbol_id, relation=EdgeRelation.DEFINES.value)
            else:
                source_id = name_to_id.get(symbol.parent, file_id)
                graph.add_edge(source_id, symbol_id, relation=EdgeRelation.CONTAINS.value)

    @staticmethod
    def _resolve_node_type(symbol: CodeSymbol, enclosing_kind: SymbolKind | None) -> NodeType | None:
        """Map a `CodeSymbol` to a graph `NodeType`, or None if it isn't graphed.

        Python's grammar has no distinct "method" node type, so
        `TreeSitterRepositoryParser` reports methods as
        `SymbolKind.FUNCTION` with `parent` set to the enclosing class's
        name. `enclosing_kind` disambiguates that case from an ordinary
        nested/closure function (whose enclosing symbol is itself a
        function, not a class).
        """
        if symbol.kind is SymbolKind.CLASS:
            return NodeType.CLASS
        if symbol.kind is SymbolKind.METHOD:
            return NodeType.METHOD
        if symbol.kind is SymbolKind.FUNCTION:
            return NodeType.METHOD if enclosing_kind is SymbolKind.CLASS else NodeType.FUNCTION
        return None

    @staticmethod
    def _build_stem_index(path_to_file_id: dict[str, str]) -> dict[str, tuple[str, str]]:
        """Map each file's stem (basename without extension) to its (path, node id).

        When two files in different directories share a stem, the last
        one wins; import resolution here is intentionally best-effort
        rather than a full module resolver, so this ambiguity is an
        accepted limitation (see `_resolve_import_targets`).
        """
        return {Path(path).stem: (path, file_id) for path, file_id in path_to_file_id.items()}

    def _add_import_edges(
        self,
        graph: nx.DiGraph,
        parsed_file: ParsedFile,
        path_to_file_id: dict[str, str],
        stems: dict[str, tuple[str, str]],
    ) -> None:
        """Add `imports` edges from `parsed_file` to every import target resolved within the repository."""
        if not parsed_file.imports:
            return
        source_id = path_to_file_id[parsed_file.path]
        for target_path, target_id in self._resolve_import_targets(parsed_file, stems):
            if target_path == parsed_file.path:
                continue
            graph.add_edge(source_id, target_id, relation=EdgeRelation.IMPORTS.value, statement=target_path)

    def _resolve_import_targets(
        self, parsed_file: ParsedFile, stems: dict[str, tuple[str, str]]
    ) -> Iterator[tuple[str, str]]:
        """Best-effort resolution of import statements to other files parsed in this repository.

        Only imports whose target's final path segment matches the stem
        of a file that was actually parsed produce an edge; unresolved,
        external, or third-party imports are silently skipped rather
        than guessed at. This is a heuristic, not a real module
        resolver -- see `_build_stem_index` for its known limitation.
        """
        extractor = _IMPORT_TARGET_EXTRACTORS.get(parsed_file.language)
        if extractor is None:
            return
        for import_statement in parsed_file.imports:
            raw_target = extractor(import_statement.module)
            if raw_target is None:
                continue
            stem = _module_stem(raw_target)
            if stem is None:
                continue
            match = stems.get(stem)
            if match is not None:
                yield match
