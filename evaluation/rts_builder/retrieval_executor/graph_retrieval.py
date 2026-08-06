"""Graph Retrieval: import/call/inheritance graph traversal from identifier-matched seed files.

Seeds are the files `identifier_matching.count_identifier_matches_by_file`
finds -- files defining a function/class the query names exactly. From
those seeds, a breadth-first search expands outward over a combined,
undirected, file-level projection of `import_graph`, `call_graph`, and
`inheritance_graph` (the same style of projection used by Feature
Extraction's `graph_features.py`, reimplemented here rather than
imported: it is a small, self-contained helper, and reaching into
another milestone's private module would create a fragile coupling
neither milestone's own docs promise to maintain).

Latency measurement follows the frozen protocol in `latency_protocol.py`:
building the file-adjacency map (`_build_file_adjacency`, repository
-dependent, query-independent -- the graph-retrieval analogue of "index
construction") is excluded from `retrieval_latency_ms`; seed-finding
(query-dependent) and the BFS traversal itself are included. See
`README.md`'s "Design Rationale: Revision 2" for why this requires two
separate timed spans rather than one contiguous span covering the
whole method body.
"""
from __future__ import annotations

from collections import deque

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.common import LatencyAccumulator, build_strategy_result, rank_scores
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.identifier_matching import count_identifier_matches_by_file
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName, StrategyResult
from tara.retrieval.utils import tokenize_for_search


class GraphRetriever:
    """Structural, expansion-based file retrieval over a `RepositoryModel`'s graphs."""

    def __init__(self, settings: RetrievalExecutorSettings | None = None) -> None:
        """Construct the retriever.

        Args:
            settings: Controls `max_graph_hops`. Defaults to
                `RetrievalExecutorSettings()` (environment defaults).
        """
        self._settings = settings or RetrievalExecutorSettings()

    def retrieve(self, model: RepositoryModel, query_text: str, top_k: int) -> StrategyResult:
        """Retrieve the top `top_k` files by graph proximity to identifier-matched seed files.

        Args:
            model: The repository to search.
            query_text: The raw developer query.
            top_k: Maximum number of files to return.

        Returns:
            This strategy's independent `StrategyResult`. Empty
            `retrieved_files` if the query names no symbol defined
            anywhere in the repository -- there is no seed to expand
            from, which is an expected outcome, not an error; see
            `README.md`'s Failure Modes. `retrieval_latency_ms`
            excludes file-adjacency-map construction -- see
            `latency_protocol.py`.
        """
        # --- Timed region: seed-finding (query-dependent) ---
        timer = LatencyAccumulator()
        timer.start()
        query_tokens = tokenize_for_search(query_text)
        seed_files = set(count_identifier_matches_by_file(model, query_tokens))
        timer.stop()

        if not seed_files:
            return build_strategy_result(RetrievalStrategyName.GRAPH, model, query_text, [], timer.total_ms, self._settings)

        # --- Index construction (file-adjacency map): excluded from the frozen latency protocol ---
        adjacency = _build_file_adjacency(model)

        # --- Timed region: graph traversal + ranking ---
        timer.start()
        scores = _bfs_proximity_scores(adjacency, seed_files, self._settings.max_graph_hops)
        retrieved_files = rank_scores(scores, top_k)
        timer.stop()

        return build_strategy_result(
            RetrievalStrategyName.GRAPH, model, query_text, retrieved_files, timer.total_ms, self._settings
        )


def _build_file_adjacency(model: RepositoryModel) -> dict[str, set[str]]:
    """Project import/call/inheritance edges onto one undirected, file-level adjacency map.

    Call and inheritance edges connect symbol ids, a different id space
    than file paths; each is resolved to the files its two endpoint
    symbols are defined in via a `symbol_id -> file_path` lookup.
    Same-file edges are skipped (a self-loop contributes nothing to
    cross-file expansion). Every file is present as a key, even with an
    empty adjacency set, so an isolated file is a valid (if unreachable
    unless it's itself a seed) BFS node.
    """
    adjacency: dict[str, set[str]] = {normalized_file.path: set() for normalized_file in model.files}
    function_file_by_id = {function.symbol_id: function.file_path for function in model.functions}
    class_file_by_id = {klass.symbol_id: klass.file_path for klass in model.classes}

    def link(file_a: str, file_b: str) -> None:
        if file_a == file_b:
            return
        adjacency.setdefault(file_a, set()).add(file_b)
        adjacency.setdefault(file_b, set()).add(file_a)

    for import_edge in model.import_graph:
        link(import_edge.source_file, import_edge.target_file)

    for call_edge in model.call_graph:
        callee_file = function_file_by_id.get(call_edge.callee_symbol_id)
        if callee_file is not None:
            link(call_edge.file_path, callee_file)

    for inheritance_edge in model.inheritance_graph:
        superclass_file = class_file_by_id.get(inheritance_edge.superclass_symbol_id)
        if superclass_file is not None:
            link(inheritance_edge.file_path, superclass_file)

    return adjacency


def _bfs_proximity_scores(adjacency: dict[str, set[str]], seed_files: set[str], max_hops: int) -> dict[str, float]:
    """Breadth-first search from every seed simultaneously, scoring by `1 / (1 + hop_distance)`.

    A file reachable from multiple seeds (or via multiple paths) keeps
    the *best* (lowest-hop) score it was reached with, via the standard
    multi-source BFS visited-distance convention: a node is only
    (re-)enqueued if this path reaches it strictly closer than any
    previously recorded distance.
    """
    best_hop: dict[str, int] = {seed: 0 for seed in seed_files if seed in adjacency}
    queue: deque[tuple[str, int]] = deque(best_hop.items())

    while queue:
        file_path, hop = queue.popleft()
        if hop >= max_hops:
            continue
        for neighbor in adjacency.get(file_path, ()):
            if neighbor not in best_hop or best_hop[neighbor] > hop + 1:
                best_hop[neighbor] = hop + 1
                queue.append((neighbor, hop + 1))

    return {file_path: 1.0 / (1.0 + hop) for file_path, hop in best_hop.items()}
