"""Exact identifier matching: a shared signal used by both Lexical and Graph Retrieval.

A single, deterministic definition of "this query mentions a symbol
defined in this file" -- reused as a scoring signal by
`lexical_retrieval.py` and as the seed-finding step by
`graph_retrieval.py`, so the two strategies never silently disagree
about what counts as an exact match.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from evaluation.rts_builder.parser.models import RepositoryModel


def count_identifier_matches_by_file(model: RepositoryModel, query_tokens: Sequence[str]) -> dict[str, int]:
    """Return `{file_path: match_count}` for files defining a symbol whose name exactly matches a query token.

    Matching is case-insensitive on the symbol's own (unqualified) name
    -- `query_tokens` containing `"animal"` matches a class named
    `Animal` -- and counts every matching function/class, so a file
    defining several query-mentioned symbols scores higher than one
    defining only one.

    Args:
        model: The repository to search.
        query_tokens: The already-tokenized query (see `tara.retrieval.utils.tokenize_for_search`).

    Returns:
        A mapping from `file_path` to its match count, omitting files
        with zero matches entirely (never a `0` entry).
    """
    query_token_set = {token.lower() for token in query_tokens}
    if not query_token_set:
        return {}

    counts: dict[str, int] = defaultdict(int)
    for function in model.functions:
        if function.name.lower() in query_token_set:
            counts[function.file_path] += 1
    for klass in model.classes:
        if klass.name.lower() in query_token_set:
            counts[klass.file_path] += 1
    return dict(counts)
