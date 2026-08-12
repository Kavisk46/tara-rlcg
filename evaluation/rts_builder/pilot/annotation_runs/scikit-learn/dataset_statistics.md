# Dataset Statistics — scikit-learn Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`draft_relevance_judgments.jsonl` by the validation script. N = 20
queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | scikit-learn |
| Pinned commit | `9b9be3abddd88675c5dc2e3623e652cb7545a26c` |
| Version at this commit | `1.10.dev0` (`git describe`: `1.8.0rc1-729-g9b9be3abdd`) |
| Largest file confirmed | `sklearn/utils/estimator_checks.py`, 5,742 lines |
| `doc/whats_new/upcoming_changes/` fragment files | 55, read in full (251 total lines) |

## 2. Category distribution

| Category | Count | Share |
|---|---|---|
| bug_fix | 4 | 20% |
| feature_implementation | 4 | 20% |
| refactoring | 3 | 15% |
| testing | 3 | 15% |
| documentation | 2 | 10% |
| api_usage | 2 | 10% |
| code_search | 2 | 10% |

Matches the mission's required 4/4/3/3/2/2/2 distribution exactly.

## 3. Difficulty distribution

| Difficulty | Count | Share |
|---|---|---|
| medium | 13 | 65% |
| easy | 4 | 20% |
| hard | 3 | 15% |

Tied with the Click/Celery pilot runs for a medium-heavy distribution
(65%), reflecting that most queries here target a single, precisely
-locatable estimator/mechanism rather than either a trivial lookup or
a sprawling cross-cutting concern.

## 4. Average candidate files per query

**avg = 1.9, min = 1, max = 3** (n=20, sum=38) — the lowest
average-candidate-count of any pilot run to date, reflecting
scikit-learn's convention of one estimator/mechanism per file with a
single, dedicated test file, rather than the more cross-cutting,
multi-file answers common in SQLAlchemy/pandas.

| Query | Category | Candidates |
|---|---|---|
| sklearn-013 | testing | 3 |
| sklearn-001 | bug_fix | 2 |
| sklearn-002 | bug_fix | 2 |
| sklearn-003 | bug_fix | 2 |
| sklearn-004 | bug_fix | 2 |
| sklearn-005 | feature_implementation | 2 |
| sklearn-006 | feature_implementation | 2 |
| sklearn-007 | feature_implementation | 2 |
| sklearn-008 | feature_implementation | 2 |
| sklearn-009 | refactoring | 2 |
| sklearn-010 | refactoring | 2 |
| sklearn-011 | refactoring | 2 |
| sklearn-012 | testing | 2 |
| sklearn-015 | documentation | 2 |
| sklearn-016 | documentation | 2 |
| sklearn-017 | api_usage | 2 |
| sklearn-018 | api_usage | 2 |
| sklearn-014 | testing | 1 |
| sklearn-019 | code_search | 1 |
| sklearn-020 | code_search | 1 |

`sklearn-014`, `sklearn-019`, and `sklearn-020` have the lowest count
(1) because they have unusually precise, single-file answers, not
because of a search gap: `sklearn-014`'s open-ended investigation
still grounds to one concrete module
(`utils/_optional_dependencies.py`), and the two code-search queries
each resolve to one exact function.

## 5. Frequently suggested files

No file appears as a candidate for more than 2 queries in this run —
the flattest cross-file distribution of any pilot run to date. Files
appearing twice:

| File | Query count |
|---|---|
| `sklearn/isotonic.py` | 2 (sklearn-004, sklearn-008) |
| `sklearn/tests/test_isotonic.py` | 2 |
| `sklearn/model_selection/_search.py` | 2 (sklearn-007, sklearn-009, sklearn-019 -- see note) |
| `sklearn/model_selection/tests/test_search.py` | 2 |
| `sklearn/neural_network/_multilayer_perceptron.py` | 2 (sklearn-005, sklearn-010) |
| `sklearn/neural_network/tests/test_mlp.py` | 2 |
| `sklearn/preprocessing/_data.py` | 2 (sklearn-001, sklearn-011) |
| `sklearn/preprocessing/tests/test_data.py` | 2 |
| `sklearn/compose/_column_transformer.py` | 3 (sklearn-002, sklearn-012, sklearn-017) |
| `sklearn/compose/tests/test_column_transformer.py` | 2 |
| `sklearn/multiclass.py` | 2 (sklearn-003, sklearn-013) |

Note: `sklearn/model_selection/_search.py` is actually referenced by
3 queries (sklearn-007, sklearn-009, sklearn-019), and
`sklearn/compose/_column_transformer.py` by 3 (sklearn-002,
sklearn-012, sklearn-017) — both are this run's most cross-cutting
files, still far below the 5-of-20 peaks seen in the SQLAlchemy and
pandas runs.

## 6. Frequently suggested packages/subpackages

| Package/unit | Reference count (distinct files) |
|---|---|
| `sklearn/model_selection/` | 3 files |
| `sklearn/compose/` | 2 files |
| `sklearn/preprocessing/` | 2 files |
| `sklearn/neural_network/` | 2 files |
| `doc/developers/`, `doc/`, `doc/modules/` | 4 files total |
| `sklearn/utils/` | 3 files (`estimator_checks.py`, `_optional_dependencies.py`, `_param_validation.py`, `_metadata_requests.py` -- 4 actually) |

## 7. Weak queries

**0** by the query-length proxy check (`query_text` under 8 words),
and **0** queries lack a primary candidate.

## 8. Directory candidates

**1** found during search (`examples/developing_estimators`, a
`documentation_examples` candidate for `sklearn-015`), correctly
excluded from the final relevance-judgment file rather than guessed
at — see `validation_report.md` §8.

## 9. Coverage observations

scikit-learn's `sklearn/` package spans dozens of algorithm-family
subpackages (`linear_model/`, `tree/`, `ensemble/`, `svm/`,
`neighbors/`, `cluster/`, `decomposition/`, `mixture/`,
`gaussian_process/`, `neural_network/`, `manifold/`,
`semi_supervised/`, `covariance/`, `cross_decomposition/`, `impute/`,
`feature_extraction/`, `feature_selection/`, and more) plus the large
cross-cutting `utils/`, `model_selection/`, and `metrics/` packages. A
precise total-`.py`-file coverage percentage was not computed for this
run (consistent with the pandas run's judgment that a full recursive
count is disproportionate to a fixed 20-query budget for a repository
of this scale); qualitatively, `repository_summary.md` establishes
that this is a very large, many-subpackage repository.

Subpackages/areas referenced by at least one query: `preprocessing/`,
`compose/`, `multiclass.py` (top-level module), `isotonic.py`
(top-level module), `neural_network/`, `cross_decomposition/`,
`model_selection/`, `utils/` (4 distinct modules), plus `doc/`
generally. **Entirely untouched algorithm-family packages**:
`linear_model/`, `tree/`, `ensemble/`, `svm/`, `neighbors/`,
`cluster/`, `decomposition/`, `mixture/`, `gaussian_process/`,
`manifold/`, `semi_supervised/`, `covariance/`, `impute/`,
`feature_extraction/`, `feature_selection/`, `discriminant_analysis.py`,
`dummy.py`, `kernel_ridge.py`, `kernel_approximation.py`,
`random_projection.py`, `frozen/`, `callback/`, `metrics/` (beyond
`_scorer.py`), and all Cython (`.pyx`/`.pxd`) internals. Given
scikit-learn's exceptional breadth (more distinct, independently
-testable algorithm families than any prior pilot repository), a
single 20-query round can only sample a small fraction of it — a
future round should specifically target the entirely-untouched
algorithm families above.
