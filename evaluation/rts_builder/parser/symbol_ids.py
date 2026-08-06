"""The single, shared symbol-id convention used across normalization and graph resolution.

Both ``normalizer.py`` (assigning ids to ``NormalizedFunction``/
``NormalizedClass``) and ``graph_builder.py`` (building the name-lookup
indices call/inheritance resolution query) must agree on the same id for
the same symbol; centralizing it here is what guarantees that rather
than relying on two call sites staying in sync by convention.
"""
from __future__ import annotations


def build_symbol_id(file_path: str, qualified_name: str, start_line: int) -> str:
    """Return a deterministic, collision-resistant id for a function or class.

    Qualifying with the file path and start line (not just the
    qualified name) keeps ids unique even across two files defining a
    same-named top-level symbol, or a single file defining the same
    name twice in the same scope (legal in Python; the later definition
    shadows the earlier one at runtime, but both appear in the AST).

    Args:
        file_path: Repository-relative, POSIX-style path of the defining file.
        qualified_name: The symbol's dotted name, e.g. 'ClassName.method_name'.
        start_line: 1-indexed line the definition begins on.

    Returns:
        A string unique within a single repository parse.
    """
    return f"{file_path}::{qualified_name}::{start_line}"
