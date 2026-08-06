"""Resolves the import graph, call graph, and class inheritance graph from parsed files.

All three resolutions are name-based and best-effort, following the
same "resolve unambiguously or skip, never guess" precedent used
throughout this project (e.g. ``tara.context.GraphBuilder``'s own
stem-based import resolution): a wrong edge would corrupt anything
built on top of this graph later (e.g. a future structural feature), and
that risk is judged worse than a missing edge. See ``README.md`` and
``REVIEW_RESPONSE.md`` for the precision/recall tradeoff this implies.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from evaluation.rts_builder.parser.ast_visitor import RawImport
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.file_parser import ParsedPythonFile
from evaluation.rts_builder.parser.models import CallEdge, ImportEdge, InheritanceEdge
from evaluation.rts_builder.parser.symbol_ids import build_symbol_id
from tara.core.logging import get_logger

logger = get_logger(__name__)

_OBJECT_BASE_CLASS = "object"


@dataclass(frozen=True)
class RepositoryGraphs:
    """The three resolved graphs this milestone builds."""

    import_graph: list[ImportEdge] = field(default_factory=list)
    call_graph: list[CallEdge] = field(default_factory=list)
    inheritance_graph: list[InheritanceEdge] = field(default_factory=list)


def _module_path_for_file(relative_path: str) -> str:
    """Return the dotted module path a file corresponds to (e.g. 'pkg/sub/mod.py' -> 'pkg.sub.mod').

    A package's ``__init__.py`` corresponds to the *package's own* dotted
    path (its containing directory), not a path ending in '.__init__'.
    """
    if relative_path in ("__init__.py", "__init__.pyi"):
        return ""
    for init_suffix in ("/__init__.py", "/__init__.pyi"):
        if relative_path.endswith(init_suffix):
            return relative_path[: -len(init_suffix)].replace("/", ".")
    for suffix in (".py", ".pyi"):
        if relative_path.endswith(suffix):
            return relative_path[: -len(suffix)].replace("/", ".")
    return relative_path.replace("/", ".")


def _package_path_for_file(relative_path: str) -> str:
    """Return the dotted path of the package a file lives in (its containing directory)."""
    if "/" not in relative_path:
        return ""
    return relative_path.rsplit("/", 1)[0].replace("/", ".")


def _build_module_index(files: list[ParsedPythonFile]) -> dict[str, str]:
    """Return {dotted module path -> repository-relative file path} for every parsed file."""
    index: dict[str, str] = {}
    for parsed_file in files:
        index[_module_path_for_file(parsed_file.path)] = parsed_file.path
    return index


def _resolve_import_targets(
    raw_import: RawImport,
    importing_file_path: str,
    module_index: dict[str, str],
) -> list[str]:
    """Return every repository file `raw_import` resolves to (usually zero or one; see README.md).

    Tries two candidate module paths per import: the imported module
    itself (``import a.b`` / ``from a.b import c`` -> try 'a.b'), and
    each imported name appended to it (``from a.b import c`` -> also try
    'a.b.c', covering the common `from package import submodule` case
    where `c` is itself a file, not a name defined inside `a/b.py`).
    """
    targets: set[str] = set()

    if raw_import.level == 0:
        base_parts = raw_import.module.split(".") if raw_import.module else []
    else:
        package_parts = [part for part in _package_path_for_file(importing_file_path).split(".") if part]
        levels_up = raw_import.level - 1
        if levels_up > len(package_parts):
            return []
        base_parts = package_parts[: len(package_parts) - levels_up]
        if raw_import.module:
            base_parts = base_parts + raw_import.module.split(".")

    base_module = ".".join(base_parts)
    if base_module:
        direct = module_index.get(base_module)
        if direct is not None:
            targets.add(direct)

    for name in raw_import.imported_names:
        candidate = ".".join([*base_parts, name])
        match = module_index.get(candidate)
        if match is not None:
            targets.add(match)

    targets.discard(importing_file_path)
    return sorted(targets)


def _build_import_graph(files: list[ParsedPythonFile]) -> list[ImportEdge]:
    module_index = _build_module_index(files)
    edges: list[ImportEdge] = []
    for parsed_file in files:
        for raw_import in parsed_file.imports:
            for target_file in _resolve_import_targets(raw_import, parsed_file.path, module_index):
                edges.append(ImportEdge(source_file=parsed_file.path, target_file=target_file, line=raw_import.line))
    return edges


def _build_call_graph(files: list[ParsedPythonFile]) -> list[CallEdge]:
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for parsed_file in files:
        for function in parsed_file.functions:
            name_to_ids[function.name].append(
                build_symbol_id(parsed_file.path, function.qualified_name, function.start_line)
            )

    edges: list[CallEdge] = []
    for parsed_file in files:
        qualified_name_to_id = {
            function.qualified_name: build_symbol_id(parsed_file.path, function.qualified_name, function.start_line)
            for function in parsed_file.functions
        }
        for call_site in parsed_file.call_sites:
            if call_site.enclosing_qualified_name is None:
                continue
            caller_id = qualified_name_to_id.get(call_site.enclosing_qualified_name)
            if caller_id is None:
                continue
            candidates = name_to_ids.get(call_site.callee_name, [])
            if len(candidates) != 1:
                continue
            edges.append(CallEdge(caller_symbol_id=caller_id, callee_symbol_id=candidates[0], file_path=parsed_file.path, line=call_site.line))
    return edges


def _build_inheritance_graph(files: list[ParsedPythonFile]) -> list[InheritanceEdge]:
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for parsed_file in files:
        for klass in parsed_file.classes:
            name_to_ids[klass.name].append(build_symbol_id(parsed_file.path, klass.qualified_name, klass.start_line))

    edges: list[InheritanceEdge] = []
    for parsed_file in files:
        for klass in parsed_file.classes:
            subclass_id = build_symbol_id(parsed_file.path, klass.qualified_name, klass.start_line)
            for base_name in klass.base_names:
                if base_name == _OBJECT_BASE_CLASS:
                    continue
                candidates = name_to_ids.get(base_name, [])
                if len(candidates) != 1:
                    continue
                superclass_id = candidates[0]
                if superclass_id == subclass_id:
                    continue
                edges.append(
                    InheritanceEdge(
                        subclass_symbol_id=subclass_id, superclass_symbol_id=superclass_id,
                        file_path=parsed_file.path, line=klass.start_line,
                    )
                )
    return edges


class GraphBuilder:
    """Builds the import, call, and inheritance graphs from a repository's parsed files."""

    def __init__(self, settings: ParserSettings | None = None) -> None:
        """Construct the builder.

        Args:
            settings: Controls whether the call and inheritance graphs
                are built at all. Defaults to ``ParserSettings()``.
        """
        self._settings = settings or ParserSettings()

    def build(self, files: list[ParsedPythonFile]) -> RepositoryGraphs:
        """Build all three graphs over `files`.

        Args:
            files: Every successfully parsed file in the repository.

        Returns:
            The resolved import, call, and inheritance graphs (the
            latter two empty if disabled via settings).
        """
        import_graph = _build_import_graph(files)
        call_graph = _build_call_graph(files) if self._settings.enable_call_graph else []
        inheritance_graph = _build_inheritance_graph(files) if self._settings.enable_inheritance_graph else []

        logger.info(
            "Built graphs: %d import edges, %d call edges, %d inheritance edges",
            len(import_graph), len(call_graph), len(inheritance_graph),
        )
        return RepositoryGraphs(import_graph=import_graph, call_graph=call_graph, inheritance_graph=inheritance_graph)
