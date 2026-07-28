"""Deterministic rule engine for task classification.

Each `Rule` is a pure function of `QueryFeatures` -> an optional
`RuleVote`. Rules never see each other, never mutate shared state, and
never call an LLM or the network -- classification stays deterministic
and inexpensive by construction. `RuleEngine.evaluate` runs every
registered rule exactly once and returns every vote that fired;
combining those votes into a single `TaskClassification` is left to
`tara.classification.classifier.HeuristicTaskClassifier`, so this module
only ever produces raw, uncombined opinions.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tara.classification.features import QueryFeatures
from tara.classification.heuristics import (
    ARCHITECTURE_KEYWORDS,
    BUG_FIX_KEYWORDS,
    DEBUG_KEYWORDS,
    DEPENDENCY_KEYWORDS,
    DOCUMENTATION_KEYWORDS,
    EXPLAIN_KEYWORDS,
    GENERATE_KEYWORDS,
    GRAPH_TRIGGER_KEYWORDS,
    IMPLEMENTATION_KEYWORDS,
    PERFORMANCE_KEYWORDS,
    REASONING_TRIGGER_KEYWORDS,
    REFACTOR_KEYWORDS,
    SEARCH_KEYWORDS,
    SECURITY_KEYWORDS,
    TEST_KEYWORDS,
    looks_like_explain_question,
)
from tara.core.exceptions import RuleEvaluationError
from tara.core.types import TaskType


@dataclass(frozen=True)
class RuleVote:
    """A single rule's opinion about a query, or part of one.

    Every field is additive: a rule sets only what it has an opinion
    about and leaves the rest at its default (no vote / False), so
    combining many `RuleVote`s is just an OR over the booleans and a
    weighted tally over `task_type` -- see
    `HeuristicTaskClassifier._combine_task_type`.
    """

    rule_name: str
    task_type: TaskType | None = None
    weight: float = 1.0
    graph_required: bool = False
    semantic_required: bool = False
    lexical_required: bool = False
    reasoning_required: bool = False


@dataclass(frozen=True)
class Rule:
    """A single named, isolated classification rule.

    `predicate` inspects `QueryFeatures` and returns True when the rule
    applies; `vote` is only called when `predicate` returns True. Kept
    as two separate callables (rather than one that returns
    `RuleVote | None`) so `RuleEngine` can log which rules fired by name
    without re-deriving the vote, and so a rule's condition and its
    effect can be read and tested independently.
    """

    name: str
    predicate: Callable[[QueryFeatures], bool]
    vote: Callable[[QueryFeatures], RuleVote]


def _keyword_rule(
    name: str,
    keywords: frozenset[str],
    *,
    task_type: TaskType | None = None,
    weight: float = 1.0,
    graph_required: bool = False,
    semantic_required: bool = False,
    lexical_required: bool = False,
    reasoning_required: bool = False,
) -> Rule:
    """Build a `Rule` that fires when any query token exactly matches `keywords`."""

    def predicate(features: QueryFeatures) -> bool:
        return not features.token_set.isdisjoint(keywords)

    def vote(_features: QueryFeatures) -> RuleVote:
        return RuleVote(
            rule_name=name,
            task_type=task_type,
            weight=weight,
            graph_required=graph_required,
            semantic_required=semantic_required,
            lexical_required=lexical_required,
            reasoning_required=reasoning_required,
        )

    return Rule(name=name, predicate=predicate, vote=vote)


def _explain_question_predicate(features: QueryFeatures) -> bool:
    return looks_like_explain_question(features.token_set) or not features.token_set.isdisjoint(EXPLAIN_KEYWORDS)


def _explain_question_vote(_features: QueryFeatures) -> RuleVote:
    return RuleVote(rule_name="explain_question", task_type=TaskType.EXPLAIN, semantic_required=True)


def _quoted_identifier_predicate(features: QueryFeatures) -> bool:
    return bool(features.quoted_identifiers)


def _quoted_identifier_vote(_features: QueryFeatures) -> RuleVote:
    return RuleVote(rule_name="quoted_identifier", lexical_required=True)


DEFAULT_RULES: tuple[Rule, ...] = (
    # Explicit examples from the Task Classifier specification:
    #   contains("trace")  -> graph_required=True      (graph_trigger_keyword, below)
    #   contains("why")    -> reasoning_required=True   (reasoning_trigger_keyword, below)
    #   contains("find")   -> lexical_required=True     (search_keyword, below)
    _keyword_rule("search_keyword", SEARCH_KEYWORDS, task_type=TaskType.SEARCH, lexical_required=True),
    _keyword_rule(
        "implementation_concept_keyword",
        IMPLEMENTATION_KEYWORDS,
        task_type=TaskType.SEARCH,
        weight=0.5,
        semantic_required=True,
    ),
    Rule(name="explain_question", predicate=_explain_question_predicate, vote=_explain_question_vote),
    _keyword_rule("debug_keyword", DEBUG_KEYWORDS, task_type=TaskType.DEBUG, reasoning_required=True, semantic_required=True),
    _keyword_rule(
        "bug_fix_keyword", BUG_FIX_KEYWORDS, task_type=TaskType.BUG_FIX, reasoning_required=True, semantic_required=True
    ),
    _keyword_rule("refactor_keyword", REFACTOR_KEYWORDS, task_type=TaskType.REFACTOR, semantic_required=True),
    _keyword_rule("generate_keyword", GENERATE_KEYWORDS, task_type=TaskType.GENERATE, semantic_required=True),
    _keyword_rule("test_keyword", TEST_KEYWORDS, task_type=TaskType.TEST, semantic_required=True),
    _keyword_rule("documentation_keyword", DOCUMENTATION_KEYWORDS, task_type=TaskType.DOCUMENTATION, semantic_required=True),
    _keyword_rule("architecture_keyword", ARCHITECTURE_KEYWORDS, task_type=TaskType.ARCHITECTURE, graph_required=True),
    _keyword_rule("dependency_keyword", DEPENDENCY_KEYWORDS, task_type=TaskType.DEPENDENCY_ANALYSIS, graph_required=True),
    _keyword_rule("security_keyword", SECURITY_KEYWORDS, task_type=TaskType.SECURITY, semantic_required=True),
    _keyword_rule("performance_keyword", PERFORMANCE_KEYWORDS, task_type=TaskType.PERFORMANCE, semantic_required=True),
    _keyword_rule("graph_trigger_keyword", GRAPH_TRIGGER_KEYWORDS, graph_required=True),
    _keyword_rule("reasoning_trigger_keyword", REASONING_TRIGGER_KEYWORDS, reasoning_required=True),
    Rule(name="quoted_identifier", predicate=_quoted_identifier_predicate, vote=_quoted_identifier_vote),
)


class RuleEngine:
    """Evaluates a fixed set of `Rule`s against `QueryFeatures`.

    Rules are supplied through the constructor (dependency injection),
    defaulting to `DEFAULT_RULES`, so callers can add, remove, or
    entirely replace the rule set -- e.g. for a domain-specific
    vocabulary -- without changing `RuleEngine` or
    `HeuristicTaskClassifier`.
    """

    def __init__(self, rules: tuple[Rule, ...] = DEFAULT_RULES) -> None:
        """Construct the engine.

        Args:
            rules: The ordered set of rules to evaluate. Order has no
                effect on the result (rules are isolated and don't see
                each other's votes); it only affects the order votes
                appear in `evaluate`'s return value and in logs.
        """
        self._rules = rules

    def evaluate(self, features: QueryFeatures) -> list[RuleVote]:
        """Run every rule once against `features` and return every vote that fired.

        Args:
            features: The `QueryFeatures` to evaluate rules against.

        Returns:
            One `RuleVote` per rule whose `predicate` returned True, in
            rule-registration order.

        Raises:
            RuleEvaluationError: If a rule's `predicate` or `vote`
                callable raises. A single misbehaving rule must not
                silently corrupt the classification; the error message
                identifies which rule failed.
        """
        votes: list[RuleVote] = []
        for rule in self._rules:
            try:
                if rule.predicate(features):
                    votes.append(rule.vote(features))
            except Exception as exc:  # noqa: BLE001 - normalize to a typed error, identify the culprit rule
                raise RuleEvaluationError(f"Rule '{rule.name}' failed to evaluate: {exc}") from exc
        return votes
