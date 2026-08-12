# LTR Execution Blocked — Final Relevance Labels Required

Produced by an explicit, just-executed audit of the RTS Dataset v1.0
split files (`evaluation/rts_builder/pilot/merged_dataset/{train,validation,test}.jsonl`
and the pre-split `queries_master.jsonl`/`draft_relevance_master.jsonl`),
run **before any training was attempted**, per the mandatory
pre-training supervision check. No file under
`evaluation/rts_builder/` or `evaluation/rts_builder/pilot/merged_dataset/`
was modified by this audit or by producing this report.

**Assumption explicitly not made**: the previous session's LTR
framework work confirmed the dataset was 100% unlabeled at that time.
This audit did **not** assume that state still holds — it re-read
every split file directly, just now, and reports what it actually
found.

## Audit method

For every candidate-file judgment across `train.jsonl`,
`validation.jsonl`, `test.jsonl`, and the pre-split
`draft_relevance_master.jsonl`, the `grade` field was classified into
exactly one of: the literal placeholder string `"TO_BE_ASSIGNED"`, a
valid integer grade in `{0, 1, 2, 3}`, or an invalid value (anything
else). `(query_id, file)` pairs appearing more than once within a
split were counted as duplicates. This is the same classification
logic as `feature_pipeline.validate_labels_are_numeric` and
`dataset_inspection.py`, re-run directly against the current files
rather than assumed from a prior run's output.

## Audit results

| Metric | train | validation | test | **Total** |
|---|---|---|---|---|
| Queries | 112 | 24 | 24 | **160** |
| Candidate judgments | 303 | 67 | 69 | **439** |
| Grade 0 (not relevant) | 0 | 0 | 0 | **0** |
| Grade 1 | 0 | 0 | 0 | **0** |
| Grade 2 | 0 | 0 | 0 | **0** |
| Grade 3 | 0 | 0 | 0 | **0** |
| Remaining `TO_BE_ASSIGNED` | 303 | 67 | 69 | **439** |
| Invalid grades | 0 | 0 | 0 | **0** |
| Duplicate `(query, file)` judgments | 0 | 0 | 0 | **0** |

Cross-checked directly against the pre-split master file
(`draft_relevance_master.jsonl`, 160 queries / 439 judgment rows):
identical totals — grade 0/1/2/3 counts are all **0**, `TO_BE_ASSIGNED`
count is **439**, invalid grades **0**, duplicates **0**.

## 1. Exact number of missing labels

**439 of 439 candidate-file relevance judgments (100%) are missing a
final human grade.** Every single judgment in the dataset still
carries the placeholder value `"TO_BE_ASSIGNED"`. Zero judgments have
been assigned a real grade of 0, 1, 2, or 3.

## 2. Affected repositories

**All 8 of 8 repositories are affected — none has any labeled data:**

| Repository | Queries | Judgments (all `TO_BE_ASSIGNED`) |
|---|---|---|
| celery | 20 | 53 |
| click | 20 | 54 |
| fastapi | 20 | 74 |
| flask | 20 | 62 |
| pandas | 20 | 55 |
| requests | 20 | 47 |
| scikit-learn | 20 | 38 |
| sqlalchemy | 20 | 56 |
| **Total** | **160** | **439** |

## 3. Affected queries

**All 160 queries in the dataset are affected** (every query has at
least one, and in most cases all, of its candidates still
`TO_BE_ASSIGNED`). Query IDs are contiguous and sequential per
repository:

- `celery-001` .. `celery-020`
- `click-001` .. `click-020`
- `fastapi-001` .. `fastapi-020`
- `flask-001` .. `flask-020`
- `pandas-001` .. `pandas-020`
- `requests-001` .. `requests-020`
- `sklearn-001` .. `sklearn-020` (repository_id `scikit-learn`)
- `sqlalchemy-001` .. `sqlalchemy-020`

Full per-query detail (which specific candidate files are attached to
each query) is in `evaluation/rts_builder/pilot/merged_dataset/queries_master.jsonl`
and `draft_relevance_master.jsonl`.

