# FastAPI Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (FastAPI) in the TARA RTS Pilot Dataset, produced end-to-end
by an AI research-data-engineering assistant against the real local
repository at `C:\Projects\tara-rlcg\fastapi`, pinned commit
`a375f6b948b99fa4260129856bbf11d037f363ef` (verified via `git
rev-parse HEAD` before any inspection began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-7 of the
pipeline described below; a human annotator following
`human_annotation_checklist.md` and the project's
`RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Repository structure, packages, modules, architecture, obtained entirely by reading the local repository. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, per `../ANNOTATION_HANDBOOK.md`'s schema. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, reason, related symbols, related files, and explicit uncertainty -- from real searches, not guesses. |
| `draft_relevance_judgments.jsonl` | Phase 4 | Scaffold matching `../RELEVANCE_ANNOTATION_HANDBOOK.md` §9.2's final aggregated schema, every grade set to `"TO_BE_ASSIGNED"`, ready for a human annotator to fill in. |
| `human_annotation_checklist.md` | Phase 5 | What a human reviewer must verify, resolve, and sign off on before this data is usable. |
| `validation_report.md` | Phase 6 | Output of an actually-executed validation script: duplicates, broken paths, empty fields, category/difficulty balance, referential consistency. Found and fixed one real broken path. |
| `dataset_statistics.md` | Phase 7 | Category/difficulty histograms, candidate-count statistics, file/package frequency, ambiguity hotspots, coverage analysis -- all computed, not estimated. |
| `research_notes.md` | Phase 8 | Observations, unexpected structure, annotation difficulties, threats to validity, future improvements. |

## Pipeline position

This run sits entirely within the **annotation-stage** layer described
in `../ANNOTATION_HANDBOOK.md` and `../RELEVANCE_ANNOTATION_HANDBOOK.md`
-- upstream of, and not a modification to, any frozen RTS Builder
subsystem:

```
repository_summary.md (orientation)
        |
        v
queries.jsonl (Phase 2: query authoring, per ANNOTATION_HANDBOOK.md)
        |
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance, per the
        |                search-assistant protocol established earlier
        |                in this project -- suggests, never grades)
        v
draft_relevance_judgments.jsonl (Phase 4: scaffold for human grading)
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
     RELEVANCE_ANNOTATION_HANDBOOK.md §10 ]
        |
        v
QuerySpec-conformant queries.jsonl -> Dataset Builder's own
QueryIterator (frozen, unmodified)
```

## Status

- Repository Loader, Parser, Feature Extraction, Retrieval Executor,
  Oracle Utility, RTS Dataset Builder, and the Annotation Protocol
  documents were **not modified** in producing this run.
- No repository code was modified. All inspection was read-only.
- `validation_report.md` §12: all automated checks pass; 7 directory
  -level candidates and 2 weakly-grounded queries (fastapi-011,
  fastapi-013) are explicitly flagged, not silently resolved.
- This run covers **one** of the pilot's 8 target repositories. See
  `../REPOSITORY_SELECTION_PLAN.md` for the full 8-repository plan;
  repeating this same Phase 1-8 process for the remaining 7
  repositories is the natural next step toward the full pilot dataset.

## Reproducibility

- Commit SHA is pinned and was verified against the actual local
  checkout before Phase 1 began (see `repository_summary.md`'s header
  table).
- Every file-path claim in `annotation_drafts.jsonl` was checked to
  actually exist by `validation_report.md`'s script — 0 broken paths
  remain (1 was found and corrected during this run; see
  `validation_report.md` §3).
- This directory's outputs are deterministic **only** in the sense that
  the same commit was inspected each time — the searches themselves
  were not re-run multiple times to confirm identical results, and an
  independent second pass (AI or human) may reasonably surface
  additional candidates this run did not find (see `research_notes.md`
  §4's threats-to-validity discussion).
