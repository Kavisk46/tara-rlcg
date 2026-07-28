"""Unit tests for `tara.classification.classifier.HeuristicTaskClassifier`.

Covers every `TaskType`, every `RetrievalStrategy` recommendation, the
specification's four worked examples verbatim, confidence scoring,
dependency injection, and edge cases (empty/whitespace/punctuation-only
queries). No ML model and no LLM is used anywhere in this file.
"""
from __future__ import annotations

import time

import pytest

from tara.classification.classifier import HeuristicTaskClassifier
from tara.classification.features import FeatureExtractor
from tara.classification.rules import Rule, RuleEngine, RuleVote
from tara.core.exceptions import RuleEvaluationError, TaskClassificationError
from tara.core.types import Language, RetrievalStrategy, TaskType
from tara.interfaces.task_classifier import TaskClassifier


@pytest.fixture
def classifier() -> HeuristicTaskClassifier:
    return HeuristicTaskClassifier()


def test_classifier_implements_task_classifier_interface(classifier: HeuristicTaskClassifier) -> None:
    assert isinstance(classifier, TaskClassifier)


# --- Specification's worked examples, verbatim -------------------------------------


def test_example_where_is_jwt_implemented_is_hybrid(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("Where is JWT implemented?")
    assert result.retriever_kind is RetrievalStrategy.HYBRID
    assert result.lexical_required is True
    assert result.semantic_required is True
    assert "JWT" in result.detected_symbols


def test_example_what_does_repositoryparser_do_is_semantic(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("What does RepositoryParser do?")
    assert result.retriever_kind is RetrievalStrategy.SEMANTIC
    assert result.task_type is TaskType.EXPLAIN
    assert "RepositoryParser" in result.detected_symbols


def test_example_find_parse_repository_is_lexical(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("Find parse_repository")
    assert result.retriever_kind is RetrievalStrategy.LEXICAL
    assert result.task_type is TaskType.SEARCH
    assert "parse_repository" in result.detected_symbols


def test_example_trace_request_flow_is_graph(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("Trace request flow")
    assert result.retriever_kind is RetrievalStrategy.GRAPH
    assert result.graph_required is True


# --- Every TaskType --------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_task_type"),
    [
        ("Find parse_repository", TaskType.SEARCH),
        ("What does RepositoryParser do?", TaskType.EXPLAIN),
        ("Investigate the authentication issue", TaskType.DEBUG),
        ("Fix the crash when parsing empty files", TaskType.BUG_FIX),
        ("Refactor the GraphBuilder class to reduce duplication", TaskType.REFACTOR),
        ("Implement a new caching layer for the retriever", TaskType.GENERATE),
        ("Write a docstring for the parser function", TaskType.DOCUMENTATION),  # docstring, not "tests"
        ("Write unit tests for the SymbolIndex", TaskType.TEST),
        ("Show me the system design overview", TaskType.ARCHITECTURE),
        ("List the dependencies of the parser module", TaskType.DEPENDENCY_ANALYSIS),
        ("Check for SQL injection vulnerabilities in the API layer", TaskType.SECURITY),
        ("Why is the search endpoint so slow?", TaskType.PERFORMANCE),
        ("banana smoothie recipe ideas", TaskType.UNKNOWN),
    ],
)
def test_every_task_type_is_reachable(
    classifier: HeuristicTaskClassifier, query: str, expected_task_type: TaskType
) -> None:
    result = classifier.classify(query)
    assert result.task_type is expected_task_type


def test_all_thirteen_task_types_are_covered() -> None:
    covered = {
        TaskType.SEARCH, TaskType.EXPLAIN, TaskType.DEBUG, TaskType.BUG_FIX, TaskType.REFACTOR,
        TaskType.GENERATE, TaskType.TEST, TaskType.DOCUMENTATION, TaskType.ARCHITECTURE,
        TaskType.DEPENDENCY_ANALYSIS, TaskType.SECURITY, TaskType.PERFORMANCE, TaskType.UNKNOWN,
    }
    assert covered == set(TaskType)


# --- Every RetrievalStrategy -------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_strategy"),
    [
        ("Find parse_repository", RetrievalStrategy.LEXICAL),
        ("What does RepositoryParser do?", RetrievalStrategy.SEMANTIC),
        ("Trace request flow", RetrievalStrategy.GRAPH),
        ("Where is JWT implemented?", RetrievalStrategy.HYBRID),
    ],
)
def test_every_retrieval_strategy_is_reachable(
    classifier: HeuristicTaskClassifier, query: str, expected_strategy: RetrievalStrategy
) -> None:
    result = classifier.classify(query)
    assert result.retriever_kind is expected_strategy


def test_unknown_query_defaults_to_semantic_retriever(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("banana smoothie recipe ideas")
    assert result.retriever_kind is RetrievalStrategy.SEMANTIC


# --- Confidence scoring -------------------------------------------------------------


def test_single_firing_rule_yields_full_confidence(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("Find parse_repository")
    assert result.confidence == 1.0


def test_conflicting_votes_reduce_confidence(classifier: HeuristicTaskClassifier) -> None:
    # "find" -> SEARCH (weight 1.0); "refactor" -> REFACTOR (weight 1.0): an exact tie.
    result = classifier.classify("Find and refactor the parser")
    assert result.task_type is TaskType.REFACTOR  # tie-break: REFACTOR outranks SEARCH
    assert result.confidence == pytest.approx(0.5)


def test_no_signal_query_yields_zero_confidence(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("banana smoothie recipe ideas")
    assert result.confidence == 0.0
    assert result.task_type is TaskType.UNKNOWN


def test_confidence_is_always_within_bounds(classifier: HeuristicTaskClassifier) -> None:
    queries = [
        "Find parse_repository",
        "What does RepositoryParser do?",
        "",
        "Fix the bug and refactor and add tests and document it",
    ]
    for query in queries:
        result = classifier.classify(query)
        assert 0.0 <= result.confidence <= 1.0


# --- Symbol / keyword / language detection surfaced through classify() -----------------


def test_bare_symbol_query_falls_back_to_search(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("GraphBuilder")
    assert result.task_type is TaskType.SEARCH
    assert result.lexical_required is True
    assert "GraphBuilder" in result.detected_symbols


def test_keyword_extraction_surfaced_on_classification(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("Find the parse_repository function in utils.py")
    assert "parse_repository" in result.extracted_keywords
    assert "the" not in [kw.lower() for kw in result.extracted_keywords]


def test_file_path_detection_surfaced_on_classification(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("What changed in src/tara/parsing/repository_parser.py?")
    assert "src/tara/parsing/repository_parser.py" in result.detected_file_paths


def test_language_hint_surfaced_on_classification(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("How do I write this in TypeScript?")
    assert result.language_hint is Language.TYPESCRIPT


def test_metadata_records_fired_rules(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("Find parse_repository")
    assert "search_keyword" in result.metadata["fired_rules"]


# --- Edge cases ----------------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", "\t\n", "??? !!! ...", "!!!@@@###$$$"])
def test_empty_or_malformed_query_does_not_raise(classifier: HeuristicTaskClassifier, query: str) -> None:
    result = classifier.classify(query)
    assert result.task_type is TaskType.UNKNOWN
    assert result.confidence == 0.0
    assert result.retriever_kind is RetrievalStrategy.SEMANTIC


def test_unicode_query_does_not_raise(classifier: HeuristicTaskClassifier) -> None:
    result = classifier.classify("héllo wörld ⚡ find things")
    assert result.task_type is TaskType.SEARCH


def test_very_long_query_does_not_raise(classifier: HeuristicTaskClassifier) -> None:
    query = "find " * 2000
    result = classifier.classify(query)
    assert result.task_type is TaskType.SEARCH


# --- Dependency injection -----------------------------------------------------------


def test_custom_feature_extractor_is_used() -> None:
    class UppercaseOnlyExtractor(FeatureExtractor):
        def extract(self, query: str):  # type: ignore[override]
            return super().extract(query.upper())

    classifier = HeuristicTaskClassifier(feature_extractor=UppercaseOnlyExtractor())
    result = classifier.classify("find parse_repository")
    # Uppercased query still tokenizes and still fires the (case-insensitive) rule.
    assert result.task_type is TaskType.SEARCH


def test_custom_rule_engine_overrides_default_behavior() -> None:
    always_generate = Rule(
        name="always_generate",
        predicate=lambda features: True,
        vote=lambda features: RuleVote(rule_name="always_generate", task_type=TaskType.GENERATE, semantic_required=True),
    )
    classifier = HeuristicTaskClassifier(rule_engine=RuleEngine(rules=(always_generate,)))

    result = classifier.classify("this would normally be UNKNOWN")
    assert result.task_type is TaskType.GENERATE
    assert result.confidence == 1.0


def test_rule_evaluation_error_propagates_from_classify() -> None:
    broken_rule = Rule(
        name="broken",
        predicate=lambda features: 1 / 0,  # type: ignore[return-value]
        vote=lambda features: RuleVote(rule_name="broken"),
    )
    classifier = HeuristicTaskClassifier(rule_engine=RuleEngine(rules=(broken_rule,)))

    with pytest.raises(RuleEvaluationError):
        classifier.classify("anything")


def test_rule_evaluation_error_is_a_task_classification_error() -> None:
    assert issubclass(RuleEvaluationError, TaskClassificationError)


# --- Performance ---------------------------------------------------------------------


def test_classification_completes_within_10ms(classifier: HeuristicTaskClassifier) -> None:
    query = "Where is the JWT authentication logic implemented in src/tara/auth/jwt_handler.py?"

    start = time.perf_counter()
    classifier.classify(query)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.01
