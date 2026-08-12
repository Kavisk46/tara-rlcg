# Human Annotation Checklist — SQLAlchemy Pilot Run

Governs human review of `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl`, both produced by an AI search
assistant (not a human annotator) against SQLAlchemy at commit
`dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` (version `2.1.0b4`, a beta
release). Per `RELEVANCE_ANNOTATION_HANDBOOK.md`, no relevance grade
here is final — every `"TO_BE_ASSIGNED"` value must be replaced by a
human annotator before this data is merged into the pipeline's
`queries.jsonl`.

## ☐ Verify suggested files

- [ ] Open every file referenced in `annotation_drafts.jsonl` and
      `draft_relevance_judgments.jsonl` at the pinned commit and
      confirm it exists exactly as stated (all 56 rows'
      files were verified to exist on disk by the validation script,
      but existence alone is not content-correctness).
- [ ] This run has **1 directory-level candidate**, excluded from the
      final file: `lib/sqlalchemy/event/`, a secondary candidate for
      `sqlalchemy-018`. Resolve to a specific file within it (or
      confirm `engine/events.py` alone is sufficient) before grading.
- [ ] Pay particular attention to `lib/sqlalchemy/orm/relationships.py`
      and `lib/sqlalchemy/pool/base.py` (each a candidate for 5 of the
      20 queries) — verify the specific class claimed
      (`RelationshipProperty`/`_JoinCondition` vs. `Pool`/
      `_ConnectionRecord`/`_ConnectionFairy`), not just the file.

## ☐ Verify symbols

- [ ] For every `important_symbols` entry, confirm the class/function
      exists at the stated file/line and still matches its described
      role.
- [ ] Specifically confirm `lib/sqlalchemy/sql/compiler.py`'s
      `_InsertManyValues`/`_InsertManyValuesBatch`/
      `InsertmanyvaluesSentinelOpts` (lines 501, 633, 658) —
      `sqlalchemy-009`'s refactor premise depends on this machinery in
      the repository's largest file (8,398 lines).
- [ ] Specifically confirm the 3-of-5-dialects `has_multi_table`
      adoption pattern underlying `sqlalchemy-011`: implemented in
      `dialects/mssql/base.py:3385`, `dialects/oracle/base.py:2336`,
      and `dialects/postgresql/base.py:3993`, and absent from a grep
      of `dialects/mysql/base.py` and `dialects/sqlite/base.py` in the
      same search.
- [ ] Specifically confirm `test/engine/test_reflection.py`'s two
      backend-conditional test markers underlying the Phase-11
      -resolved `sqlalchemy-013`: `@testing.crashes("oracle", "FIXME:
      unknown, confirm not fails_on")` at line 1169 and
      `@testing.fails_on_everything_except("sqlite", "mysql",
      "mssql")` at line 2109.
- [ ] Specifically confirm `lib/sqlalchemy/sql/ddl.py` has
      `CreateSequence` (line 1077) and `DropSequence` (line 1083) but
      no `AlterSequence` — the premise `sqlalchemy-008` was replaced
      to target after the original materialized-view premise was
      found to be false (see `README.md`'s Phase 11 audit).

## ☐ Remove hallucinations

- [ ] No file, class, or function in this run was invented — every
      entry came from an actual `Read`/`Grep`/directory-listing call,
      and every file referenced in `draft_relevance_judgments.jsonl`
      was independently verified to exist on disk by
      `validate_sqlalchemy_run.py`. Confirm this yourself for a sample
      rather than trusting the confidence labels at face value.
- [ ] Treat every candidate whose `uncertainty` says "existence
      confirmed... contents not read" as existence-only-confirmed, not
      content-verified. Given this repository's size (255 package
      files vs. 17-161 in the other five pilot runs), a substantial
      fraction of candidates fall into this category.
- [ ] **Verify the 11 already-resolved `unreleased_21/` behaviors
      listed in `repository_summary.md` §9 were correctly avoided as
      Bug Fix query targets** — spot-check at least 3 of the 12 read
      changelog fragments against their corresponding source files.

## ☐ Add missing files

