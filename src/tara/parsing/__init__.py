"""Repository Parser pipeline stage.

Turns a repository on disk into a `ParsedRepository`: a language-aware,
Tree-sitter-derived structural representation (files, symbols, imports)
that every downstream TARA stage consumes instead of re-reading and
re-parsing source files itself.
"""
from __future__ import annotations
