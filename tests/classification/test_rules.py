"""Unit tests for `tara.classification.rules.RuleEngine`."""
from __future__ import annotations

import pytest

from tara.classification.features import FeatureExtractor
from tara.classification.rules import DEFAULT_RULES, Rule, RuleEngine, RuleVote
from tara.core.exceptions import RuleEvaluationError
from tara.core.types import TaskType


def _features(query: str):
    return FeatureExtractor().extract(query)


def test_default_rule_engine_fires_search_keyword_rule() -> None:
    votes = RuleEngine().evaluate(_features("Find parse_repository"))
    names = {vote.rule_name for vote in votes}
    assert "search_keyword" in names

    search_vote = next(v for v in votes if v.rule_name == "search_keyword")
    assert search_vote.task_type is TaskType.SEARCH
    assert search_vote.lexical_required is True


def test_rule_engine_returns_no_votes_for_empty_features() -> None:
    votes = RuleEngine().evaluate(_features(""))
    assert votes == []


def test_rule_engine_evaluates_every_rule_independently() -> None:
    """Rules that fire together must not see or influence each other's votes."""
    votes = RuleEngine().evaluate(_features("Why is the search endpoint so slow?"))
    names = [vote.rule_name for vote in votes]

    assert "reasoning_trigger_keyword" in names
    assert "performance_keyword" in names
    # Each rule's vote is independent: reasoning_trigger never sets task_type.
    reasoning_vote = next(v for v in votes if v.rule_name == "reasoning_trigger_keyword")
    assert reasoning_vote.task_type is None
    assert reasoning_vote.reasoning_required is True


def test_rule_engine_accepts_custom_rule_set_via_injection() -> None:
    custom_rule = Rule(
        name="always_fires",
        predicate=lambda features: True,
        vote=lambda features: RuleVote(rule_name="always_fires", task_type=TaskType.SEARCH),
    )
    engine = RuleEngine(rules=(custom_rule,))

    votes = engine.evaluate(_features("anything at all"))
    assert len(votes) == 1
    assert votes[0].rule_name == "always_fires"


def test_rule_engine_wraps_predicate_failures_as_rule_evaluation_error() -> None:
    broken_rule = Rule(
        name="broken_predicate",
        predicate=lambda features: 1 / 0,  # type: ignore[return-value]
        vote=lambda features: RuleVote(rule_name="broken_predicate"),
    )
    engine = RuleEngine(rules=(broken_rule,))

    with pytest.raises(RuleEvaluationError, match="broken_predicate"):
        engine.evaluate(_features("anything"))


def test_rule_engine_wraps_vote_failures_as_rule_evaluation_error() -> None:
    broken_rule = Rule(
        name="broken_vote",
        predicate=lambda features: True,
        vote=lambda features: 1 / 0,  # type: ignore[return-value]
    )
    engine = RuleEngine(rules=(broken_rule,))

    with pytest.raises(RuleEvaluationError, match="broken_vote"):
        engine.evaluate(_features("anything"))


def test_default_rules_are_immutable_tuple() -> None:
    assert isinstance(DEFAULT_RULES, tuple)
    assert len(DEFAULT_RULES) > 0


@pytest.mark.parametrize(
    ("query", "expected_rule"),
    [
        ("Trace the request flow", "graph_trigger_keyword"),
        ("Why does this fail?", "reasoning_trigger_keyword"),
        ("Find the config loader", "search_keyword"),
    ],
)
def test_specification_examples_fire_the_expected_rule(query: str, expected_rule: str) -> None:
    votes = RuleEngine().evaluate(_features(query))
    assert any(vote.rule_name == expected_rule for vote in votes)
