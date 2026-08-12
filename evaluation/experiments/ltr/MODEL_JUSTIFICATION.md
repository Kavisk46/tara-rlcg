# Model Justification — LightGBM LambdaRank vs. XGBoost Ranker vs. CatBoost Ranker

Phase 3 of the LTR experiment framework. This document justifies
choosing **LightGBM's `LGBMRanker` with `objective="lambdarank"`**
(`model.py`) over the two other mainstream gradient-boosted-tree
ranking implementations, XGBoost's `XGBRanker` and CatBoost's
`CatBoostRanker`, specifically for **this dataset**
(`evaluation/rts_builder/pilot/merged_dataset/`) — not as a
general-purpose claim that LightGBM is unconditionally the best
ranking library.

## Dataset characteristics that drive this decision

From `merged_dataset/dataset_statistics.md` and this framework's own
`dataset_inspection.py` (see `outputs/reports/phase1_dataset_inspection.md`):

- **160 queries, 439 candidate rows total** (before any train/
  validation/test split) — a genuinely small dataset by GBDT-ranking
  standards (public LTR benchmarks like MSLR-WEB10K have tens of
  thousands of queries).
- **Mean group size ~2.7-2.9 candidates/query**, min 1, max 7 — very
  small, low-cardinality groups. Most public ranking benchmarks assume
  groups of tens to hundreds of documents.
- **8 repositories, 7 query categories** as the two dominant
  categorical features, both low-cardinality (8 and 7 distinct values).
- Roughly 25-50 numeric features per row once retrieval-derived
  columns are included (`feature_pipeline.py`'s `FEATURE_COLUMNS`).
- **No real relevance grades exist yet** in RTS Dataset v1.0 (every
  `grade` is the placeholder `"TO_BE_ASSIGNED"` — see
  `dataset_inspection.py`'s findings). This decision is therefore made
  for a dataset of this *shape and scale*, without yet having any real
  label distribution to additionally condition on.

## Comparison

| Criterion | LightGBM `LGBMRanker` | XGBoost `XGBRanker` | CatBoost `CatBoostRanker` |
|---|---|---|---|
| Ranking objective | `lambdarank` (LambdaMART): mature, directly optimizes NDCG via lambda gradients; native `label_gain`/`eval_at` | `rank:ndcg` / `rank:pairwise` / `rank:map`: `rank:ndcg` is functionally similar LambdaMART-style but the categorical + ranking combination is newer and less battle-tested | `YetiRank`/`YetiRankPairwise` (strong, but tuned for larger candidate lists per query) or `PairLogit`/`PairLogitPairwise` (pairwise only, not listwise NDCG) -- CatBoost's own docs steer toward `PairLogit` for small group sizes like this dataset's, which is a weaker match for our "optimize NDCG@1/3/5 directly" objective |
| Categorical feature handling | Native, since early stable releases; fully compatible with `lambdarank` | `enable_categorical=True` support for ranking objectives is newer/less mature in the XGBoost release line pinned in `config.yaml`'s target environment | CatBoost's categorical handling (ordered target statistics) is its flagship feature and is excellent -- this is CatBoost's strongest point against LightGBM, see Caveats below |
| Tree growth strategy | Leaf-wise (`num_leaves`-bounded): reaches useful splits with less data per split, which matters directly for this dataset's small group sizes and total row count | Level-wise by default (`grow_policy="depthwise"`); can be set to `"lossguide"` (leaf-wise, LightGBM-style) but that is opting into non-default, less-tested behavior for XGBoost's ranking objectives specifically | Symmetric ("oblivious") trees by default: every node at a given depth splits on the same feature/threshold -- strong regularization by construction, but this project's dataset is small enough that LightGBM's leaf-wise + explicit `num_leaves`/`max_depth`/`min_child_samples` regularization (all exposed in `ModelConfig`) is judged to give more direct, tunable control for this specific dataset than CatBoost's structural regularization |
| Missing-value handling | Native (`NaN` routed to a learned default split direction) -- used directly by this pipeline's `*_available`/`NaN` convention for disabled retrieval features (`feature_pipeline._retrieval_columns_for_candidate`) | Native, similar mechanism | Native, similar mechanism |
| Dependency footprint | Pure Python + a self-contained compiled core; no GPU/CUDA assumption for CPU-only training (this project's target: a pilot-scale, laptop/CI-reproducible experiment, not a GPU cluster) | Similar footprint to LightGBM | Historically a heavier package (larger wheel, more bundled functionality e.g. built-in viz); not a blocker, just a minor consideration for a minimal reproducibility footprint |
| Ecosystem maturity for this exact combination (small groups + low-cardinality categoricals + LambdaRank/NDCG) | Well-trodden path; this is close to LightGBM's own official ranking example configuration | Works, but XGBoost's ranking documentation and community examples skew toward much larger candidate lists per query (e.g. search-engine-scale) | CatBoost's ranking tutorials and defaults also skew toward larger candidate lists; `YetiRank`'s pairwise-sampling machinery is designed to be efficient across many pairs per query, a benefit this dataset (≤7 candidates/query) cannot exploit |

## Decision

**LightGBM `LGBMRanker(objective="lambdarank")`**, for the combination
of (a) a native, mature listwise-NDCG objective that directly matches
this project's evaluation metrics (`evaluate.py`'s NDCG@1/3/5), (b)
leaf-wise growth that is a better fit for this dataset's very small
per-query group sizes and low total row count than either
competitor's default growth strategy, and (c) categorical support that
is both native and specifically proven-compatible with the ranking
objective in the release line this project pins.

## Caveats — when this decision should be revisited

This is not a claim that LightGBM dominates XGBoost/CatBoost in
general, only that it is the better fit for *this* dataset today:

1. **If RTS Dataset v1.0 grows substantially** (more repositories, or
   candidate-generation producing far larger per-query candidate
   lists), CatBoost's `YetiRankPairwise` becomes a much stronger
   competitor, since its pairwise-sampling efficiency advantage only
   materializes with larger group sizes.
2. **If high-cardinality categorical features are added** (e.g. a raw
   file-path or symbol-name categorical rather than this pipeline's
   coarse `file_extension_code`), CatBoost's ordered-target-statistics
   categorical encoding is likely to out-perform LightGBM's native
   categorical splitting, which degrades somewhat as cardinality grows
   into the thousands.
3. **If GPU training becomes necessary** (not currently justified by
   this dataset's size), all three libraries support it, but the
   comparison would need to be redone against each library's GPU
   -specific implementation, which was not evaluated here.
4. **This comparison is a priori (architectural/documentation-based),
   not empirical** -- no head-to-head benchmark of the three rankers
   was run against this dataset, both because RTS Dataset v1.0 has no
   real relevance grades yet (see this document's "Dataset
   characteristics" section) and because doing so is out of this
   phase's scope. Once real grades exist, re-running this comparison
   empirically (train all three on identical folds, compare
   NDCG@1/3/5) would be a natural follow-up and would either confirm
   or overturn this a priori decision.
