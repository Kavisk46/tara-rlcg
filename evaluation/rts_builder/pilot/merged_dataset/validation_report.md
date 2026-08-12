# Dataset-Wide Validation Report — RTS Dataset v1.0 Assembly

Phase 5 of the merged-dataset assembly. This is a **dataset-wide**
validation of `queries_master.jsonl` and `draft_relevance_master.jsonl`
— distinct from, and in addition to, each individual repository's own
`validation_report.md` produced during its annotation run (which
validated that repository's data in isolation, before merging). Every
check below was computed programmatically against the actual merged
files. Per the standing project instruction, nothing found here was
silently fixed.

## 1. Duplicate queries

- **Duplicate `query_id` values: 0** across all 160 rows of
  `queries_master.jsonl`.
- **Exact-duplicate `query_text` values: 0** across all 160 rows —
  every query, across all 8 repositories combined, has distinct
  wording.
- Near-duplicate *intent* across different repositories (e.g. two
  different repos both having a "code search for the connection-pool
  lifecycle" style query) was not algorithmically checked — this is
  expected and unproblematic across independently-authored repository
  query sets, and each per-repository annotation run already checked
  for within-repository intent duplication (see individual
  `validation_report.md` files, e.g. fastapi's §1).

## 2. Duplicate IDs

**0 duplicate `query_id` values.** Confirmed both within each
repository's 20-query contribution and across the full 160-row merged
set (query IDs are namespaced by repository prefix, e.g.
`fastapi-001` vs. `flask-001`, so cross-repository collision was
structurally impossible, and this was still verified directly rather
than assumed).

## 3. Duplicate candidate files

**0 duplicate `(query_id, file)` pairs** across all 439 rows of
`draft_relevance_master.jsonl` — see `relevance_merge_report.md` §"No
duplicate (query, file) pairs" for the full accounting, including the
74 rows produced by flattening fastapi's nested schema.

## 4. Schema drift

**Found and disclosed in full in `schema_validation_report.md`,
resolved via explicit, documented normalization for the merge:**

- `queries.jsonl`: 2 field-naming conventions across the 8
  repositories (`query`+`repository_id` vs. `query_text` with no
  `repository_id`), normalized to one canonical schema.
- `draft_relevance_judgments.jsonl`: fastapi's nested,
  one-row-per-query schema vs. the other 7 repositories' flat,
  one-row-per-file schema, resolved via a disclosed, lossless
  flattening transformation (see `relevance_merge_report.md` §"fastapi
  — flattening transformation").
- `annotation_metrics.json`: fastapi missing the file entirely; flask
  missing the `schema_version` field within an otherwise-present file.
  Neither affects the merged query/judgment data itself (see §6
  below).

No other schema drift was found: `category` and `difficulty` values
use identical vocabularies across all 8 repositories
(`bug_fix`/`feature_implementation`/`refactoring`/`testing`/
`documentation`/`api_usage`/`code_search` and
`easy`/`medium`/`hard` respectively — confirmed by direct set
comparison, 0 unexpected values), and `grade` is uniformly
`"TO_BE_ASSIGNED"` across all 439 relevance rows.

## 5. Missing repositories

**0 missing.** All 8 repositories listed in the mission
(`fastapi`, `flask`, `requests`, `click`, `celery`, `sqlalchemy`,
`pandas`, `scikit-learn`) are present and contributed exactly 20
queries each — see `repository_inventory.md`.

## 6. Missing files

Two distinct, disclosed gaps, neither of which corrupts or blocks the
merged dataset:

1. **`fastapi/annotation_metrics.json` is entirely absent** (see
   `repository_inventory.md`). Its content is independently
   re-derivable from fastapi's present `queries.jsonl` +
   `annotation_drafts.jsonl` + `draft_relevance_judgments.jsonl`, and
   the equivalent figures for fastapi are computed directly in
   `dataset_statistics.md` from those present files.
2. **`flask/annotation_metrics.json` is present but missing the
   `schema_version` field** (see `schema_validation_report.md` §4).
   All 42 other fields in that file are present and were used
   normally.

**0 missing files among the data actually merged**: every one of the
249 distinct `(repository, file)` pairs referenced across all 439 rows
of `draft_relevance_master.jsonl` was verified to exist on disk in the
corresponding pinned-commit repository clone (see
`relevance_merge_report.md` §"File-existence verification"). **0
directory-shaped file paths** made it into the merged relevance file
(cross-checked directly; fastapi's 7 known directory-level candidates,
disclosed in its own `validation_report.md` §4, were correctly never
present in fastapi's `draft_relevance_judgments.jsonl`'s
`relevance_grades` in the first place, so none survived into the
flattened master file).

## 7. Empty fields

**0 rows** in `queries_master.jsonl` have an empty/`None` `category`,
`difficulty`, `query_text`, or `notes`. **0 rows** in
`draft_relevance_master.jsonl` have an empty `query_id`, `repository`,
`file`, `grade`, or `reason`.

## 8. Category balance

| Category | Count | Share | Required per repo | Dataset-wide expected (×8) |
|---|---|---|---|---|
| bug_fix | 32 | 20.0% | 4 | 32 |
| feature_implementation | 32 | 20.0% | 4 | 32 |
| refactoring | 24 | 15.0% | 3 | 24 |
| testing | 24 | 15.0% | 3 | 24 |
| documentation | 16 | 10.0% | 2 | 16 |
| api_usage | 16 | 10.0% | 2 | 16 |
| code_search | 16 | 10.0% | 2 | 16 |

**Exact match, every category.** All 8 repositories independently hit
the mission's required 4/4/3/3/2/2/2 distribution, so the dataset-wide
total is exactly 8× that per-repository distribution with no drift
introduced by the merge.

## 9. Difficulty balance

| Difficulty | Count | Share |
|---|---|---|
| medium | 92 | 57.5% |
| easy | 39 | 24.4% |
| hard | 29 | 18.1% |

No fixed target was specified for difficulty (unlike category), so
this is reported descriptively. See `dataset_statistics.md` §3 for the
per-repository breakdown — difficulty skew varies meaningfully by
repository (e.g. scikit-learn's flatter file-per-estimator structure
produced fewer hard queries than SQLAlchemy's or pandas's more
deeply-layered internals).

## 10. Repository balance

**Perfectly balanced: exactly 20 queries from every one of the 8
repositories**, confirmed by direct count
(`{fastapi: 20, flask: 20, requests: 20, click: 20, celery: 20,
sqlalchemy: 20, pandas: 20, scikit-learn: 20}`). Relevance-judgment row
counts are naturally unbalanced across repositories (38 for
scikit-learn to 74 for fastapi) since each query's candidate-file
count varies by query and repository structure — this is expected and
is not a balance requirement in the same sense as query count or
category distribution; see `dataset_statistics.md` §5 for the full
breakdown and explanation.

## Summary

| Check | Result |
|---|---|
| Duplicate queries | Pass (0) |
| Duplicate IDs | Pass (0) |
| Duplicate candidate files | Pass (0) |
| Schema drift | **Found, disclosed, resolved via documented normalization** |
| Missing repositories | Pass (0 / 8) |
| Missing files | **2 disclosed per-repository metadata gaps** (fastapi's whole `annotation_metrics.json`; flask's `schema_version` field); **0 missing among merged query/judgment data** |
| Empty fields | Pass (0) |
| Category balance | Pass (exact match, all 8 repos) |
| Difficulty balance | Reported (no fixed target) |
| Repository balance | Pass (20/20/20/20/20/20/20/20) |

**Overall: the merged dataset passes dataset-wide validation.** The
two disclosed per-repository metadata gaps (§6) are pre-existing
limitations of the earliest two annotation runs in this project's
sequence, not defects introduced by this assembly, and do not affect
the integrity, referential consistency, or file-existence guarantees
of `queries_master.jsonl` or `draft_relevance_master.jsonl` — both of
which pass every check above with 0 unresolved errors. This finding is
carried forward explicitly into the Phase 10 Publication Audit rather
than omitted.
