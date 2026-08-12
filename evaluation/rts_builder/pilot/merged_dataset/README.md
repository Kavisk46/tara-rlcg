# RTS Dataset v1.0 — Merged Pilot Dataset

The first unified TARA RTS Pilot Dataset, assembled from all 8
completed repository-annotation runs under `../annotation_runs/`. This
directory is the **output** of a dataset-assembly session — it merges,
validates, statistically summarizes, splits, documents, and audits the
8 repositories' independently-produced annotation artifacts. It does
not redesign, re-annotate, or modify any frozen upstream TARA
component or any file under `../annotation_runs/`.

## Files in this directory

| File | Phase | Purpose |
|---|---|---|
| `repository_inventory.md` | 1 | Confirms all 8 repositories and their required files are present; discloses 1 missing file (fastapi's `annotation_metrics.json`) and re-verifies all 8 pinned commits. |
| `schema_validation_report.md` | 2 | Discloses and resolves 2 real schema-drift findings across the source `queries.jsonl`/`draft_relevance_judgments.jsonl` files, plus 1 more missing-field finding (flask's `annotation_metrics.json`). |
| `queries_master.jsonl` | 3 | 160 merged queries (20 × 8 repositories), canonical schema. |
| `query_merge_report.md` | 3 | Verifies the query merge: 0 duplicate IDs, exact category balance, perfect repository balance. |
| `draft_relevance_master.jsonl` | 4 | 439 merged candidate-file relevance-judgment rows, canonical flat schema (fastapi's nested source schema deterministically flattened). |
| `relevance_merge_report.md` | 4 | Verifies the relevance-judgment merge: 0 duplicate `(query, file)` pairs, 0 orphaned rows, all 249 distinct referenced files re-verified to exist on disk. |
| `validation_report.md` | 5 | Dataset-wide validation across both master files: duplicates, schema drift, balance, missing files. |
| `dataset_statistics.md` | 6 | Full dataset-wide statistics: per-repository, per-category, per-difficulty, candidate-file distribution, weak/speculative query counts. |
| `train.jsonl` / `validation.jsonl` / `test.jsonl` | 7 | Deterministic 70/15/15 split (112/24/24 rows), stratified by repository, seed 42. Each row is a self-contained query record with nested candidates. |
| `dataset_card.md` | 8 | Purpose, methodology, repositories, schema, annotation protocol, quality control, known limitations, threats to validity, license considerations. |
| `reproducibility.md` | 9 | Pinned commits, pipeline/schema versions, SHA-256 input/output digests, build environment, split methodology and seed, directory structure. |
| `README.md` (this file) | -- | Overview and the Phase 10 Publication Audit. |

## Assembly pipeline

```
annotation_runs/{fastapi,flask,requests,click,celery,sqlalchemy,pandas,scikit-learn}/
        |
        v
[ Phase 1: repository_inventory.md -- 8/8 repos found;
  1 missing file disclosed (fastapi/annotation_metrics.json) ]
        |
        v
[ Phase 2: schema_validation_report.md -- 2 schema-drift patterns found
  and disclosed (queries.jsonl field names; draft_relevance_judgments.jsonl
  fastapi's nested structure); 1 more missing-field finding (flask) ]
        |
        v
[ Phase 3: queries_master.jsonl (160 rows) + query_merge_report.md ]
        |
        v
[ Phase 4: draft_relevance_master.jsonl (439 rows, fastapi flattened
  with reasons recovered from annotation_drafts.jsonl)
  + relevance_merge_report.md ]
        |
        v
[ Phase 5: validation_report.md -- dataset-wide checks, all pass;
  2 disclosed non-blocking per-repository metadata gaps carried forward ]
        |
        v
[ Phase 6: dataset_statistics.md ]
        |
        v
[ Phase 7: train.jsonl (112) / validation.jsonl (24) / test.jsonl (24),
  seed=42, stratified by repository ]
        |
        v
[ Phase 8: dataset_card.md ]
        |
        v
[ Phase 9: reproducibility.md -- SHA-256 digests, build env, split method ]
        |
        v
[ Phase 10: this Publication Audit ]
```

Two decisions in this pipeline required explicit user confirmation
before proceeding, since they involved either an incomplete input
(fastapi's missing `annotation_metrics.json`) or a structural schema
incompatibility affecting the dataset's core mergeable content
(fastapi's nested `draft_relevance_judgments.jsonl`) that could not be
resolved by a purely mechanical, unambiguous rule:

1. **Missing file** — user chose "Proceed, disclose the gap." Applied:
   the merge proceeded using fastapi's present `queries.jsonl` and
   `draft_relevance_judgments.jsonl`; the gap is disclosed in
   `repository_inventory.md`, `schema_validation_report.md`,
   `validation_report.md`, `dataset_statistics.md`, and
   `dataset_card.md`'s Known Limitations.
2. **Schema conflict** — user chose "Flatten fastapi to match the
   other 7." Applied: a deterministic, disclosed, lossless flattening
   transformation, with per-file `reason` values recovered from
   fastapi's `annotation_drafts.jsonl` (100% recovery rate — all 74
   flattened rows, 0 fallback placeholders). Full detail in
   `relevance_merge_report.md`.

## Phase 10: Publication Audit

Answering each of the mission's 8 audit questions directly, using
findings already established and cited in the reports above — nothing
new is asserted here without a citation to where it was actually
verified.

### 1. Can another researcher reproduce this dataset?

**Yes.** `reproducibility.md` provides SHA-256 digests for all 16
input files and all 5 output files, the exact deterministic merge
procedure (`query_merge_report.md`, `relevance_merge_report.md`), and
the exact split procedure including the fixed seed (42), processing
order, and CPython-specific `random.Random` dependency. A researcher
starting from the same 16 input files and following the documented
procedure exactly will reproduce the same output digests.

### 2. Are all repositories represented?

**Yes.** All 8 repositories listed in the mission contributed exactly
20 queries each to `queries_master.jsonl` (`repository_inventory.md`;
`query_merge_report.md` §"Row count") and are represented in
`draft_relevance_master.jsonl` (74/62/47/54/53/56/55/38 rows
respectively — `relevance_merge_report.md` §"Row count by repository")
and in every split file (14/3/3 per repository, all 8, in every one of
train/validation/test — `reproducibility.md` §"Resulting balance").

### 3. Is every query traceable?

**Yes.** Every one of the 160 `query_id`s traces to a specific source
repository (via its `<repository_id>-<NNN>` prefix, cross-verified
against its `repository_id` field), a specific pinned commit
(`reproducibility.md` §"Pinned commits"), and a specific source file
(`annotation_runs/<repo>/queries.jsonl`). Every relevance-judgment row
traces to a `query_id` present in `queries_master.jsonl` (0 orphans,
`relevance_merge_report.md` §"Referential integrity") and to a file
independently confirmed to exist in that repository's pinned-commit
clone (0 missing, same section).

### 4. Is every repository pinned?

**Yes.** All 8 commit SHAs are recorded in `reproducibility.md` and
were independently re-verified against each local clone's current
`git rev-parse HEAD` during this assembly session
(`repository_inventory.md` §"Pinned commit verification") — 0 drift
found.

### 5. Are all schemas identical?

**No, not in the source data — and this is disclosed prominently, not
hidden.** The 8 repositories' `queries.jsonl` files use 2 different
field-naming conventions, and fastapi's `draft_relevance_judgments.jsonl`
uses a structurally different nested schema from the other 7's flat
schema (`schema_validation_report.md` §§2-3). **The merged output
files (`queries_master.jsonl`, `draft_relevance_master.jsonl`, and the
3 split files) do all use one single, identical, internally-consistent
schema each** — the source-level drift was resolved through disclosed,
deterministic normalization before merging, not left inconsistent in
the delivered dataset. A researcher relying on this merged dataset
(rather than the raw per-repository files) sees one schema throughout.

### 6. Are there duplicate IDs?

**No.** 0 duplicate `query_id` values across all 160 queries (checked
both within and across repositories); 0 duplicate `(query_id, file)`
pairs across all 439 relevance-judgment rows (`query_merge_report.md`
§"Unique query IDs"; `relevance_merge_report.md` §"No duplicate (query,
file) pairs"; independently re-confirmed in `validation_report.md`
§§1-3).

### 7. Are there missing files?

**Yes — 2, both disclosed in full, neither blocking the merge.**
fastapi's `annotation_metrics.json` is entirely absent; flask's is
present but missing its `schema_version` field
(`repository_inventory.md`; `schema_validation_report.md` §4;
`validation_report.md` §6). Both are pre-existing limitations of the
two earliest per-repository annotation runs, not defects introduced by
this assembly. **0 files are missing among the data this assembly
actually merged**: every one of the 249 distinct `(repository, file)`
pairs referenced across `draft_relevance_master.jsonl` was
independently re-verified to exist in its repository's pinned-commit
clone.

### 8. Is every report internally consistent?

**Yes, cross-checked directly.** The dataset's core figures — 160
total queries, 439 total relevance-judgment rows, 249 distinct
referenced files, the 112/24/24 split sizes — appear identically
across every report that cites them (`dataset_card.md`,
`dataset_statistics.md`, `query_merge_report.md`,
`relevance_merge_report.md`, `schema_validation_report.md`,
`validation_report.md`, `reproducibility.md`); this was verified by a
direct grep for each figure across all Markdown reports in this
directory immediately before writing this audit, not merely assumed
from having written the numbers consistently by hand.

## Verdict

All 8 repositories merged successfully into a single, internally
-consistent, fully-traceable, fully-pinned dataset. Two disclosed,
non-blocking limitations exist in the source annotation-run metadata
(not in the merged data itself) and are carried forward transparently
into every relevant report rather than hidden — consistent with this
project's standing instruction that scientific integrity takes
priority over convenience. The dataset-wide validation in
`validation_report.md` passes on every check that governs the merged
data's correctness (no duplicates, no orphaned references, no missing
merged files, exact category and repository balance).

---

RTS DATASET VERSION 1.0 COMPLETE
