"""Parses a single Python source file into its raw extracted structure.

Kept separate from ``ast_visitor.py`` (which only knows how to walk an
already-parsed ``ast.Module``) so file I/O, decoding, and
``ast.parse``'s own failure modes are handled in exactly one place.
"""
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.rts_builder.parser.ast_visitor import PythonAstVisitor, RawCallSite, RawClass, RawFunction, RawImport
from evaluation.rts_builder.parser.exceptions import PythonFileParseError


@dataclass(frozen=True)
class ParsedPythonFile:
    """The raw structural parse of a single Python file, before repository-wide graph resolution."""

    path: str
    """Repository-relative, POSIX-style path."""
    absolute_path: str
    size_bytes: int
    content_hash: str
    module_docstring: str | None
    imports: list[RawImport] = field(default_factory=list)
    functions: list[RawFunction] = field(default_factory=list)
    classes: list[RawClass] = field(default_factory=list)
    call_sites: list[RawCallSite] = field(default_factory=list)


class PythonFileParser:
    """Parses one Python file into a ``ParsedPythonFile``."""

    def parse(self, repository_root: Path, file_path: Path) -> ParsedPythonFile:
        """Parse a single file.

        Args:
            repository_root: The repository root `file_path` is under;
                used to compute `file_path`'s repository-relative path.
            file_path: Absolute path to the ``.py``/``.pyi`` file to parse.

        Returns:
            The file's raw structural parse.

        Raises:
            PythonFileParseError: If the file cannot be decoded as UTF-8
                or contains a Python syntax error. Callers (see
                ``PythonRepositoryParser``) are expected to catch this
                per file, not let it abort the whole repository walk.
        """
        raw_bytes = file_path.read_bytes()
        try:
            source = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PythonFileParseError(f"{file_path} is not valid UTF-8: {exc}") from exc

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            raise PythonFileParseError(f"{file_path} has a syntax error: {exc}") from exc

        visitor = PythonAstVisitor()
        visitor.visit(tree)

        return ParsedPythonFile(
            path=file_path.relative_to(repository_root).as_posix(),
            absolute_path=str(file_path),
            size_bytes=len(raw_bytes),
            content_hash=hashlib.sha256(raw_bytes).hexdigest(),
            module_docstring=ast.get_docstring(tree, clean=True),
            imports=visitor.imports,
            functions=visitor.functions,
            classes=visitor.classes,
            call_sites=visitor.call_sites,
        )
