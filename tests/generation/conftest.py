"""Shared builder helpers for the `tara.generation` test suite.

`make_fused_chunk` is re-exported from `tests.fusion.conftest` rather
than redefined -- generation tests need the exact same `FusedChunk`
shape fusion tests do, just handed to a prompt/service instead of a
fusion pipeline.
"""
from __future__ import annotations

from tara.classification.models import TaskClassification
from tara.core.types import RetrievalStrategy, TaskType
from tara.fusion.models import FusedChunk, FusedContext
from tests.fusion.conftest import make_fused_chunk

__all__ = ["make_fused_chunk", "make_fused_context", "make_task_classification"]


def make_fused_context(
    *,
    query: str = "how does greet work?",
    chunks: list[FusedChunk] | None = None,
    truncated: bool = False,
    candidate_count: int | None = None,
) -> FusedContext:
    resolved_chunks = chunks if chunks is not None else []
    return FusedContext(
        query=query,
        chunks=resolved_chunks,
        total_tokens=sum(chunk.token_count for chunk in resolved_chunks),
        truncated=truncated,
        candidate_count=candidate_count if candidate_count is not None else len(resolved_chunks),
    )


def make_task_classification(
    *,
    task_type: TaskType = TaskType.EXPLAIN,
    retriever_kind: RetrievalStrategy = RetrievalStrategy.HYBRID,
    confidence: float = 0.9,
) -> TaskClassification:
    return TaskClassification(
        task_type=task_type,
        retriever_kind=retriever_kind,
        confidence=confidence,
    )
