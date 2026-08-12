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
`DATASET_BUILDER_SPEC.md` §6), Milestone 5 (Retrieval Executor,
accepted and frozen -- see `retrieval_executor/`: executes Lexical,
Dense, Graph, and Hybrid retrieval independently for every query), and
Milestone 6 (Oracle Utility, accepted and frozen -- see `oracle_utility/`:
computes Learning-to-Rank supervision labels -- Quality, normalized
Latency, Utility, rank, and confidence -- per
`docs/DATASET_BUILDER_SPEC.md` §8-9), Milestone 7 (Dataset Builder,
`dataset_builder/`: the final assembly stage -- composes all five prior
milestones into one end-to-end, checkpointed, streaming-export pipeline
producing the Retrieval Training Set itself, in long-format and grouped
JSONL/CSV/Parquet), and the Pilot subsystem (`pilot/`: the scientific
-validation-phase stage -- runs Dataset Builder unmodified, then adds a
deterministic train/validation/test split, automated validation against
the pilot's Success Criteria, quality-report figures, and dataset
documentation, producing the first pilot Retrieval Training Set).
Query generation, task annotation, and Learning-to-Rank model training
are not implemented anywhere in this package -- they are external,
human/LLM-driven inputs and a later, separate consumer of this
package's output, respectively.
"""
from __future__ import annotations
