"""RTS Builder Oracle Utility subsystem (Milestone 6).

Converts a `RetrievalExecutionResult` (Retrieval Executor's output,
accepted and frozen) plus an externally-supplied `RelevanceJudgment`
(ground-truth relevance grades) into an `OracleUtilityResult`: one
Learning-to-Rank-ready row per strategy, carrying Recall@k/MRR/NDCG
/Context Precision, latency (normalized per the frozen protocol),
Utility, rank, and label confidence. See `Architecture.md` for
architecture and design decisions, `Oracle_Math.md` for the full
mathematical formulation, and `REVIEW_RESPONSE.md` for an anticipated
-reviewer self-assessment.

Learning-to-Rank model training, the planner, task classification, the
LLM interface, and the dataset builder are later RTS Builder milestones
and are not present here.
"""
from __future__ import annotations
