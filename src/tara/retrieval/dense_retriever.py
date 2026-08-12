"""Dense Retriever: cosine-similarity search over `RepositoryContext.embeddings`.

`DenseRetriever` is the semantic-search counterpart to `LexicalRetriever`:
it embeds the query with the same injected `Embedder` used to build
`RepositoryContext.embeddings` (guaranteeing query and document vectors
share one embedding space, per `PROJECT_SPEC.md` §19), scores every
embedded symbol by cosine similarity, and reuses `RankingEngine` -- the
same sorting/normalization/top-k component `LexicalRetriever` already
uses -- to turn raw similarities into a ranked, normalized result.

No FAISS index is built here. `RepositoryContext.embeddings` is a plain
`dict[str, list[float]]` with no existing index-construction path
anywhere in this codebase, and a repository's embedded-symbol count
(classes/functions/methods only, per `tara.context.embedder`) is small
enough that an exhaustive, dependency-free linear scan is both fast
enough and, per the same rationale already documented on
`tara.retrieval.bm25_index.BM25Index`, keeps the scoring logic fully
inspectable and reproducible without taking on an unvetted third-party
dependency. `faiss-cpu` remains declared in `pyproject.toml` for a
future milestone if profiling ever shows this module needs it; adopting
it preemptively here would be exactly the kind of premature abstraction
this project's design principles (`PROJECT_SPEC.md` §14.6) warn against.
"""
from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from pathlib import Path

from tara.context.embedder import Embedder
from tara.context.models import NodeType, RepositoryContext
from tara.core.exceptions import RetrievalError
from tara.core.logging import get_logger
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.models import RetrievalScore, RetrievedChunk, RetrievedContext
from tara.retrieval.ranking import RankingEngine
from tara.retrieval.utils import decode_byte_span, read_file_bytes
from tara.routing.models import RetrievalPlan

logger = get_logger(__name__)


