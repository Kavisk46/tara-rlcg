"""Exception hierarchy for TARA.

Every exception TARA raises derives from `TaraError`, so callers that
want to catch "anything TARA can throw" have a single type to catch,
while call sites that care about a specific failure mode can still
catch the narrower subclass.
"""
from __future__ import annotations


class TaraError(Exception):
    """Base class for all exceptions raised by TARA."""


class RepositoryParsingError(TaraError):
    """Raised when a repository cannot be parsed, e.g. an invalid path."""


class UnsupportedLanguageError(TaraError):
    """Raised when an operation is requested for a language with no registered grammar or handler."""


class ConfigurationError(TaraError):
    """Raised when TARA is configured incorrectly, e.g. a missing required setting."""


class ContextExtractionError(TaraError):
    """Raised when repository context (graphs, embeddings, summaries) cannot be built."""


class GraphBuildError(ContextExtractionError):
    """Raised when the repository graph cannot be constructed from a `ParsedRepository`."""


class SymbolIndexError(ContextExtractionError):
    """Raised when a `SymbolIndex` cannot be built from a repository context graph."""


class EmbeddingError(ContextExtractionError):
    """Raised when an embedding provider fails to produce a vector for a text input."""


class TaskClassificationError(TaraError):
    """Raised when the developer's query cannot be classified into a `TaskType`."""


class RuleEvaluationError(TaskClassificationError):
    """Raised when a classification rule fails to evaluate against extracted query features."""


class RoutingError(TaraError):
    """Raised when the adaptive router cannot select a retrieval strategy."""


class PolicyError(RoutingError):
    """Raised when a routing policy fails to evaluate against a `TaskClassification`."""


class PlanningError(RoutingError):
    """Raised when the retrieval planner fails to turn a `RoutingDecision` into a `RetrievalPlan`."""


class RetrievalError(TaraError):
    """Raised when a retriever fails to produce results."""


class ContextFusionError(TaraError):
    """Raised when retrieved context cannot be fused into a single generation context."""


class CodeGenerationError(TaraError):
    """Raised when the LLM fails to produce a valid code generation result."""
