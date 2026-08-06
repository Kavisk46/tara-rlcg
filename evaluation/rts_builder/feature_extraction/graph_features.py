"""Computes `GraphFeatures` from a `RepositoryModel`'s import/call/inheritance graphs.

`import_density`/`call_density`/`inheritance_density` are computed
per-graph, each normalized against the population of nodes actually
relevant to that graph (files for imports, functions for calls, classes
for inheritance) -- not a single shared node count -- and use the same
`edges / max(nodes, 1)` convention `docs/DATASET_BUILDER_SPEC.md` §6
already established for `graph_density`, for consistency with the
project's existing terminology.

`connected_components`/`avg_degree` need one shared graph to be
meaningful at all, which none of the three raw graphs alone provides
(import edges connect files; call/inheritance edges connect symbol ids
in a disjoint id space) -- `_build_combined_file_graph` projects all
three onto a single undirected, file-level graph via `networkx`.
"""
from __future__ import annotations

import networkx as nx

from evaluation.rts_builder.feature_extraction.models import GraphFeatures
from evaluation.rts_builder.parser.models import RepositoryModel


def compute_graph_features(model: RepositoryModel) -> GraphFeatures:
    """Compute every graph-topology feature.

    Args:
        model: The parsed repository, carrying `import_graph`,
            `call_graph`, and `inheritance_graph`.

    Returns:
        The populated `GraphFeatures`.
    """
    file_count = len(model.files)
    function_count = len(model.functions)
    class_count = len(model.classes)

    import_density = len(model.import_graph) / max(file_count, 1)
    call_density = len(model.call_graph) / max(function_count, 1)
    inheritance_density = len(model.inheritance_graph) / max(class_count, 1)

    combined = _build_combined_file_graph(model)
    node_count = combined.number_of_nodes()
    connected_components = nx.number_connected_components(combined) if node_count else 0
    avg_degree = (2 * combined.number_of_edges() / node_count) if node_count else 0.0

    return GraphFeatures(
        import_density=import_density,
        call_density=call_density,
        inheritance_density=inheritance_density,
        connected_components=connected_components,
        avg_degree=avg_degree,
    )


def _build_combined_file_graph(model: RepositoryModel) -> nx.Graph:
    """Project all three graphs onto one undirected, file-level graph.

    Every file is a node, regardless of whether it participates in any
    edge (an isolated file is still its own connected component).
    Import edges are already file-to-file. Call and inheritance edges
    connect symbol ids; each is projected to an edge between the two
    files those symbols are defined in, via a `symbol_id -> file_path`
    lookup built from `model.functions`/`model.classes`. Same-file edges
    (self-loops) are skipped -- they never affect connectivity between
    distinct files and would only inflate degree without adding
    structural information.
    """
    graph: nx.Graph = nx.Graph()
    graph.add_nodes_from(normalized_file.path for normalized_file in model.files)

    function_file_by_id = {function.symbol_id: function.file_path for function in model.functions}
    class_file_by_id = {klass.symbol_id: klass.file_path for klass in model.classes}

    for edge in model.import_graph:
        if edge.source_file != edge.target_file:
            graph.add_edge(edge.source_file, edge.target_file)

    for call_edge in model.call_graph:
        callee_file = function_file_by_id.get(call_edge.callee_symbol_id)
        if callee_file is not None and callee_file != call_edge.file_path:
            graph.add_edge(call_edge.file_path, callee_file)

    for inheritance_edge in model.inheritance_graph:
        superclass_file = class_file_by_id.get(inheritance_edge.superclass_symbol_id)
        if superclass_file is not None and superclass_file != inheritance_edge.file_path:
            graph.add_edge(inheritance_edge.file_path, superclass_file)

    return graph
