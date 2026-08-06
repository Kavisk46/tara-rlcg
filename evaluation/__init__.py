"""TARA evaluation and dataset-construction tooling.

Everything under `evaluation/` is research/data-engineering code that
*depends on* the `tara` package but is not part of it: dataset builders,
metric implementations, baseline/ablation runners, and experiment
orchestration. It is held to a lighter testing bar than `src/tara`
(`PROJECT_SPEC.md` design principle 7), though individual subsystems
(e.g. `rts_builder`) may still be built to full production-quality
standards where warranted.
"""
from __future__ import annotations
