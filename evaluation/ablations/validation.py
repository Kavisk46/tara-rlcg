"""Controlled-variable validation: prevents comparing runs that silently differ.

Per this milestone's own instruction: "add validation that prevents
accidental comparison of runs with different repositories, query sets,
LLMs, token budgets, or embedding models when those variables are
supposed to be controlled." Operates on already-materialized
`evaluation.harness.models.ExperimentConfig` records -- i.e. it guards
*result-comparison* time, given two (or more) completed run configs.

**Distinct from, and complementary to, `evaluation.baselines.fairness`**,
which guards *baseline-construction* time (rejecting a per-baseline
config override before any run happens at all, operating on raw
override dicts, not on full `ExperimentConfig` records). Both exist
because they close different windows: `fairness.py` prevents an unfair
comparison from ever being *configured*; this module catches one that
was already *run* under two different configurations, e.g. two
experiment directories produced days apart, potentially with a changed
default somewhere in between.
"""
from __future__ import annotations

from collections.abc import Sequence

from evaluation.harness.models import ExperimentConfig
from tara.core.exceptions import TaraError

CONTROLLED_FIELDS: tuple[str, ...] = (
    "repository_manifest_path",
    "queries_path",
    "generation_model",
    "token_budget",
    "embedding_model_name",
)
"""The exact five variables this milestone names: "repositories, query sets, LLMs, token
budgets, or embedding models." Every other `ExperimentConfig` field (`variant_ids`,
`prompt_template`, `k_values`, `tara_git_commit`, `notes`, `experiment_id`, `created_at`) is
deliberately not controlled here -- `variant_ids`/`prompt_template` are meant to vary between
an ablation and its baseline comparison point (that variation is the whole point of an
ablation), and the rest are either per-run identifiers or informational."""


class ControlledVariableMismatchError(TaraError):
    """Raised when two or more `ExperimentConfig`s meant to be comparable differ in a variable
    this milestone requires be held constant."""


def validate_controlled_variables(
    configs: Sequence[ExperimentConfig], *, allowed_to_vary: Sequence[str] = ()
) -> None:
    """Raise if any `CONTROLLED_FIELDS` value differs across `configs`, except fields named in
    `allowed_to_vary`.

    Args:
        configs: Two or more `ExperimentConfig`s that are about to be
            compared (e.g. TARA-proper's run vs. an ablation's run, or
            two baselines' runs). Fewer than 2 configs trivially pass
            (nothing to compare).
        allowed_to_vary: Field names from `CONTROLLED_FIELDS` this
            specific comparison intentionally varies -- e.g.
            `("embedding_model_name",)` for comparing two A8 variants
            against each other, per
            `evaluation.ablations.definitions.AblationDefinition.controlled_variable_exceptions`.
            Any name here that is not actually in `CONTROLLED_FIELDS`
            is silently ignored (nothing to exempt).

    Raises:
        ControlledVariableMismatchError: If any non-exempted controlled
            field's value differs across `configs`. The error message
            names every mismatched field, its value under every
            `experiment_id` that disagreed, so the caller can act
            without re-deriving which configs are the problem.
    """
    if len(configs) < 2:
        return

    fields_to_check = [f for f in CONTROLLED_FIELDS if f not in allowed_to_vary]
    mismatches: dict[str, dict[str, object]] = {}

    baseline_config = configs[0]
    for field_name in fields_to_check:
        baseline_value = getattr(baseline_config, field_name)
        for config in configs[1:]:
            value = getattr(config, field_name)
            if value != baseline_value:
                bucket = mismatches.setdefault(field_name, {})
                bucket[baseline_config.experiment_id] = baseline_value
                bucket[config.experiment_id] = value

    if mismatches:
        details = "; ".join(
            f"{field_name}: {values!r}" for field_name, values in sorted(mismatches.items())
        )
        raise ControlledVariableMismatchError(
            f"Refusing to compare {len(configs)} experiment configs: {len(mismatches)} "
            f"controlled variable(s) differ where they were supposed to be held constant. "
            f"{details}. If this variation is intentional (e.g. an A8 embedding-model-swap "
            f"comparison), pass the field name(s) via allowed_to_vary explicitly."
        )
