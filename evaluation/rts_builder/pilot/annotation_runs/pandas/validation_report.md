# Validation Report — pandas Pilot Annotation Run

Output of an actually-executed Python validation script
(`validate_pandas_run.py`, scratchpad) run against `queries.jsonl`,
`annotation_drafts.jsonl`, and `draft_relevance_judgments.jsonl` for
the pandas run at commit `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8`.
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

Computed: `{hard: 5, medium: 11, easy: 4}` — no fixed distribution was
required by the task, reported for reference. This is the
hard-difficulty-heaviest of all seven pilot runs to date (5 of 20, or
25%), consistent with pandas being the largest and most structurally
intricate repository processed in this project so far (`repository_summary.md`
§9).

## 4. No filenames / implementation hints in query_text

**1 false positive found and dismissed, 0 real violations.** The
automated script's substring check for `"class "` flagged
`pandas-009` ("Simplify the **class** **hierarchy** used internally
...") because "the class hierarchy" contains the literal substring
"class " as ordinary English, not a class name, filename, or
implementation hint. This is the same category of self-referential
keyword false positive disclosed in the SQLAlchemy pilot run's
`sqlalchemy-014` finding ("...in a **subclass** that overrides it")
and the Celery pilot run's "STRONG FLAG" self-reference issue — no
rewrite was needed.

## 5. annotation_drafts.jsonl / queries.jsonl consistency

**Pass.** All 20 `query_id` values in `annotation_drafts.jsonl` match
`queries.jsonl` exactly, no duplicates, every `grade` field is
`"TO_BE_ASSIGNED"`.

## 6. Within-query duplicate candidate files

**Pass.** 0 duplicates found across `primary_candidates` +
`secondary_candidates` for any query.

## 7. Queries without a primary candidate

**Pass.** 0 queries have zero primary candidates.

## 8. Directory-shaped candidates

**0 found.** Every candidate file path in `annotation_drafts.jsonl`
resolves to a concrete file, not a directory — no candidate required
exclusion from `draft_relevance_judgments.jsonl` on this basis, unlike
the SQLAlchemy and Celery runs.

## 9. Speculative queries (STRONG FLAG) — resolved before this report

**1 was found during Phase 3/4 drafting, resolved immediately (not
deferred to Phase 11), 0 remain speculative in the final state
reflected by this report:**

- `pandas-006` (originally: direct DataFrame-to-Arrow-table conversion)
  — a name-based grep for `to_arrow` across `core/*.py` and
  `core/arrays/*.py` found no match, so the query was drafted with a
  `STRONG FLAG`. A broader follow-up search (grepping for
  `__arrow_c_stream__`) found that `DataFrame.__arrow_c_stream__`
  (`frame.py:744`) and `Series.__arrow_c_stream__` (`series.py:559`)
  already implement the Arrow PyCapsule Protocol — the feature already
  exists under a different name than the one searched for. The query
  was **replaced** (not merely re-grounded) with a differently
  -grounded, confirmed gap: `to_csv`'s `na_rep` parameter
  (`generic.py:2203`) is typed as a single scalar `str`, not a
  per-column mapping.

This is the second pilot run (after SQLAlchemy's `sqlalchemy-008`) in
which a name-based grep for an absent capability missed a
differently-named existing mechanism — a pattern worth flagging
explicitly for future rounds (see `research_notes.md`).

**A second, smaller correction was made during the Phase 11 audit**:
`pandas-006`'s replacement premise (`to_csv`'s `na_rep` is a scalar
`str`, not per-column) was originally grounded with the citation
`generic.py:2203`. Re-verifying this citation during the audit found
that line actually belongs to `to_excel`'s `na_rep` parameter, not
`to_csv`'s — a proximity mistake (both parameters share a name and
sit in the same large file). The underlying claim was still correct
(`to_csv`'s own `na_rep` is confirmed scalar `str` at its
implementation signature, line 3917), so no query needed replacing,
but the citation in `queries.jsonl` and `annotation_drafts.jsonl` was
corrected to the accurate line number.

## 10. draft_relevance_judgments.jsonl schema

**Pass.** All 55 rows have exactly the 5 specified keys (`query_id`,
`repository`, `file`, `grade`, `reason`), no nesting, no extra fields.
`repository` is `"pandas"` on every row. `grade` is `"TO_BE_ASSIGNED"`
on every row. No duplicate `(query_id, file)` pairs. No
directory-shaped `file` values. Every `query_id` referenced exists in
`queries.jsonl`.

## 11. File-existence verification

**Pass — the most important check.** Every one of the distinct files
referenced across all 55 rows of `draft_relevance_judgments.jsonl`
was verified to exist on disk at `C:\Projects\tara-rlcg\pandas` via
`os.path.isfile()` in the validation script. **0 missing files.** No
file, class, or symbol in this run was invented.

## 12. Weak queries

**Pass.** 0 queries have fewer than 8 words in `query_text`.

## Summary

| Check | Result |
|---|---|
| Query count / schema | Pass |
| Category distribution | Pass (exact match) |
| Filename/hint leakage | Pass (1 false positive, dismissed) |
| Draft/query consistency | Pass |
| Within-query duplicates | Pass |
| Missing primary candidates | Pass (0) |
| Directory candidates | Pass (0 found) |
| Speculative queries | 0 remaining (1 found during drafting, resolved before this report) |
| Judgment schema | Pass |
| File existence | Pass (55/55 verified on disk) |
| Weak queries | Pass (0) |

**0 validation errors requiring correction, 1 automated-check false
positive dismissed after manual review.** 1 query's original premise
was found false during drafting and replaced with a differently
-grounded, confirmed gap before this report was written — disclosed in
full above and in `research_notes.md`.
