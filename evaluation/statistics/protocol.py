"""The fixed statistical protocol: every method/threshold choice, pinned in one place.

Per this milestone's instruction: "The statistical protocol must be
fixed BEFORE looking at final outcomes." Every default value below is
copied directly from `EXPERIMENT_PLAN.md` §6, a document written and
frozen before any real TIQS query or real experimental result existed
anywhere in this project (`EXPERIMENT_PLAN.md`'s own header states this
pre-registration discipline explicitly). `StatisticalProtocol` exists to
make that already-fixed protocol *executable* -- a single object every
analysis function in `evaluation.statistics` takes as a parameter --
not to define a new one, and not to leave any method choice to be
decided ad hoc once real data is in hand.

**"Do not select a statistical test simply because it gives a favorable
p-value"**: the paired-test choice is not a `StatisticalProtocol` field
at all -- it is a fixed function of a metric's `kind` (continuous vs.
binary), see `evaluation.statistics.metrics_registry.select_paired_test_name`.
Making it data-independent, rather than configurable per call, is
deliberate: there is no parameter here a caller could tune per-metric
after seeing a result to steer the test choice.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatisticalProtocol:
    """The complete, fixed statistical protocol for one experimental run's analysis.

    Every `evaluation.statistics.paired_comparison` function takes one of
    these rather than loose keyword arguments, so an analysis script's
    entire method/threshold configuration is visible and auditable at
    one call site, and so two analyses run under two different
    `StatisticalProtocol` instances are trivially distinguishable.
    """

    alpha: float = 0.05
    """Family-wise significance level, per `EXPERIMENT_PLAN.md` §6 ("Two-sided, α = 0.05")."""

    ci_confidence_level: float = 0.95
    """Per `EXPERIMENT_PLAN.md` §6's BCa bootstrap specification."""

    ci_n_resamples: int = 10_000
    """Per `EXPERIMENT_PLAN.md` §6: "bias-corrected and accelerated (BCa) bootstrap, 10,000
    resamples.\""""

    ci_seed: int | None = None
    """`None` by default (non-reproducible entropy, fine for this package's own tests, which
    check properties rather than exact bootstrap values). A real, pre-registered experimental
    run MUST set this to a fixed integer before execution and record that value in the
    corresponding `evaluation.harness.models.ExperimentConfig` -- CI reproducibility depends on
    it, per M11's "store every experiment configuration alongside results" requirement."""

    def __post_init__(self) -> None:
        if not (0 < self.alpha < 1):
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha!r}.")
        if not (0 < self.ci_confidence_level < 1):
            raise ValueError(
                f"ci_confidence_level must be in (0, 1), got {self.ci_confidence_level!r}."
            )
        if self.ci_n_resamples < 1:
            raise ValueError(f"ci_n_resamples must be >= 1, got {self.ci_n_resamples!r}.")


DEFAULT_PROTOCOL = StatisticalProtocol()
"""The frozen, pre-registered default -- `EXPERIMENT_PLAN.md` §6 exactly. Use this unless a
specific experimental run has its own recorded, deliberately-different protocol (which would
itself need to be pre-registered before that run, not chosen after)."""
