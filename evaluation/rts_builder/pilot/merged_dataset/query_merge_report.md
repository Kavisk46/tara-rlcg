# Query Merge Report — RTS Dataset v1.0 Assembly

Phase 3 of the merged-dataset assembly. Documents how
`queries_master.jsonl` was produced from all 8 repositories'
`queries.jsonl` files, per the schema normalization disclosed in
`schema_validation_report.md` §2.

## Output

`queries_master.jsonl` — 160 rows, canonical schema per row:

```json
{"query_id": "", "repository_id": "", "category": "", "difficulty": "", "query_text": "", "notes": ""}
```

## Merge procedure

For each of the 8 repositories, in the fixed order fastapi, flask,
requests, click, celery, sqlalchemy, pandas, scikit-learn:

1. Load `annotation_runs/<repo>/queries.jsonl`.
2. For each row, set `repository_id` to the source directory name
   (cross-checked against the row's own `repository_id` field where
   present — 0 mismatches, see `schema_validation_report.md` §2a).
3. Read the query text from whichever of `query_text`/`query` is
   present, and always emit it as `query_text`.
4. Pass `category`, `difficulty`, and `notes` through unchanged.
5. Append to `queries_master.jsonl` in source order (fastapi-001
   through fastapi-020, then flask-001 through flask-020, and so on).

No query text, category, difficulty, or notes content was altered,
reworded, or invented at any point in this process — only field names
were unified across the two source conventions.

## Verification

All checks below were computed programmatically against the actual
merged output, not asserted.

### Row count

**160 total rows** = 20 queries × 8 repositories, confirmed exactly
(no repository contributed more or fewer than its expected 20).

| Repository | Queries merged |
|---|---|
| fastapi | 20 |
| flask | 20 |
| requests | 20 |
| click | 20 |
| celery | 20 |
| sqlalchemy | 20 |
| pandas | 20 |
| scikit-learn | 20 |
| **Total** | **160** |

### Unique query IDs

**0 duplicate `query_id` values** across all 160 rows. Every
`query_id` follows the `<repository_id>-<NNN>` convention with a
3-digit zero-padded sequence number, and every prefix matches the
row's `repository_id`.

### Category distribution (dataset-wide)

| Category | Count | Expected (8 × per-repo count) | Match? |
|---|---|---|---|
| bug_fix | 32 | 8 × 4 = 32 | Yes |
| feature_implementation | 32 | 8 × 4 = 32 | Yes |
| refactoring | 24 | 8 × 3 = 24 | Yes |
| testing | 24 | 8 × 3 = 24 | Yes |
| documentation | 16 | 8 × 2 = 16 | Yes |
| api_usage | 16 | 8 × 2 = 16 | Yes |
| code_search | 16 | 8 × 2 = 16 | Yes |
| **Total** | **160** | | |

**Every one of the 8 repositories independently satisfied the
mission's required 4/4/3/3/2/2/2 per-repository category distribution**
(this was independently verified and reported in each repository's own
`validation_report.md` during the annotation phase); the dataset-wide
totals above are the direct, exact sum of 8 identical per-repository
distributions, confirming no category was dropped, duplicated, or
miscounted during the merge.

### Difficulty distribution (dataset-wide)

| Difficulty | Count | Share |
|---|---|---|
| medium | 92 | 57.5% |
| easy | 39 | 24.4% |
| hard | 29 | 18.1% |

Unlike category (a fixed per-repository requirement), difficulty
distribution was left to each repository's own judgment, so this
dataset-wide total is not expected to hit a round number — it is
reported here for reference and broken down further in
`dataset_statistics.md`.

### Repository IDs

All 160 rows carry one of the 8 expected `repository_id` values, no
others. Confirmed via direct set comparison against the mission's
"Available Repositories" list.

### Required-field completeness

**0 rows** have a missing/`None` value in `category`, `difficulty`,
`query_text`, or `notes`.

## Outcome

**Phase 3 successful.** `queries_master.jsonl` contains exactly 160
well-formed, uniquely-identified, fully-populated rows, with the
category distribution matching the mission's requirement exactly and
no data loss from the underlying two-convention schema drift disclosed
in `schema_validation_report.md`.
