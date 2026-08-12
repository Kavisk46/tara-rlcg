# Research Notes — SQLAlchemy Pilot Annotation Run

Reflective notes from constructing this pilot run against SQLAlchemy
at commit `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` (version
`2.1.0b4`, a beta release). Observations and judgments, not additional
data — everything factual referenced here was already established in
`repository_summary.md`, `annotation_drafts.jsonl`, or
`validation_report.md`.

## 1. Interesting repository findings

- **SQLAlchemy is the sixth and final repository processed in this
  project's pilot runs, and its single largest file
  (`lib/sqlalchemy/sql/compiler.py`, 8,398 lines) exceeds any single
  file confirmed in any of the five prior runs**, including Celery's
  largest (`canvas.py`, 2,443 lines) by a wide margin.
- **This is a genuinely two-layer architecture** (SQL Core + ORM)
  sharing common Engine/Pool/Dialect/Event infrastructure — distinct
  from the single-layer web-framework architectures of FastAPI/Flask/
  Requests and the task-queue architecture of Celery, and closer in
  spirit to Click's "core primitives + extensible surface" shape but
  at substantially greater scale.
- **The dialect-adoption inconsistency underlying `sqlalchemy-011` was
  independently, concretely verified, not assumed**: a direct grep of
  `has_multi_table` definitions across all `dialects/*/base.py` files
  found it in exactly 3 of 5 (`mssql`, `oracle`, `postgresql`) and
  absent from the same search's results for `mysql`/`sqlite` — the
  changelog fragment `13311.rst` had already hinted at this ("...has
  been updated to use this new method...") but the specific 3-dialect
  set was confirmed by code inspection, not merely asserted from the
  fragment's prose.
- **A materialized-view feature query (`sqlalchemy-008`) was found to
  describe already-working functionality during the Phase 11 audit**,
  the first time in this project's six pilot runs that an entire
  Feature-category query (not a Bug Fix query, where this check is
  standard practice) required replacement because its premise was
  simply false. See §3 below for the full account.

## 2. Commit-specific observations

- Version `2.1.0b4` per `lib/sqlalchemy/__init__.py`'s `__version__`
  string — a pre-release beta, unlike any of the five prior pilot
  repositories, all of which were at stable release versions.
- **This run's changelog review was the most granular of any pilot run
  to date**: rather than reading a single changelog file's top
  section (Click, Celery) or not reading one at all (FastAPI, Flask,
  Requests), SQLAlchemy's `doc/build/changelog/unreleased_21/`
  convention of one file per unreleased change meant all 12 fragments
  could be read in full within a proportionate research budget,
  yielding 11 distinct confirmed already-resolved behaviors (2 of them
  new features, not bug fixes: `13311.rst`'s `has_multi_table` and
  `9693.rst`'s `String.collation_schema`) — see
  `repository_summary.md` §9 for the complete list.
- **One of those 12 fragments (`11122.rst`) ended up mattering twice**:
  first, correctly, to avoid an already-fixed "postgresql_with on
  CreateView" Bug Fix framing during Phase 2 drafting; second, less
  expectedly, its confirmed fact (postgresql_with applies to
  `CreateView` generally) combined with a separately-confirmed fact
  (`CreateView` has an independent `materialized` bool parameter) to
  reveal during Phase 11 that the *combination* of the two — which
  Phase 2 had assumed was an open gap — was never actually confirmed
  to be missing, and turned out not to be.

## 3. Annotation difficulties

- **`sqlalchemy-008`'s original premise ("materialized views can't use
  PostgreSQL storage options") required a real code trace to
  disprove, not just a changelog read.** The generic
  `visit_create_view` in `sql/compiler.py:7122` always passes
  `type_="view"` to `_generate_table_select` regardless of
  `element.materialized`; `PGDDLCompiler.create_table_select_suffixes`
  (`dialects/postgresql/base.py:2824`) applies `postgresql_with`
  whenever `type_ == "view"` — meaning the storage-option rendering
  path is identical for plain and materialized views. This was only
  found by tracing the actual compilation call chain during the Phase
  11 audit, not by reading either fact in isolation during Phase 2/4.
  The query was replaced (not reworded) with a differently-grounded
  gap: no `AlterSequence` DDL construct exists.
- **`sqlalchemy-013` had the same shape of gap as Celery's `celery-013`**:
  strong evidence a backend-dependent-test *mechanism* exists
  (`test/requirements.py`, `lib/sqlalchemy/testing/requirements.py`)
  without a specific instance located during initial drafting. Resolved
  the same way as `celery-013` was — a direct, targeted grep (this
  time for `only_on`/`skip_if`/`fails_on` decorator usage across
  candidate test files) during the Phase 11 audit, which found two
  concrete sites in `test/engine/test_reflection.py`, one of which
  (line 1169) carries a literal `"FIXME: unknown, confirm not
  fails_on"` comment — a rare case of the repository's own authors
  documenting exactly the kind of uncertainty this query asks about.
- **Scale made file-level candidate precision harder to judge for
  `sqlalchemy-011`** than for a typical refactor query: the "correct"
  answer plausibly spans up to 6 files (the generic `Inspector` method
  plus 5 dialect-specific overrides/absences), and this draft settled
  on 4 (the generic method plus the 3 dialects that *do* implement it)
  rather than also including `mysql`/`sqlite`'s `base.py` files as
  candidates for their *absence* of the method — a judgment call
  flagged for the annotator in `human_annotation_checklist.md`.

## 4. Threats to validity

- **Single-pass AI search, not independently cross-checked** — same
  limitation disclosed in all five prior pilot runs.
- **Only the 12 `unreleased_21/` changelog fragments were read**, not
  SQLAlchemy's full historical changelog (which spans many prior
  major/minor releases going back years); older, already-fixed issues
  outside this specific 2.1-beta window could still exist undetected
  and inadvertently be described as open in a query.
- **No code was executed, no test was run, no database backend was
  connected to** — consistent with all five prior pilot runs'
  identical limitation. This is especially salient for
  `sqlalchemy-013`, where the Phase 11 audit found *markers*
  indicating possible backend-dependent behavior but could not confirm
  which marked test (if any) currently, actually fails.
- **255 package files, of which only 17 (6.7%) were directly
  referenced** — an unavoidable consequence of a fixed 20-query budget
  against the largest total package-file count of any of the six
  pilot repositories (255, vs. 161 for Celery and 17-48 for the other
  four).
- **Beta-version currency**: because `2.1.0b4` is a pre-release, some
  APIs/behaviors confirmed here (including the 2 new-feature changelog
  fragments) may change before a final 2.1 release.
- **The `sqlalchemy-008` replacement's own gap (no `AlterSequence`)
  was confirmed only by the absence of a grep match**, not by reading
  every line of `ddl.py`/`compiler.py` — a true negative is inherently
  harder to fully verify than a true positive, and a differently
  -named construct providing equivalent functionality cannot be
  entirely ruled out without a human's more exhaustive review.

## 5. Potential reviewer concerns

1. **"Why was an entire query's premise wrong, not just under
   -evidenced?"** — Addressed directly in `validation_report.md` §9
   and `README.md`'s Phase 11 section: this is disclosed as a genuine,
   substantive finding, not minimized. It demonstrates the value of
   the Phase 11 audit as a real verification step (consistent with the
   Celery run's precedent) rather than a formality, and the query was
   transparently swapped rather than silently reworded to obscure the
   original mistake.
2. **"Why is package-file coverage (6.7%) so much lower than four of
   the five prior runs?"** — Addressed in `dataset_statistics.md` §9:
   an expected, size-driven artifact (255 vs. 17-161 files), consistent
   with the same pattern already established and accepted for the
   Celery run (8.7%).
3. **"Was `sqlalchemy-013`'s resolution actually conclusive?"** — No,
   and this is stated plainly: two concrete decorator usage sites were
   found, but which (if either) represents a currently-failing test
   was not determined without running them — flagged explicitly in
   `human_annotation_checklist.md` for human follow-up, consistent
   with `celery-013`'s equivalent caveat in the Celery run.

## 6. Recommendations

- Before grading begins, run `test/engine/test_reflection.py`'s tests
  at and around lines 1169 and 2109 against multiple backends to
  determine `sqlalchemy-013`'s actual current behavior.
- Resolve the one directory-level candidate (`lib/sqlalchemy/event/`
  for `sqlalchemy-018`) to a specific file.
- Independently verify the `sqlalchemy-008` replacement's premise (no
  `AlterSequence` construct) by a more exhaustive read of `ddl.py`
  and `compiler.py` than this session's targeted grep, given that this
  premise underpins the entire query.
- A future round revisiting this repository should specifically target
  the six entirely-untouched subpackages identified in
  `dataset_statistics.md` §9 (`connectors/`, `event/`, `ext/`,
  `future/`, `util/`, and `testing/` beyond `requirements.py`), plus
  the ORM's declarative/dataclass mapping API (`orm/decl_api.py`) and
  async support more broadly (touched only indirectly via the
  `oracledb` async-cursor changelog fragment) — genuinely distinct,
  unexplored territory rather than variations on subsystems already
  covered.
- Given this run's experience with the `sqlalchemy-008` premise
  correction (a Phase 11 audit disproving an entire query, not just
  filling a gap) and the `sqlalchemy-013` resolution (mirroring
  Celery's `celery-013` pattern almost exactly), the practice of
  treating Phase 11 as a genuine opportunity to re-verify claims —
  including claims that a feature gap exists at all, not only claims
  about which file answers a query — is worth carrying forward
  explicitly as this project's pilot phase concludes with its sixth
  repository.
