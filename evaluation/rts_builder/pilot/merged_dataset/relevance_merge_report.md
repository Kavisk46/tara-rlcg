# Relevance Merge Report — RTS Dataset v1.0 Assembly

Phase 4 of the merged-dataset assembly. Documents how
`draft_relevance_master.jsonl` was produced from all 8 repositories'
`draft_relevance_judgments.jsonl` files, per the structural
normalization disclosed in `schema_validation_report.md` §3.

## Output

`draft_relevance_master.jsonl` — 439 rows, canonical schema per row:

```json
{"query_id": "", "repository": "", "file": "", "grade": "TO_BE_ASSIGNED", "reason": ""}
```

## Merge procedure

### flask, requests, click, celery, sqlalchemy, pandas, scikit-learn (7 repos)

Already flat, one row per `(query_id, file)` pair, exactly matching
the canonical schema. Loaded and appended directly, with `repository`
defaulted to the source directory name if the row's own field were
ever absent (it was not, in any of these 7 repositories' 365 combined
rows).

### fastapi (1 repo) — flattening transformation

fastapi's `draft_relevance_judgments.jsonl` has 20 rows, one per
query, each with a nested `relevance_grades` object mapping file path
to grade (see `schema_validation_report.md` §3 for the full field
list). This was flattened as follows:

1. For each of fastapi's 20 query-rows, iterate its `relevance_grades`
   dict's `(file_path, grade)` pairs.
2. For each pair, emit one flat row: `query_id` and `grade` copied
   directly, `repository` set to `"fastapi"`, `file` set to
   `file_path`.
3. The flat schema's `reason` field has no source in
   `draft_relevance_judgments.jsonl` (fastapi's version of that file
   does not carry per-file reasons, only the nested grade mapping) —
   it was recovered by looking up the same `(query_id, file_path)`
   pair in `annotation_runs/fastapi/annotation_drafts.jsonl`, searching
   across that query's `primary_candidates`, `secondary_candidates`,
   `regression_tests`, and `documentation_examples` arrays (each entry
   in those arrays carries a `file_path` and a `reason` field, per this
   project's established Phase 4 annotation-drafting convention used
   identically across all 8 repositories).

**Result: 20 nested rows → 74 flat rows.** Every one of the 74 rows
successfully recovered a `reason` from `annotation_drafts.jsonl` — 0
rows required the fallback placeholder text ("reason not recoverable
..."), meaning fastapi's `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl` are fully mutually consistent (every
file listed in a `relevance_grades` dict also appears as a candidate
with a reason in the corresponding drafts entry).

This transformation is deterministic and fully reversible: no
information from fastapi's original `draft_relevance_judgments.jsonl`
was discarded (every file/grade pair is represented), and the
recovered `reason` values are copied verbatim from
`annotation_drafts.jsonl`, not paraphrased or invented. The original
`fastapi/draft_relevance_judgments.jsonl` file itself was not modified
— this flattening only produced the new, separate
`draft_relevance_master.jsonl` output.

## Verification

All checks below were computed programmatically against the actual
merged output.

### Row count by repository

| Repository | Rows in `draft_relevance_master.jsonl` | Source form |
|---|---|---|
| fastapi | 74 | flattened from 20 nested rows |
| flask | 62 | already flat |
| requests | 47 | already flat |
| click | 54 | already flat |
| celery | 53 | already flat |
| sqlalchemy | 56 | already flat |
| pandas | 55 | already flat |
| scikit-learn | 38 | already flat |
| **Total** | **439** | |

### No duplicate (query, file) pairs

**0 duplicate `(query_id, file)` pairs** across all 439 rows —
verified by direct set-cardinality comparison against the row count.
This holds both within each repository's contribution and across the
whole merged file (no risk of cross-repository collision, since every
`query_id` is already globally unique per `query_merge_report.md`).

### Referential integrity against `queries_master.jsonl`

**0 rows** reference a `query_id` not present in the 160-row
`queries_master.jsonl` — every relevance judgment traces to a real,
merged query.

### File-existence verification against the actual pinned-commit repositories

Every distinct `(repository, file)` pair across all 439 rows — 249
distinct pairs — was checked against the corresponding local repository
clone (`C:\Projects\tara-rlcg\<repo>`) via direct filesystem lookup.
**0 missing files.** This re-verifies, at the assembly level, the same
file-existence guarantee each repository's own `validation_report.md`
already established individually — no drift occurred in the merge
itself, and no file reference was corrupted by the fastapi flattening
transformation.

### Grade distribution

**439 of 439 rows (100%) have `grade: "TO_BE_ASSIGNED"`** — expected,
since no human annotation has occurred for any of the 8 repositories
yet. This master file remains a draft scaffold for human review, not a
finished relevance-judgment set, consistent with every individual
repository's own README stating the same.

### Required-field completeness

**0 rows** have a missing `query_id`, `repository`, `file`, or
`grade`. Every row (including all 74 flattened fastapi rows) has a
non-empty `reason`.

## Outcome

**Phase 4 successful.** `draft_relevance_master.jsonl` contains 439
well-formed, non-duplicated, fully-referential rows, all grades
correctly marked `"TO_BE_ASSIGNED"` pending human review, and the
fastapi schema-flattening transformation completed with 0 information
loss.
