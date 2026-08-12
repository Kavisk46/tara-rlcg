# Repository Inventory — RTS Dataset v1.0 Assembly

Phase 1 of the merged-dataset assembly. Verifies that every repository
listed in the mission exists under
`evaluation/rts_builder/pilot/annotation_runs/` and contains the 10
required per-repository artifacts, before any merge logic runs. Per
the standing project instruction, no gap found here is silently
worked around — every finding is disclosed.

## Repositories discovered

All 8 expected repository directories are present under
`evaluation/rts_builder/pilot/annotation_runs/`:

`fastapi`, `flask`, `requests`, `click`, `celery`, `sqlalchemy`,
`pandas`, `scikit-learn` — matches the mission's "Available
Repositories" list exactly. No extra, unexpected, or missing
directories.

## Per-repository file completeness

Required files (10 per repository): `repository_summary.md`,
`queries.jsonl`, `annotation_drafts.jsonl`,
`draft_relevance_judgments.jsonl`, `validation_report.md`,
`dataset_statistics.md`, `annotation_metrics.json`,
`research_notes.md`, `human_annotation_checklist.md`, `README.md`.

| Repository | Complete? | Missing files |
|---|---|---|
| fastapi | **9 / 10 -- INCOMPLETE** | `annotation_metrics.json` |
| flask | 10 / 10 | none |
| requests | 10 / 10 | none |
| click | 10 / 10 | none |
| celery | 10 / 10 | none |
| sqlalchemy | 10 / 10 | none |
| pandas | 10 / 10 | none |
| scikit-learn | 10 / 10 | none |

**Finding: `fastapi` is missing `annotation_metrics.json` entirely.**
Confirmed by direct directory listing (`ls
annotation_runs/fastapi/*.json` returns "No such file or directory" —
fastapi has zero `.json` files in its annotation-run directory, while
every other repository has exactly one, `annotation_metrics.json`).
This was the very first repository processed in this project's pilot
sequence (see `annotation_runs/fastapi/README.md`), predating the
point at which the annotation workflow's Phase 9 output convention
was established as a hard requirement for every subsequent run.

**Resolution, per explicit user decision**: proceed with the full
merge using fastapi's `queries.jsonl` and
`draft_relevance_judgments.jsonl` (both present, both used directly by
Phases 3-4 of this assembly), and carry this gap forward as an
explicitly disclosed, non-blocking completeness defect in every
downstream report that touches it (`schema_validation_report.md`,
`validation_report.md`, `dataset_statistics.md`, `dataset_card.md`'s
Known Limitations section, `reproducibility.md`). The content that
would have been in fastapi's `annotation_metrics.json` (e.g.
`avg_candidate_files`, `weak_queries`, `directory_candidates`) is
independently re-derivable by computation from fastapi's
`queries.jsonl` + `annotation_drafts.jsonl` +
`draft_relevance_judgments.jsonl`, all of which are present and were
used for that recomputation in `dataset_statistics.md` §per-repository
figures. No frozen annotation-run artifact was modified to work around
this gap.

## File presence — all other files, all repositories

Every one of the other 79 required files (8 repositories × 10 files,
minus the 1 confirmed-missing file) was confirmed present via direct
directory listing, each with a non-trivial file size (smallest:
`flask/annotation_metrics.json` at 1,278 bytes; largest:
`fastapi/annotation_drafts.jsonl` at 50,485 bytes) — no zero-byte or
placeholder files found.

## Pinned commit verification

Each repository's pinned commit SHA (extracted from its
`annotation_runs/<repo>/README.md`) was re-verified against the
corresponding local clone's current `git rev-parse HEAD`, confirming
no drift has occurred since the original annotation run:

| Repository | Pinned commit SHA | Local `HEAD` matches |
|---|---|---|
| fastapi | `a375f6b948b99fa4260129856bbf11d037f363ef` | Yes |
| flask | `6a2f545bfd8ed31e19066a299296917e034aca58` | Yes |
| requests | `1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e` | Yes |
| click | `00e592cea702e0b2caa0dee42489fdb1c22cd845` | Yes |
| celery | `f109abf852525b69a1b6eee0457c6cd5561e0529` | Yes |
| sqlalchemy | `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` | Yes |
| pandas | `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` | Yes |
| scikit-learn | `9b9be3abddd88675c5dc2e3623e652cb7545a26c` | Yes |

All 8 verified. No repository code was re-inspected beyond this
commit-pin check, consistent with the mission's instruction to use
only the generated annotation artifacts unless validation detects an
inconsistency requiring deeper investigation.

## Phase 1 outcome

**Proceeding to Phase 2**, with one disclosed, non-blocking gap
(fastapi's missing `annotation_metrics.json`) carried forward
explicitly through every subsequent phase rather than resolved
silently. This gap does not affect Phases 3-4 (the core query/judgment
merge), since both files those phases depend on are present and valid
for fastapi. It is revisited in `validation_report.md` and in the
Phase 10 Publication Audit's answer to "Are there missing files?".
