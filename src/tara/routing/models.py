"""Output contract for the Task-Guided Adaptive Router pipeline stage."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tara.core.types import RetrieverKind
from tara.routing.strategy import RoutingStrategy


class RetrievalPlan(BaseModel):
    """An executable plan for the (not-yet-implemented) retrieval stage.

    This is the router's entire output: which retriever kinds to run,
    in what order, sequentially or in parallel, how many results to
    keep, whether to expand graph neighbors, and whether to rerank.
    Nothing about *how* a retriever actually fetches results is decided
    here -- the retrieval stage itself is a future pipeline stage this
    plan is handed to.
    """

    strategy: RoutingStrategy = Field(..., description="The routing strategy this plan implements.")
    retrievers: list[RetrieverKind] = Field(
        ..., description="The retriever kinds to run, deduplicated, in no particular order."
    )
    execution_order: list[RetrieverKind] = Field(
        ..., description="`retrievers`, ordered cheapest/fastest first -- the order to run them in when sequential."
    )
    parallel: bool = Field(..., description="Whether `retrievers` should execute concurrently rather than in `execution_order`.")
    graph_depth: int = Field(
        default=0, ge=0, description="Graph traversal depth. 0 when GRAPH is not part of `retrievers`."
    )
    expand_neighbors: bool = Field(
        default=False, description="Whether the graph retriever should expand to neighboring nodes."
    )
    rerank: bool = Field(..., description="Whether retrieved candidates should be reranked before use.")
    top_k: int = Field(..., gt=0, description="Number of results to keep per retriever after any reranking.")
    candidate_limit: int = Field(
        ..., gt=0, description="Number of candidates to fetch per retriever before reranking down to `top_k`."
    )
    reason: str = Field(..., description="Human-readable explanation of why this plan was chosen.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic detail, e.g. which policy fired; not part of the stable contract."
    )
