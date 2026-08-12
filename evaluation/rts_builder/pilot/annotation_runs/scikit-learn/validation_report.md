# Validation Report — scikit-learn Pilot Annotation Run

Output of an actually-executed Python validation script
(`validate_sklearn_run.py`, scratchpad) run against `queries.jsonl`,
`annotation_drafts.jsonl`, and `draft_relevance_judgments.jsonl` for
the scikit-learn run at commit `9b9be3abddd88675c5dc2e3623e652cb7545a26c`.
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

Computed: `{medium: 13, hard: 3, easy: 4}` — no fixed distribution was
required by the task, reported for reference.

## 4. No filenames / implementation hints in query_text

**3 false positives found and dismissed, 0 real violations.** The
automated script's substring check for `"class "` flagged three
queries, all for ordinary English usage rather than an actual class
name or filename:

- `sklearn-003`: "...per-class classifiers." — "class " is the tail of
  the hyphenated adjective "per-class" followed by "classifiers".
- `sklearn-009`: "the class hierarchy" — generic English, not a named
  class.
- `sklearn-013`: "multiclass meta-estimators" — "class " is the tail
  of "multiclass".

This is the third pilot run (after SQLAlchemy's `sqlalchemy-014` and
pandas's `pandas-009`) to trigger this specific class of automated
-check false positive — the substring `"class "` is common in ordinary
English machine-learning vocabulary ("per-class", "multiclass", "class
hierarchy") and does not, by itself, indicate a leaked implementation
detail. No rewrite was needed in any of the three cases.

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

**1 found, correctly excluded from the flat file.**
`examples/developing_estimators` appears as a `documentation_examples`
candidate for `sklearn-015` in `annotation_drafts.jsonl` (explicitly
marked directory-shaped in its own `uncertainty` field) and is **not**
present in `draft_relevance_judgments.jsonl` — handled per this
project's established convention of excluding directory-shaped
candidates from the flat file and flagging them for human resolution
(see `human_annotation_checklist.md`).

## 9. Speculative queries (STRONG FLAG)

**0 found.** Two Feature-category queries (`sklearn-006`, `sklearn-007`,
`sklearn-008`) whose grounding rests on a confirmed *absence* of a
capability were each verified with more than one independent search
term before being finalized (following the multi-term verification
discipline adopted after the pandas and SQLAlchemy pilot runs' premise
corrections), so none required a `STRONG FLAG` at drafting time. This
is the first pilot run where no query needed either a `STRONG FLAG` or
a premise replacement during drafting.

## 10. draft_relevance_judgments.jsonl schema

**Pass.** All 38 rows have exactly the 5 specified keys (`query_id`,
`repository`, `file`, `grade`, `reason`), no nesting, no extra fields.
`repository` is `"scikit-learn"` on every row. `grade` is
`"TO_BE_ASSIGNED"` on every row. No duplicate `(query_id, file)`
pairs. No directory-shaped `file` values. Every `query_id` referenced
exists in `queries.jsonl`.

## 11. File-existence verification

**Pass — the most important check.** Every one of the distinct files
referenced across all 38 rows of `draft_relevance_judgments.jsonl`
was verified to exist on disk at `C:\Projects\tara-rlcg\scikit-learn`
via `os.path.isfile()` in the validation script. **0 missing files.**
No file, class, or symbol in this run was invented.

## 12. Weak queries

**Pass.** 0 queries have fewer than 8 words in `query_text`.

## Summary

| Check | Result |
|---|---|
| Query count / schema | Pass |
| Category distribution | Pass (exact match) |
| Filename/hint leakage | Pass (3 false positives, all dismissed) |
| Draft/query consistency | Pass |
| Within-query duplicates | Pass |
| Missing primary candidates | Pass (0) |
| Directory candidates | 1 found, correctly excluded |
| Speculative queries | Pass (0 -- first pilot run with none) |
| Judgment schema | Pass |
| File existence | Pass (38/38 verified on disk) |
| Weak queries | Pass (0) |

**0 validation errors requiring correction.** 3 automated-check false
positives (all the `"class "` substring pattern) and 1 directory
-shaped candidate are disclosed above; the directory candidate is
carried forward into `human_annotation_checklist.md` for human
resolution rather than guessed at.
