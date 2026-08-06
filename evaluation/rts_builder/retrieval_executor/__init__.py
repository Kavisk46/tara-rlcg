"""RTS Builder Retrieval Executor subsystem (Milestone 5).

Given a `RepositoryModel` (Parser's output), a `FeatureVector` (Feature
Extraction's output), and a developer query -- both prior milestones
accepted and frozen -- executes all four candidate retrieval strategies
(Lexical, Dense, Graph, Hybrid) independently and unconditionally,
collecting each strategy's retrieved files, retrieval score, retrieval
latency, and context token count. See `README.md` for architecture and
design decisions, `STRATEGY_COMPARISON.md` for a side-by-side strategy
comparison, and `REVIEW_RESPONSE.md` for an anticipated-reviewer self
-assessment and failure-mode catalog.

Oracle utility computation, the planner, Learning-to-Rank, task
classification, the LLM interface, and the dataset writer are later RTS
Builder milestones and are not present here.
"""
from __future__ import annotations
