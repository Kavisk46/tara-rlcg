"""The TARA ablation experiment framework (M12).

Per `PROJECT_SPEC.md` §26 / `EXPERIMENT_PLAN.md` §5, restated by this
milestone's own instructions as A1-A9. Each ablation, where supported,
is implemented as a small, composable wiring primitive (a `RoutingPolicy`
variant, a `Router` decorator, a `RepositoryContext` transform, or a
plain configuration value) that changes **exactly one** mechanism
relative to TARA's real, unablated pipeline -- never a parallel
reimplementation of retrieval/fusion/generation logic. `evaluation.ablations.definitions`
is the single source of truth for which of A1-A9 are actually
implemented here (`AblationStatus.SUPPORTED`) versus explicitly
unsupported/TBD, with the reason stated machine-readably, not just in
prose.

**This package runs no experiment and reports no result.** It provides
the configuration/wiring primitives an experiment runner (M11's
`evaluation.harness.runner.ExperimentRunner`) would use to actually
execute an ablation -- every test in this package exercises those
primitives against small, synthetic, in-memory fixtures only.
"""
from __future__ import annotations
