"""Metric implementations for the TARA evaluation harness (M11).

One module per metric family, per `ROADMAP.md` M10's proposed layout:
`retrieval.py`, `generation.py`, `efficiency.py`. Every metric function
here is a pure function over already-computed inputs (a retrieved-id
list, a ground-truth set, a candidate/reference string pair) -- none of
them runs a retriever, calls an LLM, or executes generated code. This
package is research code (`ROADMAP.md` M10 / `PROJECT_SPEC.md` §14
design principle 7): it lives outside `src/tara` and depends on `tara`
only for the Tree-sitter parsing infrastructure `syntactic_validity`
reuses.

Per `EXPERIMENT_PLAN.md` §3 and this milestone's own instructions, three
metrics named in the project's specification are deliberately **not**
implemented here, with the gap disclosed rather than papered over:

- **CodeBLEU** -- `PROJECT_SPEC.md` §13/§25 mark the choice of
  implementation library as still TBD; no dependency decision has been
  made, and adding one speculatively would not be "justified and
  reproducible" as this milestone's instructions require.
- **pass@k's underlying execution** -- the unbiased *estimator*
  (`generation.pass_at_k`) is implemented and tested, but computing its
  `n`/`c` inputs requires actually running generated code against a
  test harness, which `PROJECT_SPEC.md` §8 explicitly places out of
  scope (no sandboxed executor is built by this project). Callers with
  their own execution results may still use the estimator.
- **NDCG@k** is implemented but returns `None` whenever graded
  relevance judgments are not supplied, per `EXPERIMENT_PLAN.md` §3:
  "if only binary relevance is captured, NDCG@k is reported as not
  applicable rather than computed from an artificially graded proxy."
"""
from __future__ import annotations
