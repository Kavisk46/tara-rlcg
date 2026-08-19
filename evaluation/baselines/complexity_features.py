"""Task-agnostic query-complexity feature extraction for the complexity-based routing baseline.

Extracts simple, deterministic, observable-from-query-text-alone
signals -- token count, identifier-shaped-token count, and a coordinating
-conjunction-based clause count -- with **no dependency on
`tara.classification.classifier.HeuristicTaskClassifier`,
`tara.classification.models.TaskClassification`, or any task-intent
judgment whatsoever**. This is the load-bearing property this module
exists to guarantee: `evaluation.baselines.complexity_router` (which
consumes this module's output) must be able to select a retrieval
strategy without ever having asked "what kind of task is this query,"
only "how long/complex does this query look, syntactically."

Reuses `tara.classification.heuristics.tokenize` /
`.looks_like_identifier` / `.extract_quoted` -- the same low-level,
dependency-free, purely syntactic helpers `evaluation.rts_builder.
feature_extraction.query_features` already reuses for an analogous
reason (see that module's own docstring: "Reuses `tara.classification.
heuristics`' tokenizer and identifier ... conventions"). These three
functions are naming-convention/punctuation predicates over a single
token, not task-classification logic: they say nothing about *why* a
query was asked, only what its tokens look like. None of
`tara.classification.rules`, `.classifier`, or `.models` is imported
anywhere in this module.

**New, baseline-only feature not present anywhere in `src/tara`:**
clause counting via coordinating-conjunction detection (a
`query_has_multi_clause`-style signal, named as a proposed-but-never
-implemented feature in `docs/methodology/Adaptive_Retrieval_Definition.md`
§4 and `docs/DATASET_BUILDER_SPEC.md` §6). No such extractor exists in
`tara.classification` to reuse, so the smallest deterministic version
needed for this baseline is implemented here, deliberately kept out of
`src/tara` since it is baseline-evaluation-only code (`PROJECT_SPEC.md`
§14, design principle 7: research/evaluation code is not library code).
"""
from __future__ import annotations

from dataclasses import dataclass

from tara.classification.heuristics import extract_quoted, looks_like_identifier, tokenize

_COORDINATING_CONJUNCTIONS: frozenset[str] = frozenset({"and", "or", "but"})
"""Deliberately minimal (the three classic coordinating conjunctions joining independent
clauses) rather than the full English conjunction set -- this is a coarse, illustrative
multi-clause proxy, not a parser, matching the "coarse multi-clause indicator" framing already
used for this exact feature in `docs/DATASET_BUILDER_SPEC.md` §6."""


@dataclass(frozen=True)
class QueryComplexityFeatures:
    """Task-agnostic, purely syntactic complexity signals for one query string.

    Every field here is computable from `raw_query` alone -- no
    repository, no classification, no task-intent judgment. Immutable,
    so two calls on the same input are guaranteed equal
    (`extract_complexity_features` is a pure function).
    """

    raw_query: str
    token_count: int
    identifier_like_count: int
    """Count of tokens that look like code symbols by naming convention (PascalCase,
    camelCase, snake_case, CONSTANT_CASE, acronym) plus every quoted phrase -- a syntactic
    "does this query name something specific" signal, not a task-type judgment."""
    clause_count: int
    """`1 + (number of coordinating-conjunction tokens)` -- a coarse proxy for how many
    independent clauses/requests the query packs together."""


def extract_complexity_features(query: str) -> QueryComplexityFeatures:
    """Extract `QueryComplexityFeatures` for `query`.

    Pure function: the same `query` string always yields the same
    result, and nothing about `TaskType`, `TaskClassification`, or any
    other task-intent signal is consulted or produced.

    Args:
        query: The raw developer query. May be empty or whitespace-only;
            that degrades to a zero-valued feature bundle rather than
            raising.

    Returns:
        The extracted, task-agnostic complexity features.
    """
    tokens = tokenize(query)
    quoted = extract_quoted(query)
    identifier_like = sum(1 for token in tokens if looks_like_identifier(token)) + len(quoted)
    conjunction_count = sum(1 for token in tokens if token.lower() in _COORDINATING_CONJUNCTIONS)

    return QueryComplexityFeatures(
        raw_query=query,
        token_count=len(tokens),
        identifier_like_count=identifier_like,
        clause_count=1 + conjunction_count,
    )
