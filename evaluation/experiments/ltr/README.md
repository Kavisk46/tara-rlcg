# TARA RTS Learning-to-Rank Experiment Framework

A complete, reproducible Learning-to-Rank (LTR) pipeline for the TARA
RTS Dataset v1.0 (`evaluation/rts_builder/pilot/merged_dataset/`,
frozen). Learns `f(features) -> ranking` over candidate files retrieved
by four independent strategies -- **Lexical, Dense, Graph, and
Hybrid** -- using a LightGBM `LGBMRanker` with the `lambdarank`
objective.

This is an **experiment framework**, not a completed experiment. See
["Current dataset status"](#current-dataset-status) below before
running anything -- it explains, honestly, what this pipeline can and
cannot do against the dataset as currently shipped.

## Current dataset status

**RTS Dataset v1.0 ships with every relevance grade set to the
placeholder `"TO_BE_ASSIGNED"`** (see
`merged_dataset/dataset_card.md`, "Quality control"). Confirmed by
actually running this framework's own Phase 1 dataset inspection
against the real dataset (`outputs/reports/phase1_dataset_inspection.md`,
already generated and committed):

- train: 303 candidate rows, **0** with a real numeric grade.
- validation: 67 candidate rows, **0** with a real numeric grade.
- test: 69 candidate rows, **0** with a real numeric grade.

**Consequently, `train.py` cannot train a real model against this
dataset today, and this framework does not claim otherwise.**
`feature_pipeline.validate_labels_are_numeric` is called before any
feature construction in `train.py`, `evaluate.py`, and
`error_analysis.py`, and raises `UnlabeledDatasetError` with a clear
message when a split is fully unlabeled -- this is **verified,
intentional, correct behavior**, demonstrated by actually running it:

```
$ python -m evaluation.experiments.ltr.train --config config.yaml
...
evaluation.experiments.ltr.feature_pipeline.UnlabeledDatasetError: train: all 303
candidate rows have the placeholder grade 'TO_BE_ASSIGNED'. RTS Dataset v1.0 ships
without human-assigned relevance grades ... Refusing to proceed rather than
fabricate labels.
```

Once human annotation (per each repository's own
`human_annotation_checklist.md` under `annotation_runs/`) replaces
`"TO_BE_ASSIGNED"` with real integers in `{0, 1, 2, 3}` for enough of
the dataset, this exact pipeline runs end-to-end with no code changes.

## What was actually run, and what was not

In the spirit of this project's "never fabricate" standard, here is
exactly what this framework's own development session verified by
actually executing it, versus what it did not:

| Claim | Status |
|---|---|
| Phase 1 dataset inspection against the real train/validation/test files | **Run for real.** See `outputs/reports/phase1_dataset_inspection.md`. |
| Feature pipeline structural/categorical logic (no retrieval) against the real train split | **Run for real.** 303 rows x 27 columns produced. |
| Feature pipeline **with real retrieval features**, invoking the frozen Repository Loader -> Parser -> Feature Extraction -> Retrieval Executor chain, against a real repository (`click`, all 14 of its `train.jsonl` queries) | **Run for real.** 37 rows x 52 columns, genuine lexical/dense/graph/hybrid scores computed from `click`'s actual pinned-commit source. Log excerpt: `Executed all retrieval strategies for click@00e592ce: lexical=10 dense=10 graph=10 hybrid=10 files retrieved`, repeated for 13 more queries. |
| The same, for all 8 repositories across the full train split | **Attempted, not completed.** Started; celery, click, fastapi, and part of flask finished successfully (each producing genuine retrieval results) before the run was stopped to reclaim compute for finishing and testing the rest of this framework. Parsing `pandas` and `scikit-learn` (255+ and dozens-of-subpackage repositories respectively) is the dominant remaining cost -- a full run is expected to take significantly longer than the smaller six repositories combined. Re-running `python -m evaluation.experiments.ltr.feature_pipeline --split train` to completion (it will reuse the Parser subsystem's own on-disk cache for the repositories already parsed) is the natural next step, not performed here. |
| `model.py`'s fit/predict/save/load/checkpoint/resume-from-checkpoint | **Run for real**, on small synthetic data (never presented as a ranking-quality result -- see `tests/test_model.py`). Verified: predictions survive a save/load round-trip exactly (`np.allclose`); resuming from a checkpoint saved at iteration 15 and training 5 more iterations produces a model with exactly 20 trees. |
| `evaluate.py`'s 7 metrics (NDCG@1/3/5, MRR, Precision@1, Recall@1, Top-1 Accuracy) | **Verified against hand-computed values** for several small synthetic examples (perfect ranking, worst-case ranking, no-relevant-items). See `tests/test_evaluate.py`. |
| `train.py` refusing to train against the real, unlabeled dataset | **Run for real.** See the traceback above. |
| **Any actual trained-model ranking-quality result (NDCG, MRR, etc.) against RTS Dataset v1.0** | **Does not exist and is not claimed.** Cannot exist until real relevance grades are assigned -- see "Current dataset status". |
| Full unit test suite (70 tests) | **Run for real: 70 passed, 0 failed** (`python -m pytest evaluation/experiments/ltr/tests`). |

## Architecture

```
config.yaml            -- all hyperparameters, seed, paths (Phase 8)
dataset_inspection.py  -- Phase 1: load/validate/profile train/validation/test
feature_pipeline.py    -- Phase 2: raw rows -> numeric feature matrix
model.py                -- Phase 3: LGBMRanker(lambdarank) wrapper
MODEL_JUSTIFICATION.md -- Phase 3: LightGBM vs. XGBoost vs. CatBoost, in depth
train.py                -- Phase 4: config-driven training entry point
evaluate.py              -- Phase 5: NDCG@1/3/5, MRR, P@1, R@1, Top-1 Accuracy
importance.py            -- Phase 6: Gain / Split / SHAP + plots
error_analysis.py        -- Phase 7: repository / query / confidence failure analysis
utils.py                  -- shared seeding, logging, JSONL I/O
tests/                    -- 70 unit tests, all synthetic-fixture-based
outputs/
  models/<run_id>/        -- model.txt, encoders.json, run_manifest.json, checkpoints/
  figures/                 -- importance plots (.png)
  reports/                 -- Markdown + JSON reports from every phase
  retrieval_cache/          -- feature_pipeline.py's on-disk retrieval-result cache
```

## Setup

From the repository root (`C:\Projects\tara-rlcg`):

```bash
# 1. Install the frozen `tara`/`evaluation` packages in editable mode
#    (required for feature_pipeline.py's real retrieval integration --
#    see "Dependencies" below for what this pulls in).
python -m pip install -e .

# 2. Install this framework's own additional dependencies (not part of
#    the base `tara` package -- see requirements.txt).
python -m pip install -r evaluation/experiments/ltr/requirements.txt
```

### Dependencies

- The base `tara` package (`pip install -e .` from the repo root)
  provides `pydantic`, `networkx`, `tree-sitter`, `gitpython`,
  `sentence-transformers`, `torch`, etc. -- everything
  `feature_pipeline.RetrievalFeatureProvider` needs to invoke the
  frozen Repository Loader / Parser / Feature Extraction / Retrieval
  Executor subsystems. Dense retrieval's default embedder
  (`HashingEmbedder`, feature hashing) does **not** require downloading
  any model weights or network access.
- This framework's own `requirements.txt` adds `lightgbm`, `shap`,
  `matplotlib` (already present via the base install), and `pyyaml`
  (also already present via the base install's `dev` extra).

## Reproducing what this session verified

```bash
# Phase 1 -- real, against the real dataset:
python -m evaluation.experiments.ltr.dataset_inspection

# Phase 2 -- real structural features, fast (no retrieval):
python -m evaluation.experiments.ltr.feature_pipeline --split train --no-retrieval --allow-unlabeled

# Phase 2 -- real retrieval features, against one small repository (~25s):
python -m evaluation.experiments.ltr.feature_pipeline --split train --repositories click --allow-unlabeled

# Unit tests (70 tests, ~3 minutes on this project's reference machine,
# dominated by LightGBM's own fit/predict calls in test_model.py):
python -m pytest evaluation/experiments/ltr/tests -v

# Confirm training honestly refuses on the unlabeled dataset:
python -m evaluation.experiments.ltr.train --config evaluation/experiments/ltr/config.yaml
```

## How to train (once real labels exist)

```bash
python -m evaluation.experiments.ltr.train --config evaluation/experiments/ltr/config.yaml
```

Writes `outputs/models/<run_id>/{model.txt, model.txt.meta.json,
encoders.json, run_manifest.json}`. `run_manifest.json` records the
exact config used, a SHA-256 digest of the train/validation split
files, the git commit, and a timestamp -- everything needed to
reproduce or audit the run later.

**Resuming an interrupted run**: with `checkpoint_every` set in
`config.yaml` (default: every 25 boosting iterations), pass
`--resume-from outputs/models/<run_id>/checkpoints/checkpoint_iter_<N>.txt`
to continue from the latest checkpoint rather than restarting.

## How to evaluate

```bash
python -m evaluation.experiments.ltr.evaluate \
  --split test \
  --model-path outputs/models/<run_id>/model.txt \
  --encoders-path outputs/models/<run_id>/encoders.json
```

Computes NDCG@1/3/5, MRR, Precision@1, Recall@1, and Top-1 Accuracy
(see `evaluate.py`'s module docstring for each metric's exact
definition) and writes `outputs/reports/phase5_evaluation_test.{md,json}`.

## How to analyze feature importance

```bash
# First, materialize a feature matrix to explain (e.g. the training set):
python -m evaluation.experiments.ltr.feature_pipeline --split train

python -m evaluation.experiments.ltr.importance \
  --model-path outputs/models/<run_id>/model.txt \
  --features-npz outputs/features_train.npz
```

Writes `outputs/figures/importance_{gain,split,shap_summary}.png` and
`outputs/reports/phase6_feature_importance.{md,json}`.

## How to run error analysis

```bash
python -m evaluation.experiments.ltr.error_analysis \
  --split test \
  --model-path outputs/models/<run_id>/model.txt \
  --encoders-path outputs/models/<run_id>/encoders.json
```

Writes `outputs/reports/phase7_error_analysis_test.{md,json}`:
per-repository and per-category top-1 accuracy/NDCG@5, the 20 worst
-NDCG queries with their predicted-vs-true top file, and the subset of
wrong predictions the model was nonetheless confident about (a large
score margin between its top-1 and runner-up choice).

## Reproducibility

- **Seed**: `config.yaml`'s `seed` (default `42`) is applied to
  Python's `random`, NumPy, `PYTHONHASHSEED`, and LightGBM's
  `random_state`/`seed` via `utils.set_global_seed` and
  `model.ModelConfig.random_state`, called at the start of `train.train`.
- **Determinism**: `feature_pipeline.CategoryEncoder` always sorts its
  vocabulary before assigning codes (order-of-observation-independent);
  `feature_pipeline.build_feature_matrix`'s column order
  (`FEATURE_COLUMNS`-equivalent) is fixed and never depends on
  dict/set iteration order.
- **Every run's exact configuration is captured**: `run_manifest.json`
  (see "How to train") records the full config, split-file digests,
  and git commit for every training run.
- **Model format**: `LambdaRankModel.save`/`load` use LightGBM's own
  native text format (`Booster.save_model`/`Booster(model_file=...)`),
  which is stable across LightGBM versions within a major release line
  and human-readable.

## Publication-quality checklist (Phase 10)

- **Modular**: each phase is its own module with a single public entry
  point (a `main(argv)` CLI function) and a set of independently
  -importable, independently-testable functions/classes.
- **Documented**: every public function/class has a docstring stating
  its args, return value, and the exceptions it raises; every module
  has a module-level docstring explaining its role in the pipeline.
- **Typed**: every function signature in every module under this
  directory is fully type-annotated (`from __future__ import annotations`
  used throughout for forward-reference-friendly typing).
- **Tested**: 70 unit tests across 5 test files, covering every
  module's core logic (`tests/`), all passing against synthetic
  fixtures with analytically-verifiable expected values -- never
  against fabricated "experiment results".
- **Reproducible**: see "Reproducibility" above.

## Known limitations

1. **No real relevance grades exist yet** -- the single largest
   limitation, discussed at length above. Every metric this framework
   can compute today is either a unit-test check against synthetic
   data or a structural/schema diagnostic against the real dataset,
   never a real ranking-quality result.
2. **Full-dataset retrieval-feature extraction was not completed** in
   this session (see "What was actually run"). The two largest
   repositories (`pandas`, `scikit-learn`) are the dominant remaining
   cost; a full run should be expected to take substantially longer
   than the six smaller repositories combined and was not budgeted for
   within this development session.
3. **The enum-valued `repo_dominant_language` feature's fixed
   vocabulary** (`feature_pipeline.ENUM_COLUMN_VOCABULARIES`) is
   hardcoded from `tara.core.types.Language`'s current member list; if
   that frozen enum ever gains a new language, this framework's
   vocabulary must be updated to match (it will not silently break --
   an unrecognized value is logged and mapped to an explicit "unknown"
   code, never miscoded as an existing language).
4. **SHAP's `TreeExplainer`** is used with default settings
   (`feature_perturbation` left at its LightGBM-appropriate default);
   no alternative explainer or perturbation strategy was evaluated.
5. **This a priori model comparison (`MODEL_JUSTIFICATION.md`) has no
   empirical backing yet** -- see that document's final "Caveats"
   section.

## License / provenance

This framework consumes `merged_dataset/`'s data under the same terms
documented in that directory's own `dataset_card.md` ("License
considerations"). No new license obligations are introduced by this
framework's own code.
