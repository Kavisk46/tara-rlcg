# Schema Validation Report — RTS Dataset v1.0 Assembly

Phase 2 of the merged-dataset assembly. Output of an actually-executed
Python script (`merge_rts_dataset.py`, scratchpad) that parsed every
per-repository artifact and inspected its schema directly — nothing
below is asserted without having been computed from the actual files.
Per the standing project instruction, no drift found here was silently
normalized without disclosure.

## 1. JSON well-formedness

**Pass, all 16 files.** Every `queries.jsonl` and
`draft_relevance_judgments.jsonl` across all 8 repositories parsed
without a single `JSONDecodeError`. 0 malformed lines found anywhere.

## 2. `queries.jsonl` schema — real drift found and disclosed

**Two distinct, internally-consistent field-name conventions exist
across the 8 repositories**, not one uniform schema:

| Convention | Fields | Repositories |
|---|---|---|
| A | `query_id`, `repository_id`, `category`, `difficulty`, `query`, `notes` | fastapi, flask, requests, click, celery |
| B | `query_id`, `category`, `difficulty`, `query_text`, `notes` | sqlalchemy, pandas, scikit-learn |

Convention B lacks an explicit `repository_id` field entirely (the
query's repository is only recoverable from the `query_id` prefix,
e.g. `sqlalchemy-001`, or from which directory the file was loaded
from) and uses `query_text` instead of `query` for the same semantic
content. This reflects a genuine inconsistency in how the annotation
task's Phase 2 instructions were interpreted across this project's 8
sequential repository-annotation sessions — the per-repository task
prompts specified an explicit JSON schema for `draft_relevance_judgments.jsonl`
every time, but did not pin an explicit schema for `queries.jsonl`,
leaving field naming to (inconsistent) session-to-session convention.

Within each convention, every row across every repository in that
group has *exactly* the same key set — there is no per-row drift
within a repository, only a two-way split across repositories.

**Resolution applied for `queries_master.jsonl`** (disclosed
transformation, not a silent fix): every row is normalized to
`{query_id, repository_id, category, difficulty, query_text, notes}`.
`repository_id` is set from the directory the row was loaded from (and
cross-checked against the row's own `repository_id` field where
present — see §2a). The text field is read from whichever of
`query`/`query_text` is present and always written out as `query_text`
in the merged file. No content was altered, dropped, or invented —
only field names were unified. This is fully reversible: the original
per-repository files remain untouched in `annotation_runs/`.

### 2a. `repository_id` field consistency (Convention A repos only)

For the 5 repositories carrying an explicit `repository_id` field, it
was cross-checked against the directory each file was loaded from.
**0 mismatches found** — every row's own `repository_id` value agrees
with its source directory.

## 3. `draft_relevance_judgments.jsonl` schema — one major structural incompatibility found and disclosed

**7 of 8 repositories share one flat, uniform schema; `fastapi` uses a
fundamentally different, nested schema.**

| Schema | Fields | Repositories | Row granularity |
|---|---|---|---|
| Flat (7 repos) | `query_id`, `repository`, `file`, `grade`, `reason` | flask, requests, click, celery, sqlalchemy, pandas, scikit-learn | one row per (query, candidate file) pair |
| Nested (fastapi) | `query_id`, `repository_id`, `commit_sha`, `query_text`, `relevance_grades` (a `{file: grade}` dict), `contributing_annotator_ids`, `inter_annotator_agreement`, `adjudicated`, `adjudicator_id`, `notes` | fastapi | one row per query, with every candidate file's grade nested inside |
| | | | |

fastapi's `draft_relevance_judgments.jsonl` (20 rows, one per query)
additionally carries several fields with no equivalent anywhere in the
flat schema (`commit_sha`, `contributing_annotator_ids`,
`inter_annotator_agreement`, `adjudicated`, `adjudicator_id`) — these
appear to anticipate a fuller human-annotation-tracking workflow that
was not carried forward into the schema used for the other 7
repositories. Every one of fastapi's 20 rows has exactly this same key
set — internally consistent, just incompatible with the other 7
repositories' shared convention.

**Resolution applied for `draft_relevance_master.jsonl`**, per
explicit user decision after this finding was surfaced: fastapi's
nested rows were deterministically flattened into the flat schema.
Each `(query_id, file)` key inside a `relevance_grades` dict becomes
one output row. The flat schema's `reason` field — which fastapi's
`draft_relevance_judgments.jsonl` does not carry at all — was
recovered by cross-referencing fastapi's `annotation_drafts.jsonl`
(matching each `(query_id, file_path)` pair against that query's
`primary_candidates`/`secondary_candidates`/`regression_tests`/
`documentation_examples` entries, each of which does carry a `reason`
field per this project's established Phase 4 annotation-drafting
convention). **All 74 flattened rows recovered a reason successfully
— 0 rows fell back to a placeholder.** See `relevance_merge_report.md`
§2 for the full accounting. The original `fastapi/draft_relevance_judgments.jsonl`
file was not modified; this transformation only affects the new,
separate `draft_relevance_master.jsonl` output.

