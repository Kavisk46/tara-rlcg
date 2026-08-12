"""Unit tests for `evaluation.rts_builder.pilot.splitter.QuerySplitter`."""
from __future__ import annotations

from collections import Counter

import pytest

from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.models import SplitName
from evaluation.rts_builder.pilot.splitter import QuerySplitter


def test_assignment_is_deterministic_for_the_same_triple() -> None:
    splitter = QuerySplitter(PilotSettings(split_seed="seed-a"))
    first = splitter.assign("repo-1", "sha-a", "query text")
    second = splitter.assign("repo-1", "sha-a", "query text")
    assert first == second


def test_different_seed_can_reassign_a_query() -> None:
    # Not guaranteed for every query, but true often enough that hitting no reassignment across
    # 50 distinct queries would itself indicate the seed isn't being mixed into the hash at all.
    settings_a = PilotSettings(split_seed="seed-a")
    settings_b = PilotSettings(split_seed="seed-b")
    splitter_a, splitter_b = QuerySplitter(settings_a), QuerySplitter(settings_b)

    reassigned = sum(
        1 for i in range(50)
        if splitter_a.assign("repo-1", "sha-a", f"query-{i}") != splitter_b.assign("repo-1", "sha-a", f"query-{i}")
    )
    assert reassigned > 0


def test_assignment_does_not_depend_on_processing_order() -> None:
    splitter = QuerySplitter(PilotSettings(split_seed="seed-a"))
    queries = [(f"repo-{i % 3}", "sha", f"query-{i}") for i in range(30)]

    forward = [splitter.assign(*query) for query in queries]
    backward = [splitter.assign(*query) for query in reversed(queries)]

    assert forward == list(reversed(backward))


def test_ratios_are_approximately_respected_over_many_queries() -> None:
    settings = PilotSettings(split_seed="seed-a", train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)
    splitter = QuerySplitter(settings)

    counts: Counter[SplitName] = Counter(
        splitter.assign("repo-1", "sha-a", f"query-{i}") for i in range(2000)
    )

    train_fraction = counts[SplitName.TRAIN] / 2000
    validation_fraction = counts[SplitName.VALIDATION] / 2000
    test_fraction = counts[SplitName.TEST] / 2000

    assert train_fraction == pytest.approx(0.7, abs=0.03)
    assert validation_fraction == pytest.approx(0.15, abs=0.03)
    assert test_fraction == pytest.approx(0.15, abs=0.03)


def test_a_querys_four_strategy_rows_would_all_receive_the_same_assignment() -> None:
    # assign() is a pure function of (repository_id, commit_sha, query_text) alone -- strategy
    # is never a parameter, so every one of a query's 4 rows is guaranteed the same split.
    splitter = QuerySplitter(PilotSettings(split_seed="seed-a"))
    first_call = splitter.assign("repo-1", "sha-a", "query text")
    second_call = splitter.assign("repo-1", "sha-a", "query text")
    assert first_call == second_call
