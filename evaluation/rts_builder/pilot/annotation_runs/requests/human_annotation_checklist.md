# Human Annotation Checklist — Requests Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against Requests at commit
`1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e`. Per
`RELEVANCE_ANNOTATION_HANDBOOK.md`, no relevance grade here is final —
every `"TO_BE_ASSIGNED"` value must be replaced by a human annotator
before this data is merged into the pipeline's `queries.jsonl`.

## ☐ Verify suggested files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated.
- [ ] This run has **zero directory-level candidates** — every path
      should already be a concrete file. Treat any exception as a
      defect (check `validation_report.md` first).
- [ ] Pay particular attention to `tests/test_adapters.py`: it is
      genuinely tiny (8 lines, 1 test) and appears as a candidate for
      three different queries (requests-001, requests-010,
      requests-014) — confirm its content still matches what this run
      recorded (a single test about leading path separators,
      referencing GitHub issue #6643) before relying on that
      description.

## ☐ Verify symbols

- [ ] For every `important_classes`/`important_functions` entry,
      confirm the class/function exists at the stated file/line and
      still matches its described role.
- [ ] Specifically confirm `HOOKS = ["response"]` and the `# TODO:
      response is the only one` comment in `src/requests/hooks.py` —
      this run's single strongest-grounded feature query (requests-005)
      depends entirely on this comment still being accurate.
- [ ] Specifically confirm `HTTPBasicAuth`'s and `HTTPDigestAuth`'s
      independent `__eq__`/`__ne__` definitions in `src/requests/auth.py`
      — requests-011's refactor premise depends on this asymmetry.

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call.
      Confirm this yourself for a sample rather than trusting the
      confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "content not
      read" as existence-only-confirmed. This applies to most
      `documentation_examples` entries in this run.
- [ ] `requests-008`'s primary candidate (`certs.py`) is flagged with a
      "STRONG FLAG" in `annotation_drafts.jsonl` -- the query may
      already be substantially addressed by the existing `verify=`
      parameter. Resolve this before treating `certs.py` as
      highly relevant to a genuinely new feature.

## ☐ Add missing files

- [ ] `requests-003` (digest auth bug): no test file specifically
      covering `HTTPDigestAuth` was individually located — search
      `tests/test_requests.py` (3,094 lines, not exhaustively searched
      in this pass) directly.
- [ ] `requests-006` (new auth class feature): no existing auth-class
      test coverage was individually located — same search gap as
      above.
- [ ] `requests-002` (cookie persistence bug): the exact line(s) where
      response cookies are merged into `session.cookies` were not
      individually located — search `sessions.py`'s `send()`/`request()`
      bodies directly.
- [ ] For every query, consider whether `HISTORY.md` (66KB, not
      searched in this pass beyond what `repository_summary.md`
      already discloses as unread) documents relevant recent behavior
      changes.

## ☐ Verify regression tests

- [ ] For every regression-test candidate, open the file and identify
      the specific test function(s) actually relevant to the query —
      most were only existence-confirmed in this pass, not content
      -read (exceptions: `tests/test_adapters.py`, read in full).
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For `requests-013` specifically: confirm whether an actual
      currently-flaky low-level/socket test exists before treating this
      as a real defect — no such test was confirmed to exist in this
      pass (see `research_notes.md`).

## ☐ Verify documentation

- [ ] Every `.rst` documentation candidate in this run is
      existence-confirmed only (with one exception: `docs/dev/contributing.rst`
      was directly checked and confirmed to NOT mention `help.py`,
      for `requests-016`) — open each remaining one and confirm its
      actual content before grading.
- [ ] Requests has no `docs_src/`-style executable-example directory
      (unlike FastAPI) and no `examples/` directory (unlike Flask) —
      every documentation candidate in this repository is a `.rst`
      file's inline code block, not a separately-runnable file. There
      is nothing further to "verify runs" for documentation examples
      in this run, unlike the prior two pilot runs.

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] `requests-001` / `requests-010` / `requests-014` share the same
      underlying adapter-selection subsystem under three different
      category framings (Bug Fix / Refactoring / Testing) — grade
      independently but with consistent reasoning.
- [ ] `requests-008`: resolve whether this query describes a genuine
      feature gap or is already substantially addressed by the
      existing, documented `verify=` CA-bundle-path parameter.
- [ ] `requests-013`: decide whether to proceed with this query as-is
      or flag it for replacement — no evidence of an actual flaky test
      was found.

## ☐ Record annotation rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement.
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning.
- [ ] Record whether `requests-008` and `requests-013` were kept
      as-is, revised, or replaced, and why.
