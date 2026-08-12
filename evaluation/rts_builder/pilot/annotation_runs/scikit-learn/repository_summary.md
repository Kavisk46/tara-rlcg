# Repository Summary — scikit-learn

Produced against the real local repository at
`C:\Projects\tara-rlcg\scikit-learn`, pinned commit
`9b9be3abddd88675c5dc2e3623e652cb7545a26c` (verified via `git
rev-parse HEAD` before any inspection began; `git describe --tags`
reports `1.8.0rc1-729-g9b9be3abdd`, a development snapshot 729 commits
past the `1.8.0rc1` tag; `sklearn/__init__.py`'s own `__version__` at
this commit is `"1.10.dev0"`). Every claim below traces to a direct
directory listing, `grep`, `wc -l`, or full-text read of the
repository at this commit — nothing is asserted from memory of
scikit-learn generally.

## 1. Project overview

scikit-learn is a Python machine-learning library built around a
consistent **estimator API**: objects implementing `fit`, and
(depending on type) `predict`, `transform`, `predict_proba`, or
`score`. The package lives under `sklearn/`; performance-critical
routines are implemented in Cython (`.pyx`/`.pxd` files confirmed
throughout `tree/`, `ensemble/_hist_gradient_boosting/`,
`metrics/_pairwise_distances_reduction/`, `preprocessing/`, `utils/`,
`datasets/`). Documentation-driven release notes at this commit are
managed via a **towncrier-style fragment system**: 55 individual
change-fragment files under `doc/whats_new/upcoming_changes/`
(confirmed and read in full this session), organized into per-module
subdirectories (e.g. `sklearn.ensemble/`, `sklearn.linear_model/`)
plus a few cross-cutting categories (`array-api/`, `callback/`,
`metadata-routing/`), destined for the in-development
`doc/whats_new/v1.10.rst`.

## 2. Architecture summary

- **`sklearn/base.py`**: the estimator API's foundation —
  `BaseEstimator` and the role-specific mixins (`ClassifierMixin`,
  `RegressorMixin`, `ClusterMixin`, `BiclusterMixin`,
  `TransformerMixin`, `OneToOneFeatureMixin`,
  `ClassNamePrefixFeaturesOutMixin`, `DensityMixin`, `OutlierMixin`,
  `MetaEstimatorMixin`, `MultiOutputMixin`, `_UnstableArchMixin`) that
  every concrete estimator composes from.
- **`sklearn/pipeline.py`**: `Pipeline` and `FeatureUnion`, the
  estimator-composition machinery chaining transformers and a final
  estimator.
- **`sklearn/model_selection/`**: cross-validation, hyperparameter
  search (`GridSearchCV`/`RandomizedSearchCV` in `_search.py`,
  successive-halving variants in `_search_successive_halving.py`),
  data splitting (`_split.py`), and validation utilities
  (`_validation.py`, including `cross_validate`/`cross_val_score`).
- **`sklearn/metrics/`**: classification/regression/ranking/pairwise
  metrics and scorers (`_classification.py`, `_regression.py`,
  `_ranking.py`, `pairwise.py`, `_scorer.py`), plus Cython-accelerated
  pairwise-distance reduction (`_pairwise_distances_reduction/`).
- **`sklearn/preprocessing/`**: data transformation (`_data.py`,
  `_discretization.py`, `_encoders.py`, `_function_transformer.py`,
  `_label.py`, `_polynomial.py`, `_target_encoder.py` plus a Cython
  `_target_encoder_fast.pyx`).
- **`sklearn/compose/`**: `ColumnTransformer`
  (`_column_transformer.py`) and `TransformedTargetRegressor`
  (`_target.py`) for combining transformers across column subsets or
  the target variable.
- **`sklearn/datasets/`**: loaders/fetchers for bundled and
  remote/real-world datasets, plus synthetic-data generators
  (`_samples_generator.py`).
- **`sklearn/utils/`**: the largest support package by file count —
  parameter validation (`_param_validation.py`), metadata routing
  (`_metadata_requests.py`), array-API compatibility
  (`_array_api.py`), estimator conformance checking
  (`estimator_checks.py`, 5,742 lines — the largest file confirmed in
  `utils/`), and numerous Cython-accelerated primitives.