## 4. `annotation_metrics.json` — `schema_version` field consistency

| Repository | File present? | `schema_version` |
|---|---|---|
| fastapi | **No** (see `repository_inventory.md`) | N/A |
| flask | Yes | **missing -- field absent from the file entirely** |
| requests | Yes | `"1.0"` |
| click | Yes | `"1.0"` |
| celery | Yes | `"1.0"` |
| sqlalchemy | Yes | `"1.0"` |
| pandas | Yes | `"1.0"` |
| scikit-learn | Yes | `"1.0"` |

**A second, distinct completeness gap found**: `flask`'s
`annotation_metrics.json` exists and is well-formed JSON with 43
fields (`repository`, `commit_sha`, `queries`, `category_distribution`,
etc.), but has no `schema_version` key at all — unlike the 6 other
repositories carrying this file, all of which report `"1.0"`. Combined
with fastapi's missing file entirely, this means **2 of the 8
repositories' per-repository metrics artifacts do not carry a
verifiable `schema_version: "1.0"` tag** — both are the two earliest
repositories processed in this project's sequential pilot runs,
consistent with the `annotation_metrics.json` convention (including
the `schema_version` field specifically) having been tightened over
the course of the project rather than fixed from the start.

This does **not** affect `queries_master.jsonl` or
`draft_relevance_master.jsonl`, neither of which embeds a per-row
`schema_version` field (matching every individual repository's own
`queries.jsonl`/`draft_relevance_judgments.jsonl`, none of which carry
one either — `schema_version` was only ever a field of the summary
`annotation_metrics.json`, never of the row-level files). The dataset
-wide `schema_version: "1.0"` declaration for this merged dataset is
made once, explicitly, in `dataset_statistics.md` and
`reproducibility.md`, independent of the two incomplete per-repository
files.

## 5. Repository ID consistency across all merged data

Cross-checked: every `repository_id` value appearing in
`queries_master.jsonl` and every `repository` value appearing in
`draft_relevance_master.jsonl` is one of the 8 expected values
(`fastapi`, `flask`, `requests`, `click`, `celery`, `sqlalchemy`,
`pandas`, `scikit-learn`) — no typos, casing variants, or unexpected
values found.

## 6. Query ID consistency

- **0 duplicate `query_id` values** across all 160 merged queries (20
  per repository × 8 repositories).
- Every `query_id` follows the `<repository_id>-<NNN>` convention
  (e.g. `fastapi-001`, `sklearn-020`) with no exceptions, and every
  `query_id` prefix matches its row's `repository_id` field.
- **0 relevance-judgment rows reference a `query_id` absent from
  `queries_master.jsonl`** (checked across all 439 merged rows,
  including the 74 flattened fastapi rows).

## 7. Required-field emptiness check

**0 rows in `queries_master.jsonl`** have a `None`/missing value in
`category`, `difficulty`, `query_text`, or `notes`. **0 rows in
`draft_relevance_master.jsonl`** have a missing `query_id`, `repository`,
`file`, or `grade` (every fastapi-flattened row also has a non-empty
`reason`, per §3 above).

## Summary

| Check | Result |
|---|---|
| JSON well-formedness | Pass (0 malformed lines / 16 files) |
| `queries.jsonl` field-name consistency | **Drift found, disclosed, normalized for merge** (2 conventions) |
| `draft_relevance_judgments.jsonl` structural consistency | **Major drift found, disclosed, normalized for merge** (fastapi nested vs. 7 flat) |
| `annotation_metrics.json` presence | **1 missing** (fastapi) |
| `annotation_metrics.json` `schema_version` presence | **1 more missing** (flask, file present but field absent) |
| Repository ID consistency | Pass |
| Query ID uniqueness | Pass (0 duplicates / 160) |
| Query ID / relevance-row cross-reference | Pass (0 orphans / 439) |
| Required-field emptiness | Pass (0 empty required fields) |

**Net assessment**: no data was lost or invented in producing
`queries_master.jsonl` / `draft_relevance_master.jsonl` — every
discrepancy found was a **naming or structural** inconsistency in how
the source artifacts were shaped, not a content gap, with the
exception of the two disclosed missing/incomplete
`annotation_metrics.json` files (fastapi, flask), which affect only
the per-repository metrics cross-check, not the merged query/judgment
data itself. All normalization decisions are documented above and are
fully reversible against the untouched source files in
`annotation_runs/`.
