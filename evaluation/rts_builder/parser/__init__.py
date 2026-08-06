"""RTS Builder Parser subsystem (Python-only V1).

Converts a `Repository` (Repository Loader's output, accepted and
frozen) into a `RepositoryModel`: normalized files, imports, functions,
classes, methods, decorators, docstrings, and line numbers, plus an
import graph, a call graph, and a class inheritance graph, exportable as
JSON. See `README.md` for architecture, design decisions, and failure
modes; see `REVIEW_RESPONSE.md` for an anticipated-reviewer
self-assessment of this milestone's known limitations.

Only Python is supported in this version. Feature extraction, oracle
utility computation, retrieval, embeddings, the router, the planner, and
the LLM interface are later RTS Builder milestones and are not present
here.
"""
from __future__ import annotations
