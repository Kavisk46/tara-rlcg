# pandas Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (pandas) in the TARA RTS Pilot Dataset, produced end-to-end
by an AI research-data-engineering assistant against the real local
repository at `C:\Projects\tara-rlcg\pandas`, pinned commit
`d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` (version `3.1.0.dev0`,
verified via `git rev-parse HEAD` before any inspection began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-10 of the
pipeline described below, followed by a self-audit (Phase 11, this
document's final section, which found and fixed a real citation
error — see below); a human annotator following
`human_annotation_checklist.md` and the project's
`../RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Architecture, package layout, DataFrame execution flow, IO architecture, testing/documentation strategy for the largest repository processed in this project's pilot runs to date (`pandas/core/frame.py` alone: 19,651 lines). |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, cross-checked against the full 760-line `v3.1.0.rst` in-development changelog to avoid describing already-fixed/already-implemented behavior as open. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, reason, important symbols, and explicit uncertainty. |
| `draft_relevance_judgments.jsonl` | Phase 5 | Flat, one-row-per-file scaffold (exactly the 5 specified fields, no nesting, no extra fields), every `grade` set to `"TO_BE_ASSIGNED"`. |
| `human_annotation_checklist.md` | Phase 6 | What a human reviewer must verify, resolve, and sign off on before this data is usable. |
| `validation_report.md` | Phase 7 | Output of an actually-executed validation script: duplicates, invalid paths, weak/speculative queries, directory candidates, category/difficulty balance, schema consistency, and 100% file-existence verification against the pinned commit. |
| `dataset_statistics.md` | Phase 8 | Repository/category/difficulty statistics, candidate-count statistics, file/package frequency, coverage observations. |
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
repository_summary.md (orientation, incl. full v3.1.0.rst changelog review)
        |
        v
queries.jsonl (Phase 2: repository-grounded query authoring,
        |       cross-checked against the full 760-line changelog)
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance -- suggests, never grades;
        |       2 flawed Feature-query premises caught and replaced during drafting)
        v
draft_relevance_judgments.jsonl (Phase 5: flat, one-row-per-file scaffold)
        |
        v
   [ Phase 7 validation -- 0 real errors, 1 dismissed false positive,
     55/55 files verified to exist on disk ]
        |
        v
   [ Phase 11 audit -- re-verified class hierarchies and a parameter
     citation; found and corrected one wrong line-number citation ]
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

This is the seventh repository processed under this workflow -- see
`../annotation_runs/fastapi/`, `../annotation_runs/flask/`,
`../annotation_runs/requests/`, `../annotation_runs/click/`,
`../annotation_runs/celery/`, and `../annotation_runs/sqlalchemy/` for
the first six. `draft_relevance_judgments.jsonl` here follows the same
flat, 5-field, no-`commit_sha` schema as the Requests, Click, Celery,
and SQLAlchemy runs.

## Phase 11: Publication Audit

**This audit found and fixed a real citation error, disclosed in full
below**, consistent with this project's standing instruction that
scientific integrity outweighs the convenience of leaving prior
phases' output untouched.

### The correction made during this audit

While re-verifying the class hierarchies and parameter citations
underlying several queries, a direct re-check of `pandas-006`'s
grounding citation (`generic.py:2203`, cited as `to_csv`'s `na_rep`
parameter) found that this line actually belongs to `to_excel`'s
`na_rep` parameter, not `to_csv`'s — both methods live in the same
large file (`generic.py`) and happen to share a parameter name,
which produced a proximity mistake during Phase 3 drafting. A direct
read of `to_csv`'s own three overload/implementation signatures
(`def to_csv` at lines 3858, 3885, and 3912) confirmed `na_rep: str`
is genuinely present in all three, with the implementation's default
at line 3917 — so **the underlying claim was correct**
(`to_csv`'s `na_rep` genuinely is scalar-only, not per-column), but
the **specific line-number citation was wrong**. `queries.jsonl` and
`annotation_drafts.jsonl` were both corrected to cite line 3917
instead of 2203, and `validation_report.md` §9 discloses this in full.
No other artifact referenced the incorrect line number, so no further
propagation was required.

This is a different kind of correction than the two premise
replacements made during Phase 3/4 drafting itself (`pandas-005` and
`pandas-006`'s original forms, both described in `research_notes.md`
§1/§3 and `validation_report.md` §9) — those replaced an entire
query's premise before it reached any artifact; this one corrected a
specific supporting citation for a premise that was itself already
correct.

### 1. Can every claim be verified from the pinned commit?

**Yes.** Every architectural claim, class/function name, and line
number in `repository_summary.md` and `annotation_drafts.jsonl`
traces to a direct `Read`/`Grep`/`ls` call against
`C:\Projects\tara-rlcg\pandas` at the verified commit. The
`_MergeOperation`/`_CrossMergeOperation`/`_OrderedMerge`/`_AsOfMerge`
hierarchy (lines 931, 2293, 2344, 2409) and the `Block` hierarchy
(lines 144, 1698, 1982, 2241, 2267, 2281) were both independently
re-confirmed by a second grep during this audit and matched exactly.
The one citation that did not survive re-verification (`pandas-006`'s
`na_rep` line number) was corrected, as described above.

### 2. Did any query rely on assumptions instead of repository evidence?

**No unflagged assumption remains.** Before `queries.jsonl` was
finalized, the full 760-line `v3.1.0.rst` changelog was read
(including the I/O section, initially missed by an automated
header-regex search that required 4+ carets against a 3-caret
underline, and recovered by a manual read of the remaining file range
— see `research_notes.md` §2) and cross-checked against candidate Bug
Fix topics. Two Feature-category queries (`pandas-005`, `pandas-006`)
initially relied on a name-based grep's absence-of-match as evidence
of a gap; both were caught during Phase 3/4 drafting itself when a
broader or differently-termed follow-up search found the capability
already implemented under a different name (`merge_asof` requiring
pre-sorted input was the *correct* replacement grounding for
`pandas-005`'s slot; `to_csv`'s scalar `na_rep` was the correct
replacement for `pandas-006`'s slot). Neither reached `queries.jsonl`
in a flawed form.

### 3. Did any candidate file require guessing?

**No file was included by guessing.** Every candidate in
`annotation_drafts.jsonl` was located by directory listing, `Grep`, or
direct `Read`. This run has **zero directory-shaped candidates** —
every candidate resolved to a concrete file, unlike the SQLAlchemy and
Celery runs.

### 4. Did Schema Version 1.0 remain unchanged?

**Yes.** Checked directly:

- `draft_relevance_judgments.jsonl`: all 55 rows have exactly the 5
  specified keys (`query_id`, `repository`, `file`, `grade`, `reason`)
  with no nested values, verified programmatically.
- `annotation_metrics.json`: all 9 required fields present with
  correct types, plus clearly-labeled supplementary fields that do not
  replace or rename any required field.
- `queries.jsonl`: all 20 rows match the specified 6-field schema
  exactly.

### 5. Would an ICSE reviewer reproduce every artifact?

**Yes, including the Phase 11 correction itself.** Every file-existence
claim, quoted docstring/changelog entry, and line-numbered
function/class reference — both from the original Phases 1-10 and
from this audit's re-verification — is re-derivable by (a) checking
out `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` in the pandas
repository and (b) re-reading the specific files/lines cited, or
re-running `validate_pandas_run.py`, whose full output is reflected in
`validation_report.md`/`dataset_statistics.md`. No claim in this
package depends on information absent from the pinned commit's source
tree. No artifact in this directory currently contradicts another —
the `na_rep` line-number correction was checked against both
`queries.jsonl` and `annotation_drafts.jsonl` (the only two files that
cited it) to ensure consistency.

**All five answers are affirmative.**

---

All 11 phases complete.
