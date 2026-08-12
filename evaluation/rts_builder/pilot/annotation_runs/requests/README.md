# Requests Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (Requests) in the TARA RTS Pilot Dataset, produced
end-to-end by an AI research-data-engineering assistant against the
real local repository at `C:\Projects\tara-rlcg\requests`, pinned
commit `1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e` (verified via `git
rev-parse HEAD` before any inspection began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-10 of the
pipeline described below, followed by a self-audit (Phase 11, this
document's final section); a human annotator following
`human_annotation_checklist.md` and the project's
`../RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Architecture, package layout, request lifecycle, extension points, testing/documentation strategy. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, every one grounded in a confirmed, real repository capability. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, why, important symbols, related files, and explicit uncertainty. |
| `draft_relevance_judgments.jsonl` | Phase 5 | Flat, one-row-per-file scaffold (exactly the 5 specified fields: `query_id`, `repository`, `file`, `grade`, `reason` -- no nesting, no extra fields), every `grade` set to `"TO_BE_ASSIGNED"`. |
| `human_annotation_checklist.md` | Phase 6 | What a human reviewer must verify, resolve, and sign off on before this data is usable. |
| `validation_report.md` | Phase 7 | Output of an actually-executed validation script: duplicates, invalid paths, missing files, weak/speculative queries, directory candidates, category/difficulty imbalance, schema inconsistencies. 0 errors found. |
| `dataset_statistics.md` | Phase 8 | Repository/category/difficulty statistics, candidate-count statistics, file/package frequency, coverage observations -- all computed, not estimated. |
| `annotation_metrics.json` | Phase 9 | Machine-readable summary, `schema_version: "1.0"`, all 9 required fields present with 0 drift. |
| `research_notes.md` | Phase 10 | Findings, commit-specific observations, annotation difficulties, threats to validity, reviewer concerns, recommendations. |
| `README.md` (this file) | -- | Overview, pipeline position, and the Phase 11 publication audit. |

## Pipeline position

Sits entirely within the **annotation-stage** layer described in
`../ANNOTATION_HANDBOOK.md` and `../RELEVANCE_ANNOTATION_HANDBOOK.md`,
upstream of and not a modification to any frozen RTS Builder subsystem
(Repository Loader, Parser, Feature Extraction, Retrieval Executor,
Oracle Utility, RTS Dataset Builder, Annotation Protocol -- all
frozen, none touched):

```
repository_summary.md (orientation)
        |
        v
queries.jsonl (Phase 2: repository-grounded query authoring)
        |
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance -- suggests, never grades)
        |
        v
draft_relevance_judgments.jsonl (Phase 5: flat, one-row-per-file scaffold for human grading)
        |
        v
   [ HUMAN REVIEW -- human_annotation_checklist.md,
     RELEVANCE_ANNOTATION_HANDBOOK.md in full ]
        |
        v
final relevance_judgments.jsonl (not yet produced -- future work)
        |
        v
   [ merge with queries.jsonl's query_text, per
     RELEVANCE_ANNOTATION_HANDBOOK.md SS10 ]
        |
        v
QuerySpec-conformant queries.jsonl -> Dataset Builder's own
QueryIterator (frozen, unmodified)
```

This is the third repository processed under this workflow -- see
`../annotation_runs/fastapi/` and `../annotation_runs/flask/` for the
first two. `draft_relevance_judgments.jsonl`'s schema differs across
all three runs (FastAPI: nested per-query; Flask: flat per-file with a
`commit_sha` field; Requests: flat per-file, exactly the 5 fields
specified, no `commit_sha`) -- each followed the exact schema given in
its own task instructions. Not yet normalized against each other; see
`research_notes.md`.

## Phase 11: Publication Audit

### 1. Can every claim be verified from the pinned commit?

**Yes.** Every architectural claim, class/function name, and line
number in `repository_summary.md` and `annotation_drafts.jsonl` traces
to a direct `Read`/`Grep` call against
`C:\Projects\tara-rlcg\requests` at the verified commit. During this
audit, one previously-open uncertainty (which method contains the
`resolve_proxies(..., self.trust_env)` call referenced for
requests-017) was resolved by re-reading the relevant lines and
confirmed to be `SessionRedirectMixin.rebuild_proxies` (with
`rebuild_auth` as the sibling method for the netrc-auth call site) —
`annotation_drafts.jsonl` and `draft_relevance_judgments.jsonl` were
both updated to reflect this, and the validation script was re-run
afterward to confirm no regression (0 schema violations, 0 broken
paths, 47/47 rows intact).

### 2. Did any query rely on assumptions instead of repository evidence?

**No new assumption was left unflagged.** Two queries' premises were
explicitly checked against evidence rather than assumed:

- `requests-007` (session-level timeout default): the *absence* of a
  `self.timeout` default was directly confirmed by reading every line
  of `Session.__init__` that sets a default, not assumed from general
  HTTP-client-library knowledge.
- `requests-008` (runtime CA bundle customization): checking
  `certs.py`'s docstring surfaced that the existing mechanism is
  packaging-time only — but further reflection (recorded in
  `annotation_drafts.jsonl`) surfaced that the *already-existing*
  `verify=` parameter may substantially overlap with what the query
  asks for. This was not resolved by assumption; it was flagged as
  unresolved and handed to the human annotator (see
  `validation_report.md` §7).

### 3. Did any candidate file require guessing?

**No file was included by guessing.** Every candidate in
`annotation_drafts.jsonl` was located by directory listing, `Grep`, or
direct `Read` — confirmed by the validation script finding 0 broken
paths among 47 candidate references (`validation_report.md` §4). Where
a candidate's *content* (as opposed to its existence) was not read,
this is disclosed explicitly in that candidate's `uncertainty` field
rather than presented as verified — this is a disclosed limit on
search depth, not a guess.

### 4. Did any schema drift from Schema Version 1.0?

**No.** Checked directly (`validation_report.md` §1, §11):

- `draft_relevance_judgments.jsonl`: 47/47 rows have exactly the 5
  specified keys (`query_id`, `repository`, `file`, `grade`, `reason`)
  with no nested values — verified programmatically.
- `annotation_metrics.json`: all 9 fields from the specified schema are
  present with correct types (verified by set-difference check against
  the required key set — see the file's own generation log), plus
  clearly-labeled supplementary fields (e.g. `commit_sha`,
  `speculative_queries`) that do not replace or rename any required
  field.
- `queries.jsonl`: all 20 rows match the specified 6-field schema
  exactly.

### 5. Would an ICSE reviewer reproduce these outputs?

**Yes.** Every file-existence claim, quoted docstring/comment (e.g.
`hooks.py`'s `# TODO: response is the only one`), and line-numbered
function/class reference is re-derivable by (a) checking out
`1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e` in the Requests repository
and (b) re-reading the specific files/lines cited, or re-running the
validation script whose full output is reflected in
`validation_report.md`/`dataset_statistics.md`. No claim in this
package depends on information absent from the pinned commit's source
tree. Two queries (`requests-008`, `requests-013`) are explicitly
marked speculative rather than presented as confirmed findings — a
reviewer re-deriving this package would reach the same "not confirmed"
conclusion for both, not a contradicting one.

**All five answers are affirmative. No blocking issue was found; the
one open uncertainty discovered during this audit (Question 1) was
resolved before finishing, not left outstanding.**

---

All 11 phases complete.
