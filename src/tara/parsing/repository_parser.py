"""Tree-sitter + GitPython based implementation of `RepositoryParser`.

`TreeSitterRepositoryParser` walks a repository on disk, skips ignored
directories and unsupported/oversized files, parses each remaining
source file with Tree-sitter, and extracts a language-specific set of
symbols (classes/functions/methods) and import statements by walking
the resulting concrete syntax tree.
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from pathlib import Path

from git import InvalidGitRepositoryError, Repo
from tree_sitter import Node

from tara.core.config import TaraSettings
from tara.core.exceptions import RepositoryParsingError
from tara.core.types import Language
from tara.interfaces.repository_parser import RepositoryParser
from tara.parsing.language_registry import LanguageRegistry
from tara.parsing.models import (
    CodeSymbol,
    ImportStatement,
    ParsedFile,
    ParsedRepository,
    ParseError,
    SymbolKind,
)

logger = logging.getLogger(__name__)

# Tree-sitter node type -> SymbolKind, keyed by language. Grammar
# vocabularies differ across languages, so this mapping is intentionally
# per-language rather than a single global table.
_SYMBOL_NODE_TYPES: dict[Language, dict[str, SymbolKind]] = {
    Language.PYTHON: {
        "class_definition": SymbolKind.CLASS,
        "function_definition": SymbolKind.FUNCTION,
    },
    Language.JAVASCRIPT: {
        "class_declaration": SymbolKind.CLASS,
        "function_declaration": SymbolKind.FUNCTION,
        "method_definition": SymbolKind.METHOD,
    },
    Language.TYPESCRIPT: {
        "class_declaration": SymbolKind.CLASS,
        "function_declaration": SymbolKind.FUNCTION,
        "method_definition": SymbolKind.METHOD,
        "interface_declaration": SymbolKind.CLASS,
    },
    Language.JAVA: {
        "class_declaration": SymbolKind.CLASS,
        "method_declaration": SymbolKind.METHOD,
        "interface_declaration": SymbolKind.CLASS,
    },
    Language.GO: {
        "function_declaration": SymbolKind.FUNCTION,
        "method_declaration": SymbolKind.METHOD,
        "type_declaration": SymbolKind.CLASS,
    },
    Language.RUST: {
        "function_item": SymbolKind.FUNCTION,
        "struct_item": SymbolKind.CLASS,
        "impl_item": SymbolKind.CLASS,
    },
    Language.C: {
        "function_definition": SymbolKind.FUNCTION,
        "struct_specifier": SymbolKind.CLASS,
    },
    Language.CPP: {
        "function_definition": SymbolKind.FUNCTION,
        "class_specifier": SymbolKind.CLASS,
        "struct_specifier": SymbolKind.CLASS,
    },
}

_IMPORT_NODE_TYPES: dict[Language, frozenset[str]] = {
    Language.PYTHON: frozenset({"import_statement", "import_from_statement"}),
    Language.JAVASCRIPT: frozenset({"import_statement"}),
    Language.TYPESCRIPT: frozenset({"import_statement"}),
    Language.JAVA: frozenset({"import_declaration"}),
    Language.GO: frozenset({"import_spec"}),
    Language.RUST: frozenset({"use_declaration"}),
    Language.C: frozenset({"preproc_include"}),
    Language.CPP: frozenset({"preproc_include"}),
}

_DEFAULT_IGNORED_DIRECTORIES = frozenset(
    {
        ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", "node_modules", "dist", "build", ".venv", "venv",
        ".tox", ".idea", ".vscode", "site-packages", "egg-info", ".tara",
    }
)


class TreeSitterRepositoryParser(RepositoryParser):
    """Parses a repository into a `ParsedRepository` using Tree-sitter.

    This is the reference implementation of the `RepositoryParser`
    interface. It performs a filesystem walk (not a Git-index walk) so
    it also sees uncommitted changes, but it consults `.git` to record
    the current commit SHA for provenance.
    """

    def __init__(
        self,
        settings: TaraSettings | None = None,
        language_registry: LanguageRegistry | None = None,
    ) -> None:
        """Construct a parser.

        Args:
            settings: Configuration controlling ignored directories and
                file-size limits. Defaults to `TaraSettings()`
                (environment defaults) when omitted.
            language_registry: Registry used to detect languages and
                obtain Tree-sitter parsers. Defaults to a fresh
                `LanguageRegistry` when omitted; sharing one instance
                across multiple parsers is safe and avoids rebuilding
                parser caches.
        """
        self._settings = settings or TaraSettings()
        self._languages = language_registry or LanguageRegistry()

    def parse(self, repository_path: Path) -> ParsedRepository:
        """See `RepositoryParser.parse`."""
        repository_path = repository_path.resolve()
        if not repository_path.is_dir():
            raise RepositoryParsingError(
                f"Repository path does not exist or is not a directory: {repository_path}"
            )

        commit_sha = self._resolve_commit_sha(repository_path)
        files: list[ParsedFile] = []
        errors: list[ParseError] = []

        for file_path in self._iter_source_files(repository_path):
            relative = file_path.relative_to(repository_path).as_posix()
            try:
                parsed = self._parse_file(repository_path, file_path)
                if parsed is not None:
                    files.append(parsed)
            except Exception as exc:  # noqa: BLE001 - a single bad file must not abort the walk
                logger.warning("Failed to parse %s: %s", relative, exc)
                errors.append(ParseError(file_path=relative, message=str(exc)))

        logger.info(
            "Parsed repository %s: %d files parsed, %d errors",
            repository_path, len(files), len(errors),
        )
        return ParsedRepository(
            root_path=str(repository_path),
            commit_sha=commit_sha,
            files=files,
            errors=errors,
        )

    def _resolve_commit_sha(self, repository_path: Path) -> str | None:
        """Return the current HEAD commit SHA, or None if not a Git repo / no commits yet."""
        try:
            repo = Repo(repository_path, search_parent_directories=True)
            return repo.head.commit.hexsha
        except (InvalidGitRepositoryError, ValueError):
            return None

    def _iter_source_files(self, repository_path: Path) -> Iterator[Path]:
        """Yield candidate source files under `repository_path`, applying ignore/size filters."""
        ignored_dirs = _DEFAULT_IGNORED_DIRECTORIES | set(self._settings.ignored_directories)
        max_size = self._settings.max_file_size_bytes

        stack = [repository_path]
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError as exc:
                logger.warning("Cannot list directory %s: %s", current, exc)
                continue

            for entry in entries:
                if entry.is_dir():
                    if entry.name not in ignored_dirs:
                        stack.append(entry)
                    continue

                if self._languages.detect_language(entry.suffix) is Language.UNKNOWN:
                    continue

                try:
                    if entry.stat().st_size > max_size:
                        logger.debug("Skipping oversized file %s", entry)
                        continue
                except OSError:
                    continue

                yield entry

    def _parse_file(self, repository_path: Path, file_path: Path) -> ParsedFile | None:
        """Parse a single source file into a `ParsedFile`, or None if unsupported."""
        language = self._languages.detect_language(file_path.suffix)
        if not self._languages.is_supported(language):
            return None

        raw_bytes = file_path.read_bytes()
        parser = self._languages.get_parser(language)
        tree = parser.parse(raw_bytes)

        symbols = self._extract_symbols(tree.root_node, language, raw_bytes, parent=None)
        imports = self._extract_imports(tree.root_node, language, raw_bytes)

        return ParsedFile(
            path=file_path.relative_to(repository_path).as_posix(),
            absolute_path=str(file_path),
            language=language,
            size_bytes=len(raw_bytes),
            content_hash=hashlib.sha256(raw_bytes).hexdigest(),
            symbols=symbols,
            imports=imports,
            syntax_tree=tree,
        )

    def _extract_symbols(
        self,
        node: Node,
        language: Language,
        source: bytes,
        parent: str | None,
    ) -> list[CodeSymbol]:
        """Recursively walk a syntax tree collecting class/function/method symbols."""
        node_type_map = _SYMBOL_NODE_TYPES.get(language, {})
        symbols: list[CodeSymbol] = []

        for child in node.children:
            kind = node_type_map.get(child.type)
            if kind is not None:
                name = self._extract_name(child, source)
                if name is not None:
                    symbols.append(
                        CodeSymbol(
                            name=name,
                            kind=kind,
                            start_line=child.start_point[0],
                            end_line=child.end_point[0],
                            start_byte=child.start_byte,
                            end_byte=child.end_byte,
                            docstring=self._extract_docstring(child, language, source),
                            parent=parent,
                        )
                    )
                    symbols.extend(self._extract_symbols(child, language, source, parent=name))
                    continue

            symbols.extend(self._extract_symbols(child, language, source, parent=parent))

        return symbols

    @staticmethod
    def _extract_name(node: Node, source: bytes) -> str | None:
        """Find the identifier that names a definition node.

        Prefers the grammar's own "name" field when present (accurate
        across all supported languages); falls back to the first
        identifier-like child for grammars without a named field.
        """
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return source[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "field_identifier"):
                return source[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
        return None

    @staticmethod
    def _extract_docstring(node: Node, language: Language, source: bytes) -> str | None:
        """Extract a Python-style leading string-literal docstring, if present."""
        if language is not Language.PYTHON:
            return None
        body = node.child_by_field_name("body")
        if body is None or body.child_count == 0:
            return None
        first_statement = body.children[0]
        if first_statement.type == "expression_statement" and first_statement.child_count > 0:
            expr = first_statement.children[0]
            if expr.type == "string":
                text = source[expr.start_byte : expr.end_byte].decode("utf-8", errors="replace")
                return text.strip("\"'").strip()
        return None

    def _extract_imports(self, root: Node, language: Language, source: bytes) -> list[ImportStatement]:
        """Collect import/include/use statements from anywhere in a syntax tree."""
        target_types = _IMPORT_NODE_TYPES.get(language)
        if not target_types:
            return []

        imports: list[ImportStatement] = []
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type in target_types:
                text = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
                imports.append(
                    ImportStatement(
                        module=text,
                        imported_names=[],
                        is_relative=text.startswith((".", "from .")),
                        line=node.start_point[0],
                    )
                )
                continue
            stack.extend(node.children)

        return imports
