"""RTS (Retrieval Training Set) Builder.

The data-construction pipeline that produces the training set for the
Learning-to-Rank retrieval router (`docs/methodology/RANKER_DESIGN.md`),
per `docs/DATASET_BUILDER_SPEC.md`. Implemented one milestone at a time;
this package currently implements Milestone 1 (Repository Loader,
`docs/DATASET_BUILDER_SPEC.md` §2 Stage 0, accepted and frozen -- see
`repository_loader.py`), Milestone 2 (Parser, Stage 1 "Repository
Preprocessing", Python-only V1, accepted and frozen -- see `parser/`),
Milestone 4 (Feature Extraction, accepted and frozen -- see
`feature_extraction/`; its feature groups deliberately diverge from
`DATASET_BUILDER_SPEC.md` §6), and Milestone 5 (Retrieval Executor,
`retrieval_executor/`: executes Lexical, Dense, Graph, and Hybrid
retrieval independently for every query). Query generation, task
annotation, oracle utility computation, ranking generation, and the
dataset writer are later milestones and are not present here.
"""
from __future__ import annotations