- **Per-algorithm-family packages**: `linear_model/`, `tree/`,
  `ensemble/`, `svm/`, `neighbors/`, `cluster/`, `decomposition/`,
  `mixture/`, `naive_bayes.py`, `discriminant_analysis.py`,
  `gaussian_process/`, `neural_network/`, `manifold/`,
  `semi_supervised/`, `covariance/`, `cross_decomposition/`,
  `calibration.py`, `dummy.py`, `isotonic.py`, `kernel_ridge.py`,
  `kernel_approximation.py`, `random_projection.py`, `impute/`,
  `feature_extraction/`, `feature_selection/`, `multiclass.py`,
  `multioutput.py`, `frozen/`, `callback/`.

## 3. Important packages

Confirmed via directory listings of the packages below:

| Package | Role |
|---|---|
| `model_selection/` | Cross-validation, hyperparameter search, train/test splitting. |
| `metrics/` | Model-evaluation metrics and the scorer abstraction (`_scorer.py`) used by search/cross-validation. |
| `preprocessing/` | Feature scaling, encoding (`OneHotEncoder`, `OrdinalEncoder`, `TargetEncoder`), discretization. |
| `compose/` | `ColumnTransformer`, `TransformedTargetRegressor` — composing transformers across heterogeneous inputs. |
| `ensemble/` | Bagging, boosting (`_gb.py`, `_hist_gradient_boosting/`), random forests (`_forest.py`), stacking, voting, isolation forest. |
| `tree/` | Decision tree classifiers/regressors, with Cython-implemented splitting/partitioning/criteria. |
| `utils/` | Cross-cutting infrastructure: validation, metadata routing, array-API support, estimator conformance testing. |
| `datasets/` | Data loading/fetching/generation. |

## 4. Major modules

Confirmed by direct file reads and `grep -n "^class "` against the
files below:

- **`sklearn/base.py`** — defines `BaseEstimator` (line 165,
  inheriting `ReprHTMLMixin`, `_HTMLDocumentationLinkMixin`,
  `_MetadataRequester`) and 12 further mixin classes (lines 561-1234).
- **`sklearn/pipeline.py`** — defines `Pipeline` (line 93, inheriting
  `CallbackSupportMixin`, `_BaseComposition`) and `FeatureUnion` (line
  1626, inheriting `TransformerMixin`, `_BaseComposition`).
- **`sklearn/utils/estimator_checks.py`** (5,742 lines) — the
  estimator-conformance-testing framework (`check_estimator` and its
  many individual `check_*` functions), used both internally and by
  third-party estimator authors.
- **`sklearn/metrics/_ranking.py`** (2,353 lines), **`pairwise.py`**
  (2,695 lines), **`_regression.py`** (1,983 lines), **`_scorer.py`**
  (1,168 lines) — the largest files within `metrics/`.
- **`sklearn/model_selection/_search.py`** — `GridSearchCV`/
  `RandomizedSearchCV` implementation.
- **`sklearn/model_selection/_validation.py`** — `cross_validate`/
  `cross_val_score` implementation.
- **`sklearn/compose/_column_transformer.py`** — `ColumnTransformer`.
- **`sklearn/tree/_classes.py`** — `DecisionTreeClassifier`/
  `DecisionTreeRegressor` Python-level classes, backed by Cython
  `_tree.pyx`/`_splitter.pyx`/`_criterion.pyx`/`_partitioner.pyx`.
- **`sklearn/ensemble/_hist_gradient_boosting/`** — the
  histogram-based gradient boosting implementation
  (`HistGradientBoostingClassifier`/`Regressor`), confirmed as the
  subject of multiple 2026-era efficiency-focused changelog fragments
  (binning, prediction with categoricals).

## 5. Estimator execution flow

