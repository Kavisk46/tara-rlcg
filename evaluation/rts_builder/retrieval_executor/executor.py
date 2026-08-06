"""`RetrievalExecutor`: the Retrieval Executor subsystem's single public entry point.

Runs Lexical, Dense, and Graph retrieval independently (each producing
its own `StrategyResult`, with its own measured latency), then Hybrid
combines their already-computed scores -- see `hybrid_retrieval.py`.
"""
from __future__ import annotations

from evaluation.rts_builder.feature_extraction.models import FeatureVector, RepositorySizeCategory
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.dense_retrieval import DenseRetriever
from evaluation.rts_builder.retrieval_executor.exceptions import InvalidQueryError, MismatchedInputsError
from evaluation.rts_builder.retrieval_executor.graph_retrieval import GraphRetriever
from evaluation.rts_builder.retrieval_executor.hybrid_retrieval import HybridRetriever
from evaluation.rts_builder.retrieval_executor.lexical_retrieval import LexicalRetriever
from evaluation.rts_builder.retrieval_executor.models import RetrievalExecutionResult
from tara.core.logging import get_logger

logger = get_logger(__name__)


class RetrievalExecutor:
    """Executes all four retrieval strategies independently for one (repository, query) pair.

    Every collaborator is injected, following the same
    constructor-injection convention as every prior RTS Builder
    milestone's own top-level orchestrator (`RepositoryLoader`,
    `ParserPipeline`, `FeatureExtractor`).
    """

    def __init__(
        self,
        settings: RetrievalExecutorSettings | None = None,
        lexical_retriever: LexicalRetriever | None = None,
        dense_retriever: DenseRetriever | None = None,
        graph_retriever: GraphRetriever | None = None,
        hybrid_retriever: HybridRetriever | None = None,
    ) -> None:
        """Construct the executor.

        Args:
            settings: Configuration shared by every strategy. Defaults
                to `RetrievalExecutorSettings()` (environment defaults).
            lexical_retriever: Defaults to `LexicalRetriever(settings)`.
            dense_retriever: Defaults to `DenseRetriever(settings=settings)`
                (using the default `HashingEmbedder`/`InMemoryVectorIndex`).
            graph_retriever: Defaults to `GraphRetriever(settings)`.
            hybrid_retriever: Defaults to `HybridRetriever(settings)`.
        """
        self._settings = settings or RetrievalExecutorSettings()
        self._lexical = lexical_retriever or LexicalRetriever(self._settings)
        self._dense = dense_retriever or DenseRetriever(settings=self._settings)
        self._graph = graph_retriever or GraphRetriever(self._settings)
        self._hybrid = hybrid_retriever or HybridRetriever(self._settings)

    def execute_all(
        self, repository_model: RepositoryModel, feature_vector: FeatureVector, query_text: str
    ) -> RetrievalExecutionResult:
        """Run Lexical, Dense, Graph, and Hybrid retrieval, independently, for one query.

        Args:
            repository_model: The Parser subsystem's normalized output
                for the repository to search.
            feature_vector: The Feature Extraction subsystem's output
                for the same `(repository_model, query_text)` pair.
                Used only to scale `top_k` by
                `feature_vector.resource.repository_size_category`
                (see `README.md`) -- never to change which files are
                retrieved or how they're scored based on query-intent
                signals (`query.has_bug_keyword`, etc.), which would
                begin to implement the excluded Task Classifier/Router.
            query_text: The raw developer query. An empty string is
                valid (see each strategy's own Failure Modes).

        Returns:
            All four strategies' independent `StrategyResult`s.

        Raises:
            InvalidQueryError: If `query_text` is not a `str`.
            MismatchedInputsError: If `feature_vector` was not computed
                from `repository_model` (differing `repository_id` or `commit_sha`).
        """
        if not isinstance(query_text, str):
            raise InvalidQueryError(f"query_text must be a str, got {type(query_text).__name__}.")
        self._validate_inputs_match(repository_model, feature_vector)

        top_k = self._effective_top_k(feature_vector)

        lexical_result = self._lexical.retrieve(repository_model, query_text, top_k)
        dense_result = self._dense.retrieve(repository_model, query_text, top_k)
        graph_result = self._graph.retrieve(repository_model, query_text, top_k)
        hybrid_result = self._hybrid.combine(
            repository_model, query_text, lexical_result, dense_result, graph_result, top_k
        )

        logger.info(
            "Executed all retrieval strategies for %s@%s: lexical=%d dense=%d graph=%d hybrid=%d files retrieved",
            repository_model.repository_id, repository_model.commit_sha[:8],
            len(lexical_result.retrieved_files), len(dense_result.retrieved_files),
            len(graph_result.retrieved_files), len(hybrid_result.retrieved_files),
        )

        return RetrievalExecutionResult(
            repository_id=repository_model.repository_id,
            commit_sha=repository_model.commit_sha,
            query_text=query_text,
            lexical=lexical_result,
            dense=dense_result,
            graph=graph_result,
            hybrid=hybrid_result,
        )

    @staticmethod
    def _validate_inputs_match(repository_model: RepositoryModel, feature_vector: FeatureVector) -> None:
        if (
            feature_vector.repository_id != repository_model.repository_id
            or feature_vector.commit_sha != repository_model.commit_sha
        ):
            raise MismatchedInputsError(
                f"feature_vector ({feature_vector.repository_id!r}@{feature_vector.commit_sha!r}) was not "
                f"computed from repository_model ({repository_model.repository_id!r}@{repository_model.commit_sha!r})."
            )

    def _effective_top_k(self, feature_vector: FeatureVector) -> int:
        """Scale `top_k` down for large repositories, to bound total latency.

        The only use this executor makes of `feature_vector`: a purely
        performance-oriented adaptation based on repository *size*, not
        query *intent* -- see `execute_all`'s docstring.
        """
        if feature_vector.resource.repository_size_category is RepositorySizeCategory.LARGE:
            return min(self._settings.top_k, self._settings.large_repository_top_k_cap)
        return self._settings.top_k
