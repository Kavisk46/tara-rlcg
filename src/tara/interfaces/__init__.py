"""Abstract contracts for every TARA pipeline stage.

Each pipeline stage (repository parsing, context extraction, task
classification, adaptive routing, retrieval, context fusion, code
generation) is defined here as an `abc.ABC`. Downstream code depends on
these interfaces rather than concrete implementations, so any stage's
implementation can be swapped without touching its callers
(Dependency Inversion, the "D" in SOLID).

Only stages with a shipped implementation have an interface module here
today; see the project README for the pipeline stages still on the
roadmap.
"""
from __future__ import annotations
