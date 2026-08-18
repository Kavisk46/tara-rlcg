"""A3 -- Graph retrieval disabled.

Per `EXPERIMENT_PLAN.md` §5: "Graph retriever forced unavailable
regardless of plan (forces the planner's context-capability-downgrade
path)." `tara.routing.planner.RetrievalPlanner._apply_context_constraints`
already drops `RetrieverKind.GRAPH` from any plan whenever
`context.graph.number_of_nodes() <= 1` (falling back to `LEXICAL` if
graph was the only retriever a policy asked for) -- exactly TARA's
existing, already-tested behavior for a repository whose graph
genuinely has no content. `disable_graph_retrieval` reproduces that
same condition for *any* repository, real or synthetic, without
touching `tara.routing.planner` or the real `RepositoryContext` object
it was built from.
"""
from __future__ import annotations

import networkx as nx

from tara.context.models import RepositoryContext


def disable_graph_retrieval(context: RepositoryContext) -> RepositoryContext:
    """Return a copy of `context` whose graph is empty, forcing GRAPH to be planner-downgraded.

    Args:
        context: The real `RepositoryContext` to ablate.

    Returns:
        `context.model_copy(update={"graph": <empty DiGraph>})` --
        every other field (`symbol_index`, `embeddings`, `root_path`,
        etc.) is the exact same object `context` already held, so
        lexical/dense retrieval and generation are entirely unaffected;
        only `RetrievalPlanner`'s graph-availability check (and any
        code that reads `context.graph` directly, which no retriever
        other than a graph retriever does) sees a trivial, 0-node graph.

    Note:
        `context.symbol_index` is deliberately left untouched (still
        built from the real, non-empty graph) -- lexical/dense
        retrieval depend on the symbol index and embeddings, not on
        `context.graph`, so this asymmetry is harmless for this
        ablation's purpose (graph retrieval is never selected by any
        plan built against the returned context, so nothing ever reads
        its now-stale graph/symbol_index relationship). Register no
        `GraphRetriever` in the `RetrievalOrchestrator` used for an A3
        run as a second, independent safeguard against graph retrieval
        occurring by any path.
    """
    return context.model_copy(update={"graph": nx.DiGraph()})
