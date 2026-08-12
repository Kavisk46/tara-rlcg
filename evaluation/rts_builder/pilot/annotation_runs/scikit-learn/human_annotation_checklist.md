# Human Annotation Checklist — scikit-learn Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against scikit-learn at commit
`9b9be3abddd88675c5dc2e3623e652cb7545a26c` (version `1.10.dev0`, a
development snapshot). Per `RELEVANCE_ANNOTATION_HANDBOOK.md`, no
relevance grade here is final — every `"TO_BE_ASSIGNED"` value must be
replaced by a human annotator before this data is merged into the
pipeline's `queries.jsonl`.

## ☐ Verify suggested files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated (all 38 rows' files were
      verified to exist on disk by the validation script, but
      existence alone is not content-correctness).
- [ ] This run has **one directory-level candidate**:
      `examples/developing_estimators`, a `documentation_examples`
      candidate for `sklearn-015`, excluded from
      `draft_relevance_judgments.jsonl` rather than guessed at.
      Resolve it to a specific example file if judged relevant.
- [ ] `sklearn/model_selection/_search.py` and
      `sklearn/compose/_column_transformer.py` are each candidates
      for 3 of the 20 queries (this run's most cross-cutting files,
      though far less concentrated than in prior pilot runs) — verify
      the specific class/function claimed for each query, not just
      the file.

## ☐ Verify symbols

- [ ] For every `important_symbols` entry, confirm the class/function
      exists at the stated file/line and still matches its described
      role.
- [ ] Specifically confirm `neural_network/_multilayer_perceptron.py`'s
      early-stopping code path underlying `sklearn-005`/`sklearn-010`:
      `_update_no_improvement_count` calling `self._score(...)`, with
      separately-defined `_score` methods for `MLPClassifier` (line
      1292) and `MLPRegressor` (line 1758), and the private
      `_score_with_function` helper (line 863) not exposed as a
      public parameter.
- [ ] Specifically confirm `cross_decomposition/_pls.py` genuinely has
      no sparse-input support underlying `sklearn-006` — this was
      checked via two grep terms ('sparse' broadly, and
      'accept_sparse'/'issparse' specifically) but not a full read of
      the file; verify no differently-named sparse-handling code path
      exists.
- [ ] Specifically confirm `model_selection/_search.py` has no
      wall-clock time-budget parameter underlying `sklearn-007` —
      checked via grep for 'max_time'/'time_budget'/'timeout' only.
- [ ] Specifically confirm `isotonic.py`'s `IsotonicRegression` has no
      multi-output support underlying `sklearn-008` — checked via grep
      for 'multioutput'/'multi-output'/'n_outputs' only.

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call,
      and every file referenced in `draft_relevance_judgments.jsonl`
      was independently verified to exist on disk by
      `validate_sklearn_run.py`. Confirm this yourself for a sample
      rather than trusting the confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "existence
      confirmed... contents not read" as existence-only-confirmed, not
      content-verified.
- [ ] **Verify a sample of the 55 already-resolved `upcoming_changes/`
      behaviors listed in `repository_summary.md` §9 were correctly
      avoided as Bug Fix/Feature query targets** — spot-check at least
      5 of the 55 fragments against the corresponding query topics
      (`sklearn-001` through `sklearn-004` for Bug Fix,
      `sklearn-005` through `sklearn-008` for Feature).

## ☐ Add missing files

- [ ] `sklearn-015`: resolve `examples/developing_estimators` (a
      directory) to the specific example file(s) most relevant to
      writing a new compatible estimator, if any exist beyond
      `doc/developers/develop.rst`.
- [ ] For every query, consider whether any of the 55 changelog
      fragments not explicitly cross-referenced in that query's
      `notes` field bears on it in ways this pass did not identify.
- [ ] Consider whether any of the entirely-untouched algorithm-family
      packages identified in `dataset_statistics.md` §9
      (`linear_model/`, `tree/`, `ensemble/`, `svm/`, `neighbors/`,
      `cluster/`, `decomposition/`, `mixture/`, `gaussian_process/`,
      `manifold/`, `semi_supervised/`, `covariance/`, `impute/`,
      `feature_extraction/`, `feature_selection/`, and more) should be
      represented in a future annotation round for this repository.

## ☐ Verify regression tests

- [ ] For every regression-test candidate, open the file and identify
      the specific test function(s) actually relevant to the query —
      all were existence-confirmed only in this pass, none
      individually read for content.
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For `sklearn-013` specifically: confirm whether
      `sklearn/tests/test_common.py` already includes
      `OneVsRestClassifier`/`OneVsOneClassifier` in its generic
      estimator collection, or whether this query's premise (that they
      are not yet covered) is accurate — not verified by reading the
      file's content this session.

## ☐ Verify documentation

- [ ] Every `.rst` documentation candidate in this run is
      existence-confirmed only via directory listing — open each one
      and confirm its actual content before grading.
- [ ] `doc/metadata_routing.rst` (candidate for `sklearn-016`) is
      directly motivated by the 4 confirmed metadata-routing bug-fix
      changelog fragments at this commit — verify whether the
      documentation already reflects those fixes or genuinely needs
      updating.

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] `sklearn-001`: the StandardScaler.partial_fit numerical
      -stability scenario is grounded in real machinery but not
      confirmed as an actual reproducible defect at this commit —
      confirm whether it should be treated as a genuinely open
      bug-fix target or reworded.
- [ ] `sklearn-010`: the degree of duplication cited (the two `_score`
      methods) is confirmed, but the query's broader framing ("scoring
      logic") was not verified beyond that one pair of methods —
      confirm the refactor premise holds up under closer reading of
      the rest of both classes.
- [ ] `sklearn-011`: confirm the actual degree of structural
      duplication across the 9-class scaler/transformer family beyond
      their shared class definitions.

## ☐ Record annotation rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement.
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning.
- [ ] Record that this is the first pilot run (of eight to date) in
      which no query required a `STRONG FLAG` or a premise replacement
      during drafting — note whether this reflects genuinely cleaner
      grounding or simply a smaller, more self-contained sample of
      query topics this round happened to select.
