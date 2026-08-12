# Human Annotation Checklist — FastAPI Pilot Run

This checklist governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against the FastAPI repository at
commit `a375f6b948b99fa4260129856bbf11d037f363ef`. Per
`RELEVANCE_ANNOTATION_HANDBOOK.md`, no relevance grade in these files
is final — every `"TO_BE_ASSIGNED"` value must be replaced by a human
annotator following that handbook's protocol before this data is
merged into the pipeline's `queries.jsonl`.

**Do not treat anything in `annotation_drafts.jsonl` as verified.** It
records what the AI assistant read and its confidence, not ground
truth.

## 1. Verify candidate files

For every candidate listed in `annotation_drafts.jsonl` (all four
buckets: primary, secondary, regression tests, documentation
examples):

- [ ] Open the file at the pinned commit and confirm it exists exactly
      as stated (path, not a typo or a directory mistaken for a file).
- [ ] Confirm the file's actual content matches the `reason` given —
      the AI assistant's summaries are drawn from real reads, but
      re-verify rather than trust by transitivity.
- [ ] For any candidate whose `confidence` is `Low`, treat it as a
      genuine "maybe" rather than a near-miss — several `Low`
      candidates in this run are speculative by design (see §2 of
      `research_notes.md`).
- [ ] Directory-level entries (e.g. `fastapi/security/`, `docs/en/docs/`,
      or any `tests/test_tutorial/test_*` entry without a specific
      filename) must be resolved to the actual file(s) relevant to that
      query — these were left unresolved deliberately rather than
      guessed at. See `validation_report.md`'s "broken paths / unresolved
      directories" section for the full list.

## 2. Verify symbols

- [ ] For every `related_symbols` entry, confirm the named
      class/function actually exists at the stated location and still
      matches its described role (symbol names can drift even between
      nearby commits — this run pins one exact commit, but re-verify).
- [ ] Where `related_symbols` is empty or sparse (e.g. queries
      fastapi-002, fastapi-014), do not assume this means "nothing
      relevant exists" — it may mean the assistant's search did not go
      deep enough. Use your own search.

## 3. Verify tests

- [ ] For every `regression_tests` entry, open the file (or, for
      directory-level entries, enumerate the directory) and identify
      the specific test function(s) actually relevant to the query.
- [ ] Run the identified tests against the pinned commit and record
      pass/fail — no test in this run was executed by the AI assistant;
      every regression-test candidate is untested-as-of-inclusion.
- [ ] For fastapi-013 specifically: no actual flaky/concurrency test
      was located. If you cannot find one either, this query should be
      escalated for revision (see `research_notes.md`), not force-fit
      onto `tests/test_tutorial/test_async_tests/test_main_a.py`.

## 4. Verify docs

- [ ] For every `documentation_examples` entry under `docs_src/`,
      confirm the file exists and open it — several entries in this run
      (e.g. fastapi-007's three candidates, fastapi-002's
      `tutorial001_py310.py`) were included based on directory-naming
      conventions or partial listings, not full content reads.
- [ ] For fastapi-015 and fastapi-016 specifically: the rendered
      documentation source tree (`docs/en/docs/`) was **not searched**
      by the AI assistant in this run — only `docs_src/` (executable
      examples) was. Search `docs/en/docs/` directly to find the actual
      prose documentation page(s) before finalizing these two queries.

## 5. Remove hallucinations

No file, symbol, or test in `annotation_drafts.jsonl` was invented —
every entry was produced by an actual `Read`/`Grep`/directory-listing
call against the local repository. However:

- [ ] Confirm this claim yourself for at least a sample of entries —
      do not take the assistant's own "verified by direct read" labels
      as sufficient on their own.
- [ ] Treat every `Low`-confidence entry whose `uncertainty` field says
      "content not read" as **unverified existence-only** — the path
      was confirmed to exist via a directory listing, but its content
      and true relevance were not inspected. This applies to a
      significant fraction of `documentation_examples` entries across
      this run.
- [ ] Any candidate whose reasoning depends on an inference from
      "general FastAPI/Starlette convention" rather than a direct read
      (flagged explicitly in fastapi-017's secondary candidate,
      `fastapi/applications.py`) should be re-derived from the actual
      code, not accepted as-is.

## 6. Add missing files

The AI assistant's searches were targeted, not exhaustive. In
particular:

- [ ] fastapi-001: re-check whether `tests/test_multi_body_errors.py`
      is actually about nested single-model bodies or about multiple
      separate `Body(...)` parameters (flagged as genuinely uncertain).
- [ ] fastapi-005/fastapi-009: `fastapi/security/api_key.py` and
      `fastapi/security/open_id_connect_url.py` were only partially
      read — check whether `open_id_connect_url.py` (not inspected at
      all in this run) also participates in the duplicated-logic
      pattern or the new-scheme template set.
- [ ] fastapi-012: enumerate the full contents of the three form-related
      test directories to identify the specific untested edge case the
      query implies, rather than relying on the one candidate file
      offered.
- [ ] For every query, consider whether a file outside `fastapi/`,
      `tests/`, and `docs_src/` (e.g. `pyproject.toml`, `.github/`
      workflow files) is genuinely relevant — none were proposed in
      this run, but that reflects search scope, not a confirmed absence
      of relevance.

## 7. Assign grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full — grade
      definitions (§1), the decision procedure (§2), multi-file
      relevance (§3), tie handling (§4), and ambiguous cases (§5) all
      apply unchanged to this data.
- [ ] Replace every `"TO_BE_ASSIGNED"` value in
      `draft_relevance_judgments.jsonl` with an integer grade in
      `{1, 2, 3}`, or remove the key entirely if the file turns out to
      be not relevant (grade 0 — per the handbook, absence is how
      grade 0 is recorded in the final file).
- [ ] Files added under §6 need new keys added to `relevance_grades`,
      not just the pre-populated ones graded.
- [ ] Do not grade a file solely because it appears in this draft —
      the draft is a candidate list, not a pre-approved relevant set.

## 8. Resolve ambiguity

- [ ] For fastapi-011: decide whether this query should proceed at all.
      All five named middleware files were read in full and four are
      single-line Starlette re-exports with no custom logic; the fifth
      has no explicit error handling. If no genuine relevant-file set
      can be constructed, flag this query for revision or replacement
      rather than forcing weak grades onto irrelevant files (see
      `research_notes.md` §3).
- [ ] For fastapi-013: decide whether this query should proceed. No
      evidence of an actual flaky/concurrency test was found in this
      repository snapshot.
- [ ] For fastapi-017: resolve the `use_cache`-is-per-request-not
      -per-application distinction explicitly in your final judgment —
      grade `fastapi/dependencies/utils.py` according to what the query
      is actually asking, not according to what looks like the nearest
      keyword match.
- [ ] For fastapi-014: confirm whether the "combining two different
      security schemes" scenario is genuinely untested (as the search
      suggests) or whether a matching test exists under a
      non-obviously-named file the keyword search missed.
- [ ] Record every ambiguity resolution as a `notes` entry in the final
      `relevance_judgments.jsonl`, per the handbook's §5 guidance —
      resolving silently discards information a future reviewer would
      want.

## 9. Sign-off

- [ ] All `"TO_BE_ASSIGNED"` values replaced.
- [ ] All directory-level candidates resolved to specific files.
- [ ] fastapi-011 and fastapi-013 explicitly resolved (proceed with a
      real relevant set, or flagged for query revision — not left
      ambiguous).
- [ ] Every added/removed file recorded, so `dataset_statistics.md` can
      be regenerated accurately once real grades exist.
