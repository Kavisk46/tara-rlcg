"""TIQS: the Task-Intent Query Set, TARA's evaluation dataset.

Per PROJECT_SPEC.md §22 and DATASET_PLAN.md.

This package formalizes `DATASET_PLAN.md`'s already-accepted design into
a concrete, machine-validatable schema (`evaluation.tiqs.models`) and a
validator (`evaluation.tiqs.validation`). It ships **no annotated query
content** -- as of this milestone, no TIQS annotation has been performed
under the protocol `DATASET_PLAN.md` specifies (see that document's own
status line: "No dataset construction described in this document has
occurred yet"). `evaluation/tiqs/schema_example/` contains a small,
explicitly-labeled synthetic fixture used only to test the schema and
validator -- never real annotation content.

See `TIQS_SCHEMA.md` in this directory for the full schema specification
and its mapping to RQ1-RQ5.
"""
from __future__ import annotations
