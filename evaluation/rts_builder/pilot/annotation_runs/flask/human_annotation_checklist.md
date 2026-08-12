# Human Annotation Checklist — Flask Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against Flask at commit
`6a2f545bfd8ed31e19066a299296917e034aca58`. Per
`RELEVANCE_ANNOTATION_HANDBOOK.md`, no relevance grade here is final —
every `"TO_BE_ASSIGNED"` value must be replaced by a human annotator
before this data is merged into the pipeline's `queries.jsonl`.

## ☐ Verify candidate files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated.
- [ ] This run has **zero directory-level candidates** (unlike the
      prior FastAPI pilot run) — every path in
      `draft_relevance_judgments.jsonl` should already be a concrete
      file. If you find one that isn't, treat it as a defect and check
      `validation_report.md` first (it should have caught this).
- [ ] Pay particular attention to `src/flask/sansio/app.py` vs.
      `src/flask/app.py` and `src/flask/sansio/blueprints.py` vs.
      `src/flask/blueprints.py` — these are four distinct, easily
      -confused file pairs (see `repository_summary.md` §3).

## ☐ Verify classes

- [ ] For every `important_classes` entry, confirm the class exists at
      the stated file and still matches its described role.
- [ ] Specifically confirm `AppContext` in `src/flask/ctx.py` — this
      run's central, commit-specific finding (the `RequestContext`/
      `AppContext` merge) depends entirely on this class's current
      docstring accurately reflecting a 3.2-specific change. If a
      future commit is annotated instead, re-verify this fact rather
      than assuming it still holds.

## ☐ Verify functions

- [ ] For every `important_functions` entry, confirm the function
      exists at the stated file/line and still matches its described
      role.
- [ ] Several candidates (e.g. flask-006's `app.py`/`ctx.py` secondary
      candidates, flask-004's `signals.py` secondary candidate) are
      flagged in `annotation_drafts.jsonl`'s `uncertainty` field as
      "plausible but not individually confirmed" — these specifically
      need a human to confirm the actual function body, not just the
      file's existence.

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call.
      Confirm this yourself for a sample rather than trusting the
      confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "content not
      read" as existence-only-confirmed, not content-verified. This
      applies to most `documentation_examples` entries in this run —
      no `.rst` file's actual prose was read in this pass, only its
      existence and filename.

## ☐ Add missing files

- [ ] flask-004 (flash message bug): no test file was individually
      confirmed for flash-specific coverage — search
      `tests/test_helpers.py` (confirmed to exist) directly.
- [ ] flask-007 (session backend feature): no documentation candidate
      was found — search more broadly (`docs/quickstart.rst`,
      `docs/api.rst`) before concluding this is a genuine
      documentation gap.
- [ ] flask-008 (new URL converter feature): resolve the open question
      in `annotation_drafts.jsonl` about whether Flask itself
      implements any converters, or whether all converter
      implementations live in Werkzeug — this materially changes
      whether any file in this repository is a true primary candidate.
- [ ] For every query, consider whether `CHANGES.rst` (not searched in
      this pass at all, beyond the versionchanged note already found
      via `ctx.py`'s own docstring) documents relevant recent history.

## ☐ Verify regression tests

- [ ] For every `regression_tests`/relevance-file test entry, open the
      file and identify the specific test function(s) actually
      relevant to the query — none were read in this pass, only
      confirmed to exist.
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For flask-013 specifically: confirm whether `tests/test_async.py`
      contains any test with genuinely inconsistent (not just
      skip-when-absent) behavior before treating this as a real defect
      — see `research_notes.md` §3.

## ☐ Verify documentation

- [ ] Every `.rst` documentation candidate in this run is
      existence-confirmed only — open each one and confirm its actual
      content before grading.
- [ ] For flask-015 specifically: read `docs/reqcontext.rst` and
      `docs/appcontext.rst` in full and determine whether they already
      reflect the 3.2 `AppContext`/`RequestContext` merge or are
      actively stale. This determines whether flask-015 describes a
      real, current gap or something already fixed.

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] flask-002/flask-017 share the same primary implementation
      (`copy_current_request_context`) under different category framings
      (Bug Fix vs. API Usage) — decide independently for each whether
      the underlying behavior is a defect or documented-as-expected;
      do not let one query's grading silently determine the other's.
- [ ] flask-003 (error handler not invoked): decide whether the query
      concerns registration or lookup before finalizing which of the
      two primary candidates is more relevant.
- [ ] flask-013: decide whether to proceed with this query as-is
      (accept a likely near-empty or purely-structural relevant set) or
      flag it for replacement — no evidence of an actual inconsistent
      test was found, only the structural pattern that would produce
      environment-dependent (skip, not fail) behavior by design.
- [ ] flask-016: resolve whether "cleanup code after a request" means
      `after_this_request` (success-path only) or `teardown_request`
      (unconditional, including exceptions) before grading — these are
      different mechanisms.

## ☐ Record rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement ("a grade with no rationale is not acceptable
      for submission").
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning — silently resolving discards information a future
      reviewer would want, per the handbook's §5 guidance.
- [ ] Record whether flask-008 and flask-013 were kept as-is, revised,
      or replaced, and why — these are this run's two most structurally
      uncertain queries (see `research_notes.md` §3-4).
