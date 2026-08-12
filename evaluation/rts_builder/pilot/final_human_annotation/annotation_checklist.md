# Annotation Checklist — Final Human Relevance Grading

For human annotators grading `annotation_queue.jsonl` (or a per
-annotator copy under `sessions/annotator_<X>/`). This checklist
summarizes and operationalizes
`evaluation/rts_builder/pilot/RELEVANCE_ANNOTATION_HANDBOOK.md` — that
document is the authoritative protocol; this file is a working
checklist derived from it, not a replacement for reading it in full at
least once before starting.

## Grading framework

**Grade scale:**

| Grade | Label | Meaning |
|---|---|---|
| 0 | Not relevant | No bearing on resolving the query; a developer would not open this file. |
| 1 | Slightly relevant | Tangential — touched incidentally or minor supporting context, not central. |
| 2 | Relevant | A file a developer would clearly need to read or modify; directly related but not the primary locus. |
| 3 | Highly relevant | The primary file(s) where the core logic or change lives. |

**The test to apply, per candidate:** *"Would a competent developer,
actually resolving this query, need to open this file — either to
understand context or to make a change?"*

**You must inspect evidence, not grade from:**

- [ ] Filename alone.
- [ ] Keyword match alone.
- [ ] Directory name alone.
- [ ] The AI-prepared `evidence`/`confidence` fields as if they were a
      grading recommendation — they are search-assistant context, not
      a suggested grade, and were produced by an assistant explicitly
      barred from recommending grades.
- [ ] Assumptions from general repository knowledge not confirmed at
      this exact pinned commit.

