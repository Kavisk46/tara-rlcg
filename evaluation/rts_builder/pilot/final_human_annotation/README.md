# Final Human Relevance Annotation Workspace

Prepares the RTS Dataset v1.0's **439 candidate-file judgments**
(across **160 queries**, **8 repositories**) for final human relevance
grading. This workspace does not itself assign any relevance grade —
see [Hard rule](#hard-rule-role-of-this-workspace) below.

Governing protocol documents (accepted source of truth, read in full
before building this workspace):

- `evaluation/rts_builder/pilot/RELEVANCE_ANNOTATION_HANDBOOK.md` —
  the grading protocol, schema, disagreement/adjudication rules, and
  QC requirements this workspace implements.
- `evaluation/rts_builder/pilot/ANNOTATION_HANDBOOK.md` — governs how
  the queries themselves were written (context only; queries are
  already finalized in `merged_dataset/queries_master.jsonl`, not
  reopened here).
- `evaluation/rts_builder/pilot/REPOSITORY_SELECTION_PLAN.md` —
  governs repository selection. **A discrepancy was found in an
  earlier session and has since been corrected**: see
  [Repository-selection-plan discrepancy](#repository-selection-plan-discrepancy-found-and-corrected)
  below.

## The candidate queue is a starting point, not a closed set

**The candidate queue is a starting point, not a closed candidate
set. Annotators MUST search broadly before assigning grades and MAY
add relevant files that are not present in `annotation_queue.jsonl`.**
This is the authoritative instruction from
`RELEVANCE_ANNOTATION_HANDBOOK.md` §2 step 2 ("Search the repository
broadly before grading anything... **Recall matters as much as
precision**: a relevance set that only contains the first file you
happened to find is a common and serious annotation failure") and §3
("Annotators must identify the **complete** relevant set, not stop at
the first plausible file"). The 439 candidates in this workspace's
queue were identified by an AI search assistant during earlier
pipeline stages — a helpful starting point and not a substitute for
each human annotator's own broad search of the repository at the
pinned commit. See `annotation_checklist.md`'s "Missing candidates"
section for exactly how to record an added file. This does not change
the grading protocol itself (the 0–3 scale, the "would a developer
need to open this file" test, or the adjudication rules) — it only
clarifies that the pre-populated queue does not bound what annotators
may grade.

## Hard rule: role of this workspace

**This workspace, and the assistant that built it, is an annotation
ASSISTANT — never the final annotator.** Every one of the 439 records
in `annotation_queue.jsonl` has `"grade": "TO_BE_ASSIGNED"` and
`"rationale": ""`. No grade was assigned, recommended, inferred from
confidence, or inferred from retrieval results anywhere in this
workspace. A human annotator must independently read the evidence,
apply the handbook's grading test, and fill in `grade`, `rationale`,
`annotator_id`, and `timestamp` themselves.

## Repository-selection-plan discrepancy (found and corrected)

An earlier session found that `REPOSITORY_SELECTION_PLAN.md` §1 listed
**Django** as repository #1 of 8 (alongside Flask, requests, pandas,
scikit-learn, Click, SQLAlchemy, Celery) — but the 8 repositories
actually annotated and present in `merged_dataset/` throughout this
project are **fastapi**, flask, requests, click, celery, sqlalchemy,
pandas, and scikit-learn. fastapi did not appear anywhere in
`REPOSITORY_SELECTION_PLAN.md`, and Django did not appear anywhere in
the actual dataset. This was flagged (not silently resolved) in that
earlier session, since the plan document was not yet in scope to
modify.

**This has since been corrected.** `REPOSITORY_SELECTION_PLAN.md` §1's
table and its example `manifest.json` now list **FastAPI**
(`https://github.com/tiangolo/fastapi`, MIT license) as repository #1,
matching the repository actually used throughout the pipeline. The two
cross-references that compared Flask and SQLAlchemy against "Django"
(§1's Flask/SQLAlchemy rows and their `manifest.json` `reason`
fields) were also updated — not as a mechanical find-and-replace, but
rewritten to state facts that are actually true of FastAPI (which,
unlike Django, has no built-in ORM, templating engine, or admin
interface, so a direct "architecturally distinct from Django's ORM"
-style comparison would not have been meaningful for FastAPI). No
content under `merged_dataset/` or any `annotation_runs/<repo>/`
directory was touched — this correction was confined entirely to
`REPOSITORY_SELECTION_PLAN.md`, a planning document, not the frozen
dataset itself.

## Files in this workspace

| File | Purpose |
|---|---|
| `README.md` (this file) | Overview, methodology, and disclosures. |
| `annotation_queue.jsonl` | 439 records, one per candidate-file judgment, ready for human grading. Schema below. |
| `annotation_checklist.md` | The grading framework (from the handbook), session guidance, and a pre-submission checklist. |
| `qc_validation.py` | Automated structural validation — run before and after annotation; distinguishes PRE-ANNOTATION expectations from FINAL-ANNOTATION requirements. |
| `agreement_analysis.py` | Computes quadratic-weighted Cohen's kappa and related statistics — **only runs meaningfully once both annotator streams are complete**; documented to refuse otherwise. |
| `merge_final_judgments.py` | Produces `final_relevance_judgments.jsonl` from completed, adjudicated annotations. **Not run in this session** — grades do not exist yet. |
| `sessions/annotator_A/`, `sessions/annotator_B/` | Independent per-annotator working copies of the queue, plus session-log scaffolding. |

## `annotation_queue.jsonl` schema

Exactly the schema specified for this task's Phase 4, extended with
two fields (`verification_status`, `verification_notes`) that Phase 3
explicitly requires but Phase 4's base schema did not enumerate a slot
for, plus two informational fields carried from the existing pipeline
for auditability:

```json
{
  "query_id": "",
  "repository": "",
  "commit_sha": "",
  "query_text": "",
  "file_path": "",
  "evidence": "",
  "relevant_symbols": [],
  "grade": "TO_BE_ASSIGNED",
  "rationale": "",
  "annotator_id": "",
  "timestamp": "",
  "verification_status": "VERIFIED | INVALID",
  "verification_notes": "",
  "original_ai_search_reason": "",
  "uncertainty": ""
}
```

The human annotator fills in **only**: `grade`, `rationale`,
`annotator_id`, `timestamp` — every other field is prepared context,
not to be edited during grading (a change to any other field is an
annotation-tooling change, not a grading action, and should go through
this workspace's own versioning practice, not a silent edit inside a
grading session).

## How `evidence` and `relevant_symbols` were populated (methodology, disclosed in full)

**This session did not re-read all 439 candidate files' full source
from scratch.** Doing so would substantially duplicate work already
performed, with real repository inspection (`Read`/`Grep` calls
against these exact pinned commits), during each repository's original
11-phase annotation run (`annotation_runs/<repo>/annotation_drafts.jsonl`).
Instead:

1. **`evidence` and `relevant_symbols` are carried forward from each
   repository's own `annotation_drafts.jsonl`**, matched by exact
   `(query_id, file_path)` pair. All **439 of 439** candidates matched
   successfully — every candidate in the final judgment set traces
   back to a specific, already-documented piece of original evidence
   (a `reason` string, plus `related_symbols`/`important_symbols`/
   `important_classes`+`important_functions`, whichever field name
   that repository's original session used — see
   `schema_validation_report.md` in `merged_dataset/` for why this
   varies by repository). Each `evidence` string is prefixed
   `"[Carried forward from original repository-grounded annotation
   drafting -- annotation_runs/<repo>/annotation_drafts.jsonl
   (bucket=..., confidence=...)]"` so its provenance is never
   ambiguous to the human annotator.
2. **File existence was re-verified fresh, right now, in this
   session** — not carried forward. Every one of the 439 candidates
   was checked against the actual local repository clone on disk:
   does `C:\Projects\tara-rlcg\<repository>` exist, and does the exact
   `file_path` exist within it. **Result: 439 / 439 VERIFIED, 0
   INVALID.** See `verification_status`/`verification_notes` on every
   record. (Commit-pin freshness was not independently re-checked
   file-by-file in this pass beyond what `verification_status`
   captures — see `merged_dataset/repository_inventory.md`'s "Pinned
   commit verification" for the most recent full re-check of all 8
   repositories' pinned commits, which found 0 drift.)
3. **No candidate was added or removed by this workspace itself.** The
   439-candidate set in `annotation_queue.jsonl` is copied exactly
   from `merged_dataset/draft_relevance_master.jsonl` — per this
   task's Phase 2 instruction not to change the existing candidate set
   silently, and this remains true of how the queue was *built*.
   **This is a starting point for the human annotator, not a ceiling**
   — see ["The candidate queue is a starting point, not a closed
   set"](#the-candidate-queue-is-a-starting-point-not-a-closed-set)
   above: annotators are required to search broadly and may add a file
   they find that is missing from the queue, per
   `RELEVANCE_ANNOTATION_HANDBOOK.md` §2/§3, following the recording
   procedure in `annotation_checklist.md`'s "Missing candidates"
   section (never a silent, undocumented addition).

This means the *evidence* an annotator reads was genuinely produced by
inspecting these exact files at these exact pinned commits — just in
an earlier session, not this one. A human annotator (or a QC reviewer)
who wants an independent, from-scratch read of a specific file remains
free — and, per the handbook's grading test, is expected — to open the
actual file rather than grade from the evidence text alone.

## Verification summary (from this session, real output)

```
Loaded 439 candidate judgments from draft_relevance_master.jsonl
Built evidence lookup with 450 (query_id, file_path) entries from 8 repos' annotation_drafts.jsonl
Evidence matched from original annotation_drafts.jsonl: 439
Evidence NOT matched (needs fresh review): 0
Verification: VERIFIED=439  INVALID=0
Distinct query_ids covered: 160 (expected up to 160)
```

## Workflow to complete annotation

1. Two independent annotators (`annotator_A`, `annotator_B`) each work
   from their own copy of `annotation_queue.jsonl` under
   `sessions/annotator_<X>/`, in sessions of approximately 2 hours per
   `annotation_checklist.md` §"Session management", grading every
   candidate per the handbook's test in §"Grading framework" — without
   seeing the other annotator's grades.
2. Run `python qc_validation.py --mode final --input sessions/annotator_A/annotation_queue.jsonl`
   (and the same for `annotator_B`) after each stream completes, to
   catch structural problems before agreement analysis.
3. Run `python agreement_analysis.py` once both streams are complete —
   computes quadratic-weighted Cohen's kappa and flags every
   disagreement with an absolute grade difference `>= 2` for
   adjudication.
4. A third-party adjudicator resolves every flagged disagreement
   independently (see `annotation_checklist.md` §"Adjudication") —
   **not** performed by averaging or by either original annotator.
5. Run `python merge_final_judgments.py` to produce
   `final_relevance_judgments.jsonl` — **only after** every judgment
   has a final grade. The script refuses to run otherwise (see its own
   docstring).
6. Re-run `python qc_validation.py --mode final` against the merged
   output as the final readiness gate.

**None of steps 1–6 above were performed in this session.** This
workspace prepares steps 1–6; it does not simulate or fabricate their
output.
