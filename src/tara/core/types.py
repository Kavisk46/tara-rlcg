"""Shared enums used across TARA pipeline stages.

Keeping these in a single, dependency-free module lets every pipeline
stage (parsing, context extraction, classification, routing, retrieval,
generation) agree on the same vocabulary without introducing coupling
between the stages themselves.
"""
from __future__ import annotations

from enum import Enum


class Language(str, Enum):
    """Programming languages TARA can parse and reason about."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    C = "c"
    CPP = "cpp"
    UNKNOWN = "unknown"


class TaskType(str, Enum):
    """Software-engineering task categories the Task Classifier can assign.

    This taxonomy drives the Task-Guided Adaptive Router: each value is
    expected to map to a different mix of retrievers best suited to that
    kind of task. The mapping itself lives in the router (and, at a
    coarser grain, in `TaskClassification.retriever_kind`), not here, so
    new retrieval strategies can be added without changing the taxonomy.
    """

    SEARCH = "search"
    EXPLAIN = "explain"
    DEBUG = "debug"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    GENERATE = "generate"
    TEST = "test"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    SECURITY = "security"
    PERFORMANCE = "performance"
    UNKNOWN = "unknown"


class RetrieverKind(str, Enum):
    """Concrete retriever implementations composed by the Task-Guided Adaptive Router.

    Distinct from `RetrievalStrategy`: this enumerates *retriever
    components* the router assembles (e.g. a graph retriever backed by
    `RepositoryContext.graph`), while `RetrievalStrategy` is the
    higher-level *strategy* the Task Classifier recommends before any
    retriever is invoked.
    """

    LEXICAL = "lexical"
    GRAPH = "graph"
    DENSE = "dense"
    API = "api"
    STATIC_ANALYSIS = "static_analysis"


class RetrievalStrategy(str, Enum):
    """The retrieval strategy the Task Classifier recommends for a query.

    Coarser-grained than `RetrieverKind`: a `HYBRID` recommendation
    tells the router to combine multiple retrievers, without prescribing
    which ones.
    """

    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"
    HYBRID = "hybrid"
