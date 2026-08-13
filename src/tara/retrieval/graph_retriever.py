"""Graph Retriever: multi-source BFS traversal over `RepositoryContext.graph`.

`GraphRetriever` seeds traversal from graph nodes matching a query's
detected symbols/file paths, then explores outward up to
`RetrievalPlan.graph_depth` hops, scoring every visited node by its
(minimum) hop distance from the nearest seed and reusing `RankingEngine`
-- the same ranking component `LexicalRetriever`/`DenseRetriever` already
use -- to normalize and truncate to `plan.candidate_limit`.

Two design decisions were required that the current codebase does not
already settle, and are documented here rather than silently assumed:

1. **Seed resolution reuses `FeatureExtractor`, not `TaskClassification`.**
   `Retriever.retrieve(query, plan, context)` never receives a
   `TaskClassification`, and `RetrievalPlan.metadata` (see
   `tara.routing.planner.RetrievalPlanner.plan`) never carries
   `detected_symbols`/`detected_file_paths` through. Rather than modify
   `RetrievalPlan` (routing is out of scope for this milestone) or the
   `Retriever` ABC's signature (which would ripple into the already-shipped
   `LexicalRetriever`/`DenseRetriever`), this retriever re-extracts the
   same signal directly from the raw query via
   `tara.classification.features.FeatureExtractor` -- verified to be
   exactly the function `HeuristicTaskClassifier` itself calls to produce
   `TaskClassification.detected_symbols`/`.detected_file_paths` with no
   further transformation, so this is a provably identical recomputation,
   not an approximation.
2. **`expand_neighbors` controls edge directionality, not just a toggle
   for "more hops."** `RetrievalPlanner` currently always sets
   `expand_neighbors` in lockstep with `graph_depth > 0`, so there is no
   existing behavioral contract distinguishing them. Here, `graph_depth`
   bounds the maximum BFS hop count; `expand_neighbors=True` traverses
   every edge incident to a node (both predecessors and successors, via
   `networkx.all_neighbors`), while `expand_neighbors=False` traverses
   only outgoing/successor edges (containment children, defined symbols,
   import targets) -- a directed, "downward" traversal only.

This retriever does **not** fall back to dense/lexical results when no
seed resolves. Nothing in the `Retriever` interface gives one retriever
access to another's output -- combining multi-retriever results is
Context Fusion's job, not yet implemented. An empty seed set produces a
clean, empty `RetrievedContext`, the same "handle it safely, don't
invent a cross-stage dependency" behavior `LexicalRetriever`/
`DenseRetriever` already use for their own no-match cases.

Known limitation of the current graph representation (see
`tara.context.graph_builder.GraphBuilder`): only `CONTAINS`, `DEFINES`,
and `IMPORTS` edges are populated. `CALLS`, `INHERITS`, `IMPLEMENTS`, and
`DEPENDS_ON` are reserved on `EdgeRelation` but not yet written by any
stage. This means true call-flow tracing (`PROJECT_SPEC.md` §2's own
motivating "trace the login flow" example) is not actually possible on
today's graph -- this retriever can only traverse structural
containment/definition/import relationships, not call graphs.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path, PurePosixPath

import networkx as nx

from tara.classification.features import FeatureExtractor
from tara.context.models import NodeType, RepositoryContext
from tara.context.symbol_index import SymbolRecord
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.models import RetrievalScore, RetrievedChunk, RetrievedContext
from tara.retrieval.ranking import RankingEngine
from tara.retrieval.utils import decode_byte_span, read_file_bytes
from tara.routing.models import RetrievalPlan

_SYMBOL_NODE_TYPE_VALUES: frozenset[str] = frozenset(
    {NodeType.CLASS.value, NodeType.FUNCTION.value, NodeType.METHOD.value}
)


class GraphRetriever(Retriever):
    """BFS traversal over `RepositoryContext.graph`, seeded from the query's detected symbols/paths.

    All collaborators are injected: `ranking_engine` is required
    (matching `LexicalRetriever`'s convention exactly -- no internal
    default construction of something a caller might reasonably want to
    substitute), and `feature_extractor` defaults to a plain
    `FeatureExtractor()`, matching the same default-construction pattern
    `HeuristicTaskClassifier` itself uses.

    Stateless between calls: no index is built or cached, since BFS over
    an already-constructed `networkx.DiGraph` needs no preprocessing step
    analogous to `LexicalRetriever`'s BM25 corpus build.
    """

    def __init__(
        self, ranking_engine: RankingEngine, feature_extractor: FeatureExtractor | None = None
    ) -> None:
        """Construct the retriever.

        Args:
            ranking_engine: Turns raw hop-distance-derived scores into a
                sorted, normalized, top-k ranking. The same component
                type `LexicalRetriever`/`DenseRetriever` use.
            feature_extractor: Re-derives detected symbols/file paths
                from the raw query text. Injected rather than
                constructed internally so tests can substitute a fake,
                and defaults to `FeatureExtractor()` when omitted.
        """
        self._ranking_engine = ranking_engine
        self._feature_extractor = feature_extractor or FeatureExtractor()

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        """Execute graph traversal for `query`, per `plan`.

        Fetches up to `plan.candidate_limit` ranked candidates -- the
        pre-fusion candidate pool `RetrievalPlan.candidate_limit` is
        defined to hold, matching `LexicalRetriever`/`DenseRetriever`'s
        convention exactly. Final reranking and truncation down to
        `plan.top_k` is Context Fusion's responsibility, not this
        retriever's.

        Args:
            query: The raw developer query. Detected symbols/file paths
                are re-derived from this text (see module docstring);
                no `TaskClassification` is consumed.
            plan: The routing plan this call is executing; `graph_depth`
                bounds traversal hops and `expand_neighbors` controls
                edge directionality (see module docstring).
            context: The repository's semantic context to traverse.
                A trivial or missing graph (0 or 1 node -- just the
                repository root, if any) is handled cleanly: an empty
                `RetrievedContext` is returned, not an error.

        Returns:
            A `RetrievedContext` tagged `retriever_kind=RetrieverKind.GRAPH`,
            with `chunks` sorted by descending proximity (ascending hop
            distance) to the nearest seed.
        """
        if context.graph.number_of_nodes() <= 1:
            return RetrievedContext(
                retriever_kind=RetrieverKind.GRAPH, query=query, chunks=[], total_candidates=0
            )

        seed_ids = self._resolve_seeds(query, context)
        if not seed_ids:
            return RetrievedContext(
                retriever_kind=RetrieverKind.GRAPH, query=query, chunks=[], total_candidates=0
            )

        distances = self._traverse(seed_ids, context.graph, plan.graph_depth, plan.expand_neighbors)
        raw_scores = {node_id: 1.0 / (1 + distance) for node_id, distance in distances.items()}

        ranked = self._ranking_engine.rank(raw_scores, top_k=plan.candidate_limit)

        chunks: list[RetrievedChunk] = []
        for node_id, score in ranked:
            chunk = self._to_chunk(node_id, score, context)
            if chunk is not None:
                chunks.append(chunk)

        return RetrievedContext(
            retriever_kind=RetrieverKind.GRAPH,
            query=query,
            chunks=chunks,
            total_candidates=len(chunks),
        )

    def _resolve_seeds(self, query: str, context: RepositoryContext) -> list[str]:
        """Resolve the query's detected symbols/file paths to graph node ids.

        Returns a sorted (deterministic), deduplicated list. A detected
        symbol/path that matches nothing in `context.symbol_index` is
        silently dropped -- handling a missing seed safely is this
        method's whole job, not a failure.
        """
        features = self._feature_extractor.extract(query)
        seed_ids: dict[str, None] = {}

        for symbol_name in features.detected_symbols:
            for record in context.symbol_index.get_by_name(symbol_name):
                if record.node_type in _SYMBOL_NODE_TYPE_VALUES:
                    seed_ids.setdefault(record.node_id, None)

        for candidate_path in features.detected_file_paths:
            for record in self._resolve_file_seed(candidate_path, context):
                seed_ids.setdefault(record.node_id, None)

        return sorted(seed_ids)

    @staticmethod
    def _resolve_file_seed(candidate: str, context: RepositoryContext) -> list[SymbolRecord]:
        """Resolve one detected file-path token to file node(s), full-path match first.

        Mirrors `LexicalRetriever.find_path`/`.find_file`'s two-tier
        convention: an exact full-path match is tried first (file nodes
        are indexed by name = their full repository-relative path, per
        `GraphBuilder._add_file_node`); a bare filename with no exact
        match falls back to basename matching across every indexed file.
        """
        exact = [
            record
            for record in context.symbol_index.get_by_name(candidate)
            if record.node_type == NodeType.FILE.value
        ]
        if exact:
            return exact

        basename = PurePosixPath(candidate).name
        return [
            record
            for record in context.symbol_index
            if record.node_type == NodeType.FILE.value
            and record.file_path is not None
            and PurePosixPath(record.file_path).name == basename
        ]

    @staticmethod
    def _traverse(
        seed_ids: list[str], graph: nx.DiGraph, max_depth: int, expand_neighbors: bool
    ) -> dict[str, int]:
        """Multi-source BFS from `seed_ids`, returning `node_id -> minimum hop distance`.

        Standard unweighted multi-source BFS: every edge has weight 1,
        so a node's first discovery (in FIFO queue order) is always its
        true shortest distance from the nearest seed -- no relaxation
        step is needed. Seeds themselves are included at distance 0, so
        a direct symbol/path match is always present in the result even
        when `max_depth` is 0 (no traversal beyond the seeds).

        Deterministic: seed ids and each node's neighbor ids are sorted
        before being enqueued, so traversal order -- and therefore the
        resulting distance map -- is identical across repeated calls
        against the same graph, independent of Python's dict/set
        iteration order.
        """
        distances: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque()

        for seed_id in seed_ids:
            if seed_id in graph and seed_id not in distances:
                distances[seed_id] = 0
                queue.append((seed_id, 0))

        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            neighbor_ids = GraphRetriever._neighbors(graph, node_id, expand_neighbors)
            for neighbor_id in sorted(neighbor_ids):
                if neighbor_id not in distances:
                    distances[neighbor_id] = depth + 1
                    queue.append((neighbor_id, depth + 1))

        return distances

    @staticmethod
    def _neighbors(graph: nx.DiGraph, node_id: str, expand_neighbors: bool) -> set[str]:
        """A node's traversal neighbors, per `expand_neighbors` (see module docstring)."""
        if expand_neighbors:
            return set(nx.all_neighbors(graph, node_id))
        return set(graph.successors(node_id))

    def _to_chunk(
        self, node_id: str, score: RetrievalScore, context: RepositoryContext
    ) -> RetrievedChunk | None:
        """Enrich a scored node id with graph metadata and source text into a `RetrievedChunk`.

        Returns `None` (skipped defensively, never raised) if `node_id`
        is not in `context.symbol_index`, or has no `file_path` -- the
        latter is how the repository-root node (the only node type with
        `file_path=None`) is excluded, since `RetrievedChunk.file_path`
        is a required field the shared model has no optional variant
        for; see the module docstring's limitation note.
        """
        record = context.symbol_index.get_by_id(node_id)
        if record is None or record.file_path is None:
            return None

        attributes = record.attributes
        if record.node_type == NodeType.FILE.value:
            content = record.name
        else:
            content = self._read_source(record.file_path, attributes, context) or record.name

        return RetrievedChunk(
            chunk_id=node_id,
            retriever_kind=RetrieverKind.GRAPH,
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

        Read lazily, only for candidates that survive ranking, matching
        `DenseRetriever._read_source`'s identical rationale: traversal
        and ranking never need source text, only the final, already-
        truncated `RetrievedChunk` list does.
        """
        start_byte = attributes.get("start_byte")
        end_byte = attributes.get("end_byte")
        if not isinstance(start_byte, int) or not isinstance(end_byte, int):
            return None
        raw_bytes = read_file_bytes(Path(context.root_path) / file_path)
        if raw_bytes is None:
            return None
        return decode_byte_span(raw_bytes, start_byte, end_byte)
