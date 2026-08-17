"""Fairness-invariant enforcement: guarantees that only a baseline's
retrieval strategy may differ between runs, per this milestone's
FAIRNESS INVARIANTS requirement.

**Structural guarantee, already true by construction:**
`evaluation.baselines.definitions.BaselineDefinition` is
`(baseline_id, name, description, strategy)` only -- there is no field on
it a baseline could use to override the shared corpus, query set,
generation config, or evaluation config even if it wanted to, and
`evaluation.baselines.runner.BaselineRunner` is constructed once, with
one `CodeGenerator`/`TaraSettings`/`ContextFusion`, reused for every
`.run()` call regardless of which baseline is passed in.

This module adds an explicit, second layer on top of that structural
guarantee: a runtime check that rejects any attempted per-baseline
override of the shared, immutable `GenerationConfig`/`EvaluationConfig`/
corpus/query-set, so a future caller who tries anyway (e.g. a config
source with a stray per-baseline `model:` override) fails loudly at load
time rather than silently running an unfair comparison.
"""
from __future__ import annotations

from collections.abc import Mapping

from tara.core.exceptions import TaraError

GENERATION_CONFIG_FIELDS = frozenset({"model", "temperature", "max_tokens", "prompt_template"})
EVALUATION_CONFIG_FIELDS = frozenset(
    {"evaluator", "metrics", "scoring_protocol", "output_schema", "query_set_id", "corpus_id"}
)
CORPUS_FIELDS = frozenset({"context", "repository_context", "corpus", "root_path"})
QUERY_SET_FIELDS = frozenset({"query", "query_id", "queries", "query_set"})


class FairnessInvariantError(TaraError):
    """Raised when a per-baseline override would violate the "only retrieval strategy may
    differ" comparison invariant this milestone requires."""


def _reject(overrides: Mapping[str, object], forbidden: frozenset[str], subject: str) -> None:
    violating = sorted(set(overrides) & forbidden)
    if violating:
        raise FairnessInvariantError(
            f"Baseline configuration attempted to override shared {subject} setting(s) "
            f"{violating}; only the retrieval/routing mechanism may differ between baselines. "
            f"Remove these keys from the baseline-specific configuration."
        )


def reject_generation_overrides(overrides: Mapping[str, object]) -> None:
    """Raise `FairnessInvariantError` if `overrides` names any `GenerationConfig` field.

    Args:
        overrides: Whatever a baseline-specific configuration source
            (e.g. a per-baseline entry in a future config file) attempted
            to set.
    """
    _reject(overrides, GENERATION_CONFIG_FIELDS, "generation")


def reject_evaluation_overrides(overrides: Mapping[str, object]) -> None:
    """Raise `FairnessInvariantError` if `overrides` names any `EvaluationConfig` field."""
    _reject(overrides, EVALUATION_CONFIG_FIELDS, "evaluation")


def reject_corpus_override(overrides: Mapping[str, object]) -> None:
    """Raise `FairnessInvariantError` if `overrides` attempts to set a corpus/repository-context
    field -- every baseline must run against the exact same `RepositoryContext` instance."""
    _reject(overrides, CORPUS_FIELDS, "corpus")


def reject_query_set_override(overrides: Mapping[str, object]) -> None:
    """Raise `FairnessInvariantError` if `overrides` attempts to set a query/query-set field --
    every baseline must be evaluated against the exact same query IDs and query text."""
    _reject(overrides, QUERY_SET_FIELDS, "query-set")


def validate_no_overrides(overrides: Mapping[str, object]) -> None:
    """Run every rejection check in this module against `overrides`.

    Raises:
        FairnessInvariantError: If `overrides` names any field belonging
            to the shared corpus, query set, generation config, or
            evaluation config.
    """
    reject_generation_overrides(overrides)
    reject_evaluation_overrides(overrides)
    reject_corpus_override(overrides)
    reject_query_set_override(overrides)
