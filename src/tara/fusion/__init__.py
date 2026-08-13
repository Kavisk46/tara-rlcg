"""Context Fusion: merges one or more `RetrievedContext` objects into a single `FusedContext`.

See `tara.fusion.fusion.ContextFusion` for the top-level entry point, and
`PROJECT_SPEC.md` §20 for the stage's design rationale.
"""
from __future__ import annotations

from tara.fusion.deduplication import DeduplicatedCandidate, Deduplicator
from tara.fusion.fusion import ContextFusion
from tara.fusion.models import FusedChunk, FusedContext
from tara.fusion.reranker import BaselineReranker
from tara.fusion.score_merge import ScoreMerger
from tara.fusion.token_budget import TokenBudgeter, approximate_token_count

__all__ = [
    "ContextFusion",
    "DeduplicatedCandidate",
    "Deduplicator",
    "FusedChunk",
    "FusedContext",
    "BaselineReranker",
    "ScoreMerger",
    "TokenBudgeter",
    "approximate_token_count",
]
