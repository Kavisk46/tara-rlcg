# Research Notes — scikit-learn Pilot Annotation Run

Reflective notes from constructing this pilot run against scikit-learn
at commit `9b9be3abddd88675c5dc2e3623e652cb7545a26c` (version
`1.10.dev0`, a development snapshot 729 commits past the `1.8.0rc1`
tag). Observations and judgments, not additional data — everything
factual referenced here was already established in
`repository_summary.md`, `annotation_drafts.jsonl`, or
`validation_report.md`.

## 1. Interesting repository findings

- **scikit-learn is the eighth repository processed in this project's
  pilot runs, and the first with a truly flat, per-estimator file
  layout**: unlike pandas/SQLAlchemy's deeply cross-cutting internals
  (where single files like `orm/relationships.py` or
  `pool/base.py` were candidates for 5 of 20 queries each), no file in
  this run was a candidate for more than 3 of the 20 queries — a
  direct consequence of scikit-learn's convention of one estimator (or
  a small, closely related family) per module, each with its own
  dedicated test file.
- **scikit-learn's towncrier-style changelog fragments are unusually
  terse**: all 55 `upcoming_changes/` fragments totaled only 251 lines
  combined (an average of ~4.5 lines per fragment), making a full read
  of every single fragment — rather than a representative sample —
  practical within a proportionate research budget, the most complete
  changelog coverage of any pilot run to date by fragment count (55,
  versus SQLAlchemy's 12).
- **This is the first pilot run in which no Feature-category query
  required a premise replacement during drafting.** Both the pandas
  and SQLAlchemy runs each had at least one Feature query whose "this
  capability doesn't exist" premise turned out to be false when
  checked more carefully; this run's three most absence-dependent
  Feature queries (`sklearn-006`, `sklearn-007`, `sklearn-008`) were
  each verified with at least two independent search terms before
  being finalized, a discipline adopted directly in response to those
  two prior runs' findings.
- **A genuinely interesting structural echo of the pandas run's
  `SeriesGroupBy`/`DataFrameGroupBy` refactor query**: scikit-learn's
  `MLPClassifier`/`MLPRegressor` independently duplicate a `_score`
  method (lines 1292 and 1758 of
  `neural_network/_multilayer_perceptron.py`) despite both inheriting
  from the same `BaseMultilayerPerceptron`, the same
  shared-base-class-with-duplicated-leaf-logic pattern found in
  pandas's groupby classes — grounding `sklearn-010`.

## 2. Commit-specific observations

- Version `1.10.dev0` per `sklearn/__init__.py`'s `__version__`
  string; `git describe --tags` reports `1.8.0rc1-729-g...`, meaning
  this snapshot is 729 commits past the last release-candidate tag —
  a larger commit-distance-past-tag than any prior pilot repository's
  equivalent figure (SQLAlchemy's `2.1.0b4` and pandas's
  `3.1.0.dev0-1495-g...` are the closest comparisons, though pandas's
  commit count past tag was larger).
- **The four `metadata-routing/` changelog fragments (all read in
  full) point to metadata routing being an actively-scrutinized area
  at this commit**: fixes to `Pipeline`, `TransformedTargetRegressor`,
  `BaggingClassifier`, and several `feature_selection`/`impute`
  meta-estimators were all made very recently relative to this
  snapshot. This directly motivated `sklearn-003` (a still-open
  metadata-routing-adjacent scenario for `OneVsRestClassifier`/
  `OneVsOneClassifier`, deliberately distinguished from the 4
  already-fixed cases) and `sklearn-016` (documentation of the routing
  mechanism itself).
- **Two of the 55 fragments describe genuinely major, not incremental,
  changes**: native categorical-feature support for decision trees
  (`33354.major-feature.rst`) and a new GLM solver with L1/Elastic-Net
  support (`34523.major-feature.rst`), both explicitly tagged
  `major-feature` in their filenames (a towncrier convention distinct
  from the plain `feature`/`enhancement`/`fix`/`efficiency`/`api`
  tags used elsewhere) — both were excluded from query grounding as
  already-implemented, consistent with this run's general practice.

## 3. Annotation difficulties

- **Verifying the absence of a capability required more search effort
  than verifying its presence**, a structural difficulty carried
  forward from the pandas run's lesson: `sklearn-006`'s sparse-PLS gap
  was checked via two separate grep terms across the same file, and
  `sklearn-007`/`sklearn-008`'s gaps were each checked via 3-term
  greps — more search calls per query than any Bug Fix or Code Search
  query in this run required, since a single positive match ends a
  search but a claimed absence needs multiple negative results to be
  credible.
- **`sklearn-005`'s premise required reading actual code, not just
  grepping for a parameter name**, since the relevant gap (no
  user-configurable scoring callable for MLP early stopping) is a
  matter of a private method (`_score_with_function`) not being
  exposed publicly, rather than a missing name entirely — a
  distinction that a shallow grep for something like "custom scorer"
  or "scoring" would likely have missed, since `_score_with_function`
  itself does contain "score" in its name.
- **`sklearn-013`'s premise (that `OneVsRestClassifier`/
  `OneVsOneClassifier` are not yet covered by the generic conformance
  -check collection) was not verified by reading `test_common.py`'s
  actual content** — this is disclosed as an open question in
  `human_annotation_checklist.md` rather than asserted as fact, since
  confirming it would require reading a file not opened this session.