- [ ] `sqlalchemy-018`: resolve `lib/sqlalchemy/event/` (a directory)
      to the specific file(s) most relevant to registering a
      before-execute-style event listener, if `engine/events.py`
      alone is judged insufficient.
- [ ] For every query, consider whether any of the changelog fragments
      *not* explicitly cross-checked against a specific query (only
      11 of the 12 were used to rule out specific Bug Fix candidates;
      `11122.rst`'s postgresql_with-for-CreateView content was reused
      to both avoid one Bug Fix framing and, indirectly, to resolve
      `sqlalchemy-008`'s original premise) bear on any of the other
      19 queries in ways this pass did not identify.
- [ ] Consider whether `orm/decl_api.py` (declarative/dataclass
      mapping API, confirmed present in `repository_summary.md` but
      not the subject of any of this round's 20 queries) or the
      `connectors/`, `ext/`, `future/` subpackages (entirely untouched
      this round, per `dataset_statistics.md` §9) should be
      represented in a future annotation round for this repository.

## ☐ Verify regression tests

- [ ] For every regression-test candidate, open the file and identify
      the specific test function(s) actually relevant to the query —
      all were existence-confirmed only in this pass (plus, for
      `sqlalchemy-013`, two specific decorator usage *lines*, but not
      the full test function bodies at those lines).
- [ ] Run the identified tests against the pinned commit; no test in
      this run was executed by the AI assistant.
- [ ] For `sqlalchemy-013` specifically: read the full test functions
      at `test/engine/test_reflection.py:1169` and `:2109` to
      determine what specific reflection behavior each guards, and
      whether either currently exhibits actual cross-backend
      inconsistency (as opposed to being defensively pre-marked).

## ☐ Verify documentation

- [ ] Every `.rst` documentation candidate in this run is
      existence-confirmed only via directory listing — open each one
      and confirm its actual content before grading.
- [ ] `doc/build/orm/basic_relationships.rst` is a candidate for both
      `sqlalchemy-015` and `sqlalchemy-017` — reading it once during
      review will inform grading for both simultaneously, alongside
      `doc/build/orm/relationships.rst` and `relationship_api.rst`
      (also candidates for `sqlalchemy-015`).

## ☐ Assign relevance grades

- [ ] Follow `RELEVANCE_ANNOTATION_HANDBOOK.md` in full.
- [ ] Replace every `"TO_BE_ASSIGNED"` in `draft_relevance_judgments.jsonl`
      with an integer grade in `{1, 2, 3}`, or remove the line entirely
      if the file is not relevant (grade 0 — per the handbook, absence
      is how grade 0 is recorded).
- [ ] Do not grade a file relevant solely because it appears in this
      draft.

## ☐ Resolve ambiguity

- [ ] `sqlalchemy-004`: the loader-strategy duplicate-row scenario is
      grounded in real machinery (`orm/strategies.py`'s `_JoinedLoader`)
      but not confirmed as an actual reproducible defect at this
      commit — confirm whether it should be treated as a genuinely
      open bug-fix target or reworded.
  - [ ] `sqlalchemy-013`: the two specific test lines identified during
      Phase 11 are strong evidence of *some* backend-dependent
      behavior, but which one (if either) is the "right" answer for
      this query, and whether either is currently actually failing
      rather than defensively marked, was not determined this pass.
- [ ] `sqlalchemy-011`: confirm whether `mysql` and `sqlite` dialects
      genuinely lack `has_multi_table` (as this pass's grep found) or
      whether an equivalent mechanism exists under a different name
      not searched for.

## ☐ Record annotation rationale

- [ ] For every grade assigned, record a rationale in the final
      relevance-judgment file per `RELEVANCE_ANNOTATION_HANDBOOK.md`
      §2's requirement.
- [ ] For every ambiguity resolved above, record the resolution and
      its reasoning.
- [ ] Record that `sqlalchemy-008` was substantively replaced (not
      merely re-grounded) during the Phase 11 audit, and why — this is
      the first pilot run where a query's underlying premise was found
      to be factually false (not just under-evidenced) and the query
      itself was swapped out rather than reworded in place.
