"""Unit tests for `evaluation.rts_builder.pilot.identifiers.compute_query_id`."""
from __future__ import annotations

from evaluation.rts_builder.pilot.identifiers import compute_query_id


def test_same_triple_produces_the_same_id() -> None:
    first = compute_query_id("repo-1", "sha-a", "how does it work")
    second = compute_query_id("repo-1", "sha-a", "how does it work")
    assert first == second


def test_different_query_text_produces_a_different_id() -> None:
    first = compute_query_id("repo-1", "sha-a", "query one")
    second = compute_query_id("repo-1", "sha-a", "query two")
    assert first != second


def test_different_repository_produces_a_different_id() -> None:
    first = compute_query_id("repo-1", "sha-a", "same query")
    second = compute_query_id("repo-2", "sha-a", "same query")
    assert first != second


def test_different_commit_produces_a_different_id() -> None:
    first = compute_query_id("repo-1", "sha-a", "same query")
    second = compute_query_id("repo-1", "sha-b", "same query")
    assert first != second


def test_id_is_a_16_character_hex_string() -> None:
    query_id = compute_query_id("repo-1", "sha-a", "some query")
    assert len(query_id) == 16
    int(query_id, 16)  # raises ValueError if not valid hex


def test_field_boundaries_are_not_confusable() -> None:
    # Without a separator, ("ab", "c") and ("a", "bc") would hash identically -- confirm the
    # \x1f field separator actually prevents that kind of boundary collision.
    first = compute_query_id("ab", "c", "query")
    second = compute_query_id("a", "bc", "query")
    assert first != second