## 4. Threats to validity

- **Single-pass AI search, not independently cross-checked** — same
  limitation disclosed in all seven prior pilot runs.
- **All 55 `upcoming_changes/` fragments were read in full, but
  scikit-learn's much longer historical changelog (`v0.13.rst` through
  `v1.9.rst`, dozens of files) was not** — an already-fixed issue from
  an earlier release cycle that resembles a plausible bug-fix query
  topic could exist undetected outside the window actually read.
- **No code was executed, no test was run, and no Cython extension
  module was built, read in depth, or profiled** — all findings are
  static-inspection-only, consistent with every prior pilot run, and
  especially significant here given scikit-learn's reliance on Cython
  for tree-splitting, histogram-based boosting, and pairwise-distance
  computation.
- **Both `sklearn-006`'s and `sklearn-007`'s/`sklearn-008`'s absence
  claims were confirmed only by grep for 2-3 specific term(s) each**,
  not an exhaustive read of every relevant file; a differently-named
  mechanism satisfying any of these queries' premises cannot be fully
  ruled out — explicitly flagged in `human_annotation_checklist.md`.
- **Extremely broad surface area relative to the fixed query budget**:
  the large majority of scikit-learn's algorithm-family packages
  (`linear_model/`, `tree/`, `ensemble/`, `svm/`, `neighbors/`,
  `cluster/`, `decomposition/`, `mixture/`, `gaussian_process/`,
  `manifold/`, `semi_supervised/`, `covariance/`, `impute/`,
  `feature_extraction/`, `feature_selection/`, and more) were never
  touched by this round's 20 queries — the same acute coverage caveat
  already raised for Celery, SQLAlchemy, and pandas in this project's
  prior pilot runs, arguably even more pronounced here given
  scikit-learn's unusually large number of independently-testable
  algorithm families.

## 5. Potential reviewer concerns

1. **"Why does this run have no premise corrections, unlike the
   pandas and SQLAlchemy runs?"** — Addressed directly in
   `validation_report.md` §9 and this document's §1/§3: a deliberate
   methodological improvement (multi-term verification before
   finalizing any absence-dependent Feature query), not a claim that
   this run's grounding is inherently more reliable than the prior
   two. The underlying risk (a differently-named existing mechanism)
   remains and is disclosed per-query in
   `human_annotation_checklist.md`.
2. **"Why is the average candidate-file count (1.9) so much lower than
   every prior run (2.75-2.8 for pandas/SQLAlchemy, up to 5+ for
   Celery/SQLAlchemy's most cross-cutting files)?"** — Addressed in
   `dataset_statistics.md` §4/§9: a structural property of
   scikit-learn's flat, one-estimator-per-file convention, not a
   sign of weaker search effort.
3. **"Was `sklearn-013`'s premise (OneVsRestClassifier/OneVsOneClassifier
   not yet in the generic conformance-check collection) actually
   verified?"** — No, disclosed honestly in
   `human_annotation_checklist.md` as an open question requiring a
   human to read `test_common.py`'s actual content, consistent with
   this project's practice of reporting absence of verification rather
   than manufacturing false confidence.

## 6. Recommendations

- Before grading begins, independently verify `sklearn-006`'s,
  `sklearn-007`'s, and `sklearn-008`'s absence claims more
  exhaustively than this session's targeted greps, given that each
  underpins its entire query.
- Resolve `sklearn-015`'s directory-level candidate
  (`examples/developing_estimators`) to a specific file.
- Confirm `sklearn-013`'s premise by reading `test_common.py`'s actual
  estimator collection.
- A future round revisiting this repository should specifically target
  the large number of entirely-untouched algorithm-family packages
  identified in `dataset_statistics.md` §9 — given scikit-learn's
  unusually large number of independently-testable estimator families
  relative to even pandas or SQLAlchemy, a single 20-query round
  covers a smaller fraction of the "conceptual surface area" here than
  in any prior pilot run, even though the raw file-count coverage
  question was not computed precisely for this run.
- Given this run's success in avoiding any premise corrections through
  proactive multi-term verification, this practice — checking an
  absence claim with at least two independently-phrased searches
  before finalizing a Feature query, rather than relying on a single
  grep — is worth formalizing as a standard step (not just a
  post-hoc audit safety net) in any future pilot round.