Confirmed from `base.py` and `pipeline.py`: a concrete estimator
subclasses `BaseEstimator` plus the mixin(s) matching its role
(`ClassifierMixin` for `.score()` via accuracy,
`RegressorMixin` for `.score()` via R², `TransformerMixin` for the
`fit_transform` convenience method built from `fit`+`transform`, etc.).
`fit(X, y=None, **fit_params)` mutates the estimator's own attributes
(scikit-learn convention: attributes learned during `fit` are suffixed
with `_`); depending on the mixin, `predict`/`transform`/
`predict_proba`/`score` are then available. Composite estimators
(`Pipeline`, `ColumnTransformer`, `FeatureUnion`,
`TransformedTargetRegressor`, and meta-estimators such as
`GridSearchCV`) wrap one or more inner estimators and delegate `fit`/
`predict`/`transform` calls to them in sequence or in combination,
using the **metadata routing** mechanism (`utils/_metadata_requests.py`)
to determine which fit parameters (e.g. `sample_weight`) are passed to
which sub-estimator — confirmed as an active area of change at this
commit via 4 separate `metadata-routing/` changelog fragments fixing
routing gaps in `Pipeline.fit_transform`/`fit_predict`,
`TransformedTargetRegressor`, `BaggingClassifier`, and several
`feature_selection`/`impute` meta-estimators used as intermediate
`Pipeline` steps.

## 6. Training/evaluation pipeline

Confirmed from `model_selection/_search.py`, `_validation.py`, and
`metrics/_scorer.py`: `cross_validate`/`cross_val_score`
(`_validation.py`) repeatedly fit a clone of an estimator on
training folds produced by a splitter (`_split.py`) and evaluate it
via a **scorer** (`_scorer.py`, built via `make_scorer` or a metric-name
string) on held-out folds. `GridSearchCV`/`RandomizedSearchCV`
(`_search.py`) wrap this cross-validation loop over a hyperparameter
grid/distribution, exposing `cv_results_` (and, per a confirmed
changelog fragment for `HalvingGridSearchCV`/`HalvingRandomSearchCV`,
a new `all_cv_results_` attribute covering every halving iteration,
not just the last). A `Pipeline` can itself be the estimator under
search, so preprocessing steps are refit within each fold — the
mechanism the `transform_input` parameter (confirmed changed in a
`sklearn.pipeline` changelog fragment, default now `("X_val",)`)
governs for validation-set-aware transformers.

## 7. Testing strategy

Confirmed via `sklearn/tests/` top-level listing: a mix of
per-mechanism test files (`test_base.py`, `test_calibration.py`,
`test_metadata_routing.py`, `test_metaestimators.py`,
`test_metaestimators_metadata_routing.py`, `test_docstrings.py`,
`test_docstring_parameters.py`,
`test_docstring_parameters_consistency.py`, `test_config.py`) plus
`test_common.py`, which (together with `utils/estimator_checks.py`,
5,742 lines, confirmed present) drives generic conformance checks
across every estimator in the library — the primary mechanism ensuring
new/changed estimators satisfy the shared `BaseEstimator` API
contract. Each algorithm-family subpackage (`ensemble/`, `tree/`,
`linear_model/`, etc., confirmed via their own `tests/` subdirectories)
additionally carries its own dedicated test suite.

## 8. Documentation structure

Confirmed via `doc/` listing: `doc/modules/` holds one narrative guide
per topic/subpackage (`clustering.rst`, `compose.rst`, `ensemble.rst`,
`grid_search.rst`, `impute.rst`, `cross_validation.rst`, etc., 20+
files confirmed in a partial listing). `doc/whats_new/` holds one
`.rst` file per released version (from `v0.13.rst` through the
in-development `v1.10.rst`) plus the `upcoming_changes/` fragment
directory (55 files, read in full this session — see §9). `examples/`
(top level of the repo) holds runnable example scripts organized by
topic (`applications/`, `bicluster/`, `calibration/`, `callbacks/`,
`classification/`, `cluster/`, `compose/`, `covariance/`,
`cross_decomposition/`, `datasets/`, `decomposition/`,
`developing_estimators/`, `ensemble/`, `feature_selection/`,
`frozen/`, `gaussian_process/`, `impute/`, `inspection/`,
`kernel_approximation/`, and more — 20+ subdirectories confirmed in a
partial listing).

## 9. Potential annotation challenges

