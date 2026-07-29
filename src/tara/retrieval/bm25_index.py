"""Okapi BM25 index: a generic, in-process, dependency-free ranking engine.

Implements Okapi BM25 (Robertson & Sparck Jones, 1994; as popularized by
Robertson & Walker, 1994) as a standalone, corpus-agnostic inverted
index over documents identified by an arbitrary string id. This module
knows nothing about symbols, files, or `RepositoryContext` -- it scores
`(document_id, tokens)` pairs against a token query and nothing else --
so it is independently testable and, in principle, reusable outside
TARA. Domain-specific wiring (extracting tokens from repository symbols
and files, mapping a `document_id` back to a `SearchResult`) belongs in
`lexical_retriever.py`, not here.

No external ranking library is used. BM25 is a well-specified,
moderate-complexity algorithm; implementing it directly keeps the
scoring logic fully inspectable and reproducible -- a requirement for
this project's research artifact -- without taking on an unvetted
third-party dependency whose exact scoring behavior would otherwise
need to be independently verified anyway.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from math import isfinite, log

from tara.core.config import TaraSettings
from tara.core.exceptions import ConfigurationError, RetrievalError


class BM25Index:
    """A generic Okapi BM25 inverted index over string-identified documents.

    Usage is build-once, query-many: construct an index, call `build`
    once with the full corpus, then call `score` for each query. Calling
    `build` again discards and replaces the previous index in place.

    Query terms are scored as given, including repeats: a query
    containing the same token twice contributes that token's BM25 term
    score twice, matching the convention used by the standard reference
    implementations (e.g. Lucene, `rank_bm25`) rather than silently
    deduplicating the query -- this is what lets a repeated keyword in
    a multi-keyword query count as a stronger relevance signal.

    Complexity:
        `build` is O(T) where T is the total number of tokens across
        every document in the corpus -- each token is visited exactly
        once to update its document's term-frequency counter and the
        global inverted index.

        `score` is O(sum over query terms of |documents containing that
        term|), not O(N) in corpus size: only documents sharing at
        least one token with the query are ever visited, via the
        inverted index (term -> set of document ids) built by `build`.
        This keeps `score` cheap even for corpora with 100,000+
        documents, provided query terms are not near-universally common
        across the corpus; a term that *is* near-universal still costs
        O(N) for that term specifically, which is an inherent property
        of BM25's exhaustive-posting-list scoring, not something this
        implementation optimizes away (a document-frequency-based
        posting-list cutoff would be a reasonable future addition if
        profiling ever shows it is needed).

    Example:
        >>> index = BM25Index(k1=1.5, b=0.75)
        >>> index.build([
        ...     ("doc-1", ["parse", "repository", "tree", "sitter"]),
        ...     ("doc-2", ["build", "graph", "from", "repository"]),
        ... ])
        >>> scores = index.score(["repository"])
        >>> sorted(scores)
        ['doc-1', 'doc-2']
    """

    def __init__(
        self,
        k1: float | None = None,
        b: float | None = None,
        settings: TaraSettings | None = None,
    ) -> None:
        """Construct an empty index; populate it via `build`.

        Args:
            k1: BM25 term-frequency saturation parameter. Must be a
                finite number > 0. Defaults to `settings.bm25_k1` when
                omitted.
            b: BM25 document-length normalization parameter. Must be a
                finite number in `[0, 1]`. Defaults to `settings.bm25_b`
                when omitted.
            settings: Configuration source for the defaults above.
                Defaults to `TaraSettings()` (environment defaults) when
                omitted, matching the pattern used elsewhere in TARA
                (e.g. `TreeSitterRepositoryParser`, `SentenceTransformerEmbedder`).

        Raises:
            ConfigurationError: If the resolved `k1` is not finite and
                positive, or the resolved `b` is not finite or is
                outside `[0, 1]`.
        """
        resolved_settings = settings or TaraSettings()
        self._k1 = k1 if k1 is not None else resolved_settings.bm25_k1
        self._b = b if b is not None else resolved_settings.bm25_b
        self._validate_parameters()

        self._document_lengths: dict[str, int] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._inverted_index: dict[str, set[str]] = {}
        self._average_document_length: float = 0.0

    def _validate_parameters(self) -> None:
        """Validate `k1`/`b` against BM25's documented, well-behaved ranges.

        Raises:
            ConfigurationError: As documented on `__init__`.
        """
        if not isfinite(self._k1) or self._k1 <= 0.0:
            raise ConfigurationError(f"BM25 k1 must be a finite number > 0, got {self._k1!r}.")
        if not isfinite(self._b) or not (0.0 <= self._b <= 1.0):
            raise ConfigurationError(f"BM25 b must be a finite number in [0, 1], got {self._b!r}.")

    @property
    def k1(self) -> float:
        """The term-frequency saturation parameter this index was constructed with."""
        return self._k1

    @property
    def b(self) -> float:
        """The document-length normalization parameter this index was constructed with."""
        return self._b

    def build(self, documents: Iterable[tuple[str, Sequence[str]]]) -> None:
        """Build the index from `(document_id, tokens)` pairs, replacing any existing index.

        Args:
            documents: An iterable of `(document_id, tokens)` pairs, safe
                to pass as a generator (this method makes a single pass
                over it). `document_id` must be unique and non-empty
                across the iterable; `tokens` is the document's
                already-tokenized text -- this index has no opinion on
                what counts as a token, tokenization is the caller's
                responsibility. An empty `tokens` sequence is valid: the
                document is indexed but can never match any query, since
                it contributes no entries to the inverted index.

        Raises:
            RetrievalError: If a `document_id` is empty, or if the same
                `document_id` appears more than once in `documents`.
        """
        document_lengths: dict[str, int] = {}
        term_frequencies: dict[str, Counter[str]] = {}
        inverted_index: dict[str, set[str]] = {}
        total_document_length = 0

        for document_id, tokens in documents:
            if not document_id:
                raise RetrievalError("BM25Index.build received a document with an empty document_id.")
            if document_id in document_lengths:
                raise RetrievalError(f"BM25Index.build received a duplicate document_id: {document_id!r}.")

            counts = Counter(tokens)
            document_lengths[document_id] = len(tokens)
            term_frequencies[document_id] = counts
            total_document_length += len(tokens)

            for term in counts:
                inverted_index.setdefault(term, set()).add(document_id)

        self._document_lengths = document_lengths
        self._term_frequencies = term_frequencies
        self._inverted_index = inverted_index
        self._average_document_length = (
            total_document_length / len(document_lengths) if document_lengths else 0.0
        )

    def score(self, query_tokens: Sequence[str]) -> dict[str, float]:
        """Score every indexed document that shares at least one token with the query.

        Documents sharing no token with `query_tokens` are omitted from
        the result entirely (never returned with a score of 0.0), which
        is both the standard sparse-BM25 convention and what keeps this
        method's cost proportional to the query's selectivity rather
        than to the corpus size.

        Args:
            query_tokens: The already-tokenized query. May contain
                repeated tokens; see the class docstring for how repeats
                are handled.

        Returns:
            A mapping from `document_id` to its raw (unnormalized) BM25
            score, for every document with a nonzero score. Empty if
            `query_tokens` is empty or the index has no documents.
        """
        if not query_tokens or not self._document_lengths:
            return {}

        scores: dict[str, float] = {}
        idf_cache: dict[str, float] = {}

        for term in query_tokens:
            matching_documents = self._inverted_index.get(term)
            if not matching_documents:
                continue

            idf = idf_cache.get(term)
            if idf is None:
                idf = self._idf(len(matching_documents))
                idf_cache[term] = idf

            for document_id in matching_documents:
                term_frequency = self._term_frequencies[document_id][term]
                document_length = self._document_lengths[document_id]
                scores[document_id] = scores.get(document_id, 0.0) + self._term_score(
                    term_frequency, document_length, idf
                )

        return scores

    def _idf(self, document_frequency: int) -> float:
        """Inverse document frequency, using the smoothed (BM25+-style) formulation.

        The `+ 1` inside the logarithm keeps IDF strictly positive even
        for a term appearing in every indexed document, so a very
        common term can never drag a document's total score negative --
        which would otherwise complicate downstream min-max score
        normalization in `tara.retrieval.ranking`.

        `document_frequency` is always >= 1 here: this is only called
        for terms present in `self._inverted_index`, which by
        construction never maps a term to an empty document set.
        """
        total_documents = len(self._document_lengths)
        return log((total_documents - document_frequency + 0.5) / (document_frequency + 0.5) + 1.0)

    def _term_score(self, term_frequency: int, document_length: int, idf: float) -> float:
        """A single query term's BM25 contribution to one document's score.

        `self._average_document_length` is guaranteed > 0 whenever this
        method runs: it is only called for a `document_id` present in
        `self._inverted_index`, which means that document has at least
        one token, which means `self._average_document_length` (an
        average over a corpus containing at least that one non-empty
        document) cannot be zero.
        """
        length_normalization = 1.0 - self._b + self._b * (document_length / self._average_document_length)
        return idf * (term_frequency * (self._k1 + 1.0)) / (term_frequency + self._k1 * length_normalization)

    def document_length(self, document_id: str) -> int:
        """Return the token count `document_id` was indexed with.

        Raises:
            RetrievalError: If `document_id` is not indexed.
        """
        if document_id not in self._document_lengths:
            raise RetrievalError(f"BM25Index has no document with id {document_id!r}.")
        return self._document_lengths[document_id]

    def __len__(self) -> int:
        """Number of documents currently indexed."""
        return len(self._document_lengths)

    def __contains__(self, document_id: object) -> bool:
        return document_id in self._document_lengths
