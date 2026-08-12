# Human Annotation Checklist — Click Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against Click at commit
`00e592cea702e0b2caa0dee42489fdb1c22cd845`. Per
`RELEVANCE_ANNOTATION_HANDBOOK.md`, no relevance grade here is final —
every `"TO_BE_ASSIGNED"` value must be replaced by a human annotator
before this data is merged into the pipeline's `queries.jsonl`.

**This repository is an unreleased `.dev` version (`8.5.0.dev`) with
several very recent changes** (see `repository_summary.md` §9 and
`research_notes.md` §2) — pay special attention when verifying, since
released-version documentation, tutorials, or the annotator's own
memory of Click may not reflect this exact commit's state.

## ☐ Verify suggested files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated.
- [ ] This run has **zero directory-level candidates in the final
      files** — one was found during search (`examples/aliases`, for
      `click-008`) and resolved to its concrete file
      (`examples/aliases/aliases.py`) before being included; confirm
      this resolution is still accurate.
- [ ] Pay particular attention to `src/click/core.py` (3,792 lines,
      appearing as a candidate for 10 of the 20 queries) — its sheer
      size means "confirmed to exist" is a much weaker relevance signal
      here than for smaller files; verify the specific class/method
      claimed, not just the file.

## ☐ Verify symbols

- [ ] For every `important_classes`/`important_functions` entry,
      confirm the class/function exists at the stated file/line and
      still matches its described role.
- [ ] Specifically confirm `custom_version_option` (decorators.py) and
      the CHANGES.md claim that `version_option`'s feature set is "now
      frozen" — `click-016`'s documentation premise depends on this.
- [ ] Specifically confirm the 7 deprecated aliases in `utils.py`'s
      module `__getattr__` — `click-015`'s premise depends on this.
- [ ] Specifically confirm `PowerShellComplete` in `shell_completion.py`
      — several queries (`click-005`, `click-011`) reference its recent
      addition as grounding.

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call.
      Confirm this yourself for a sample rather than trusting the
      confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "content not
      read" or "not individually confirmed by name" as
      existence-only-confirmed, not content-verified. This applies to
      most `documentation_examples` entries (all 36 `docs/*.md` pages
      were only existence-confirmed via directory listing, except
      where a specific section header was grepped).
- [ ] **Verify the CHANGES.md-derived claims specifically** — this run
      relied more heavily on a changelog than any prior pilot run
      (FastAPI/Flask/Requests). Re-read `CHANGES.md`'s top ("Version
      8.5.0 / Unreleased") section directly and confirm the six
      changes cited in `repository_summary.md` §9 (PowerShell
      completion, Colorama removal, `Argument.help`, `custom_version_option`,
      the `_click_default_help` rename, `Option.__init__` refactor) are
      accurately described.

## ☐ Add missing files

- [ ] `click-002`/`click-010`: the specific help-record/help-formatting
      method names in `core.py`/`formatting.py` were not individually
      confirmed by name — search directly before finalizing.
- [ ] `click-003`/`click-018`: `ParamType`'s exact validation-failure
      method name (commonly `fail()` in Click's public API, not
      independently confirmed by reading this file's method list in
      this pass) should be verified directly.
- [ ] `click-020`: the specific `Command`/`Parameter` methods that call
      into `parser.py`'s internals were not individually named —
      search directly.
- [ ] For every query, consider whether `CHANGES.md`'s older
      (pre-8.5.0) sections document relevant, still-current behavior
      not surfaced in this pass (only the top ~40 lines plus a
      keyword search for "version_option is now frozen" were read).

## ☐ Verify regression tests

- [ ] For every regression-test candidate, open the file and identify
      the specific test function(s) actually relevant to the query —
      all were existence/line-count-confirmed only in this pass, none
      individually read for content.
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For `click-013` specifically: confirm whether an actual
      currently-inconsistent platform/terminal test exists before
      treating this as a real defect (see `research_notes.md`).

## ☐ Verify documentation

- [ ] Every `.md` documentation candidate in this run is
      existence-confirmed only, with two exceptions directly verified
      by content read: `docs/contrib.md` (confirmed to list Cloup as
      adding option groups and command aliases — grounding `click-007`/
      `click-008`) and `docs/options.md` (confirmed section headers,
      no "option group" heading present among them).
- [ ] Click's documentation is Markdown (MyST/Sphinx), not `.rst` —
      the first Markdown-based documentation source across this
      project's four pilot runs so far; no structural surprises are
      expected from this format difference, but note it if it affects
      how documentation candidates should be graded.

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] `click-004`: resolve whether "context values" means `ctx.obj`,
      `ctx.params`, or environment-derived defaults before grading —
      these have different inheritance mechanics.
- [ ] `click-013`: decide whether to proceed with this query as-is or
      flag it for replacement — no evidence of an actual
      platform-inconsistent test was found.
- [ ] `click-015`: confirm which of this codebase's three distinct
      deprecation stories (utils.py's 7 aliases, `__version__`, or
      `version_option`'s frozen feature set) the query is meant to
      address; the query text does not name one specifically.
- [ ] `click-016`: confirm whether any existing documentation page
      already mentions `custom_version_option` (it may be new enough
      that none do) before treating this as an update-in-place task
      versus new-content task.

## ☐ Record annotation rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement.
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning.
- [ ] Record whether `click-013` was kept as-is, revised, or replaced,
      and why.
