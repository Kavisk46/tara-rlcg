"""The frozen latency-measurement protocol (Reviewer #2, Minor Revision, Revision 2).

This module is the single source of truth for what
`StrategyResult.retrieval_latency_ms` measures. `config.yaml` and
`README.md` both describe this same protocol in prose for a human
reader; `test_latency_protocol.py` asserts `config.yaml`'s
include/exclude lists textually match the constants below, so the two
descriptions cannot silently drift apart.

Protocol (frozen -- do not change without a corresponding review):

    Starts:  immediately before `retrieve()` is invoked.
    Ends:    immediately after ranked results are returned.

    Included operations (counted toward `retrieval_latency_ms`):
        - Embedding generation (query and/or document embedding)
        - Vector search
        - Graph traversal
        - Score computation (BM25 scoring, identifier/keyword matching,
          normalization, weighted combination, ranking)

    Excluded operations (never counted, even though they may execute
    inside the `retrieve()` call in the current, uncached architecture
    -- see README.md's "Design Rationale: Revision 2" for why this is
    a measurement-boundary decision, not an architecture change):
        - Repository loading (Repository Loader's own concern; never
          happens inside this subsystem at all)
        - Index construction (BM25Index.build, VectorIndex.build, the
          graph-retrieval file-adjacency map -- repository-dependent,
          query-independent setup work)
        - Model download / model loading (SentenceTransformerEmbedder's
          lazy first-use load; never applicable to the default
          HashingEmbedder, which loads nothing)

Rationale: the protocol reports *per-query* retrieval cost against an
already-available repository representation, since that is the
number a dataset-construction consumer actually needs (many queries
will be run against the same repository) -- not the one-time cost of
building that representation, which this milestone's architecture does
not currently cache across calls (a separate, already-documented
limitation; see REVIEW_RESPONSE.md).
"""
from __future__ import annotations

LATENCY_INCLUDED_OPERATIONS: tuple[str, ...] = (
    "embedding_generation",
    "vector_search",
    "graph_traversal",
    "score_computation",
)
"""Operations counted toward `StrategyResult.retrieval_latency_ms`."""

LATENCY_EXCLUDED_OPERATIONS: tuple[str, ...] = (
    "repository_loading",
    "index_construction",
    "model_download",
)
"""Operations never counted, even if they execute inside `retrieve()`."""

LATENCY_STARTS: str = "immediately before retrieve() is invoked"
LATENCY_ENDS: str = "immediately after ranked results are returned"
