"""Single-pass extraction of imports, functions, classes, and call sites from one file's AST.

``PythonAstVisitor`` is the one piece of this milestone with no
equivalent in the previous Tree-sitter-based design: Python's own
``ast`` module already gives structurally correct, semantically precise
access to decorators (``decorator_list``), docstrings
(``ast.get_docstring``), and base classes (``ClassDef.bases``) that a
generic multi-language Tree-sitter walk could only approximate. It also
tracks lexical scope (which class or function a node is nested inside)
via ``ast.NodeVisitor``'s natural recursive traversal, which is why call
-site attribution here does not need the previous design's separate
line-range containment search.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class RawImport:
    """A single import statement, as written, before any within-repository resolution."""

    module: str
    """For ``import a.b``: ``"a.b"``. For ``from a.b import c``: ``"a.b"``. For a bare
    ``from . import c`` (no module named): ``""``."""
    imported_names: list[str]
    is_relative: bool
    level: int
    """0 for an absolute import; the number of leading dots for a relative ``from`` import."""
    line: int


@dataclass(frozen=True)
class RawFunction:
    """A single function or method definition."""

    name: str
    qualified_name: str
    is_method: bool
    parent_class: str | None
    is_async: bool
    decorators: list[str]
    docstring: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True)
class RawClass:
    """A single class definition."""

    name: str
    qualified_name: str
    parent_class: str | None
    """The enclosing class's qualified name, for a nested class; else None."""
    base_names: list[str]
    """Base class names exactly as written (``Foo`` from ``class X(Foo):``, ``mod.Bar``'s
    final segment ``Bar`` from ``class X(mod.Bar):``), unresolved -- see ``graph_builder.py``."""
    decorators: list[str]
    docstring: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True)
class RawCallSite:
    """A single call expression, before resolution to a callee symbol."""

    enclosing_qualified_name: str | None
    """The qualified name of the innermost enclosing function/method, or None if the call
    occurs at module or class-body level (no single function it can be attributed to)."""
    callee_name: str
    line: int


@dataclass(frozen=True)
class _ScopeFrame:
    kind: str  # "class" | "function"
    qualified_name: str


def _unparse_decorators(decorator_list: list[ast.expr]) -> list[str]:
    """Return each decorator's source text, without the leading ``@``."""
    return [ast.unparse(decorator) for decorator in decorator_list]


def _extract_dotted_tail(node: ast.expr) -> str | None:
    """Reduce a (possibly dotted, e.g. ``pkg.Base``) expression to its final simple name.

    Used for both call-target and base-class extraction: Python's
    ``ast.Attribute`` already exposes the final segment directly via
    ``.attr``, so unlike the Tree-sitter version of this logic, no
    generic "rightmost identifier" tree walk is needed -- the grammar
    does the work.

    Returns:
        The simple name, or None if `node` isn't a plain name or dotted
        attribute access (e.g. it's a subscript like ``Generic[T]``, or
        a call expression -- both left unresolved rather than guessed at).
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class PythonAstVisitor(ast.NodeVisitor):
    """Walks one file's AST, collecting imports, functions, classes, and call sites.

    A single traversal serves all four extraction targets plus call
    -site attribution, using an explicit scope stack
    (``_ScopeFrame``) to track lexical nesting: a function's
    ``is_method`` is true exactly when its immediate enclosing scope is
    a class (not merely "inside a class somewhere," which would
    misclassify a function nested inside a method as a method of the
    class rather than a nested function of that method).
    """

    def __init__(self) -> None:
        """Construct an empty visitor; call ``visit(tree)`` to populate it."""
        self.imports: list[RawImport] = []
        self.functions: list[RawFunction] = []
        self.classes: list[RawClass] = []
        self.call_sites: list[RawCallSite] = []
        self._scope_stack: list[_ScopeFrame] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Record each ``import a.b[, c.d]`` name as a separate ``RawImport``."""
        for alias in node.names:
            self.imports.append(
                RawImport(module=alias.name, imported_names=[], is_relative=False, level=0, line=node.lineno)
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record a ``from module import a, b`` (or relative ``from . import a``) statement."""
        self.imports.append(
            RawImport(
                module=node.module or "",
                imported_names=[alias.name for alias in node.names],
                is_relative=node.level > 0,
                level=node.level,
                line=node.lineno,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Record a class definition, then recurse into its body with the class pushed onto scope."""
        qualified_name = self._qualify(node.name)
        parent_class = self._enclosing_class()
        base_names = [name for base in node.bases if (name := _extract_dotted_tail(base)) is not None]

        self.classes.append(
            RawClass(
                name=node.name,
                qualified_name=qualified_name,
                parent_class=parent_class,
                base_names=base_names,
                decorators=_unparse_decorators(node.decorator_list),
                docstring=ast.get_docstring(node, clean=True),
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            )
        )

        self._scope_stack.append(_ScopeFrame(kind="class", qualified_name=qualified_name))
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Record a ``def`` function/method definition."""
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Record an ``async def`` function/method definition."""
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool) -> None:
        qualified_name = self._qualify(node.name)
        is_method = bool(self._scope_stack) and self._scope_stack[-1].kind == "class"
        parent_class = self._scope_stack[-1].qualified_name if is_method else None

        self.functions.append(
            RawFunction(
                name=node.name,
                qualified_name=qualified_name,
                is_method=is_method,
                parent_class=parent_class,
                is_async=is_async,
                decorators=_unparse_decorators(node.decorator_list),
                docstring=ast.get_docstring(node, clean=True),
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            )
        )

        self._scope_stack.append(_ScopeFrame(kind="function", qualified_name=qualified_name))
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """Record a call site, attributed to the innermost enclosing function/method, if any."""
        callee_name = _extract_dotted_tail(node.func)
        if callee_name is not None:
            self.call_sites.append(
                RawCallSite(
                    enclosing_qualified_name=self._innermost_enclosing_function(),
                    callee_name=callee_name,
                    line=node.lineno,
                )
            )
        self.generic_visit(node)

    def _qualify(self, name: str) -> str:
        if self._scope_stack:
            return f"{self._scope_stack[-1].qualified_name}.{name}"
        return name

    def _enclosing_class(self) -> str | None:
        if self._scope_stack and self._scope_stack[-1].kind == "class":
            return self._scope_stack[-1].qualified_name
        return None

    def _innermost_enclosing_function(self) -> str | None:
        for frame in reversed(self._scope_stack):
            if frame.kind == "function":
                return frame.qualified_name
        return None
