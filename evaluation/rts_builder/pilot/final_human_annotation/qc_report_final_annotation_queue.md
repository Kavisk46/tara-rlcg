# QC Validation Report -- mode=final

Input: `annotation_queue.jsonl`
Records: 439

## Structural checks

- Malformed JSONL lines: 0
- Missing query IDs (by line): 0
- Invalid repository values: 0
- Commit SHA mismatches: 0
- Invalid/nonexistent file paths (checked against local clones just now): 0
- Duplicate (query_id, file_path) pairs: 0

## Grade-related checks

- Remaining `TO_BE_ASSIGNED`: 439
- Invalid grade values (not TO_BE_ASSIGNED and not in {0,1,2,3}): 0
- Missing rationale (grade >= 1): 0
- Missing annotator_id (on graded records): 0
- Missing timestamp (on graded records): 0
- Grade distribution (of validly-graded records): {}

## Verdict: FINAL-ANNOTATION FAIL

**FAIL reason: 439 judgment(s) still `TO_BE_ASSIGNED`.** Final annotation requires this to be exactly 0.