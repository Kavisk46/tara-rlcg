# SQLAlchemy Pilot Annotation Run

A complete, human-review-ready **draft** annotation package for one
repository (SQLAlchemy) in the TARA RTS Pilot Dataset, produced
end-to-end by an AI research-data-engineering assistant against the
real local repository at `C:\Projects\tara-rlcg\sqlalchemy`, pinned
commit `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` (version `2.1.0b4`,
verified via `git rev-parse HEAD` before any inspection began).

**Nothing in this directory is a final, publishable label.** Every
relevance grade is `"TO_BE_ASSIGNED"`. This is Phases 1-10 of the
pipeline described below, followed by a self-audit (Phase 11, this
document's final section, which made a substantive correction — see
below); a human annotator following `human_annotation_checklist.md`
and the project's `../RELEVANCE_ANNOTATION_HANDBOOK.md` completes it.

## Files in this directory

| File | Produced in | Purpose |
|---|---|---|
| `repository_summary.md` | Phase 1 | Architecture, package layout, ORM execution flow, SQL compilation pipeline, testing/documentation strategy, and the 11 already-resolved `unreleased_21/` changelog behaviors for this project's largest (255 package files) and only beta-version pilot repository. |
| `queries.jsonl` | Phase 2 | 20 hand-authored developer queries, 4/4/3/3/2/2/2 across bug_fix/feature_implementation/refactoring/testing/documentation/api_usage/code_search, cross-checked against all 12 `unreleased_21/` changelog fragments to avoid describing already-fixed/already-implemented behavior as open. Updated during Phase 11 -- see below. |
| `annotation_drafts.jsonl` | Phases 3-4 | Per-query candidate files (primary/secondary/regression tests/documentation examples), each with confidence, reason, important symbols, and explicit uncertainty. Updated during Phase 11 -- see below. |
| `draft_relevance_judgments.jsonl` | Phase 5 | Flat, one-row-per-file scaffold (exactly the 5 specified fields, no nesting, no extra fields), every `grade` set to `"TO_BE_ASSIGNED"`. Updated during Phase 11 -- see below. |
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
repository_summary.md (orientation, incl. full unreleased_21/ changelog review)
        |
        v
queries.jsonl (Phase 2: repository-grounded query authoring,
        |       cross-checked against all 12 unreleased_21/ fragments)
        v
annotation_drafts.jsonl (Phases 3-4: AI search assistance -- suggests, never grades)
        |
        v
draft_relevance_judgments.jsonl (Phase 5: flat, one-row-per-file scaffold)
        |
        v
   [ Phase 7 validation -- 0 real errors, 1 dismissed false positive,
     56/56 files verified to exist on disk ]
        |
        v
   [ Phase 11 audit -- disproved sqlalchemy-008's original premise and
     replaced it; resolved sqlalchemy-013's missing concrete evidence;
     propagated both through every affected artifact ]
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

This is the sixth repository processed under this workflow -- see
`../annotation_runs/fastapi/`, `../annotation_runs/flask/`,
`../annotation_runs/requests/`, `../annotation_runs/click/`, and
`../annotation_runs/celery/` for the first five.
`draft_relevance_judgments.jsonl` here follows the same flat, 5-field,
no-`commit_sha` schema as the Requests, Click, and Celery runs (all
four tasks specified the identical schema).

## Phase 11: Publication Audit

**This audit found and fixed two real, substantive gaps, not just
minor wording issues** -- disclosed in full below, consistent with
this project's standing instruction that scientific integrity
outweighs the convenience of leaving prior phases' output untouched.

### The corrections made during this audit

**`sqlalchemy-008`** originally asked to "add a way to specify
PostgreSQL-specific storage options when creating a materialized
view." A direct trace of the actual compilation call chain --
`visit_create_view` (`sql/compiler.py:7122`), which always passes
`type_="view"` to `_generate_table_select` regardless of
`element.materialized`, feeding into
`PGDDLCompiler.create_table_select_suffixes`
(`dialects/postgresql/base.py:2824`), which applies `postgresql_with`
whenever `type_ == "view"` -- proved this premise **false**: the
feature already works identically for plain and materialized views.
Unlike every prior correction made in this project's five earlier
pilot runs (which resolved an *under-evidenced* query to a concrete
answer), this is the first case where an entire query's premise was
disproved outright. Rather than leave a query describing already
-working functionality, it was **replaced** with a differently
-grounded, confirmed-open gap: `sql/ddl.py` has `CreateSequence`
(line 1077) and `DropSequence` (line 1083) but no corresponding
`AlterSequence` construct anywhere in `ddl.py` or `compiler.py`.

