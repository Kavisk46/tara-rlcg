# Research Notes — Flask Pilot Annotation Run

Reflective notes from constructing this pilot run against Flask at
commit `6a2f545bfd8ed31e19066a299296917e034aca58`. Observations and
judgments, not additional data — everything factual referenced here
was already established in `repository_summary.md`,
`annotation_drafts.jsonl`, or `validation_report.md`.

## 1. Interesting repository observations

- **The single most important, load-bearing fact this run surfaced is
  commit-specific and would not have been known from memory**: at this
  exact pinned commit, Flask's historically separate `RequestContext`
  and `AppContext` classes have been merged into one `AppContext`,
  with `RequestContext` reduced to a deprecated, warning-emitting
  alias (`.. versionchanged:: 3.2`, confirmed by direct read of
  `src/flask/ctx.py`). Most developers' and most language models'
  general knowledge of Flask describes the pre-merge, two-class design
  — this is exactly the scenario the task's "never answer from memory"
  instruction exists to prevent, and it materially shaped query
  authoring (flask-015 exists specifically because of this finding).
- **Flask's `sansio/` split is a genuine, intentional architecture
  decision, not incidental duplication.** `App`/`Scaffold`/
  `SansioBlueprint` hold transport-independent logic; `Flask`/
  `Blueprint` add the WSGI-specific layer on top via inheritance. This
  initially tempted a "duplicated logic" refactor query analogous to
  the prior FastAPI run's fastapi-009 — but on inspection, the split
  exists precisely to AVOID duplication, so such a query would have
  misrepresented the architecture. The refactor queries actually
  written (flask-009, flask-010, flask-011) target genuine complexity/
  consistency concerns instead.
- **A real, verified structural asymmetry**: `before_request`/
  `after_request`/`teardown_request` are defined on the shared
  `Scaffold` base (usable by both `Flask` and `Blueprint`), but
  `teardown_appcontext` is defined only on `App` (application-level
  only, confirmed by direct line-number search). This is a genuine,
  citable fact grounding flask-011, not a speculative refactor target.
- **`app.url_map.converters['list'] = ListConverter`** appears as a
  literal in-code comment in `src/flask/sansio/app.py` — an
  unusually direct, self-documenting example of exactly the extension
  mechanism flask-008 asks about, found by simple proximity search
  rather than inference.

## 2. Annotation difficulties

- **Distinguishing "this repository's own extension point" from "a
  wrapper around an external dependency's mechanism"** was the
  recurring difficulty in this run, mirroring the FastAPI pilot run's
  CORS/Starlette finding: flask-001/flask-008 (URL converters, likely
  substantially implemented in Werkzeug) and flask-020 (session
  signing, delegated to itsdangerous) both required explicit
  disclosure that this repository may only contain the wiring around a
  mechanism, not the mechanism itself.
- **Two queries (flask-008, flask-013) could not be confirmed as
  describing a genuine, locatable gap or defect**, and are flagged
  "speculative" rather than force-fit onto weak candidates — see
  `validation_report.md` §7. This required resisting the temptation to
  manufacture plausible-sounding candidates for the sake of hitting a
  higher average candidate count.
- **Flask's documentation is prose-first (`.rst`), not executable
  -example-first** the way FastAPI's `docs_src/` is. This meant every
  documentation candidate in this run is existence-confirmed only, with
  no equivalent of the FastAPI run's "directly read a working code
  example" grounding for `documentation_examples` entries. This is a
  structural limitation of this run's search depth, not of Flask's
  documentation quality.

## 3. Threats to validity

- **Single-pass AI search, not independently cross-checked.** Same
  limitation as the FastAPI pilot run — no second, independent search
  pass has been run over these 20 queries.
- **Werkzeug and itsdangerous are external dependencies not present in
  this local checkout.** Any query whose true implementation lives in
  either (plausible for flask-001, flask-008, flask-020) cannot be
  fully resolved from this repository alone.
- **`CHANGES.rst` (75KB) was read only for the specific versionchanged
  note already surfaced via `ctx.py`'s own docstring — not searched
  independently.** A fuller changelog read might surface additional
  recent, commit-specific behavior changes this run did not capture,
  analogous to how the context merge was found only because it
  happened to be documented directly in the class docstring being read
  for an unrelated purpose.
- **No code was executed, no test was run, no bug was reproduced** —
  every candidate reflects structural plausibility, not behavioral
  confirmation. This is by design (repository code must never be
  modified), consistent with the FastAPI pilot run's identical
  limitation.
- **`query_id`/`category`/`difficulty`/`notes` are this run's own
  tracking metadata**, not part of the frozen `QuerySpec`/
  `RelevanceJudgment` pipeline schema — a downstream merge step is
  still required, and has not been built or exercised in this run.

## 4. Queries requiring reviewer attention

In priority order:

1. **flask-008** (speculative) — resolve whether Flask itself
   implements any URL converter logic at all before any grading.
2. **flask-013** (speculative) — resolve whether a genuinely
   inconsistent test exists, or whether this query should be replaced.
3. **flask-015** — requires reading `docs/reqcontext.rst` and
   `docs/appcontext.rst` in full to determine whether they are
   already updated for the 3.2 context merge (in which case the query
   describes a already-resolved non-gap) or still stale.
4. **flask-002 / flask-017** — same underlying subsystem under
   different category framings; grade independently but with
   consistent reasoning about whether the behavior is a defect.
5. **flask-003** — registration vs. lookup ambiguity should be
   resolved before finalizing which primary candidate is more central.
6. **flask-016** — `after_this_request` vs. `teardown_request`
   ambiguity should be resolved before grading.

## 5. Repository-specific risks

- **Version churn risk**: this repository was pinned at a `.dev`
  version (`3.2.0.dev`) with a very recent, still-settling architectural
  change (the context merge). A future pilot round re-pinning a later
  Flask commit should re-verify whether `RequestContext` has been fully
  removed (per the docstring's own "will be removed in Flask 4.0"
  notice) — any prior annotation grounded in the deprecated-alias
  behavior would need re-verification at that point.
- **External-dependency boundary risk**: a higher-than-typical fraction
  of this run's queries (flask-001, flask-008, flask-020, and
  arguably flask-004's session-storage question) have their true
  implementation partly or wholly in Werkzeug or itsdangerous. A future
  round might deliberately pull those dependencies' source in
  alongside Flask's own, if queries spanning that exact boundary are
  desired as a research question in their own right.

## 6. Recommendations

- Before grading begins, hold a short adjudication pass specifically on
  flask-008 and flask-013 (the two speculative queries) — deciding to
  keep, revise, or replace each, rather than letting the human
  annotator discover the same uncertainty independently and
  potentially resolve it inconsistently across a multi-annotator team.
- Consider adding Werkzeug (and possibly itsdangerous) as a second,
  read-only reference checkout for future annotation runs on Flask
  specifically, given how often this run's searches hit that boundary
  — this would let candidate-file search resolve questions like
  flask-008's rather than leaving them as structural uncertainty.
- When this repository's pilot round is repeated for the remaining 6
  target repositories (per `../REPOSITORY_SELECTION_PLAN.md`), the
  "recently-changed, well-documented subsystem" pattern that made
  `ctx.py` this run's richest source (§1) is worth deliberately
  searching for in each new repository — recent architectural changes
  documented in code (not just changelogs) appear to produce
  unusually well-grounded queries.
