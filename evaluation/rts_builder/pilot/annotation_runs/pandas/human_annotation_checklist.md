# Human Annotation Checklist — pandas Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against pandas at commit
`d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` (version `3.1.0.dev0`, a
development snapshot). Per `RELEVANCE_ANNOTATION_HANDBOOK.md`, no
relevance grade here is final — every `"TO_BE_ASSIGNED"` value must be
replaced by a human annotator before this data is merged into the
pipeline's `queries.jsonl`.

**This is the largest and most structurally intricate repository
processed in this project's pilot runs to date** (see
`repository_summary.md` §9, `dataset_statistics.md` §1) — budget more
review time per query than for any of the six prior repository runs.

## ☐ Verify suggested files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated (all 55 rows' files were
      verified to exist on disk by the validation script, but
      existence alone is not content-correctness).
- [ ] This run has **zero directory-level candidates** — every
      candidate resolved to a concrete file, unlike the SQLAlchemy and
      Celery runs.
- [ ] Pay particular attention to `pandas/core/reshape/merge.py`,
      `pandas/core/frame.py`, `pandas/core/groupby/generic.py`,
      `pandas/core/groupby/groupby.py`, `pandas/core/internals/managers.py`,
      and `pandas/core/internals/blocks.py` (each a candidate for 3 of
      the 20 queries) — verify the specific class/function claimed,
      not just the file.

## ☐ Verify symbols

- [ ] For every `important_symbols` entry, confirm the class/function
      exists at the stated file/line and still matches its described
      role.
- [ ] Specifically confirm `internals/blocks.py`'s 6-class hierarchy
      underlying `pandas-009`: `Block` (144), `EABackedBlock` (1698),
      `ExtensionBlock` (1982), `NumpyBlock` (2241),
      `NDArrayBackedExtensionBlock` (2267), `DatetimeLikeBlock` (2281).
- [ ] Specifically confirm `reshape/merge.py`'s 4-class hierarchy
      underlying `pandas-011`: `_MergeOperation` (931),
      `_CrossMergeOperation` (2293), `_OrderedMerge` (2344),
      `_AsOfMerge` (2409).
- [ ] Specifically confirm `merge_asof`'s docstring requirement
      underlying `pandas-005` ("Both DataFrames must be first sorted
      by the merge key in ascending order before calling this
      function") is still accurate at this commit.
- [ ] Specifically confirm `to_csv`'s `na_rep: str = ""` parameter
      typing underlying `pandas-006` (`generic.py:2203`) — the query
      premise depends on `na_rep` genuinely being scalar-only, not a
      per-column mapping.
- [ ] Specifically confirm `DataFrame.__arrow_c_stream__`
      (`frame.py:744`) and `Series.__arrow_c_stream__`
      (`series.py:559`) implement the Arrow PyCapsule Protocol — this
      finding is why `pandas-006`'s original premise (no direct
      Arrow-table conversion) was replaced; confirm the replacement
      premise doesn't have the same kind of blind spot.

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call,
      and every file referenced in `draft_relevance_judgments.jsonl`
      was independently verified to exist on disk by
      `validate_pandas_run.py`. Confirm this yourself for a sample
      rather than trusting the confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "existence
      confirmed... contents not read" as existence-only-confirmed, not
      content-verified. Given this repository's size, a substantial
      fraction of candidates fall into this category.
- [ ] **Verify the 20 already-resolved `v3.1.0.rst` behaviors informally
      cross-checked during query drafting were correctly avoided as
      Bug Fix query targets** — spot-check at least the Groupby/
      resample/rolling, Reshaping, Indexing, and I/O sections (all
      read in full this session) against the corresponding query
      topics (`pandas-001`, `pandas-002`, `pandas-003`, `pandas-004`).

## ☐ Add missing files

- [ ] For every query, consider whether any part of `v3.1.0.rst` not
      explicitly cross-referenced in that query's `notes` field (e.g.
      the Categorical, Datetimelike, Timedelta, Timezones, Numeric,
      Conversion, Strings, Interval, Period, Plotting, Sparse,
      ExtensionArray, Styler, or Other sections) bears on it in ways
      this pass did not identify.
- [ ] Consider whether `pandas/core/computation/` (the `eval`/`query`
      engine), `pandas/core/window/` (rolling/expanding/EWM),
      `pandas/tseries/`, `pandas/plotting/`, or `pandas/_libs/`
      (Cython internals, confirmed present but never opened this
      session) should be represented in a future annotation round for
      this repository — all entirely untouched by this round's 20
      queries per `dataset_statistics.md` §9.

## ☐ Verify regression tests

- [ ] For every regression-test candidate, open the file and identify
      the specific test function(s) actually relevant to the query —
      all were existence-confirmed only in this pass, none
      individually read for content.
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For `pandas-014` specifically (6 candidates, the most of any
      query in this run): confirm the C/Python/PyArrow engine test
      files (`test_c_parser_only.py`, `test_python_parser_only.py`)
      are the right pair to compare, or whether a cross-engine test
      file not captured in this pass would be a better primary answer.

## ☐ Verify documentation

- [ ] Every `.rst` documentation candidate in this run is
      existence-confirmed only via directory listing — open each one
      and confirm its actual content before grading.
- [ ] `doc/source/development/internals.rst` is a candidate for both
      `pandas-009` and `pandas-016` — reading it once during review
      will inform grading for both simultaneously.

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] `pandas-001`: the groupby-apply inconsistent-result-shape
      scenario is grounded in real machinery but not confirmed as an
      actual reproducible defect at this commit — confirm whether it
      should be treated as a genuinely open bug-fix target or
      reworded.
- [ ] `pandas-010`: the degree of duplication between `SeriesGroupBy`
      and `DataFrameGroupBy` was inferred from both classes sharing a
      `GroupBy` base, not measured directly by diffing their bodies —
      confirm the refactor premise holds up under closer reading.
- [ ] `pandas-013`: `interface.py` was selected as the primary
      candidate among 16 confirmed `pandas/tests/extension/base/`
      modules based on its name alone — confirm whether coverage is
      better distributed across several of these files.

## ☐ Record annotation rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement.
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning.
- [ ] Record that `pandas-006` was substantively replaced (not merely
      re-grounded) during drafting, and why — the second pilot run
      (after SQLAlchemy's `sqlalchemy-008`) where a name-based grep for
      an absent capability missed a differently-named existing
      mechanism.
