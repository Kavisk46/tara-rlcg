# scikit-learn Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (scikit-learn) in the TARA RTS Pilot Dataset, produced
end-to-end by an AI research-data-engineering assistant against the
real local repository at `C:\Projects\tara-rlcg\scikit-learn`, pinned
commit `9b9be3abddd88675c5dc2e3623e652cb7545a26c` (version
`1.10.dev0`, verified via `git rev-parse HEAD` before any inspection
began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-10 of the
pipeline described below, followed by a self-audit (Phase 11, this
document's final section); a human annotator following
`human_annotation_checklist.md` and the project's
`../RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Architecture, package layout, estimator execution flow, training/evaluation pipeline, testing/documentation strategy for the eighth repository processed in this project's pilot runs. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, cross-checked against all 55 `upcoming_changes/` changelog fragments (read in full) to avoid describing already-fixed/already-implemented behavior as open. |
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
repository_summary.md (orientation, incl. full 55-fragment changelog review)
        |
        v
queries.jsonl (Phase 2: repository-grounded query authoring,
        |       cross-checked against all 55 changelog fragments;
        |       3 Feature queries' absence-claims verified with
        |       multiple independent search terms before finalizing)
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance -- suggests, never grades)
        |
        v
draft_relevance_judgments.jsonl (Phase 5: flat, one-row-per-file scaffold)
        |
        v
   [ Phase 7 validation -- 0 real errors, 3 dismissed false positives,
     38/38 files verified to exist on disk ]
        |
        v
   [ Phase 11 audit -- re-verified every cited line number; all
     confirmed exactly accurate, 0 corrections needed ]
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

This is the eighth repository processed under this workflow -- see
`../annotation_runs/fastapi/`, `../annotation_runs/flask/`,
`../annotation_runs/requests/`, `../annotation_runs/click/`,
`../annotation_runs/celery/`, `../annotation_runs/sqlalchemy/`, and
`../annotation_runs/pandas/` for the first seven.
`draft_relevance_judgments.jsonl` here follows the same flat, 5-field,
no-`commit_sha` schema as the Requests, Click, Celery, SQLAlchemy, and
pandas runs.

## Phase 11: Publication Audit

**This audit re-verified every line-number citation used to ground a
query and found all of them exactly accurate** — unlike the pandas
run (which found and corrected one wrong citation) and the SQLAlchemy
run (which found and replaced one query whose entire premise was
false), this run required no corrections. This is disclosed
transparently rather than presented as evidence of superior work: it
reflects both a smaller, more self-contained set of query topics this
round happened to select, and the multi-term absence-verification
discipline adopted after the two prior runs' findings (see
`research_notes.md` §1/§3).

### What was re-checked during this audit

Every class/function definition line cited in `annotation_drafts.jsonl`
was re-confirmed by a direct `sed`/`grep` read against the pinned
commit during this audit, including:

- `neural_network/_multilayer_perceptron.py`'s `_score` methods at
  lines 1292 (`MLPClassifier`, confirmed calling
  `_score_with_function(..., score_function=accuracy_score)`) and 1758
  (`MLPRegressor`, confirmed calling
  `_score_with_function(..., score_function=r2_score)`) — this
  re-check additionally **strengthened** `sklearn-005`'s grounding by
  confirming the exact hardcoded scoring functions each class uses.
- `utils/_param_validation.py`'s `InvalidParameterError` (line 20) and
  `validate_parameter_constraints` (line 28).
- `compose/_column_transformer.py`'s `ColumnTransformer` (line 64) and
  `make_column_selector` (line 1427).
- `isotonic.py`'s `IsotonicRegression` (line 181).
- `multiclass.py`'s `OneVsRestClassifier` (line 202) and
  `OneVsOneClassifier` (line 678).
- `preprocessing/_data.py`'s `StandardScaler.partial_fit` (line 931).

All six re-checks matched their citation exactly. No propagated
correction was necessary in any downstream artifact.

### 1. Can every claim be verified from the pinned commit?

**Yes.** Every architectural claim, class/function name, and line
number in `repository_summary.md` and `annotation_drafts.jsonl`
traces to a direct `Read`/`Grep`/`ls` call against
`C:\Projects\tara-rlcg\scikit-learn` at the verified commit, and the
line-number citations above were independently re-verified during
this audit with 0 discrepancies found.

### 2. Did any query rely on assumptions instead of repository evidence?

**No unflagged assumption remains.** Before `queries.jsonl` was
finalized, all 55 `upcoming_changes/` changelog fragments were read in
full and cross-checked against candidate Bug Fix/Feature topics. Three
Feature-category queries (`sklearn-006`, `sklearn-007`, `sklearn-008`)
rest on a claimed absence of a capability; each was checked with 2-3
independent search terms rather than a single grep, following the
practice adopted after the pandas and SQLAlchemy runs' premise
corrections — disclosed as a real limitation (absence confirmed by
targeted search, not an exhaustive read) in
`human_annotation_checklist.md`, not overstated as certainty.

### 3. Did any candidate file require guessing?

**No file was included by guessing.** Every candidate in
`annotation_drafts.jsonl` was located by directory listing, `Grep`, or
direct `Read`. One directory-shaped candidate
(`examples/developing_estimators` for `sklearn-015`) was found during
search and explicitly excluded from `draft_relevance_judgments.jsonl`
rather than narrowed to an arbitrary file within it.

### 4. Did Schema Version 1.0 remain unchanged?

**Yes.** Checked directly:

- `draft_relevance_judgments.jsonl`: all 38 rows have exactly the 5
  specified keys (`query_id`, `repository`, `file`, `grade`, `reason`)
  with no nested values, verified programmatically.
- `annotation_metrics.json`: all 9 required fields present with
  correct types, plus clearly-labeled supplementary fields that do not
  replace or rename any required field.
- `queries.jsonl`: all 20 rows match the specified 6-field schema
  exactly.

### 5. Would an ICSE reviewer reproduce every artifact?

**Yes.** Every file-existence claim, quoted docstring/changelog entry,
and line-numbered function/class reference — both from the original
Phases 1-10 and from this audit's re-verification — is re-derivable by
(a) checking out `9b9be3abddd88675c5dc2e3623e652cb7545a26c` in the
scikit-learn repository and (b) re-reading the specific files/lines
cited, or re-running `validate_sklearn_run.py`, whose full output is
reflected in `validation_report.md`/`dataset_statistics.md`. No claim
in this package depends on information absent from the pinned commit's
source tree. No artifact in this directory contradicts another.

**All five answers are affirmative.**

---

All 11 phases complete.
