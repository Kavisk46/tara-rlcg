# Click Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (Click) in the TARA RTS Pilot Dataset, produced end-to-end
by an AI research-data-engineering assistant against the real local
repository at `C:\Projects\tara-rlcg\click`, pinned commit
`00e592cea702e0b2caa0dee42489fdb1c22cd845` (verified via `git
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
| `repository_summary.md` | Phase 1 | Architecture, package layout, CLI architecture, extension points, testing/documentation strategy. Documents six commit-specific changes found in `CHANGES.md`'s unreleased section. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, every one grounded in a confirmed, real repository capability -- and checked against `CHANGES.md` to avoid describing already-fixed bugs as open. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, reason, important symbols, related files, and explicit uncertainty. |
| `draft_relevance_judgments.jsonl` | Phase 5 | Flat, one-row-per-file scaffold (exactly the 5 specified fields, no nesting, no extra fields), every `grade` set to `"TO_BE_ASSIGNED"`. |
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
repository_summary.md (orientation, incl. CHANGES.md review)
        |
        v
queries.jsonl (Phase 2: repository-grounded query authoring,
        |       cross-checked against CHANGES.md for already-fixed bugs)
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance -- suggests, never grades)
        |
        v
draft_relevance_judgments.jsonl (Phase 5: flat, one-row-per-file scaffold)
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

This is the fourth repository processed under this workflow -- see
`../annotation_runs/fastapi/`, `../annotation_runs/flask/`, and
`../annotation_runs/requests/` for the first three.
`draft_relevance_judgments.jsonl` here follows the same flat,
5-field, no-`commit_sha` schema as the Requests run (both tasks
specified the identical schema); FastAPI's and Flask's runs used
different shapes per their own tasks' instructions. See
`research_notes.md` §2 for this run's most distinctive methodological
addition: reading `CHANGES.md` substantively before finalizing queries.

## Phase 11: Publication Audit

### 1. Can every claim be verified from the pinned commit?

**Yes.** Every architectural claim, class/function name, and line
number in `repository_summary.md` and `annotation_drafts.jsonl` traces
to a direct `Read`/`Grep` call against `C:\Projects\tara-rlcg\click`
at the verified commit. During this audit, three previously-open
uncertainties were resolved by re-reading `types.py` and `core.py`:
`ParamType.convert()` (line 168) and `ParamType.fail()` (line 204)
were confirmed for `click-003`/`click-018`, and `Option.get_help_record`
(line 3331, overriding `Parameter.get_help_record` at line 2811) was
confirmed for `click-002`. `annotation_drafts.jsonl` and
`draft_relevance_judgments.jsonl` were both updated to reflect these,
and the validation script was re-run afterward to confirm no
regression (0 schema violations, 0 broken paths, 54/54 rows intact).

### 2. Did any query rely on assumptions instead of repository evidence?

**No unflagged assumption remains, and this run actively removed
several during drafting rather than only at audit time.** Before
`queries.jsonl` was finalized, an initial round of candidate Bug Fix
and Refactoring queries was checked against `CHANGES.md`'s unreleased
section and found to describe issues **already fixed** at this pinned
commit (ANSI-stripping in prompts, a `BytesWarning` under `python
-bb`, a dropped 256-color index, and `Option.__init__`'s already
-completed refactor) — these were replaced before finalizing, not left
in and merely flagged (see `research_notes.md` §2). The two remaining
feature queries most dependent on a documentation inference
(`click-007`, `click-008`) are grounded in a *direct quote* from
`docs/contrib.md` plus, for `click-008`, an independently-read working
example (`examples/aliases/aliases.py`) — two pieces of corroborating
evidence, not one assumption.

### 3. Did any candidate file require guessing?

**No file was included by guessing.** Every candidate in
`annotation_drafts.jsonl` was located by directory listing, `Grep`, or
direct `Read` — confirmed by the validation script finding 0 broken
paths among 54 candidate references (`validation_report.md` §4). One
directory-shaped candidate (`examples/aliases`, for `click-008`) was
found during search and resolved to its concrete file
(`examples/aliases/aliases.py`) by reading it, before being included —
not guessed at or left as an unresolved directory.

### 4. Did any schema drift from Schema Version 1.0?

**No.** Checked directly (`validation_report.md` §1, §11):

- `draft_relevance_judgments.jsonl`: 54/54 rows have exactly the 5
  specified keys (`query_id`, `repository`, `file`, `grade`, `reason`)
  with no nested values.
- `annotation_metrics.json`: all 9 required fields present with
  correct types, plus clearly-labeled supplementary fields that do not
  replace or rename any required field.
- `queries.jsonl`: all 20 rows match the specified 6-field schema
  exactly.

### 5. Would an ICSE reviewer reproduce these outputs?

**Yes.** Every file-existence claim, quoted docstring/changelog entry
(e.g. `CHANGES.md`'s "Add built-in shell completion support for
PowerShell..." and "The feature set of `version_option` is now
frozen"), and line-numbered function/class reference is re-derivable
by (a) checking out `00e592cea702e0b2caa0dee42489fdb1c22cd845` in the
Click repository and (b) re-reading the specific files/lines cited, or
re-running the validation script whose full output is reflected in
`validation_report.md`/`dataset_statistics.md`. No claim in this
package depends on information absent from the pinned commit's source
tree. One query (`click-013`) is explicitly marked speculative rather
than presented as a confirmed finding — a reviewer re-deriving this
package would reach the same "not confirmed" conclusion, not a
contradicting one.

**All five answers are affirmative. No blocking issue was found; the
open uncertainties discovered during this audit (Question 1) were
resolved before finishing, not left outstanding.**

---

All 11 phases complete.