**Every non-zero grade requires a written `rationale`.** Grade-0
files may also be recorded with a rationale when they were genuinely
considered and rejected (the handbook's §9.1 raw-judgment convention —
this is the *raw*, pre-aggregation stage, so recording an explicit 0
is expected and useful, unlike the final aggregated file where grade-0
is represented by a file's absence).

## Grading procedure, per candidate

1. Read `query_text` and privately restate what a developer would
   actually need to do to resolve it.
2. Read `evidence` — note it is carried forward from an earlier
   AI-assisted search pass (see workspace `README.md`'s methodology
   section) and is not itself a grading recommendation.
3. **Open the actual file** (`file_path`, at `commit_sha`, in the
   local checkout) rather than grading from `evidence` text alone. The
   handbook's test requires judging what a developer would need to
   open — you should actually open it.
4. Assign a grade 0–3 per the table above.
5. Write a `rationale` for any grade >= 1 (and, ideally, for 0 too, if
   the file was non-obviously irrelevant).
6. Note any ambiguity, alternative query interpretation, or concern
   about the query itself in a session note (see `qc_validation.py`'s
   `notes` handling) — do not resolve query-level ambiguity
   unilaterally; flag it.

## Multi-file relevance reminders

- Most queries have more than one relevant file. Grade the **complete**
  relevant set, not just the first plausible file.
- **Avoid grade inflation** — more than ~8–10 files at grade >= 1 for
  one query is a signal to stop and reconsider (either the query is
  overly broad, or grades are inflated).
- **Ties are expected and correct.** Do not invent an artificial
  ranking between two genuinely equally-relevant files.
- **When torn between two adjacent grades, default to the lower one**
  — a deliberate, documented bias toward precision in the ground
  truth.
- Generated/vendored/migration code: grade 0 by default unless the
  query is specifically about that content.
- A file with mostly-irrelevant content and a small relevant portion:
  grade conservatively (typically 1–2, not 3).

## Missing candidates

**The candidate queue is a starting point, not a closed set.** Per
`RELEVANCE_ANNOTATION_HANDBOOK.md` §2 ("search the repository broadly
before grading anything... recall matters as much as precision") and
§3 ("identify the complete relevant set, not stop at the first
plausible file"), you are required to search the repository yourself
before finalizing grades for a query, not just grade the files already
listed.

If your own search finds a file that genuinely helps resolve the query
and is **not** already in this query's candidate list: add it — as a
new record in your working copy of `annotation_queue.jsonl`, using the
same schema as the existing rows (`query_id`, `repository`,
`commit_sha`, `query_text`, `file_path`, `grade`, `rationale`,
`annotator_id`, `timestamp`; set `evidence` to your own note on why you
found it and `relevant_symbols` if applicable; set
`verification_status` to `"VERIFIED"` only after confirming the file
actually exists at the pinned commit yourself). This is an addition
you make and document, never a silent one — record in your session
notes: the `query_id`, the added `file_path`, and why your search
surfaced it. `agreement_analysis.py` and `merge_final_judgments.py`
both key judgments by `(query_id, file_path)`, so an addition present
in only one annotator's stream is visible as exactly that kind of
recall disagreement when the two streams are compared — per the
handbook §6, "any file graded relevant by one annotator that the other
annotator's candidate search did not even surface" is treated with
the same seriousness as a grading disagreement, not silently dropped.

**Known tooling limitation (disclosed, not yet fixed):** as written,
`agreement_analysis.py` and `merge_final_judgments.py` currently
require both annotator streams to cover the *exact same* set of
`(query_id, file_path)` pairs, and raise a hard error otherwise. Now
that annotators are permitted to add files, two independent streams
may legitimately end up with different candidate sets (a recall
disagreement, not a bug). **This is a real gap between this policy
update and the existing analysis-script code, disclosed here rather
than silently left for a future run to discover** — before running
`agreement_analysis.py`/`merge_final_judgments.py` against a real
completed double-annotation that includes added files, that gap needs
a code fix (e.g. reconciling recall disagreements into the analysis
explicitly, rather than erroring out), which is outside the scope of
the current documentation-only update that introduced this policy.

## Session management

- Target session length: **approximately 2 hours**. Longer sessions
  correlate with grading-quality drift; take a break rather than push
  through.
- Log every session (see `sessions/annotator_<X>/session_log.jsonl`):
  `session_id`, `annotator_id`, `start_time`, `end_time`,
  `queries_completed`, `judgments_completed`.
- **Do not alter a grade because a session ran long or you are
  fatigued** — if you are unsure of a grade at the end of a long
  session, leave it for a fresh session rather than guess.

## Calibration (before independent work begins)

Per the handbook §7: all annotators should jointly grade a small
shared practice set (**not** drawn from these 8 repositories) and
discuss discrepancies against this checklist/the handbook before
starting independent work on `annotation_queue.jsonl`. This workspace
does not include a practice set — assemble one separately before
annotators begin.

## Adjudication (disagreements >= 2 grade levels)

- A disagreement is any file where `annotator_A` and `annotator_B`'s
  grades differ by **2 or more levels** (e.g. 0 vs. 2, 0 vs. 3, 1 vs.
  3).
- `agreement_analysis.py` identifies these automatically once both
  streams are complete (see that script).
- A **third annotator** (ideally more senior, uninvolved in either
  original pass) reviews each flagged disagreement independently and
  records a final grade **with a written rationale**.
- The adjudicator's grade becomes the final value. **It is never an
  average or midpoint of the two original grades** — the handbook is
  explicit that averaging is not a substitute for adjudication.
- A single-grade-level disagreement (e.g. 2 vs. 3) is common, not
  automatically escalated, but still contributes to the reported
  agreement statistics.

## Quality control (ongoing)

- **Spot-check auditing**: a QC reviewer should re-examine a random
  sample of at least 10% of completed, single-annotated judgments
  against this checklist, independent of the double-annotation process.
- **Annotator-level statistics**: `agreement_analysis.py` reports,
  per annotator, average number of files graded relevant per query,
  average grade given, and (if session logs are complete) time spent —
  outliers should be reviewed, not silently accepted.
- **Versioning**: any correction to a submitted grade after initial
  submission must go through a recorded revision (who, what, why),
  never a silent edit.

## Pre-submission checklist (per repository, before final merge)

- [ ] Every candidate in `annotation_queue.jsonl` for this repository
      has a grade in `{0, 1, 2, 3}` (no remaining `TO_BE_ASSIGNED`).
- [ ] Every grade >= 1 has a non-empty `rationale`.
- [ ] `annotator_id` and `timestamp` are set on every graded record.
- [ ] Any query with zero relevant files (grade >= 1) has an explicit
      note explaining why, not a silent empty set.
- [ ] Double-annotation is complete for this repository's queries
      (both `annotator_A` and `annotator_B` streams).
- [ ] Every disagreement with absolute grade difference >= 2 has been
      adjudicated, with a recorded rationale.
- [ ] Per-repository inter-annotator agreement (quadratic-weighted
      kappa) has been computed and recorded.
- [ ] Annotator-level QC statistics have been reviewed for outliers.
