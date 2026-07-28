"""Data models produced by the TARA repository parsing stage.

These models are the contract between `RepositoryParser` implementations
and every downstream pipeline stage (context extraction, task
classification, retrieval). They are intentionally decoupled from
Tree-sitter's own node types, so downstream code never needs to import
`tree_sitter` directly and can treat a `ParsedRepository` as a plain,
(mostly) serializable data structure.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tara.core.types import Language


class SymbolKind(str, Enum):
    """The kind of structural element a `CodeSymbol` represents."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"


class CodeSymbol(BaseModel):
    """A single named, addressable element extracted from a source file."""

    name: str = Field(..., description="The symbol's identifier, e.g. a function or class name.")
    kind: SymbolKind = Field(..., description="The structural category of the symbol.")
    start_line: int = Field(..., ge=0, description="0-indexed line where the symbol begins.")
    end_line: int = Field(..., ge=0, description="0-indexed line where the symbol ends (inclusive).")
    start_byte: int = Field(..., ge=0, description="Byte offset where the symbol begins in the source file.")
    end_byte: int = Field(..., ge=0, description="Byte offset where the symbol ends in the source file.")
    docstring: str | None = Field(
        default=None, description="Extracted docstring/leading comment for the symbol, if any."
    )
    parent: str | None = Field(
        default=None,
        description="Name of the immediately enclosing symbol (e.g. the class containing a method), or None for top-level symbols.",
    )


class ImportStatement(BaseModel):
    """A single import/include/use statement extracted from a source file."""

    module: str = Field(..., description="The import statement's source text, as written in the file.")
    imported_names: list[str] = Field(
        default_factory=list,
        description="Specific names imported from `module`, if statically resolvable (e.g. `from x import a, b`).",
    )
    is_relative: bool = Field(default=False, description="Whether the import is a relative/local import.")
    line: int = Field(..., ge=0, description="0-indexed line of the import statement.")


class ParseError(BaseModel):
    """Records a recoverable failure while parsing a single file."""

    file_path: str = Field(..., description="Repository-relative path of the file that failed to parse.")
    message: str = Field(..., description="Human-readable description of the failure.")


class ParsedFile(BaseModel):
    """The structural representation of a single source file."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: str = Field(..., description="Repository-relative, POSIX-style path of the file.")
    absolute_path: str = Field(..., description="Absolute filesystem path of the file at parse time.")
    language: Language = Field(..., description="Detected programming language of the file.")
    size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    content_hash: str = Field(
        ..., description="SHA-256 hash of the file's raw bytes, used for downstream change detection."
    )
    symbols: list[CodeSymbol] = Field(
        default_factory=list, description="Top-level and nested symbols extracted from the file."
    )
    imports: list[ImportStatement] = Field(
        default_factory=list, description="Import statements extracted from the file."
    )
    syntax_tree: Any = Field(
        default=None,
        exclude=True,
        repr=False,
        description="The raw `tree_sitter.Tree` for this file, retained in-memory for downstream stages that need full-fidelity ASTs; never serialized.",
    )


class ParsedRepository(BaseModel):
    """The complete structural parse of a repository at a given commit."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    root_path: str = Field(..., description="Absolute filesystem path to the repository root.")
    commit_sha: str | None = Field(
        default=None, description="The HEAD commit SHA at parse time, or None if not a Git repository."
    )
    files: list[ParsedFile] = Field(default_factory=list, description="Successfully parsed files.")
    errors: list[ParseError] = Field(default_factory=list, description="Files that failed to parse, with reasons.")

    @property
    def file_count(self) -> int:
        """Number of successfully parsed files."""
        return len(self.files)

    def get_file(self, relative_path: str) -> ParsedFile | None:
        """Look up a parsed file by its repository-relative path.

        Args:
            relative_path: Path relative to the repository root, using
                either forward or backward slashes.

        Returns:
            The matching `ParsedFile`, or None if no file at that path
            was successfully parsed.
        """
        normalized = relative_path.replace("\\", "/")
        for parsed_file in self.files:
            if parsed_file.path == normalized:
                return parsed_file
        return None
