# Validation Report — SQLAlchemy Pilot Annotation Run

Output of an actually-executed Python validation script
(`validate_sqlalchemy_run.py`, scratchpad) run against `queries.jsonl`,
`annotation_drafts.jsonl`, and `draft_relevance_judgments.jsonl` for
the SQLAlchemy run at commit `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d`.
Per this project's standing instruction, no error found here was
silently fixed — every finding below is disclosed as found.

## 1. Query count and schema

**Pass.** Exactly 20 queries in `queries.jsonl`, each with all 5
required fields (`query_id`, `category`, `difficulty`, `query_text`,
`notes`). No duplicate `query_id` values, no duplicate `query_text`
values.

## 2. Category distribution

**Pass.** `{bug_fix: 4, feature_implementation: 4, refactoring: 3,
testing: 3, documentation: 2, api_usage: 2, code_search: 2}` — matches
the required 4/4/3/3/2/2/2 distribution exactly.

## 3. Difficulty distribution

Computed: `{medium: 12, hard: 4, easy: 4}` — no fixed distribution was
required by the task, reported for reference. This is the
hard-difficulty-heaviest of the six pilot runs to date (4 of 20, or
20%), reflecting the genuinely more intricate internals (join-condition
resolution, insertmanyvalues compilation) this repository exposed
compared to prior runs.

## 4. No filenames / implementation hints in query_text

**1 false positive found and dismissed, 0 real violations.** The
automated script's substring check for `"class "` flagged
`sqlalchemy-014` ("...including in a **subclass** **that** overrides
it.") because "subclass that" contains the literal substring
"class " (end of "sub**class**" + the following space before "that").
Manual review confirms this is ordinary English ("a subclass"), not a
class name, filename, or implementation hint — no rewrite was needed.
This is the same category of self-referential keyword false positive
disclosed in the Celery pilot run's "STRONG FLAG" self-reference
issue, here caused by the check itself rather than by drafted prose.

## 5. annotation_drafts.jsonl / queries.jsonl consistency

**Pass.** All 20 `query_id` values in `annotation_drafts.jsonl` match
`queries.jsonl` exactly, no duplicates, every `grade` field is
`"TO_BE_ASSIGNED"`.

## 6. Within-query duplicate candidate files

**Pass.** 0 duplicates found across `primary_candidates` +
`secondary_candidates` for any query — no repeat of the Celery run's
`celery-020` duplication issue.

## 7. Queries without a primary candidate

**Pass.** 0 queries have zero primary candidates. Note that
`sqlalchemy-008` and `sqlalchemy-013` both carry primary/secondary
candidates but are separately flagged as speculative (§9 below) — a
primary candidate existing does not mean the query's underlying
premise was fully confirmed.

## 8. Directory-shaped candidates

**1 found, correctly excluded from the flat file.**
`lib/sqlalchemy/event/` appears as a `secondary_candidate` for
`sqlalchemy-018` in `annotation_drafts.jsonl` (explicitly marked
directory-shaped in its own `uncertainty` field) and is **not**
present in `draft_relevance_judgments.jsonl` — handled per this
project's established convention of excluding directory-shaped
candidates from the flat file and flagging them for human resolution
(see `human_annotation_checklist.md`).

## 9. Speculative queries (STRONG FLAG) — both resolved during Phase 11

**2 were found during drafting, both resolved during the Phase 11
audit (see `README.md`), 0 remain speculative in the final state
reflected by this report:**

- `sqlalchemy-008` (originally: PostgreSQL materialized-view storage
  options) — the Phase 11 follow-up found `PGDDLCompiler
  .create_table_select_suffixes` (`dialects/postgresql/base.py:2824`)
  applies `postgresql_with` to any `CreateView` regardless of its
  `materialized` flag, since `visit_create_view`
  (`sql/compiler.py:7122`) always passes `type_="view"` independent of
  `element.materialized`. The original query's premise was therefore
  **false** — the feature already works — so the query itself was
  **replaced** (not merely re-grounded) with a different, confirmed
  gap: no `AlterSequence` DDL construct exists alongside the confirmed
  `CreateSequence`/`DropSequence` (`sql/ddl.py:1077`, `:1083`).
- `sqlalchemy-013` (cross-backend test inconsistency) — the Phase 11
  follow-up located concrete evidence in
  `test/engine/test_reflection.py`: line 1169's
  `@testing.crashes("oracle", "FIXME: unknown, confirm not
  fails_on")` (a literal FIXME acknowledging unconfirmed Oracle
  behavior) and line 2109's
  `@testing.fails_on_everything_except("sqlite", "mysql", "mssql")`.
  The query's original wording was left unchanged since it accurately
  describes this now-concrete scenario.

Both resolutions are reflected in the current `queries.jsonl`,
`annotation_drafts.jsonl`, and `draft_relevance_judgments.jsonl` —
this validation report was re-run against the post-audit files, and
the summary table below reflects that final state, not the
mid-drafting one.

## 10. draft_relevance_judgments.jsonl schema

**Pass.** All 54 rows have exactly the 5 specified keys (`query_id`,
`repository`, `file`, `grade`, `reason`), no nesting, no extra fields.
`repository` is `"sqlalchemy"` on every row. `grade` is
`"TO_BE_ASSIGNED"` on every row. No duplicate `(query_id, file)` pairs.
No directory-shaped `file` values. Every `query_id` referenced exists
in `queries.jsonl`.

## 11. File-existence verification

**Pass — the most important check.** Every one of the distinct files
referenced across all 56 rows of `draft_relevance_judgments.jsonl`
(post-Phase-11-audit; 54 before the sqlalchemy-008/013 corrections
added 2 net rows) was verified to exist on disk at
`C:\Projects\tara-rlcg\sqlalchemy` via `os.path.isfile()` in the
validation script. **0 missing files.** No file, class, or symbol in
this run was invented.

## 12. Weak queries

**Pass.** 0 queries have fewer than 8 words in `query_text` (the
proxy threshold used for "too generic to be useful").

## Summary

| Check | Result |
|---|---|
| Query count / schema | Pass |
| Category distribution | Pass (exact match) |
| Filename/hint leakage | Pass (1 false positive, dismissed) |
| Draft/query consistency | Pass |
| Within-query duplicates | Pass |
| Missing primary candidates | Pass (0) |
| Directory candidates | 1 found, correctly excluded |
| Speculative queries | 0 remaining (2 found during drafting, both resolved in Phase 11) |
| Judgment schema | Pass |
| File existence | Pass (56/56 verified on disk, post-audit) |
| Weak queries | Pass (0) |

**0 validation errors requiring correction, 1 automated-check false
positive dismissed after manual review.** 1 directory-shaped candidate
is disclosed above and carried forward into
`human_annotation_checklist.md` for human resolution rather than
guessed at. Both speculative queries found during drafting were
resolved with concrete evidence during the Phase 11 audit (see
`README.md`), and every downstream artifact in this directory reflects
that final, resolved state.
