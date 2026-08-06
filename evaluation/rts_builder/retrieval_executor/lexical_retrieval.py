"""Lexical Retrieval: BM25 + exact identifier matching + keyword overlap, blended.

Reuses `tara.retrieval.bm25_index.BM25Index` (a generic, corpus
-agnostic `(document_id, tokens)` ranker -- see its own module
docstring) directly, unmodified, rather than reimplementing BM25: it
has no dependency on `RepositoryContext` and accepts exactly the
`(file_path, tokens)` shape this module can already produce from
`document_index.build_file_documents`. `tara.retrieval.utils.tokenize_for_search`
/`normalize_scores` are reused for the same reason.

The three sub-signals (BM25, exact identifier match, raw keyword
overlap) are each independently min-max normalized before being
combined by configured weights -- BM25 scores and raw match counts are
on entirely different scales, so combining them unnormalized would let
whichever signal happens to produce larger raw numbers dominate
regardless of its configured weight.

Latency measurement follows the frozen protocol in `latency_protocol.py`:
building the BM25 index (`BM25Index.build`) is "index construction" and
is excluded from `retrieval_latency_ms`; tokenizing the query and every
downstream scoring step is included. See `README.md`'s "Design
Rationale: Revision 2" for why this requires a discontiguous timed
region rather than a single span covering the whole method body.
"""
from __future__ import annotations

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.common import LatencyAccumulator, build_strategy_result, rank_scores
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.document_index import build_file_documents
from evaluation.rts_builder.retrieval_executor.identifier_matching import count_identifier_matches_by_file
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName, StrategyResult
from tara.retrieval.bm25_index import BM25Index
from tara.retrieval.utils import normalize_scores, tokenize_for_search


class LexicalRetriever:
    """Sparse, keyword-driven file retrieval over a `RepositoryModel`."""

    def __init__(self, settings: RetrievalExecutorSettings | None = None) -> None:
        """Construct the retriever.

        Args:
            settings: Controls BM25's `k1`/`b` and the three sub-signal
                combination weights. Defaults to
                `RetrievalExecutorSettings()` (environment defaults).
        """
        self._settings = settings or RetrievalExecutorSettings()

    def retrieve(self, model: RepositoryModel, query_text: str, top_k: int) -> StrategyResult:
        """Retrieve the top `top_k` files for `query_text` by combined lexical relevance.

        Args:
            model: The repository to search.
            query_text: The raw developer query.
            top_k: Maximum number of files to return.

        Returns:
            This strategy's independent `StrategyResult`. `retrieval_latency_ms`
            excludes BM25 index construction -- see `latency_protocol.py`.
        """
        documents = build_file_documents(model)

        # --- Index construction: excluded from the frozen latency protocol ---
        bm25_index = self._build_bm25_index(documents)

        # --- Timed region: query tokenization + score computation ---
        timer = LatencyAccumulator()
        timer.start()
        query_tokens = tokenize_for_search(query_text)
        bm25_scores = bm25_index.score(query_tokens) if documents else {}
        identifier_scores = {
            file_path: float(count) for file_path, count in count_identifier_matches_by_file(model, query_tokens).items()
        }
        keyword_scores = self._keyword_overlap_scores(documents, query_tokens)

        bm25_norm = normalize_scores(bm25_scores)
        identifier_norm = normalize_scores(identifier_scores)
        keyword_norm = normalize_scores(keyword_scores)

        combined = {
            file_path: (
                self._settings.lexical_bm25_weight * bm25_norm.get(file_path, 0.0)
                + self._settings.lexical_identifier_weight * identifier_norm.get(file_path, 0.0)
                + self._settings.lexical_keyword_overlap_weight * keyword_norm.get(file_path, 0.0)
            )
            for file_path in set(bm25_norm) | set(identifier_norm) | set(keyword_norm)
        }

        retrieved_files = rank_scores(combined, top_k)
        timer.stop()
        # --- Timed region ends ---

        return build_strategy_result(
            RetrievalStrategyName.LEXICAL, model, query_text, retrieved_files, timer.total_ms, self._settings
        )

    def _build_bm25_index(self, documents: dict[str, str]) -> BM25Index:
        index = BM25Index(k1=self._settings.bm25_k1, b=self._settings.bm25_b)
        if documents:
            index.build((file_path, tokenize_for_search(text)) for file_path, text in documents.items())
        return index

    @staticmethod
    def _keyword_overlap_scores(documents: dict[str, str], query_tokens: list[str]) -> dict[str, float]:
        """Raw count of query tokens also present in a file's own token set."""
        query_token_set = set(query_tokens)
        if not query_token_set:
            return {}
        scores: dict[str, float] = {}
        for file_path, text in documents.items():
            overlap = query_token_set.intersection(tokenize_for_search(text))
            if overlap:
                scores[file_path] = float(len(overlap))
        return scores