- **A very large number of behaviors are already fixed/implemented at
  this pinned commit and must NOT be described as open Bug Fix or
  Feature targets** in Phase 2's queries — all 55 changelog fragments
  under `doc/whats_new/upcoming_changes/` were read in full this
  session (only 251 total lines, unusually terse per-fragment
  compared to prior pilot repositories), covering: array-API
  compatibility fixes/features across `LedoitWolf`,
  `LogisticRegressionCV`, `LogisticRegression`, `matthews_corrcoef`,
  `median_absolute_error`, `det_curve`/`roc_curve`/`zero_one_loss`/
  `jaccard_score`/`balanced_accuracy_score`/`cohen_kappa_score`,
  `precision_recall_fscore_support` and related F-score functions,
  `PoissonRegressor`; metadata-routing fixes across `Pipeline`,
  `TransformedTargetRegressor`, `BaggingClassifier`, and several
  `feature_selection`/`impute` meta-estimators; bug fixes in `DBSCAN`,
  `fetch_openml`, `LinearDiscriminantAnalysis`/
  `QuadraticDiscriminantAnalysis`, `average_precision_score`,
  `LinearSVR` (memory leak), `LinearSVC` (out-of-bound write); new
  features/enhancements in `calibration_curve`/`CalibrationDisplay`
  (`n_bins="cube_root"`), GLM solvers (`newton-cg`, and a new
  `newton-cd-gram` solver with L1/Elastic-Net support),
  `NeighborhoodComponentsAnalysis` (sparse `init`), `IterativeImputer`
  (no longer experimental), `DecisionTreeClassifier`/`Regressor`
  (native categorical-feature support, up to 256 categories),
  `plot_tree`/`export_graphviz` (`fill_colors`); API
  deprecations/changes in `ScoringMonitor`,
  `enable_hist_gradient_boosting`, `DecisionBoundaryDisplay`
  (`multiclass_colors`→`target_colors`),
  `precision_recall_fscore_support`'s `average` default,
  `DetCurveDisplay` (`estimator_name`→`name`), `HalvingGridSearchCV`/
  `HalvingRandomSearchCV` (new `all_cv_results_`), `BallTree`/`KDTree`
  statistics; and roughly a dozen efficiency improvements across
  `GradientBoostingClassifier`, `HistGradientBoostingClassifier`/
  `Regressor`, `RandomForestClassifier`, `nan_euclidean_distances`,
  the `newton-cholesky` solver, `ElasticNetCV`/`LassoCV`/
  `MultiTaskElasticNetCV`, `make_scorer`, `GaussianMixture`,
  `KNeighborsRegressor`/`Classifier`, `OneHotEncoder`/
  `OrdinalEncoder`/`TargetEncoder`. Given the sheer volume (55
  individual entries), Phase 2 query authoring cross-checks candidate
  topics against this full list directly (all fragments were read, not
  sampled) rather than against a subset, and documents which specific
  fragment(s) were checked in each query's `notes` field where
  relevant.
- **Cython (`.pyx`/`.pxd`) implementation details are largely opaque
  to static inspection** — source is readable, but compiled behavior
  of performance-critical paths (tree splitting, histogram-based
  boosting, pairwise-distance reduction) cannot be verified without
  building the extension modules, which this session did not do.
- **Extremely broad surface area relative to the fixed 20-query
  budget**: dozens of algorithm-family subpackages plus the large
  cross-cutting `utils/`, `model_selection/`, and `metrics/` packages
  mean only a small fraction can be represented in any single
  annotation round.

## 10. Threats to validity

- **Single-session, single-pass repository inspection** — not
  independently cross-checked by a second reviewer or a second AI
  pass, consistent with every prior pilot run in this project.
- **All 55 `upcoming_changes/` fragments were read in full, but
  scikit-learn's much longer historical changelog (`v0.13.rst` through
  `v1.9.rst`, dozens of files) was not** — an already-fixed issue from
  an earlier release cycle that happens to resemble a plausible
  bug-fix query topic could exist undetected outside the window
  actually read.
- **No code was executed, no test was run, and no Cython extension
  was built or profiled** — all findings are static-inspection-only,
  consistent with every prior pilot run.
- **Development snapshot version**: `1.8.0rc1-729-g...`
  (`__version__ == "1.10.dev0"`) is a development snapshot well past
  the most recent release candidate tag, not a tagged release itself;
  APIs and behaviors documented in the `upcoming_changes/` fragments
  may still change before an actual 1.10.0 release.
- **Scale relative to the fixed query budget**: with dozens of
  algorithm-family subpackages, extensive Cython internals, and a very
  large `utils/`/`model_selection/`/`metrics/` cross-cutting surface,
  20 queries can only sample a very small fraction of the overall
  codebase — the same acute coverage caveat already raised for Celery,
  SQLAlchemy, and pandas in this project's prior pilot runs.
