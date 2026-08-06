"""Computes `QueryFeatures` from raw developer query text.

Reuses `tara.classification.heuristics`' tokenizer and identifier
-shape predicates (`tokenize`, `looks_like_identifier`) -- the same
low-level, stateless primitives `tara.retrieval.utils.tokenize_for_search`
already reuses for a different purpose (BM25 indexing). This is
reusing tested primitives, not "implementing the Task Classifier": no
`TaskType` is assigned, no confidence is scored, no rule engine runs --
see `REVIEW_RESPONSE.md`.
"""
from __future__ import annotations

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.models import QueryFeatures
from tara.classification.heuristics import looks_like_identifier, tokenize

_QUESTION_KEYWORDS: frozenset[str] = frozenset({"how", "why", "what", "where", "explain", "does"})
_BUG_KEYWORDS: frozenset[str] = frozenset({"bug", "fix", "error", "exception", "crash", "fail", "failing", "broken"})
_TEST_KEYWORDS: frozenset[str] = frozenset({"test", "tests", "testing", "pytest", "unittest"})
_REFACTOR_KEYWORDS: frozenset[str] = frozenset({"refactor", "rename", "cleanup", "simplify", "restructure"})

_CLAUSE_SEPARATORS: tuple[str, ...] = (" and ", " or ", " then ", ";", ",")


def compute_query_features(query_text: str, settings: FeatureExtractionSettings) -> QueryFeatures:
    """Compute every query-level feature for `query_text`.

    Args:
        query_text: The raw developer query. An empty string is valid
            and yields all-zero/False features.
        settings: Controls the weights and normalization constants used
            by `complexity`.

    Returns:
        The populated `QueryFeatures`.
    """
    tokens = tokenize(query_text)
    lowered_tokens = [token.lower() for token in tokens]
    token_set = frozenset(lowered_tokens)

    identifier_count = sum(1 for token in tokens if looks_like_identifier(token))
    api_token_count = sum(1 for token in tokens if "." in token)

    clause_count = 1 + sum(query_text.count(separator) for separator in _CLAUSE_SEPARATORS)

    complexity = _compute_complexity(
        word_count=len(tokens),
        identifier_count=identifier_count,
        clause_count=clause_count,
        settings=settings,
    )

    return QueryFeatures(
        length=len(query_text),
        identifier_count=identifier_count,
        api_token_count=api_token_count,
        has_question_keyword=not token_set.isdisjoint(_QUESTION_KEYWORDS),
        has_bug_keyword=not token_set.isdisjoint(_BUG_KEYWORDS),
        has_test_keyword=not token_set.isdisjoint(_TEST_KEYWORDS),
        has_refactor_keyword=not token_set.isdisjoint(_REFACTOR_KEYWORDS),
        complexity=complexity,
    )


def _compute_complexity(
    word_count: int, identifier_count: int, clause_count: int, settings: FeatureExtractionSettings
) -> float:
    """A simple, explainable [0, 1] heuristic -- see `QueryFeatures.complexity` and `README.md`.

    Each of the three signals is independently clamped to [0, 1] by
    normalizing against a configured "maximal" value before being
    combined by configured weights (validated in
    `FeatureExtractionSettings` to sum to 1.0), so the result is always
    in [0, 1] regardless of how long or identifier-dense a query is.
    """
    length_component = min(word_count / settings.query_complexity_length_norm, 1.0)
    identifier_component = min(identifier_count / settings.query_complexity_identifier_norm, 1.0)
    clause_component = min((clause_count - 1) / settings.query_complexity_clause_norm, 1.0)

    return (
        settings.query_complexity_length_weight * length_component
        + settings.query_complexity_identifier_weight * identifier_component
        + settings.query_complexity_clause_weight * clause_component
    )
