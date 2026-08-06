"""Hybrid Retrieval: a weighted combination of the other three strategies' already-computed scores.

Does not re-run Lexical/Dense/Graph retrieval itself. It combines the
`retrieved_files` scores already present on their `StrategyResult`s, for
two reasons: efficiency (no repeated work), and correctness -- combining
the *exact* scores already reported in the other three independent
results guarantees Hybrid's output is a genuine function of what was
actually measured, not a second, potentially-diverging recomputation.
`RetrievalExecutor` is what calls Lexical/Dense/Graph once each and
passes their results here.
"""
from __future__ import annotations

import time

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.common import build_strategy_result, elapsed_ms, rank_scores
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName, StrategyResult
from tara.retrieval.utils import normalize_scores


class HybridRetriever:
    """Weighted combination of Lexical, Dense, and Graph retrieval scores."""

    def __init__(self, settings: RetrievalExecutorSettings | None = None) -> None:
        """Construct the retriever.

        Args:
            settings: Controls the three strategy weights
                (`hybrid_lexical_weight`/`hybrid_dense_weight`/`hybrid_graph_weight`,
                validated to sum to 1.0). Defaults to
                `RetrievalExecutorSettings()`.
        """
        self._settings = settings or RetrievalExecutorSettings()

    def combine(
        self,
        model: RepositoryModel,
        query_text: str,
        lexical_result: StrategyResult,
        dense_result: StrategyResult,
        graph_result: StrategyResult,
        top_k: int,
    ) -> StrategyResult:
        """Combine three already-computed strategy results into one hybrid ranking.

        Args:
            model: The repository these results were computed for (used
                for `context_token_count`).
            query_text: The raw developer query (carried through for provenance).
            lexical_result: `LexicalRetriever.retrieve`'s output.
            dense_result: `DenseRetriever.retrieve`'s output.
            graph_result: `GraphRetriever.retrieve`'s output.
            top_k: Maximum number of files to return.

        Returns:
            This strategy's independent `StrategyResult`. Its own
            `retrieval_latency_ms` measures only the combination step,
            not the other three strategies' own (separately reported)
            latencies.
        """
        start = time.perf_counter()

        lexical_norm = normalize_scores({retrieved.file_path: retrieved.score for retrieved in lexical_result.retrieved_files})
        dense_norm = normalize_scores({retrieved.file_path: retrieved.score for retrieved in dense_result.retrieved_files})
        graph_norm = normalize_scores({retrieved.file_path: retrieved.score for retrieved in graph_result.retrieved_files})

        all_files = set(lexical_norm) | set(dense_norm) | set(graph_norm)
        combined = {
            file_path: (
                self._settings.hybrid_lexical_weight * lexical_norm.get(file_path, 0.0)
                + self._settings.hybrid_dense_weight * dense_norm.get(file_path, 0.0)
                + self._settings.hybrid_graph_weight * graph_norm.get(file_path, 0.0)
            )
            for file_path in all_files
        }

        retrieved_files = rank_scores(combined, top_k)
        return build_strategy_result(
            RetrievalStrategyName.HYBRID, model, query_text, retrieved_files, elapsed_ms(start), self._settings
        )
