"""The TARA evaluation harness (M11).

query -> routing -> retrieval -> fusion -> generation -> metrics.

`evaluation.harness.runner.ExperimentRunner` executes this pipeline for
one query against one `Variant` (TARA-proper, or any baseline from
`evaluation.baselines`), producing a `evaluation.harness.models.QueryRunResult`
-- a machine-readable record covering plan/retrieval/generation output,
every metric family (`evaluation.metrics`), and per-stage latency.
`evaluation.harness.aggregation` rolls a batch of results up overall, and
per TaskType/repository/variant.

**This package runs no experiment against real data.** No TIQS query
exists yet (M9), and `ExperimentRunner` is exercised in this package's
own tests only against small, synthetic, in-memory fixtures -- mirroring
`evaluation.baselines`'s identical stance. Result and config files this
harness writes are the *only* legitimate way such files are produced;
per this milestone's own instruction, they must never be hand-edited.
"""
from __future__ import annotations
