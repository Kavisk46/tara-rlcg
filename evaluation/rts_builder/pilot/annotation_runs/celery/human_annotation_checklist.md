# Human Annotation Checklist — Celery Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against Celery at commit
`f109abf852525b69a1b6eee0457c6cd5561e0529`. Per
`RELEVANCE_ANNOTATION_HANDBOOK.md`, no relevance grade here is final —
every `"TO_BE_ASSIGNED"` value must be replaced by a human annotator
before this data is merged into the pipeline's `queries.jsonl`.

**This is the largest and most subsystem-rich repository processed in
this project's pilot runs so far** (see `repository_summary.md` §8) —
budget more review time per query than for the smaller FastAPI/Flask/
Requests/Click runs.

## ☐ Verify suggested files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated.
- [ ] This run has **zero directory-level candidates in the final
      files** — two were found during search (`t/unit/worker` for
      `celery-004`, `docs/getting-started/backends-and-brokers` for
      `celery-005`) and were excluded from
      `draft_relevance_judgments.jsonl` rather than guessed at; resolve
      both to specific files before grading those two queries.
- [ ] Pay particular attention to `celery/canvas.py` (2,443 lines,
      appearing as a candidate for 8 of the 20 queries) — verify the
      specific class claimed (`Signature`, `_chain`/`chain`, `group`,
      `_chord`, `StampingVisitor`), not just the file.

## ☐ Verify symbols

- [ ] For every `important_classes`/`important_functions` entry,
      confirm the class/function exists at the stated file/line and
      still matches its described role.
- [ ] Specifically confirm `celery/app/autoretry.py`'s
      `add_autoretry_behaviour` function — `celery-017`'s primary
      grounding depends on this, and was confirmed by a full function
      -body read during drafting (see README.md's Phase 11 audit),
      not just a filename match.
- [ ] Specifically confirm the six `bootsteps`-subclassing classes in
      `celery/worker/components.py` (`Timer`, `Hub`, `Pool`, `Beat`,
      `StateDB`, `Consumer`) — `celery-009`'s refactor premise depends
      on this concrete assembly.
- [ ] Specifically confirm the `flaky` marker's real definition in
      `t/integration/conftest.py` (`pytest.mark.flaky(reruns=5,
      reruns_delay=1, cause=is_retryable_exception)`) and its
      application in `t/integration/test_canvas.py` (10+ uses) —
      `celery-013`'s premise depends on these, found during the Phase
      11 audit; `pyproject.toml` only registers the marker's name.

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call.
      Confirm this yourself for a sample rather than trusting the
      confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "content not
      read" as existence-only-confirmed, not content-verified. Given
      this repository's size, a much larger fraction of candidates
      fall into this category than in any prior pilot run (e.g. all 3
      `docs/userguide/*.rst` references, most `t/unit/` test-file
      references beyond confirmed existence).
- [ ] **Verify the `celery-003` / already-fixed-bug distinction
      specifically**: `Changelog.rst`'s 5.6.2 section confirms "Revoked
      tasks now immediately update backend status to REVOKED" was
      already fixed at this commit. `celery-003` was deliberately
      written to describe a different, still-open scenario (general
      custom-backend state reporting, not revocation specifically) —
      confirm this distinction still holds and the query doesn't
      inadvertently overlap with the fixed issue.

## ☐ Add missing files

- [ ] `celery-004`: resolve `t/unit/worker` (a directory) to the
      specific test file covering autoscaling, if one exists.
- [ ] `celery-005`: resolve `docs/getting-started/backends-and-brokers`
      (a directory) to the specific documentation file(s) relevant to
      adding a new backend.
- [ ] `celery-013`: resolved during the Phase 11 audit — the `flaky`
      marker's real definition and 10+ applications were located in
      `t/integration/` (not `t/unit/`, which is pytest's default
      `testpaths`). Confirm this resolution still holds, and identify
      which of the 10+ `@flaky`-decorated tests in
      `t/integration/test_canvas.py` is the one currently, actually
      unreliable (as opposed to defensively pre-marked) — this specific
      determination was not made in this pass.
- [ ] For every query, consider whether `Changelog.rst`'s older
      (pre-5.6.2) entries document relevant, still-current behavior not
      surfaced in this pass (only the 5.6.0-5.6.2 sections were read).

## ☐ Verify regression tests

- [ ] For every regression-test candidate, open the file and identify
      the specific test function(s) actually relevant to the query —
      all were existence-confirmed only in this pass, none
      individually read for content.
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For `celery-013` specifically: run the 10+ `@flaky`-decorated
      tests in `t/integration/test_canvas.py` (and the one in
      `t/integration/test_worker.py`) against the pinned commit to
      determine which, if any, is currently unreliable in practice.

## ☐ Verify documentation

- [ ] Every `.rst` documentation candidate in this run is
      existence-confirmed only via directory listing — open each one
      and confirm its actual content before grading.
- [ ] `docs/userguide/canvas.rst` is a candidate for 5 different
      queries (`celery-001`, `celery-006`, `celery-008`, `celery-015`,
      `celery-018`) — reading it once during review will inform
      grading for all five simultaneously.

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] `celery-002`: confirm whether the timezone-mismatch scenario is
      genuinely open or touches any of the fixes documented in the
      reviewed `Changelog.rst` excerpt (none were found to match, but
      only the 5.6.0-5.6.2 sections were read).
- [ ] `celery-009`: decide whether `bootsteps.py` (the generic
      mechanism) or `worker/components.py` (its concrete use) — or
      both — should be graded as primary; the query's wording doesn't
      disambiguate, consistent with `repository_summary.md` §8's
      predicted ambiguity.
- [ ] `celery-013`: the marker mechanism and its main application site
      are now known (see "Add missing files" above); the remaining
      ambiguity is narrowing 10+ candidate tests down to the one(s)
      actually observed to be unreliable, which requires running them.
- [ ] `celery-011`: confirm whether the 18 concrete backend modules
      actually use `BackendError`/`BackendGetMetaError`/
      `BackendStoreError` inconsistently, or whether this refactor
      query's premise needs revision — not verified in this pass.

## ☐ Record annotation rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement.
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning.
- [ ] Record how `celery-013` was ultimately resolved (which specific
      flaky test was found, or whether the query was replaced) — this
      is the run's one query without a primary candidate.
