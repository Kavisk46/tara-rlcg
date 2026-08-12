# Celery Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (Celery) in the TARA RTS Pilot Dataset, produced end-to-end
by an AI research-data-engineering assistant against the real local
repository at `C:\Projects\tara-rlcg\celery`, pinned commit
`f109abf852525b69a1b6eee0457c6cd5561e0529` (verified via `git
rev-parse HEAD` before any inspection began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-10 of the
pipeline described below, followed by a self-audit (Phase 11, this
document's final section, which made a substantive correction — see
below); a human annotator following `human_annotation_checklist.md`
and the project's `../RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Architecture, package layout, task execution pipeline, extension points, testing/documentation strategy for the largest repository processed in this project's pilot runs to date. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, cross-checked against `Changelog.rst` to avoid describing already-fixed bugs as open. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, reason, important symbols, related files, and explicit uncertainty. Updated during Phase 11 -- see below. |
| `draft_relevance_judgments.jsonl` | Phase 5 | Flat, one-row-per-file scaffold (exactly the 5 specified fields, no nesting, no extra fields), every `grade` set to `"TO_BE_ASSIGNED"`. Updated during Phase 11 -- see below. |
| `human_annotation_checklist.md` | Phase 6 | What a human reviewer must verify, resolve, and sign off on before this data is usable. Updated during Phase 11 -- see below. |
| `validation_report.md` | Phase 7 | Output of an actually-executed validation script: duplicates, invalid paths, weak/speculative queries, directory candidates, category/difficulty balance, schema consistency. Found and corrected 1 real duplicate. Updated during Phase 11 -- see below. |
| `dataset_statistics.md` | Phase 8 | Repository/category/difficulty statistics, candidate-count statistics, file/package frequency, coverage observations. Updated during Phase 11 -- see below. |
| `annotation_metrics.json` | Phase 9 | Machine-readable summary, `schema_version: "1.0"`, all 9 required fields present with 0 drift. Updated during Phase 11 -- see below. |
| `research_notes.md` | Phase 10 | Findings, commit-specific observations, annotation difficulties, threats to validity, reviewer concerns, recommendations. Updated during Phase 11 -- see below. |
| `README.md` (this file) | -- | Overview, pipeline position, and the Phase 11 publication audit. |

## Pipeline position

Sits entirely within the **annotation-stage** layer described in
`../ANNOTATION_HANDBOOK.md` and `../RELEVANCE_ANNOTATION_HANDBOOK.md`,
upstream of and not a modification to any frozen RTS Builder subsystem
(Repository Loader, Parser, Feature Extraction, Retrieval Executor,
Oracle Utility, RTS Dataset Builder, Annotation Protocol -- all
frozen, none touched):

```
repository_summary.md (orientation, incl. brief Changelog.rst review)
        |
        v
queries.jsonl (Phase 2: repository-grounded query authoring,
        |       cross-checked against Changelog.rst for already-fixed bugs)
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance -- suggests, never grades)
        |
        v
draft_relevance_judgments.jsonl (Phase 5: flat, one-row-per-file scaffold)
        |
        v
   [ Phase 7 validation -- caught and drove correction of 1 duplicate ]
        |
        v
   [ Phase 11 audit -- resolved celery-013's missing primary candidate,
     then propagated that resolution back through every affected artifact ]
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

This is the fifth repository processed under this workflow -- see
`../annotation_runs/fastapi/`, `../annotation_runs/flask/`,
`../annotation_runs/requests/`, and `../annotation_runs/click/` for
the first four. `draft_relevance_judgments.jsonl` here follows the
same flat, 5-field, no-`commit_sha` schema as the Requests and Click
runs (all three tasks specified the identical schema).

## Phase 11: Publication Audit

**This audit found and fixed a real, substantive gap, not just minor
wording issues** -- disclosed in full below, consistent with this
project's standing instruction that scientific integrity outweighs
the convenience of leaving prior phases' output untouched.

### The correction made during this audit

`celery-013` ("Investigate and fix a test that is marked as flaky and
does not reliably pass") left Phase 4 with **zero primary
candidates** -- the `flaky` pytest marker's *name* was confirmed in
`pyproject.toml`, but no specific flaky-marked test had been located.
`validation_report.md` (Phase 7) and `dataset_statistics.md` (Phase 8)
both disclosed this honestly rather than hiding it.

During this audit, a direct search of `t/` (not `t/unit/`, which
turned out to be the wrong location) resolved it completely:
`t/integration/conftest.py` defines the marker's actual behavior
(`pytest.mark.flaky(reruns=5, reruns_delay=1,
cause=is_retryable_exception)`, combined with a timeout marker), and
`t/integration/test_canvas.py` applies it to 10+ individual tests
(confirmed at lines 118, 125, 132, 141, 150, 174, 179, 184, 231, and
more), with at least one more use in `t/integration/test_worker.py`
(line 74). A secondary, genuinely useful finding fell out of this
search too: `pyproject.toml`'s `testpaths = "t/unit/"` means these
flaky-marked tests are specifically an **integration**-test concern,
excluded from a default `pytest` invocation entirely.

**Every artifact that had described `celery-013` as unresolved was
then updated to reflect this**, not left inconsistent with each other:
`annotation_drafts.jsonl` (new primary candidates, corrected
`ambiguity_notes`), `draft_relevance_judgments.jsonl` (3 new rows),
`validation_report.md` (§5, §6, §11), `dataset_statistics.md` (§4,
§7), `annotation_metrics.json` (`speculative_queries`,
`queries_without_primary_candidate`, `avg_candidate_files`, and new
fields documenting the resolution), `research_notes.md` (§2, §3, §5,
§6), and `human_annotation_checklist.md` (5 separate checklist items).
This cross-artifact propagation is the point of doing this check at
all -- a correction that fixes one file while leaving four others
contradicting it would not actually improve reproducibility.

Separately, Phase 7's own validation script caught a second, smaller
issue during drafting (not held over to this audit): `celery-020`
initially listed `celery/schedules.py` twice within one query's
candidate list. This was corrected immediately when found, with full
disclosure in `validation_report.md` §3.

### 1. Can every claim be verified from the pinned commit?

**Yes.** Every architectural claim, class/function name, and line
number in `repository_summary.md` and `annotation_drafts.jsonl`
traces to a direct `Read`/`Grep` call against
`C:\Projects\tara-rlcg\celery` at the verified commit -- including the
`t/integration/conftest.py`/`test_canvas.py` findings made during this
audit itself.

### 2. Did any query rely on assumptions instead of repository evidence?

**No unflagged assumption remains.** Before `queries.jsonl` was
finalized, candidate Bug Fix queries were checked against
`Changelog.rst`'s 5.6.0-5.6.2 sections and two were avoided because
they described already-fixed issues (recursive `WorkController`
instantiation in `DjangoWorkerFixup`; revoked-task backend status).
`celery-003` was deliberately written to describe a different,
still-open scenario from the second of those, with the distinction
recorded explicitly. `celery-013`, the one query that DID rely on an
incomplete search through Phase 7, is the subject of this audit's
correction above -- not left as an unflagged assumption.

### 3. Did any candidate file require guessing?

**No file was included by guessing.** Every candidate in
`annotation_drafts.jsonl` was located by directory listing, `Grep`, or
direct `Read`. Two directory-shaped candidates (`t/unit/worker` for
`celery-004`, `docs/getting-started/backends-and-brokers` for
`celery-005`) were found during search and explicitly excluded from
`draft_relevance_judgments.jsonl` rather than narrowed to an arbitrary
file within them -- flagged in `human_annotation_checklist.md` for
human resolution instead.

### 4. Did Schema Version 1.0 remain unchanged?

**Yes.** Checked directly:

- `draft_relevance_judgments.jsonl`: all 53 rows (post-audit) have
  exactly the 5 specified keys (`query_id`, `repository`, `file`,
  `grade`, `reason`) with no nested values.
- `annotation_metrics.json`: all 9 required fields present with
  correct types, plus clearly-labeled supplementary fields that do not
  replace or rename any required field.
- `queries.jsonl`: all 20 rows match the specified 6-field schema
  exactly.

### 5. Would an ICSE reviewer reproduce every artifact?

**Yes, including the Phase 11 correction itself.** Every file
-existence claim, quoted docstring/changelog entry, and line-numbered
function/class reference -- both from the original Phases 1-10 and
from this audit's `t/integration/` findings -- is re-derivable by (a)
checking out `f109abf852525b69a1b6eee0457c6cd5561e0529` in the Celery
repository and (b) re-reading the specific files/lines cited, or
re-running the validation script whose full output is reflected in
`validation_report.md`/`dataset_statistics.md`. No claim in this
package depends on information absent from the pinned commit's source
tree. No artifact in this directory currently contradicts another --
every downstream document was checked and updated after the
`celery-013` resolution specifically to ensure this.

**All five answers are affirmative.**

---

All 11 phases complete.
