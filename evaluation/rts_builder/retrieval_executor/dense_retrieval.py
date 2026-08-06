"""Dense Retrieval: embedding-based file search over a `RepositoryModel`.

Both collaborators are injected (`Embedder`, `VectorIndex`), so a real
backend (`tara.context.embedder.SentenceTransformerEmbedder`, or a
FAISS-backed `VectorIndex`) can be substituted without changing this
class -- see `embedding_backend.py` and `vector_index.py`.

Latency measurement follows the frozen protocol in `latency_protocol.py`:
document-corpus assembly (`build_file_documents`, repository-dependent,
query-independent) and vector-index construction
(`VectorIndex.build`) are excluded from `retrieval_latency_ms`;
embedding generation (both the document batch and the query) and
vector search are included. See `README.md`'s "Design Rationale:
Revision 2" for why this requires two separate timed spans rather than
one contiguous span covering the whole method body.
"""
from __future__ import annotations

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.common import LatencyAccumulator, build_strategy_result
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.document_index import build_file_documents
from evaluation.rts_builder.retrieval_executor.embedding_backend import HashingEmbedder
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName, RetrievedFile, StrategyResult
from evaluation.rts_builder.retrieval_executor.vector_index import InMemoryVectorIndex, VectorIndex
from tara.context.embedder import Embedder


class DenseRetriever:
    """Embedding-based file retrieval over a `RepositoryModel`."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_index: VectorIndex | None = None,
        settings: RetrievalExecutorSettings | None = None,
    ) -> None:
        """Construct the retriever.

        Args:
            embedder: The embedding backend. Defaults to
                `HashingEmbedder(dimensions=settings.embedding_dimensions)`
                -- deterministic and offline; see `embedding_backend.py`
                for how to plug in a real model.
            vector_index: The vector index. Defaults to `InMemoryVectorIndex()`.
            settings: Controls `embedding_dimensions` when `embedder` is
                omitted. Defaults to `RetrievalExecutorSettings()`.
        """
        self._settings = settings or RetrievalExecutorSettings()
        self._embedder = embedder or HashingEmbedder(dimensions=self._settings.embedding_dimensions)
        self._vector_index = vector_index or InMemoryVectorIndex()

    def retrieve(self, model: RepositoryModel, query_text: str, top_k: int) -> StrategyResult:
        """Retrieve the top `top_k` files for `query_text` by embedding cosine similarity.

        Args:
            model: The repository to search.
            query_text: The raw developer query.
            top_k: Maximum number of files to return.

        Returns:
            This strategy's independent `StrategyResult`. Empty
            `retrieved_files` if the repository has no files.
            `retrieval_latency_ms` excludes document-corpus assembly and
            vector-index construction -- see `latency_protocol.py`.
        """
        documents = build_file_documents(model)
        if not documents:
            return build_strategy_result(RetrievalStrategyName.DENSE, model, query_text, [], 0.0, self._settings)

        file_paths = list(documents.keys())

        # --- Timed region: document embedding generation ---
        timer = LatencyAccumulator()
        timer.start()
        document_vectors = self._embedder.embed_batch([documents[file_path] for file_path in file_paths])
        timer.stop()

        # --- Index construction: excluded from the frozen latency protocol ---
        self._vector_index.build(dict(zip(file_paths, document_vectors, strict=True)))

        # --- Timed region: query embedding generation + vector search ---
        timer.start()
        query_vector = self._embedder.embed(query_text)
        matches = self._vector_index.search(query_vector, top_k)
        timer.stop()
        # `VectorIndex.search` already returns at most top_k matches, sorted by
        # (-score, file_path) -- the same deterministic tie-break `common.rank_scores`
        # applies -- so no second ranking pass is needed here.
        retrieved_files = [RetrievedFile(file_path=file_path, score=score) for file_path, score in matches]

        return build_strategy_result(
            RetrievalStrategyName.DENSE, model, query_text, retrieved_files, timer.total_ms, self._settings
        )
