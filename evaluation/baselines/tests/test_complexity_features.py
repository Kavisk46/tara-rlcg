"""Unit tests for `evaluation.baselines.complexity_features`.

Confirms the extractor is (a) a pure function of query text alone, and
(b) genuinely task-agnostic -- it does not import, construct, or call
anything from `tara.classification.classifier`/`.models`/`.rules`.
"""
from __future__ import annotations

import evaluation.baselines.complexity_features as complexity_features_module
from evaluation.baselines.complexity_features import extract_complexity_features


def test_empty_query_yields_zero_valued_features() -> None:
    features = extract_complexity_features("")
    assert features.token_count == 0
    assert features.identifier_like_count == 0
    assert features.clause_count == 1  # 1 + 0 conjunctions


def test_short_lookup_query_features() -> None:
    features = extract_complexity_features("find parse_repository")
    assert features.token_count == 2
    assert features.identifier_like_count == 1  # parse_repository is snake_case
    assert features.clause_count == 1


def test_multi_clause_query_increments_clause_count_per_conjunction() -> None:
    features = extract_complexity_features(
        "explain the parser and trace the graph builder and check the symbol index"
    )
    assert features.clause_count == 3  # 1 + 2 "and" tokens


def test_quoted_phrase_counts_as_identifier_like_regardless_of_naming_convention() -> None:
    features = extract_complexity_features('search for "the login flow"')
    assert features.identifier_like_count >= 1


def test_extraction_is_a_pure_function_of_query_text() -> None:
    query = "why does get_user_by_id return None for valid ids"
    first = extract_complexity_features(query)
    second = extract_complexity_features(query)
    assert first == second


def test_different_queries_can_yield_different_token_counts() -> None:
    short = extract_complexity_features("find X")
    long = extract_complexity_features(
        "explain in detail how the repository context extractor builds its graph and embeddings"
    )
    assert long.token_count > short.token_count


def test_module_never_imports_task_classification_machinery() -> None:
    """Structural proof, alongside the behavioral ones above: this module's own source has no
    dependency on `tara.classification.classifier`, `.models`, or `.rules` -- only the
    low-level, dependency-free `tara.classification.heuristics` predicates."""
    source_module = complexity_features_module.__name__
    assert source_module == "evaluation.baselines.complexity_features"
    import sys

    module = sys.modules[source_module]
    module_globals = vars(module)
    # Only `tara.classification.heuristics` names should be present among the
    # `tara.classification.*`-sourced globals this module imports.
    disallowed = {"HeuristicTaskClassifier", "TaskClassification", "TaskType", "DEFAULT_RULES"}
    assert disallowed.isdisjoint(module_globals)
