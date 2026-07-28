"""Output contract for the Task Classifier pipeline stage."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tara.core.types import Language, RetrievalStrategy, TaskType


class TaskClassification(BaseModel):
    """The result of classifying a single developer query.

    Every field downstream stages need to decide *how* to retrieve
    context lives here: `task_type` and `retriever_kind` are the
    headline recommendation; the four `*_required` flags are the raw
    signals `retriever_kind` was derived from, exposed separately so a
    caller can build its own retrieval policy instead of trusting the
    default derivation; and `extracted_keywords` / `detected_symbols` /
    `detected_file_paths` / `language_hint` are what a retriever should
    actually search for.
    """

    task_type: TaskType = Field(..., description="The kind of software-engineering task the query represents.")
    retriever_kind: RetrievalStrategy = Field(
        ..., description="The recommended retrieval strategy: LEXICAL, SEMANTIC, GRAPH, or HYBRID."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in `task_type`, derived from rule agreement."
    )
    graph_required: bool = Field(default=False, description="Whether graph traversal is likely beneficial.")
    semantic_required: bool = Field(
        default=False, description="Whether semantic/embedding-based search is likely beneficial."
    )
    lexical_required: bool = Field(
        default=False, description="Whether exact lexical/keyword search is likely beneficial."
    )
    reasoning_required: bool = Field(
        default=False,
        description="Whether the downstream stage should reason about *why*, not just retrieve *what*.",
    )
    extracted_keywords: list[str] = Field(
        default_factory=list, description="Search-worthy terms extracted from the query, stop words removed."
    )
    detected_symbols: list[str] = Field(
        default_factory=list,
        description="Tokens that read like code symbols (PascalCase, camelCase, snake_case, CONSTANT_CASE, "
        "or an acronym) plus any explicitly quoted phrase.",
    )
    detected_file_paths: list[str] = Field(
        default_factory=list, description="Tokens that read like file paths or bare filenames."
    )
    language_hint: Language | None = Field(default=None, description="Programming language mentioned in the query, if any.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic detail, e.g. which rules fired; not part of the stable contract."
    )
