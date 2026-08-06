"""RTS Builder Feature Extraction subsystem (Milestone 4).

Converts a `RepositoryModel` (Parser's output, Python-only V1, accepted
and frozen) plus a developer query into a normalized `FeatureVector`:
Query, Repository, Graph, Structural, and Resource feature groups,
suitable for machine learning (`FeatureVector.to_flat_dict`). See
`README.md` for architecture and design decisions, `FEATURE_CATALOG.md`
for the full feature reference, and `REVIEW_RESPONSE.md` for an
anticipated-reviewer self-assessment.

Task classification, oracle utility computation, retrieval, the router,
the planner, Learning-to-Rank, embeddings, and the LLM interface are
later RTS Builder milestones and are not present here.
"""
from __future__ import annotations
