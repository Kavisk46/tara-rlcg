"""Unit tests for `evaluation.baselines.fairness`.

Covers this milestone's explicit rejection requirements: attempting to
override common generation settings, the corpus, the query set, or the
evaluation protocol on a per-baseline basis must fail loudly.
"""
from __future__ import annotations

import pytest

from evaluation.baselines.fairness import (
    FairnessInvariantError,
    reject_corpus_override,
    reject_evaluation_overrides,
    reject_generation_overrides,
    reject_query_set_override,
    validate_no_overrides,
)
from tara.core.exceptions import TaraError


def test_fairness_invariant_error_is_a_tara_error() -> None:
    assert issubclass(FairnessInvariantError, TaraError)


# ============================================================================
# Generation settings
# ============================================================================


def test_reject_generation_overrides_allows_unrelated_keys() -> None:
    reject_generation_overrides({"baseline_id": "B1"})  # must not raise


@pytest.mark.parametrize("field_name", ["model", "temperature", "max_tokens", "prompt_template"])
def test_reject_generation_overrides_rejects_each_generation_field(field_name: str) -> None:
    with pytest.raises(FairnessInvariantError, match=field_name):
        reject_generation_overrides({field_name: "override"})


# ============================================================================
# Evaluation protocol
# ============================================================================


def test_reject_evaluation_overrides_allows_unrelated_keys() -> None:
    reject_evaluation_overrides({"baseline_id": "B1"})  # must not raise


@pytest.mark.parametrize(
    "field_name",
    ["evaluator", "metrics", "scoring_protocol", "output_schema", "query_set_id", "corpus_id"],
)
def test_reject_evaluation_overrides_rejects_each_evaluation_field(field_name: str) -> None:
    with pytest.raises(FairnessInvariantError, match=field_name):
        reject_evaluation_overrides({field_name: "override"})


# ============================================================================
# Corpus
# ============================================================================


@pytest.mark.parametrize("field_name", ["context", "repository_context", "corpus", "root_path"])
def test_reject_corpus_override_rejects_each_corpus_field(field_name: str) -> None:
    with pytest.raises(FairnessInvariantError, match="corpus"):
        reject_corpus_override({field_name: "override"})


def test_reject_corpus_override_allows_unrelated_keys() -> None:
    reject_corpus_override({"strategy": "lexical_only"})  # must not raise


# ============================================================================
# Query set
# ============================================================================


@pytest.mark.parametrize("field_name", ["query", "query_id", "queries", "query_set"])
def test_reject_query_set_override_rejects_each_query_field(field_name: str) -> None:
    with pytest.raises(FairnessInvariantError, match="query-set"):
        reject_query_set_override({field_name: "override"})


def test_reject_query_set_override_allows_unrelated_keys() -> None:
    reject_query_set_override({"strategy": "lexical_only"})  # must not raise


# ============================================================================
# validate_no_overrides: runs every check
# ============================================================================


def test_validate_no_overrides_passes_for_a_legitimate_baseline_override_attempt() -> None:
    """A baseline is only ever allowed to specify its own id/name/description/strategy."""
    validate_no_overrides(
        {"baseline_id": "B1", "strategy": "semantic_only", "name": "Fixed semantic-only"}
    )


def test_validate_no_overrides_catches_a_generation_field_hidden_among_legitimate_ones() -> None:
    with pytest.raises(FairnessInvariantError):
        validate_no_overrides({"baseline_id": "B1", "temperature": 0.9})


def test_validate_no_overrides_catches_a_corpus_field() -> None:
    with pytest.raises(FairnessInvariantError):
        validate_no_overrides({"baseline_id": "B1", "corpus": "a-different-repository"})
