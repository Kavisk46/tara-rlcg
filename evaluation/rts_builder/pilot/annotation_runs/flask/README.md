# Flask Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (Flask) in the TARA RTS Pilot Dataset, produced end-to-end
by an AI research-data-engineering assistant against the real local
repository at `C:\Projects\tara-rlcg\flask`, pinned commit
`6a2f545bfd8ed31e19066a299296917e034aca58` (verified via `git
rev-parse HEAD` before any inspection began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-10 of the
pipeline described below, followed by a self-review (Phase 11, this
document's final section); a human annotator following
`human_annotation_checklist.md` and the project's
`../RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Repository structure, packages, modules, architecture, testing/documentation strategy, obtained entirely by reading the local repository. Surfaces one commit-specific, load-bearing finding: the 3.2 `RequestContext`/`AppContext` merge. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, every one grounded in a confirmed, real repository capability. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, reason, important classes/functions, related files, and explicit uncertainty. |
| `draft_relevance_judgments.jsonl` | Phase 5 | Flat, one-row-per-(query, file) scaffold, every `grade` set to `"TO_BE_ASSIGNED"`, ready for a human annotator to fill in. |
| `human_annotation_checklist.md` | Phase 6 | What a human reviewer must verify, resolve, and sign off on before this data is usable. |
| `validation_report.md` | Phase 7 | Output of an actually-executed validation script: duplicates, broken paths, missing files, empty fields, weak/speculative queries, directory candidates, category/difficulty balance, average candidate count. 0 errors found this run. |
| `dataset_statistics.md` | Phase 8 | Repository/category/difficulty statistics, candidate-count statistics, file/package frequency, coverage analysis, ambiguous-query cross-reference -- all computed, not estimated. |
| `annotation_metrics.json` | Phase 9 | Machine-readable summary metrics for this run. |
| `research_notes.md` | Phase 10 | Observations, annotation difficulties, threats to validity, queries needing reviewer attention, repository-specific risks, recommendations. |
| `README.md` (this file) | -- | Overview, pipeline position, and the Phase 11 publication-readiness review. |

## Pipeline position

Sits entirely within the **annotation-stage** layer described in
`../ANNOTATION_HANDBOOK.md` and `../RELEVANCE_ANNOTATION_HANDBOOK.md`,
upstream of and not a modification to any frozen RTS Builder subsystem
(Repository Loader, Parser, Feature Extraction, Retrieval Executor,
Oracle Utility, RTS Dataset Builder, RTS Annotation Protocol -- all
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
draft_relevance_judgments.jsonl (Phase 5: flat scaffold for human grading)
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

This is the second repository processed under this workflow -- see
`../annotation_runs/fastapi/` for the first. A schema note for whoever
eventually merges both: `draft_relevance_judgments.jsonl`'s shape
differs between the two runs (FastAPI: one row per query, a nested
`relevance_grades` dict, field `repository_id`; Flask: one row per
`(query, file)` pair, a flat `grade` field, field `repository`) --
both were produced to match explicit schemas given for each run;
neither has been normalized against the other yet.

## Phase 11: Publication Readiness Review

### Scientific correctness

- Every architectural claim in `repository_summary.md` traces to a
  direct file read or grep with a cited line number, re-verified
  during this review for two previously less-certain claims
  (`session_interface: SessionInterface = SecureCookieSessionInterface()`
  at `src/flask/app.py:252`, and `make_setup_state` at
  `src/flask/sansio/blueprints.py:246`) -- both confirmed correct.
- The one commit-specific fact this run leans on most heavily (the
  `RequestContext`/`AppContext` merge) was read directly from
  `src/flask/ctx.py`'s own class docstring, not inferred or recalled.
- Category and difficulty distributions in `annotation_metrics.json`
  were cross-checked programmatically against `queries.jsonl` during
  this review and matched exactly.

### Repository grounding

- 62 of 62 candidate-file path references (100%) were verified to
  exist on disk at the pinned commit by an executed script, not
  asserted (`validation_report.md` SS3).
- Every `annotation_drafts.jsonl` entry's `confidence`/`uncertainty`
  fields honestly distinguish "read directly" from "existence
  confirmed only" from "inferred, not individually checked" -- spot
  -checked during this review, not found to overstate certainty
  anywhere sampled.

### Reproducibility

- Commit SHA pinned and verified against the actual local checkout
  before Phase 1 began.
- `validate_flask_run.py`'s full output is reflected verbatim into
  `validation_report.md` and `dataset_statistics.md` -- every number
  in both documents is re-derivable by re-running the same script
  against the same commit.
- No repository code was modified at any point (confirmed: only
  `Read`/`Grep`/directory-listing operations were used against
  `C:\Projects\tara-rlcg\flask` throughout this run).

### Annotation quality

- 0 weak queries (every query has at least one Medium/High-confidence
  candidate).
- 2 queries (flask-008, flask-013) are explicitly, prominently flagged
  as speculative rather than silently padded with weak candidates to
  look more complete -- visible in `annotation_drafts.jsonl`,
  `validation_report.md`, `dataset_statistics.md`,
  `research_notes.md`, and `human_annotation_checklist.md` alike (not
  buried in only one artifact).
- 0 directory-level candidates (every path is a concrete file, unlike
  the FastAPI run).

### Potential reviewer criticisms, and disposition

| # | Criticism | Severity | Disposition |
|---|---|---|---|
| 1 | Documentation (`.rst`) candidates were never content-verified, only existence-confirmed. | Moderate | Disclosed in every relevant artifact's `uncertainty` field and in `human_annotation_checklist.md`'s "Verify documentation" section; not fixable without reading ~9 `.rst` files in full, which was out of scope for a search-assistance pass per this project's established division of labor (AI suggests, human verifies). Not fixed; explicitly deferred to human review. |
| 2 | Two queries (flask-008, flask-013) may not describe real, locatable issues. | Moderate | Already the intended outcome of honest search, not a defect to fix -- Phase 7's own instructions require reporting, not manufacturing, coverage. Explicitly flagged in 5 separate artifacts (see above) rather than hidden or silently dropped. |
| 3 | `draft_relevance_judgments.jsonl`'s schema differs from the FastAPI run's. | Minor | Both runs correctly followed the explicit schema given in their respective task instructions. Flagged above as a note for a future cross-repository merge step; not a defect within this run. |
| 4 | `CHANGES.rst` (75KB) was not searched beyond the one versionchanged note found incidentally. | Minor | Disclosed in `repository_summary.md` SS8 and `research_notes.md` SS3 as a threat to validity, not hidden. |
| 5 | No second, independent search pass has validated this run's candidate lists. | Minor | Disclosed in `research_notes.md` SS3 and recommended as future work SS6; standard limitation of a single-pass search-assistance run, consistent with the FastAPI pilot run's identical disclosure. |

**No Critical issues were found.** The two Moderate items are inherent,
disclosed properties of a pre-human-review draft (their remedy IS the
human review this package hands off to), not defects introduced by
this run. No fix was required or applied beyond what Phases 1-10
already produced -- this review found the existing disclosures
sufficient rather than requiring rework.

### Final audit

**"Could an ICSE reviewer reproduce every artifact from the pinned
commit?"**

**YES.** Every file-existence claim, every quoted docstring, every
line-numbered function/class reference, and every computed statistic
in this directory is re-derivable by (a) checking out
`6a2f545bfd8ed31e19066a299296917e034aca58` in the Flask repository and
(b) re-reading the specific files/lines cited, or re-running the
validation script whose full output is reflected in
`validation_report.md`/`dataset_statistics.md`. No claim in this
package depends on information not present in the pinned commit's
source tree.
