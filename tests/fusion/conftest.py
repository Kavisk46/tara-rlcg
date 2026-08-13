"""Shared builder helpers for the `tara.fusion` test suite.

Plain, directly-importable functions (not fixtures): every test module
in this package needs the same `RetrievedChunk` / `RetrievedContext` /
`RetrievalPlan` shapes, just with different field overrides per test, so
a shared factory function (mirroring `tests/retrieval/test_models.py`'s
own `_make_chunk` helper, generalized across files here since fusion
tests span several modules) avoids re-deriving the same boilerplate five
times over.
"""
from __future__ import annotations

from tara.context.models import NodeType
from tara.core.types import RetrieverKind
from tara.fusion.models import FusedChunk
from tara.retrieval.models import RetrievalScore, RetrievedChunk, RetrievedContext
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy


def make_score(raw: float = 1.0, normalized: float = 0.5) -> RetrievalScore:
    return RetrievalScore(raw_score=raw, normalized_score=normalized)


def make_chunk(
    *,
    chunk_id: str = "file::app.py::greet::5",
    retriever_kind: RetrieverKind = RetrieverKind.LEXICAL,
    node_type: NodeType = NodeType.FUNCTION,
    name: str = "greet",
    file_path: str = "app.py",
    start_line: int | None = 5,
    end_line: int | None = 10,
    content: str = "def greet(): ...",
    docstring: str | None = None,
    normalized_score: float = 0.5,
    raw_score: float = 1.0,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        retriever_kind=retriever_kind,
        node_type=node_type,
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        content=content,
        docstring=docstring,
        score=make_score(raw=raw_score, normalized=normalized_score),
    )


def make_context(
    *,
    retriever_kind: RetrieverKind = RetrieverKind.LEXICAL,
    query: str = "greet",
    chunks: list[RetrievedChunk] | None = None,
    total_candidates: int = 0,
) -> RetrievedContext:
    return RetrievedContext(
        retriever_kind=retriever_kind,
        query=query,
        chunks=chunks or [],
        total_candidates=total_candidates,
    )


def make_fused_chunk(
    *,
    chunk_id: str = "file::app.py::greet::5",
    found_by: tuple[RetrieverKind, ...] = (RetrieverKind.LEXICAL,),
    source_scores: dict[str, float] | None = None,
    fused_score: float = 0.5,
    start_line: int | None = 5,
    end_line: int | None = 10,
    token_count: int = 4,
) -> FusedChunk:
    return FusedChunk(
        chunk_id=chunk_id,
        node_type=NodeType.FUNCTION,
        name="greet",
        file_path="app.py",
        start_line=start_line,
        end_line=end_line,
        content="def greet(): ...",
        fused_score=fused_score,
        found_by=found_by,
        source_scores=(
            source_scores if source_scores is not None else {RetrieverKind.LEXICAL.value: 0.5}
        ),
        token_count=token_count,
    )


def make_plan(
    *,
    retrievers: list[RetrieverKind] | None = None,
    rerank: bool = False,
    top_k: int = 10,
    candidate_limit: int = 30,
) -> RetrievalPlan:
    resolved_retrievers = retrievers if retrievers is not None else [RetrieverKind.LEXICAL]
    return RetrievalPlan(
        strategy=RoutingStrategy.HYBRID,
        retrievers=resolved_retrievers,
        execution_order=resolved_retrievers,
        parallel=False,
        rerank=rerank,
        top_k=top_k,
        candidate_limit=candidate_limit,
        reason="test",
    )