**`sqlalchemy-013`** ("investigate a test that behaves differently
depending on which database backend it is run against") left Phase 4
with only mechanism-level grounding -- `test/requirements.py`'s
existence confirmed backend-gating infrastructure exists, but no
specific test had been located. A direct grep for
`only_on`/`skip_if`/`fails_on` usage across candidate test files
during this audit resolved it: `test/engine/test_reflection.py:1169`
carries `@testing.crashes("oracle", "FIXME: unknown, confirm not
fails_on")` -- a literal FIXME comment from the repository's own
authors acknowledging unconfirmed backend-specific behavior -- and
`test/engine/test_reflection.py:2109` carries
`@testing.fails_on_everything_except("sqlite", "mysql", "mssql")`, a
test confirmed to behave differently across backends by design. The
query's original wording remained accurate and was left unchanged;
only its grounding was strengthened.

**Every artifact that had described either query's prior state was
then updated to reflect this**, not left inconsistent with each
other: `queries.jsonl` (both queries' `notes` fields), 
`annotation_drafts.jsonl` (both queries' candidates and
`ambiguity_notes`), `draft_relevance_judgments.jsonl` (56 total rows,
post-correction), `validation_report.md` (SS9 and the summary table),
`dataset_statistics.md` (SS4's candidate-count table), and
`annotation_metrics.json` (`speculative_queries`,
`phase_11_audit_resolutions`, `total_candidate_files`, and related
fields). This cross-artifact propagation is the point of doing this
check at all -- a correction that fixes one file while leaving four
others contradicting it would not actually improve reproducibility.

Separately, Phase 7's own validation script caught one automated
-check false positive during drafting: `sqlalchemy-014`'s query text
("...including in a **subclass** **that** overrides it") was flagged
by a substring check for `"class "`, because "subclass that" contains
that substring incidentally. Manually confirmed to be ordinary English,
not an actual implementation hint -- disclosed in `validation_report.md`
SS4 rather than silently dismissed without explanation.

### 1. Can every claim be verified from the pinned commit?

**Yes.** Every architectural claim, class/function name, and line
number in `repository_summary.md` and `annotation_drafts.jsonl`
traces to a direct `Read`/`Grep`/`ls` call against
`C:\Projects\tara-rlcg\sqlalchemy` at the verified commit -- including
the `sql/compiler.py`/`dialects/postgresql/base.py` call-chain trace
and the `test/engine/test_reflection.py` decorator findings made
during this audit itself.

### 2. Did any query rely on assumptions instead of repository evidence?

**No unflagged assumption remains.** Before `queries.jsonl` was
finalized, all 12 `unreleased_21/` changelog fragments were read in
full and 11 already-resolved behaviors were confirmed and excluded
from Bug Fix query framing (see `repository_summary.md` SS9). One
query (`sqlalchemy-008`) *did* rely on an assumption that repository
evidence later disproved -- rather than leave it unflagged, this audit
traced the actual code path, confirmed the assumption false, and
replaced the query with a directly-confirmed alternative gap. This is
the specific subject of this audit's first correction above, not an
unflagged assumption left standing.

### 3. Did any candidate file require guessing?

**No file was included by guessing.** Every candidate in
`annotation_drafts.jsonl` was located by directory listing, `Grep`, or
direct `Read`. One directory-shaped candidate
(`lib/sqlalchemy/event/` for `sqlalchemy-018`) was found during search
and explicitly excluded from `draft_relevance_judgments.jsonl` rather
than narrowed to an arbitrary file within it -- flagged in
`human_annotation_checklist.md` for human resolution instead.

### 4. Did Schema Version 1.0 remain unchanged?

**Yes.** Checked directly:

- `draft_relevance_judgments.jsonl`: all 56 rows (post-audit) have
  exactly the 5 specified keys (`query_id`, `repository`, `file`,
  `grade`, `reason`) with no nested values, verified programmatically.
- `annotation_metrics.json`: all 9 required fields present with
  correct types (`repository`, `schema_version`, `queries`,
  `avg_candidate_files`, `weak_queries`, `directory_candidates`,
  `validation_errors`, `manual_additions`, `manual_removals`), plus
  clearly-labeled supplementary fields that do not replace or rename
  any required field.
- `queries.jsonl`: all 20 rows match the specified 6-field schema
  exactly.

### 5. Would an ICSE reviewer reproduce every artifact?

**Yes, including both Phase 11 corrections.** Every file-existence
claim, quoted docstring/changelog entry, and line-numbered
function/class reference -- both from the original Phases 1-10 and
from this audit's `sql/compiler.py`/`dialects/postgresql/base.py`/
`test/engine/test_reflection.py` findings -- is re-derivable by (a)
checking out `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` in the
SQLAlchemy repository and (b) re-reading the specific files/lines
cited, or re-running `validate_sqlalchemy_run.py`, whose full output
is reflected in `validation_report.md`/`dataset_statistics.md`. No
claim in this package depends on information absent from the pinned
commit's source tree. No artifact in this directory currently
contradicts another -- every downstream document was checked and
updated after both Phase 11 resolutions specifically to ensure this.

**All five answers are affirmative.**

---

All 11 phases complete.