## 4. Exact files that need annotation

Human annotation must be recorded in each repository's own source
annotation file (the authoritative per-repository source of truth,
upstream of the frozen merge that produced `merged_dataset/`):

| Repository | File requiring annotation |
|---|---|
| fastapi | `evaluation/rts_builder/pilot/annotation_runs/fastapi/draft_relevance_judgments.jsonl` |
| flask | `evaluation/rts_builder/pilot/annotation_runs/flask/draft_relevance_judgments.jsonl` |
| requests | `evaluation/rts_builder/pilot/annotation_runs/requests/draft_relevance_judgments.jsonl` |
| click | `evaluation/rts_builder/pilot/annotation_runs/click/draft_relevance_judgments.jsonl` |
| celery | `evaluation/rts_builder/pilot/annotation_runs/celery/draft_relevance_judgments.jsonl` |
| sqlalchemy | `evaluation/rts_builder/pilot/annotation_runs/sqlalchemy/draft_relevance_judgments.jsonl` |
| pandas | `evaluation/rts_builder/pilot/annotation_runs/pandas/draft_relevance_judgments.jsonl` |
| scikit-learn | `evaluation/rts_builder/pilot/annotation_runs/scikit-learn/draft_relevance_judgments.jsonl` |

Each repository's own `human_annotation_checklist.md` (same directory)
documents exactly what a human annotator must verify and resolve
before assigning each grade — including, per repository, any flagged
directory-shaped candidates, speculative/unresolved queries, or
ambiguity notes that predate a final grade. Per
`RELEVANCE_ANNOTATION_HANDBOOK.md`, every `"TO_BE_ASSIGNED"` value must
be replaced with an integer in `{0, 1, 2, 3}`, or the row removed
entirely if grade 0 is recorded by omission rather than an explicit
value (see that handbook for which convention applies).

**Downstream files that must then be regenerated** (not hand-edited —
they are the output of the frozen merge-and-split pipeline documented
in `merged_dataset/reproducibility.md`) once the 8 files above carry
real grades:

- `evaluation/rts_builder/pilot/merged_dataset/draft_relevance_master.jsonl`
- `evaluation/rts_builder/pilot/merged_dataset/train.jsonl`
- `evaluation/rts_builder/pilot/merged_dataset/validation.jsonl`
- `evaluation/rts_builder/pilot/merged_dataset/test.jsonl`

## 5. Command / workflow required to continue

1. For each of the 8 files listed in §4, a qualified human annotator
   completes the review described in that repository's
   `human_annotation_checklist.md`, replacing every `"grade":
   "TO_BE_ASSIGNED"` with a final integer grade in `{0, 1, 2, 3}` (or
   removing the row, per the handbook's grade-0-by-omission
   convention, if that is the project's chosen recording method).
2. Re-run the dataset-assembly merge that produced
   `merged_dataset/{draft_relevance_master.jsonl, train.jsonl,
   validation.jsonl, test.jsonl}` from the 8 updated source files (see
   `merged_dataset/reproducibility.md` for the exact deterministic
   merge/split procedure, including the fixed seed and repository
   -stratified 70/15/15 split — re-running it against updated inputs
   reproduces the same query-to-split assignment, only with real
   grades attached).
3. Re-run this audit to confirm 0 remaining `TO_BE_ASSIGNED` values
   (or an acceptable, explicitly-documented residual count, if partial
   annotation is intentionally being used for a pilot training run —
   that would be a separate, explicit decision, not a default).
4. Only then re-invoke the LTR execution pipeline
   (`evaluation/experiments/ltr/train.py` via Phase 4 onward of this
   task), which will itself re-verify labels via
   `feature_pipeline.validate_labels_are_numeric` before proceeding —
   this audit is a second, independent check ahead of that same gate,
   not a replacement for it.

No training, feature-importance analysis, baseline evaluation, or any
other phase of this task's Phase 1-14 workflow was executed. No label
was fabricated, inferred from retrieval results, or derived from
Oracle Utility or confidence scores. This report is the complete
output of this session.
