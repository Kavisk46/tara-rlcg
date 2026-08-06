"""The normalized Repository Model: this milestone's entire, JSON-exportable output contract.

Every other module in this package either produces an input to
``normalizer.normalize`` (``file_parser``, ``graph_builder``) or
consumes ``RepositoryModel`` once built (``export``, ``cache``). None of
these types carry any non-serializable object (no raw ``ast`` nodes, no
``networkx`` graph): the whole point of a normalized model is that it
survives a round trip through ``model_dump_json`` /
``model_validate_json`` unchanged, which is what makes both JSON export
(requirement 7) and the incremental-parsing cache (``cache.py``) simple.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class NormalizedImport(BaseModel):
    """A single import statement, exactly as written, resolved or not.

    Statement-level granularity, and includes external/unresolved
    imports -- unlike ``import_graph``, which only records the subset
    ``graph_builder`` could resolve to another file in this repository.
    """

    source_file: str = Field(..., description="Repository-relative path of the file containing the statement.")
    module: str = Field(..., description="The dotted module path as written (e.g. 'a.b' for both 'import a.b' and 'from a.b import c').")
    imported_names: list[str] = Field(default_factory=list, description="Names imported, for a 'from ... import' statement.")
    is_relative: bool = Field(..., description="Whether this is a relative import ('from . import x', 'from ..pkg import y').")
    level: int = Field(..., ge=0, description="0 for an absolute import; the number of leading dots for a relative import.")
    line: int = Field(..., ge=1, description="1-indexed line of the import statement.")


class NormalizedFunction(BaseModel):
    """A single function or method definition.

    ``is_method`` discriminates a method from a top-level (or nested,
    non-method) function; ``RepositoryModel.top_level_functions`` /
    ``.methods`` are filtered views over this one list rather than
    separate stored lists, so the two can never drift out of sync with
    each other -- the same design choice made for the previous
    milestone's ``functions``/``classes``/``methods`` split.
    """

    symbol_id: str = Field(..., description="Globally unique id: '<file_path>::<qualified_name>::<start_line>'.")
    name: str = Field(..., description="The function's own name, without any enclosing class qualification.")
    qualified_name: str = Field(..., description="'ClassName.method_name' for a method, else same as name.")
    file_path: str = Field(..., description="Repository-relative, POSIX-style path of the defining file.")
    is_method: bool = Field(..., description="True if the immediate enclosing scope is a class.")
    parent_class: str | None = Field(default=None, description="The enclosing class's qualified name, if is_method.")
    is_async: bool = Field(..., description="True for 'async def'.")
    decorators: list[str] = Field(default_factory=list, description="Decorator source expressions, without the leading '@', outermost first.")
    docstring: str | None = Field(default=None, description="The function's docstring, if any (via ast.get_docstring, cleaned).")
    start_line: int = Field(..., ge=1, description="1-indexed line the 'def'/'async def' begins on.")
    end_line: int = Field(..., ge=1, description="1-indexed line the function's body ends on (inclusive).")


class NormalizedClass(BaseModel):
    """A single class definition."""

    symbol_id: str = Field(..., description="Globally unique id: '<file_path>::<qualified_name>::<start_line>'.")
    name: str = Field(..., description="The class's own name, without any enclosing class qualification.")
    qualified_name: str = Field(..., description="'Outer.Inner' for a nested class, else same as name.")
    file_path: str = Field(..., description="Repository-relative, POSIX-style path of the defining file.")
    parent_class: str | None = Field(default=None, description="The enclosing class's qualified name, for a nested class.")
    base_names: list[str] = Field(default_factory=list, description="Base class names exactly as written, unresolved (see inheritance_graph for resolved edges).")
    decorators: list[str] = Field(default_factory=list, description="Decorator source expressions, without the leading '@', outermost first.")
    docstring: str | None = Field(default=None, description="The class's docstring, if any (via ast.get_docstring, cleaned).")
    start_line: int = Field(..., ge=1, description="1-indexed line the 'class' statement begins on.")
    end_line: int = Field(..., ge=1, description="1-indexed line the class's body ends on (inclusive).")


class NormalizedFile(BaseModel):
    """A single Python source file (a "module")."""

    path: str = Field(..., description="Repository-relative, POSIX-style path.")
    size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    content_hash: str = Field(..., description="SHA-256 hash of the file's raw bytes.")
    module_docstring: str | None = Field(default=None, description="The file's module-level docstring, if any.")
    function_count: int = Field(..., ge=0, description="Number of top-level and nested functions/methods defined in this file.")
    class_count: int = Field(..., ge=0, description="Number of classes defined in this file.")
    import_count: int = Field(..., ge=0, description="Number of import statements in this file.")


class ImportEdge(BaseModel):
    """A single resolved file-to-file import dependency: `source_file` imports from `target_file`.

    Only imports ``graph_builder`` could resolve to another file parsed
    in this same repository produce an edge here; external/third-party
    and unresolvable imports appear in ``RepositoryModel.imports`` but
    not here. See ``README.md`` for the resolution algorithm.
    """

    source_file: str = Field(..., description="Repository-relative path of the importing file.")
    target_file: str = Field(..., description="Repository-relative path of the imported-from file.")
    line: int = Field(..., ge=1, description="1-indexed line of the import statement that produced this edge.")


class CallEdge(BaseModel):
    """A single resolved function/method call: `caller_symbol_id` calls `callee_symbol_id`."""

    caller_symbol_id: str = Field(..., description="symbol_id of the enclosing function/method making the call.")
    callee_symbol_id: str = Field(..., description="symbol_id of the resolved, unambiguous, called function/method.")
    file_path: str = Field(..., description="Repository-relative path of the file containing the call site.")
    line: int = Field(..., ge=1, description="1-indexed line of the call site.")


class InheritanceEdge(BaseModel):
    """A single resolved class inheritance relationship: `subclass_symbol_id` extends `superclass_symbol_id`."""

    subclass_symbol_id: str = Field(..., description="symbol_id of the class declaring the base.")
    superclass_symbol_id: str = Field(..., description="symbol_id of the resolved, unambiguous base class.")
    file_path: str = Field(..., description="Repository-relative path of the file containing the class definition.")
    line: int = Field(..., ge=1, description="1-indexed line the subclass's 'class' statement begins on.")


class RepositoryModel(BaseModel):
    """The complete, normalized structural parse of a Python repository at a pinned commit.

    This is the Parser subsystem's entire output contract: persisted as
    ``<cache_root>/<repository_id>/repository_model.json`` (see
    ``cache.py``) and returned by
    ``PythonParserPipeline.parse_repository``.
    """

    repository_id: str = Field(..., min_length=1, description="The repository_id this parse belongs to.")
    commit_sha: str = Field(..., min_length=1, description="The pinned commit this parse was produced from.")
    root_path: str = Field(..., description="Absolute filesystem path to the repository root at parse time.")

    files: list[NormalizedFile] = Field(default_factory=list, description="Every successfully parsed file.")
    functions: list[NormalizedFunction] = Field(default_factory=list, description="Every function and method extracted (see is_method).")
    classes: list[NormalizedClass] = Field(default_factory=list, description="Every class extracted.")
    imports: list[NormalizedImport] = Field(default_factory=list, description="Every import statement extracted.")

    import_graph: list[ImportEdge] = Field(default_factory=list, description="Resolved file-to-file import dependency edges.")
    call_graph: list[CallEdge] = Field(default_factory=list, description="Resolved function/method call edges.")
    inheritance_graph: list[InheritanceEdge] = Field(default_factory=list, description="Resolved class inheritance edges.")

    parse_errors: list[str] = Field(default_factory=list, description="Repository-relative paths of files that failed to parse.")

    from_cache: bool = Field(default=False, description="Whether this RepositoryModel was served from repository_model.json rather than freshly computed.")
    manifest_path: str | None = Field(default=None, description="Absolute path to this parse's persisted repository_model.json.")
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When this RepositoryModel was computed (not when it was loaded from cache).")

    @property
    def top_level_functions(self) -> list[NormalizedFunction]:
        """Every function that is not a method (module-level or nested-in-a-function)."""
        return [function for function in self.functions if not function.is_method]

    @property
    def methods(self) -> list[NormalizedFunction]:
        """Every method (a function whose immediate enclosing scope is a class)."""
        return [function for function in self.functions if function.is_method]