class DenseRetriever(Retriever):
    """Cosine-similarity search over `RepositoryContext.embeddings`.

    All collaborators are injected: `embedder` (required -- must be the
    same `Embedder` implementation, and ideally the same instance, used
    by `RepositoryContextExtractor` to build the embeddings this
    retriever searches over, or query/document vectors will not share a
    space) and `ranking_engine` (required, reused unchanged from
    `LexicalRetriever` rather than reimplementing sorting/normalization
    here). Stateless between calls: unlike `LexicalRetriever`, no index
    needs to be built or cached, since `RepositoryContext.embeddings` is
    already a fully materialized mapping this retriever reads directly.
    """

    def __init__(self, embedder: Embedder, ranking_engine: RankingEngine) -> None:
        """Construct the retriever.

        Args:
            embedder: Embeds the query text into the same vector space
                as `context.embeddings`. Injected rather than
                constructed internally so tests can substitute a small,
                deterministic fake instead of loading a real model.
            ranking_engine: Turns raw cosine-similarity scores into a
                sorted, normalized, top-k ranking. The same component
                type `LexicalRetriever` uses for its BM25 scores.
        """
        self._embedder = embedder
        self._ranking_engine = ranking_engine

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        """Execute dense (embedding-similarity) retrieval for `query`, per `plan`.

        Fetches up to `plan.candidate_limit` ranked candidates -- the
        pre-fusion candidate pool `RetrievalPlan.candidate_limit` is
        defined to hold, matching `LexicalRetriever.retrieve`'s
        convention exactly. Final reranking and truncation down to
        `plan.top_k` is Context Fusion's responsibility, not this
        retriever's.

        Args:
            query: The raw developer query. Embedded once, via
                `self._embedder`, into the same space `context.embeddings`
                was built in.
            plan: The routing plan this call is executing.
            context: The repository's semantic context to search.
                `context.embeddings` empty (no embeddings computed for
                this repository) is handled cleanly: an empty
                `RetrievedContext` is returned, not an error.

        Returns:
            A `RetrievedContext` tagged `retriever_kind=RetrieverKind.DENSE`,
            with `chunks` sorted by descending cosine similarity.

        Raises:
            RetrievalError: If the query embedding's dimensionality does
                not match `context.embedding_dimension`. This is a
                systemic misconfiguration (this retriever's `embedder`
                is not the one `context` was built with) that the caller
                can and should fix, unlike a single malformed document
                embedding (handled by skipping just that document, see
                `_score_candidates`), which this retriever cannot fix on
                its own and must not let abort the whole query.
        """
        if not context.embeddings:
            return RetrievedContext(
                retriever_kind=RetrieverKind.DENSE, query=query, chunks=[], total_candidates=0
            )

        query_vector = self._embedder.embed(query)
        self._validate_query_dimension(query_vector, context)

        raw_scores = self._score_candidates(query_vector, context)
        if not raw_scores:
            return RetrievedContext(
                retriever_kind=RetrieverKind.DENSE, query=query, chunks=[], total_candidates=0
            )

        ranked = self._ranking_engine.rank(raw_scores, top_k=plan.candidate_limit)

        chunks: list[RetrievedChunk] = []
        for node_id, score in ranked:
            chunk = self._to_chunk(node_id, score, context)
            if chunk is not None:
                chunks.append(chunk)

        return RetrievedContext(
            retriever_kind=RetrieverKind.DENSE,
            query=query,
            chunks=chunks,
            total_candidates=len(chunks),
        )

    def _validate_query_dimension(
        self, query_vector: Sequence[float], context: RepositoryContext
    ) -> None:
        """Ensure the query embedding shares `context`'s declared embedding space.

        Raises:
            RetrievalError: As documented on `retrieve`.
        """
        expected = context.embedding_dimension
        if expected is not None and len(query_vector) != expected:
            raise RetrievalError(
                f"Query embedding has dimension {len(query_vector)}, but "
                f"RepositoryContext.embedding_dimension is {expected}. The Embedder "
                "injected into DenseRetriever must be the same one (or an equivalent "
                "model producing the same vector space) used to build the context's "
                "embeddings, or similarity scores are meaningless."
            )

    def _score_candidates(
        self, query_vector: Sequence[float], context: RepositoryContext
    ) -> dict[str, float]:
        """Cosine-similarity-score every embedded symbol against `query_vector`.

        A document embedding whose length disagrees with `query_vector`
        is skipped (not scored, and never raises) rather than aborting
        the whole query: this is isolated, per-document malformed data
        distinct from the systemic embedder mismatch `retrieve` already
        rejects up front via `_validate_query_dimension`, and one bad
        entry must not fail every other candidate's retrieval, mirroring
        the failure-isolation convention already used by
        `tara.retrieval.utils.read_file_bytes`.
        """
        query_dimension = len(query_vector)
        scores: dict[str, float] = {}
        skipped = 0
        for node_id, document_vector in context.embeddings.items():
            if len(document_vector) != query_dimension:
                skipped += 1
                continue
            scores[node_id] = _cosine_similarity(query_vector, document_vector)
        if skipped:
            logger.warning(
                "DenseRetriever skipped %d embedding(s) with a dimension mismatching the "
                "query (%d); this indicates corrupted or mixed-model RepositoryContext.embeddings.",
                skipped,
                query_dimension,
            )
        return scores

    def _to_chunk(
        self, node_id: str, score: RetrievalScore, context: RepositoryContext
    ) -> RetrievedChunk | None:
        """Enrich a scored node id with graph metadata and source text into a `RetrievedChunk`.

        Returns `None` (skipped defensively, never raised) if `node_id`
        is not in `context.symbol_index` or has no `file_path` --
        unreachable in practice since every id scored here came from
        `context.embeddings`, which `RepositoryContextExtractor` always
        keys by the same node ids present in the symbol index, but
        handled the same defensive way `LexicalRetriever._to_chunk`
        does, since a single stale id must not fail the whole query.
        """
        record = context.symbol_index.get_by_id(node_id)
        if record is None or record.file_path is None:
            return None

        attributes = record.attributes
        content = self._read_source(record.file_path, attributes, context) or record.name

        return RetrievedChunk(
            chunk_id=node_id,
            retriever_kind=RetrieverKind.DENSE,
            node_type=NodeType(record.node_type),
            name=record.name,
            file_path=record.file_path,
            start_line=attributes.get("start_line"),
            end_line=attributes.get("end_line"),
            content=content,
            docstring=attributes.get("docstring"),
            score=score,
            metadata={},
        )

    def _read_source(
        self, file_path: str, attributes: dict[str, object], context: RepositoryContext
    ) -> str | None:
        """Slice a symbol's source text from disk via its recorded byte span.

        Read lazily, only for candidates that survive ranking (unlike
        `LexicalRetriever`, which must read every indexed symbol's
        source eagerly to build its BM25 corpus): dense retrieval never
        needs source text to compute a similarity score, only to
        populate the final, already-truncated `RetrievedChunk` list.
        """
        start_byte = attributes.get("start_byte")
        end_byte = attributes.get("end_byte")
        if not isinstance(start_byte, int) or not isinstance(end_byte, int):
            return None
        raw_bytes = read_file_bytes(Path(context.root_path) / file_path)
        if raw_bytes is None:
            return None
        return decode_byte_span(raw_bytes, start_byte, end_byte)


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equal-length vectors, in `[-1.0, 1.0]`.

    Pure Python, no numpy/faiss dependency -- see this module's
    docstring for why. Deterministic: floating-point summation order
    always follows `a`/`b`'s own iteration order, so the same two
    vectors always produce the exact same result.

    Args:
        a: The first vector. Must be the same length as `b`; callers
            (`_score_candidates`) are responsible for filtering out
            length mismatches before calling this function -- enforced
            here too via `zip(..., strict=True)`, so a violated
            precondition raises immediately rather than silently
            truncating to the shorter vector and computing a
            plausible-looking but wrong similarity score.
        b: The second vector.

    Returns:
        The cosine of the angle between `a` and `b`. `0.0` if either
        vector has zero magnitude (a zero vector has no direction, so it
        cannot be "similar" to anything, including itself; treating this
        as `0.0` rather than raising or returning `1.0`/`nan` keeps
        `RankingEngine.rank`'s downstream min-max normalization well
        defined).
    """
    dot_product = 0.0
    norm_a_squared = 0.0
    norm_b_squared = 0.0
    for x, y in zip(a, b, strict=True):
        dot_product += x * y
        norm_a_squared += x * x
        norm_b_squared += y * y

    if norm_a_squared == 0.0 or norm_b_squared == 0.0:
        return 0.0

    return dot_product / (sqrt(norm_a_squared) * sqrt(norm_b_squared))
