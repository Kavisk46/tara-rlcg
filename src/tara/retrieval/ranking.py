"""Ranking engine: turns raw BM25 scores into a sorted, normalized, top-k ranking.

`RankingEngine` is deliberately domain-agnostic, mirroring `BM25Index`:
it operates on `document_id -> raw_score` mappings, the exact shape
`BM25Index.score` returns, and knows nothing about symbols, files,
`NodeType`, or `RepositoryContext`. Turning a ranked `document_id` back
into a full `SearchResult` (with its name, node type, file path, and
matched field) is `lexical_retriever.py`'s responsibility, once ranking
has already decided which document ids matter and in what order --
`RankingEngine` never constructs a `SearchResult` itself, only the
`RetrievalScore` half of one.
"""
from __future__ import annotations

from collections.abc import Mapping

from tara.core.exceptions import RetrievalError
from tara.retrieval.models import RetrievalScore
from tara.retrieval.utils import normalize_scores


class RankingEngine:
    """Sorts and truncates raw per-document scores into a final ranking.

    Stateless: holds no configuration and no per-call caching, so a
    single instance (or, equivalently, no instance at all beyond a
    default construction) can be shared freely across concurrent
    queries. Mirrors `tara.context.symbol_index.SymbolIndexBuilder`'s
    shape -- a small class with one method and no constructor
    dependencies -- for structural consistency with the rest of TARA
    rather than being a free function, since `RankingEngine` is named
    as its own component in this module's design.
    """

    def rank(self, raw_scores: Mapping[str, float], top_k: int) -> list[tuple[str, RetrievalScore]]:
        """Rank `raw_scores`, returning at most `top_k` results.

        Normalization is computed over the *entire* candidate pool in
        `raw_scores`, before truncation to `top_k` -- not over only the
        `top_k` survivors. Normalizing after truncation would make the
        single best-scoring document always read `normalized_score ==
        1.0` regardless of how much better it actually was than the
        rest of the pool, which would misrepresent its true relative
        quality once Context Fusion later compares normalized scores
        across multiple retrievers.

        Complexity:
            O(N log N) in `len(raw_scores)`, dominated by the sort;
            normalization is a single O(N) pass (`normalize_scores`).
            No work is proportional to `top_k` beyond the final slice.

        Args:
            raw_scores: `document_id -> raw BM25 score`, e.g. the direct
                output of `BM25Index.score`. An empty mapping is valid
                and yields an empty result.
            top_k: Maximum number of results to return. Must be a
                positive integer; if fewer than `top_k` candidates
                exist, every candidate is returned.

        Returns:
            `(document_id, RetrievalScore)` pairs, sorted by descending
            raw score. Ties are broken by ascending `document_id`, so
            ranking order is fully deterministic even when two
            documents score identically.

        Raises:
            RetrievalError: If `top_k` is not a positive integer.
        """
        if top_k <= 0:
            raise RetrievalError(f"RankingEngine.rank requires top_k > 0, got {top_k!r}.")
        if not raw_scores:
            return []

        normalized_scores = normalize_scores(raw_scores)
        ordered_ids = sorted(raw_scores, key=lambda document_id: (-raw_scores[document_id], document_id))

        return [
            (
                document_id,
                RetrievalScore(
                    raw_score=raw_scores[document_id],
                    normalized_score=normalized_scores[document_id],
                ),
            )
            for document_id in ordered_ids[:top_k]
        ]
