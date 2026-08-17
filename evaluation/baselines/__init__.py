"""Evaluation baselines: fixed, non-adaptive retrieval configurations compared against TARA.

Per `PROJECT_SPEC.md` §24 / `EXPERIMENT_PLAN.md` §4 and this milestone's
own task instructions. This package is **research code, not library
code** (`ROADMAP.md` M10, `PROJECT_SPEC.md` §14 design principle 7): it
depends on `tara` but lives outside `src/tara`, and is held to a lighter
testing bar than the core pipeline stages.

**No experiment is run by this package.** It implements baseline
*interfaces and configuration* only: which fixed strategy each baseline
uses (`evaluation.baselines.definitions`), how a fixed strategy is
turned into a `RetrievalPlan` **without constructing or calling
`AdaptiveRouter`, `RoutingPolicy`, or `TaskClassifier` at all**
(`evaluation.baselines.plan_builder` -- reusing only `RetrievalPlanner`,
which makes no strategy-selection decision of its own), and a runner
that executes one baseline's full retrieve -> fuse -> generate pipeline
for one query (`evaluation.baselines.runner`). No baseline is run
against a real repository corpus or real TIQS queries here, and no
result is reported -- see `BASELINE_DISCREPANCIES.md` in this directory
for the naming/scope decisions made relative to `PROJECT_SPEC.md` §24
and `EXPERIMENT_PLAN.md` §4, including why this package no longer builds
baselines on top of `AdaptiveRouter`.
"""
from __future__ import annotations
