"""RTS Builder Pilot subsystem (scientific validation phase, first pilot RTS).

Consumes the frozen, accepted Dataset Builder subsystem's output
(`evaluation.rts_builder.dataset_builder.DatasetGenerator`) unmodified
and adds exactly what a first pilot dataset needs before it is
"immediately usable for Learning-to-Rank": a deterministic
train/validation/test split, automated validation (missing values,
duplicates, distributions, the four Success Criteria), quality-report
figures, and dataset documentation (`README.md`, `DATASET_CARD.md`,
`validation_report.md`).

Repository Loader, Parser, Feature Extraction, Retrieval Executor,
Oracle Utility, and Dataset Builder are not modified or redesigned by
this subsystem -- see `README.md`'s Architecture section for exactly
where the boundary sits. Learning-to-Rank model training, the planner,
task classification, LLM inference, and paper writing are not present
here.
"""
from __future__ import annotations
