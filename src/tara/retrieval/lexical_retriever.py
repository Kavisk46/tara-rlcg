"""Lexical Retriever: exact and keyword-ranked search over a `RepositoryContext`.

`LexicalRetriever` is the domain-specific layer that wires together
`BM25Index` (generic ranking math), `RankingEngine` (generic sorting /
normalization / top-k), and `tara.retrieval.utils` (tokenization and
byte-level source reading) into TARA's actual search surface:

- Exact symbol lookup (`find_symbol`, `find_function`, `find_class`,
  `find_method`), via `RepositoryContext.symbol_index` -- O(1)
  average-case, no ranking involved, since an exact name either matches
  or it doesn't.
- Exact file lookup (`find_file` by basename, `find_path` by full
  repository-relative path).
- Ranked keyword search (`keyword_search`), backed by three separate
  BM25 indices -- name, docstring, source -- combined with configurable
  per-field weights, so an exact-name match outranks a source-text
  mention of the same term.
- `retrieve`, the entry point satisfying `tara.interfaces.retriever.Retriever`:
  `(query, plan, context) -> RetrievedContext`.

Design rationale for three separate BM25 indices rather than one
combined index: keeping name/docstring/source scored independently is
what lets `keyword_search` both (a) apply different relevance weights
per field and (b) report which field actually drove a match
(`SearchResult.matched_field`) -- neither is recoverable from a single
pre-concatenated document per symbol.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from tara.classification.heuristics import is_stop_word
from tara.context.models import NodeType, RepositoryContext
from tara.core.config import TaraSettings
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.bm25_index import BM25Index
from tara.retrieval.models import MatchedField, RetrievalScore, RetrievedChunk, RetrievedContext, SearchResult
from tara.retrieval.ranking import RankingEngine
from tara.retrieval.utils import decode_byte_span, read_file_bytes, tokenize_for_search
from tara.routing.models import RetrievalPlan

_SYMBOL_NODE_TYPE_VALUES: frozenset[str] = frozenset(
    {NodeType.CLASS.value, NodeType.FUNCTION.value, NodeType.METHOD.value}
)
_INDEXABLE_NODE_TYPE_VALUES: frozenset[str] = _SYMBOL_NODE_TYPE_VALUES | {NodeType.FILE.value}

# Splits a compound identifier/path token into its sub-parts, e.g.
# "parse_repository" -> ["parse", "repository"], "utils.py" -> ["utils", "py"].
_IDENTIFIER_SPLIT_PATTERN = re.compile(r"[_./\\]+")

_EXACT_MATCH_SCORE = RetrievalScore(raw_score=1.0, normalized_score=1.0)
"""Shared score for exact lookups: an exact name/path match has no
relevance gradient to express -- it either matches or it doesn't -- so
every exact-match `SearchResult` reports the same maximal score.
`matched_terms` is set per call site, since that varies with what was
searched for; everything else about this score never does.
"""


def _expand_identifier_tokens(tokens: Sequence[str]) -> list[str]:
    """Expand each token into itself plus its snake_case/path sub-parts.

    Applied identically to both corpus tokens (at index-build time) and
    query tokens (at search time), so a query for a bare sub-identifier
    like `"parse"` can match a corpus token like `"parse_repository"`
    (which `tara.classification.heuristics.tokenize` deliberately keeps
    as one compound token) without losing the ability to rank an exact
    compound-token query (`"parse_repository"`) even higher: the
    original compound token is always kept alongside its parts, so a
    document containing `"parse_repository"` matches on three query
    terms for that exact query (`parse_repository`, `parse`,
    `repository`) versus one term for the partial query (`parse`
    alone), which is precisely the ranking behavior a partial match
    should have relative to an exact one.

    Args:
        tokens: Already-tokenized text, e.g. `tokenize_for_search`'s output.

    Returns:
        `tokens`, plus every non-empty, non-stop-word sub-part produced
        by splitting each token on `_`, `.`, `/`, or `\\`. Order is
        preserved; a token that doesn't split contributes only itself.
    """
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        for part in _IDENTIFIER_SPLIT_PATTERN.split(token):
            if part and part != token and not is_stop_word(part):
                expanded.append(part)
    return expanded


class LexicalRetriever(Retriever):
    """Exact and BM25-ranked keyword search over a `RepositoryContext`.

    Formally implements `tara.interfaces.retriever.Retriever`, mirroring
    `DenseRetriever`'s declared inheritance (Dependency Inversion at the
    pipeline level is a hard architectural constraint, per
    `PROJECT_SPEC.md` §14.1, not something left implicit even when the
    method signature already happens to match structurally).

    A single instance is safe to reuse across many queries and across
    many different `RepositoryContext` objects: the BM25 indices it
    builds are cached per context (keyed by a lightweight content
    signature -- root path, commit SHA, and symbol count -- not by
    Python object identity, which would be vulnerable to a garbage
    -collected object's address being reused) and rebuilt automatically
    if a call arrives for a context that signature doesn't recognize.

    All collaborators are injected: `ranking_engine` is required (no
    internal default construction of something a caller might
    reasonably want to substitute), and `settings` defaults to
    `TaraSettings()` only for the BM25/field-weight tunables, matching
    the pattern used by every other TARA component that reads
    configuration.
    """

    def __init__(self, ranking_engine: RankingEngine, settings: TaraSettings | None = None) -> None:
        """Construct the retriever. No indexing happens until the first search call.

        Args:
            ranking_engine: Turns raw per-field BM25 scores into a
                sorted, normalized, top-k ranking. Injected rather than
                constructed internally so a caller can substitute a
                different ranking policy without subclassing this class.
            settings: Source of BM25 hyperparameters (`bm25_k1`,
                `bm25_b`) and per-field weights
                (`lexical_name_weight`, `lexical_docstring_weight`,
                `lexical_source_weight`). Defaults to `TaraSettings()`
                (environment defaults) when omitted.
        """
        self._ranking_engine = ranking_engine
        self._settings = settings or TaraSettings()

        self._name_index: BM25Index | None = None
        self._docstring_index: BM25Index | None = None
        self._source_index: BM25Index | None = None
        self._source_text_by_id: dict[str, str] = {}
        self._indexed_signature: tuple[str, str | None, int] | None = None

    def retrieve(self, query: str, plan: RetrievalPlan, context: RepositoryContext) -> RetrievedContext:
        """Execute lexical retrieval for `query`, per `plan`, against `context`.

        Fetches up to `plan.candidate_limit` ranked candidates via
        `keyword_search` -- the pre-fusion candidate pool
        `RetrievalPlan.candidate_limit` is defined to hold. Final
        reranking and truncation down to `plan.top_k` is Context
        Fusion's responsibility (a later pipeline stage), not this
        retriever's.

        Args:
            query: The raw developer query.
            plan: The routing plan this call is executing.
            context: The repository's semantic context to search.

        Returns:
            A `RetrievedContext` tagged `retriever_kind=RetrieverKind.LEXICAL`,
            with `chunks` sorted by descending relevance.
        """
        results = self.keyword_search(query, context, top_k=plan.candidate_limit)
        chunks = [self._to_chunk(result, context) for result in results]
        return RetrievedContext(
            retriever_kind=RetrieverKind.LEXICAL,
            query=query,
            chunks=chunks,
            total_candidates=len(results),
        )

    def keyword_search(self, query: str, context: RepositoryContext, top_k: int) -> list[SearchResult]:
        """Rank every indexed symbol/file against `query`, combining name/docstring/source matches.

        Args:
            query: The raw query text; tokenized internally (see
                `tara.retrieval.utils.tokenize_for_search` and
                `_expand_identifier_tokens`).
            context: The repository's semantic context to search. Its
                BM25 indices are built on first use and cached.
            top_k: Maximum number of results to return. Must be > 0.

        Returns:
            `SearchResult`s sorted by descending combined relevance,
            each tagged with whichever field (name, docstring, or
            source) contributed the largest weighted share of its
            score. Empty if `query` tokenizes to nothing, or if nothing
            in `context` matches.

        Raises:
            RetrievalError: If `top_k` is not a positive integer
                (propagated from `RankingEngine.rank`).
        """
        self._ensure_indexed(context)
        query_tokens = _expand_identifier_tokens(tokenize_for_search(query))
        if not query_tokens:
            return []

        assert self._name_index is not None
        assert self._docstring_index is not None
        assert self._source_index is not None

        name_scores = self._name_index.score(query_tokens)
        docstring_scores = self._docstring_index.score(query_tokens)
        source_scores = self._source_index.score(query_tokens)

        combined = self._combine_field_scores(name_scores, docstring_scores, source_scores)
        if not combined:
            return []

        ranked = self._ranking_engine.rank(combined, top_k=top_k)

        results: list[SearchResult] = []
        for document_id, score in ranked:
            record = context.symbol_index.get_by_id(document_id)
            if record is None or record.file_path is None:
                # Every id scored here came from an index built from
                # context.symbol_index itself, so this should be
                # unreachable; skipped defensively rather than raised,
                # since a single stale id must not fail the whole query.
                continue
            results.append(
                SearchResult(
                    node_id=document_id,
                    node_type=NodeType(record.node_type),
                    name=record.name,
                    file_path=record.file_path,
                    score=score,
                    matched_field=self._determine_matched_field(document_id, name_scores, docstring_scores, source_scores),
                )
            )
        return results

    def find_symbol(self, name: str, context: RepositoryContext) -> list[SearchResult]:
        """Find every class, function, or method whose name exactly equals `name`.

        Args:
            name: The exact symbol name to look up.
            context: The repository's semantic context to search.

        Returns:
            One `SearchResult` per exact match (there can be more than
            one, e.g. the same function name defined in different
            files), each with the maximal exact-match score. Empty if
            no symbol has this exact name.
        """
        return self._find_exact_by_name(name, context, _SYMBOL_NODE_TYPE_VALUES)

    def find_function(self, name: str, context: RepositoryContext) -> list[SearchResult]:
        """Find every top-level function whose name exactly equals `name`.

        Args:
            name: The exact function name to look up.
            context: The repository's semantic context to search.

        Returns:
            `SearchResult`s for exact `NodeType.FUNCTION` matches only.
        """
        return self._find_exact_by_name(name, context, {NodeType.FUNCTION.value})

    def find_class(self, name: str, context: RepositoryContext) -> list[SearchResult]:
        """Find every class whose name exactly equals `name`.

        Args:
            name: The exact class name to look up.
            context: The repository's semantic context to search.

        Returns:
            `SearchResult`s for exact `NodeType.CLASS` matches only.
        """
        return self._find_exact_by_name(name, context, {NodeType.CLASS.value})

    def find_method(self, name: str, context: RepositoryContext) -> list[SearchResult]:
        """Find every method whose name exactly equals `name`.

        Args:
            name: The exact method name to look up.
            context: The repository's semantic context to search.

        Returns:
            `SearchResult`s for exact `NodeType.METHOD` matches only.
        """
        return self._find_exact_by_name(name, context, {NodeType.METHOD.value})

    def find_file(self, file_name: str, context: RepositoryContext) -> list[SearchResult]:
        """Find every file whose basename exactly equals `file_name`.

        Unlike `find_path`, this matches on the filename component only
        (e.g. `"repository_parser.py"`), not the full repository-relative
        path, so it can find a file without the caller knowing which
        directory it lives in.

        Args:
            file_name: The exact basename to look up, e.g. `"utils.py"`.
            context: The repository's semantic context to search.

        Returns:
            One `SearchResult` per file whose basename matches exactly.
            Empty if none match. Can return more than one result if two
            files in different directories share a basename.
        """
        results: list[SearchResult] = []
        for record in context.symbol_index:
            if record.node_type != NodeType.FILE.value or record.file_path is None:
                continue
            if PurePosixPath(record.file_path).name == file_name:
                results.append(self._exact_file_result(record.node_id, record.name, record.file_path, file_name))
        return results

    def find_path(self, file_path: str, context: RepositoryContext) -> list[SearchResult]:
        """Find the file whose full repository-relative path exactly equals `file_path`.

        Args:
            file_path: The exact repository-relative path to look up,
                e.g. `"src/tara/parsing/repository_parser.py"`.
            context: The repository's semantic context to search.

        Returns:
            A single-element list with the matching `SearchResult` if
            `file_path` is indexed, otherwise an empty list.
        """
        results: list[SearchResult] = []
        for record in context.symbol_index.get_by_name(file_path):
            if record.node_type != NodeType.FILE.value or record.file_path is None:
                continue
            results.append(self._exact_file_result(record.node_id, record.name, record.file_path, file_path))
        return results

    def _find_exact_by_name(
        self, name: str, context: RepositoryContext, node_types: frozenset[str] | set[str]
    ) -> list[SearchResult]:
        """Shared implementation behind `find_symbol`/`find_function`/`find_class`/`find_method`."""
        results: list[SearchResult] = []
        for record in context.symbol_index.get_by_name(name):
            if record.node_type not in node_types or record.file_path is None:
                continue
            results.append(
                SearchResult(
                    node_id=record.node_id,
                    node_type=NodeType(record.node_type),
                    name=record.name,
                    file_path=record.file_path,
                    score=RetrievalScore(raw_score=1.0, normalized_score=1.0, matched_terms=(name,)),
                    matched_field=MatchedField.NAME,
                )
            )
        return results

    @staticmethod
    def _exact_file_result(node_id: str, name: str, file_path: str, matched_term: str) -> SearchResult:
        """Shared `SearchResult` construction behind `find_file`/`find_path`."""
        return SearchResult(
            node_id=node_id,
            node_type=NodeType.FILE,
            name=name,
            file_path=file_path,
            score=RetrievalScore(raw_score=1.0, normalized_score=1.0, matched_terms=(matched_term,)),
            matched_field=MatchedField.PATH,
        )

    def _combine_field_scores(
        self,
        name_scores: dict[str, float],
        docstring_scores: dict[str, float],
        source_scores: dict[str, float],
    ) -> dict[str, float]:
        """Weighted-sum name/docstring/source BM25 scores into one score per document.

        Complexity: O(D) where D is the number of distinct documents
        appearing in any of the three inputs -- each document is
        visited at most three times, once per field.
        """
        combined: dict[str, float] = {}
        for document_id, raw_score in name_scores.items():
            combined[document_id] = combined.get(document_id, 0.0) + self._settings.lexical_name_weight * raw_score
        for document_id, raw_score in docstring_scores.items():
            combined[document_id] = (
                combined.get(document_id, 0.0) + self._settings.lexical_docstring_weight * raw_score
            )
        for document_id, raw_score in source_scores.items():
            combined[document_id] = combined.get(document_id, 0.0) + self._settings.lexical_source_weight * raw_score
        return combined

    def _determine_matched_field(
        self,
        document_id: str,
        name_scores: dict[str, float],
        docstring_scores: dict[str, float],
        source_scores: dict[str, float],
    ) -> MatchedField:
        """Report whichever field contributed the largest weighted share of `document_id`'s score."""
        weighted_contributions = {
            MatchedField.NAME: name_scores.get(document_id, 0.0) * self._settings.lexical_name_weight,
            MatchedField.DOCSTRING: docstring_scores.get(document_id, 0.0) * self._settings.lexical_docstring_weight,
            MatchedField.SOURCE: source_scores.get(document_id, 0.0) * self._settings.lexical_source_weight,
        }
        return max(weighted_contributions, key=weighted_contributions.get)  # type: ignore[arg-type]

    def _to_chunk(self, result: SearchResult, context: RepositoryContext) -> RetrievedChunk:
        """Enrich a `SearchResult` with cached source text and graph metadata into a `RetrievedChunk`."""
        record = context.symbol_index.get_by_id(result.node_id)
        attributes = record.attributes if record is not None else {}
        content = self._source_text_by_id.get(result.node_id) or result.name
        return RetrievedChunk(
            chunk_id=result.node_id,
            retriever_kind=RetrieverKind.LEXICAL,
            node_type=result.node_type,
            name=result.name,
            file_path=result.file_path,
            start_line=attributes.get("start_line"),
            end_line=attributes.get("end_line"),
            content=content,
            docstring=attributes.get("docstring"),
            score=result.score,
            metadata={"matched_field": result.matched_field.value},
        )

    def _ensure_indexed(self, context: RepositoryContext) -> None:
        """Build (or reuse the cached) BM25 indices for `context`.

        Complexity: O(1) on a cache hit. On a cache miss, O(T) where T
        is the total token count across every indexed symbol's name,
        docstring, and source text, plus one file read per distinct
        file referenced by an indexed symbol (each file is read at most
        once regardless of how many symbols it defines).
        """
        signature = (context.root_path, context.commit_sha, context.symbol_count)
        if signature == self._indexed_signature:
            return

        name_documents, docstring_documents, source_documents, source_text_by_id = self._build_corpus(context)

        name_index = BM25Index(settings=self._settings)
        name_index.build(name_documents)
        docstring_index = BM25Index(settings=self._settings)
        docstring_index.build(docstring_documents)
        source_index = BM25Index(settings=self._settings)
        source_index.build(source_documents)

        self._name_index = name_index
        self._docstring_index = docstring_index
        self._source_index = source_index
        self._source_text_by_id = source_text_by_id
        self._indexed_signature = signature

    def _build_corpus(
        self, context: RepositoryContext
    ) -> tuple[
        list[tuple[str, list[str]]],
        list[tuple[str, list[str]]],
        list[tuple[str, list[str]]],
        dict[str, str],
    ]:
        """Extract per-field, per-document token lists from every indexable node in `context`.

        Reads each distinct source file at most once, caching its raw
        bytes for the duration of this call, regardless of how many
        symbols within it are indexed.
        """
        name_documents: list[tuple[str, list[str]]] = []
        docstring_documents: list[tuple[str, list[str]]] = []
        source_documents: list[tuple[str, list[str]]] = []
        source_text_by_id: dict[str, str] = {}
        file_bytes_cache: dict[str, bytes | None] = {}

        for record in context.symbol_index:
            if record.node_type not in _INDEXABLE_NODE_TYPE_VALUES or record.file_path is None:
                continue

            name_documents.append((record.node_id, _expand_identifier_tokens(tokenize_for_search(record.name))))

            docstring = record.attributes.get("docstring")
            if docstring:
                docstring_documents.append(
                    (record.node_id, _expand_identifier_tokens(tokenize_for_search(docstring)))
                )

            if record.node_type not in _SYMBOL_NODE_TYPE_VALUES:
                continue  # file nodes have no source span of their own to index

            start_byte = record.attributes.get("start_byte")
            end_byte = record.attributes.get("end_byte")
            if start_byte is None or end_byte is None:
                continue

            if record.file_path not in file_bytes_cache:
                file_bytes_cache[record.file_path] = read_file_bytes(Path(context.root_path) / record.file_path)
            raw_bytes = file_bytes_cache[record.file_path]
            if raw_bytes is None:
                continue

            source_text = decode_byte_span(raw_bytes, start_byte, end_byte)
            source_text_by_id[record.node_id] = source_text
            source_documents.append((record.node_id, _expand_identifier_tokens(tokenize_for_search(source_text))))

        return name_documents, docstring_documents, source_documents, source_text_by_id
