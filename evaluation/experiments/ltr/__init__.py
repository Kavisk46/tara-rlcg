"""Learning-to-Rank experiment framework for the TARA RTS Dataset v1.0.

Consumes `evaluation/rts_builder/pilot/merged_dataset/` (frozen) and,
for feature construction, the frozen Feature Extraction and Retrieval
Executor subsystems under `evaluation.rts_builder`. Trains a LightGBM
LambdaRank model to rank candidate files for a developer query.

Modules:
    dataset_inspection: Phase 1 -- load, validate, and profile the split files.
    feature_pipeline:   Phase 2 -- turn raw query/candidate rows into a numeric feature matrix.
    model:               Phase 3 -- the LambdaRank model wrapper.
    train:               Phase 4 -- the training entry point (CLI).
    evaluate:            Phase 5 -- ranking-metric computation (CLI).
    importance:          Phase 6 -- gain/split/SHAP feature-importance analysis (CLI).
    error_analysis:      Phase 7 -- systematic failure-mode analysis (CLI).
    utils:               Shared seeding, logging, and I/O helpers.
"""

__version__ = "1.0.0"
