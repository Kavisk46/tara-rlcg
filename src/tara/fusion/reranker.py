"""Reranking baseline: orders deduplicated, score-merged candidates by descending fused_score.

Per PROJECT_SPEC.md §20.2, this IS the "weighted merge of normalized
per-retriever scores" baseline -- `tara.fusion.score_merge.ScoreMerger`
computes each candidate's `fused_score`, and this component's entire job
is to sort by it. A cross-encoder reranker is explicitly named in the
spec as a *future ablation variant*, not assumed superior to this
baseline; it is NOT implemented here (nor is any other learned or
LLM-based reranking).
"""
from __future__ import annotations

from tara.fusion.models import FusedChunk


class BaselineReranker:
    """Sorts `FusedChunk`s by descending `fused_score`, tie-broken by ascending `chunk_id`.

    Stateless: mirrors `tara.retrieval.ranking.RankingEngine`'s shape --
    a single-method, no-constructor-dependency component, invoked only
    when `RetrievalPlan.rerank` is true. The decision of *whether* to
    invoke this belongs to the caller (`ContextFusion`); this class has
    no opinion on it.
    """

    def rerank(self, chunks: list[FusedChunk]) -> list[FusedChunk]:
        """Return `chunks` sorted by descending `fused_score`.

        Args:
            chunks: Already-deduplicated, already-scored candidates.

        Returns:
            A new list (input is not mutated), sorted by descending
            `fused_score`; ties broken by ascending `chunk_id` so the
            order is fully deterministic even when two candidates score
            identically -- the same tie-break convention already used
            by `RankingEngine.rank`.
        """
        return sorted(chunks, key=lambda chunk: (-chunk.fused_score, chunk.chunk_id))
