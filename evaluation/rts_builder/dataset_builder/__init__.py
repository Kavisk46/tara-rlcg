"""RTS Builder Dataset Builder subsystem (Milestone 7 -- final assembly stage).

Composes all five prior, accepted-and-frozen RTS Builder milestones
(Repository Loader, Parser, Feature Extraction, Retrieval Executor,
Oracle Utility) into one end-to-end pipeline, driven across a
repository manifest and query population, producing the Retrieval
Training Set: a long-format dataset (JSONL/CSV/Parquet, one row per
`(query, strategy)`) and a grouped dataset (JSONL, one record per
query), with streaming writes, checkpoint/resume support, and dataset
statistics.

See `README.md` for usage and design decisions, `Pipeline.md` for the
full stage-by-stage data-flow diagram, `DatasetSchema.md` for the
complete output schema, and `REVIEW_RESPONSE.md` for an anticipated
-reviewer self-assessment.

Learning-to-Rank model training, the planner, the LLM interface, and
task classification are not present here.
"""
from __future__ import annotations
