"""Score merging: combines multiple retrievers' normalized scores for one deduplicated candidate.

Implements PROJECT_SPEC.md §20.2's baseline: a weighted merge of
normalized per-retriever scores, deliberately implemented and used
*before* any cross-encoder -- the spec frames the cross-encoder as a
later ablation to be evaluated for latency impact, "not assumed
superior a priori." No cross-encoder, no learned reranking model, and
no dependency beyond arithmetic.
"""
from __future__ import annotations

from collections.abc import Mapping

from tara.core.exceptions import ContextFusionError

_DEFAULT_WEIGHT = 1.0


class ScoreMerger:
    """Weighted-average merge of a deduplicated candidate's per-retriever normalized scores.

    Stateless aside from its injected weight table -- matching
    `LexicalRetriever`'s injected-tunables pattern, just narrower (this
    component only needs the weight table, not a whole settings object).
    """

    def __init__(self, retriever_weights: Mapping[str, float] | None = None) -> None:
        """Construct the merger.

        Args:
            retriever_weights: RetrieverKind.value -> weight. A kind
                absent from this mapping defaults to weight 1.0 (every
                retriever trusted equally), matching
                `TaraSettings.fusion_retriever_weights`'s own documented
                default. Injected rather than read from `TaraSettings`
                directly, so tests and callers with a pre-resolved
                weight table don't need a full settings object.
        """
        self._weights = dict(retriever_weights) if retriever_weights else {}

    def merge(self, source_scores: Mapping[str, float]) -> float:
        """Weighted average of `source_scores`' values, weighted by each key's configured weight.

        Args:
            source_scores: RetrieverKind.value -> that retriever's own
                `normalized_score` for one deduplicated candidate (see
                `tara.fusion.deduplication.DeduplicatedCandidate.source_scores`).
                Must be non-empty -- every `DeduplicatedCandidate`
                `Deduplicator` produces has at least one contributing
                retriever by construction.

        Returns:
            A weighted average (not a weighted sum) of `source_scores`'
            values: a candidate found by more retrievers is not
            automatically scored higher purely for being found more
            often -- it scores higher only if those retrievers'
            individual scores were themselves high. Stays within the
            range spanned by `source_scores`' own values (e.g. always
            in `[0, 1]` when every input already is, which
            `RetrievalScore.normalized_score` guarantees), so callers
            never need to re-clip it.

        Raises:
            ContextFusionError: If `source_scores` is empty (nothing to
                merge -- a caller/data-integrity error, not a normal
                "no score" case).
        """
        if not source_scores:
            raise ContextFusionError(
                "ScoreMerger.merge received empty source_scores; nothing to merge."
            )

        weighted_sum = 0.0
        total_weight = 0.0
        for kind_value, score in source_scores.items():
            weight = self._weights.get(kind_value, _DEFAULT_WEIGHT)
            weighted_sum += weight * score
            total_weight += weight

        if total_weight == 0.0:
            # Every contributing retriever was explicitly configured with weight 0 -- a
            # legitimate way to mute a retriever's influence on ranking without removing
            # it from found_by/source_scores' provenance record.
            return 0.0

        return weighted_sum / total_weight
