"""Deduplication: groups `RetrievedChunk`s across multiple `RetrievedContext`s by `chunk_id`.

`chunk_id` reuses the exact node-id scheme `tara.context.models` already
establishes (`build_file_node_id` / `build_symbol_node_id`), so "the same
underlying symbol/node" (PROJECT_SPEC.md §20.1) is exactly "the same
`chunk_id`" -- no separate identity/similarity computation is needed or
implemented here.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tara.core.types import RetrieverKind
from tara.retrieval.models import RetrievedChunk, RetrievedContext


@dataclass(frozen=True)
class DeduplicatedCandidate:
    """One `chunk_id`'s canonical chunk, plus every retriever that surfaced it.

    Fusion-internal, not-yet-scored representation -- kept distinct from
    `tara.fusion.models.FusedChunk` (the public, cross-stage output) the
    same way `tara.retrieval.models.SearchResult` is kept distinct from
    `RetrievedChunk`: an internal, pipeline-stage-facing shape vs. a
    published contract. A frozen dataclass, not a Pydantic model,
    matching this project's convention for internal/ephemeral value
    objects that never cross a stage boundary (`PROJECT_SPEC.md` §14.3).
    """

    chunk: RetrievedChunk
    found_by: tuple[RetrieverKind, ...]
    source_scores: dict[str, float]


class Deduplicator:
    """Merges chunks sharing the same `chunk_id` across multiple `RetrievedContext`s.

    Stateless: holds no configuration, so a single instance (or no
    instance at all beyond a default construction) can be shared freely
    -- mirrors `tara.retrieval.ranking.RankingEngine`'s shape.
    """

    def deduplicate(self, contexts: Sequence[RetrievedContext]) -> list[DeduplicatedCandidate]:
        """Group every chunk across `contexts` by `chunk_id`, preserving first-seen order.

        Args:
            contexts: One `RetrievedContext` per retriever that ran,
                ideally in a fixed, deterministic order (e.g.
                `RetrievalOrchestrator.execute`'s own output order,
                which already follows `RetrievalPlan.execution_order`)
                -- this order decides which context's chunk becomes the
                "canonical" one for a `chunk_id` found by more than one
                retriever, and decides this method's own output order.

        Returns:
            One `DeduplicatedCandidate` per distinct `chunk_id`, in
            first-seen order across `contexts`. Empty if `contexts` is
            empty or every context has zero chunks.
        """
        canonical_chunks: dict[str, RetrievedChunk] = {}
        found_by: dict[str, list[RetrieverKind]] = {}
        source_scores: dict[str, dict[str, float]] = {}

        for context in contexts:
            for chunk in context.chunks:
                chunk_id = chunk.chunk_id
                if chunk_id not in canonical_chunks:
                    canonical_chunks[chunk_id] = chunk
                    found_by[chunk_id] = []
                    source_scores[chunk_id] = {}

                if chunk.retriever_kind not in found_by[chunk_id]:
                    found_by[chunk_id].append(chunk.retriever_kind)
                # A repeated (chunk_id, retriever_kind) pair is unreachable in practice --
                # RankingEngine.rank operates on a dict keyed by node id, so a single
                # RetrievedContext can never contain the same chunk_id twice -- but
                # setdefault keeps the first-seen score rather than silently overwriting
                # it if that invariant were ever violated upstream.
                source_scores[chunk_id].setdefault(
                    chunk.retriever_kind.value, chunk.score.normalized_score
                )

        return [
            DeduplicatedCandidate(
                chunk=canonical_chunks[chunk_id],
                found_by=tuple(sorted(found_by[chunk_id], key=lambda kind: kind.value)),
                source_scores=source_scores[chunk_id],
            )
            for chunk_id in canonical_chunks
        ]
