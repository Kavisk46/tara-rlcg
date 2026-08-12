# Dataset Statistics — Flask Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`annotation_drafts.jsonl` by script (same computation underlying
`validation_report.md`, here focused on description rather than
correctness). N = 20 queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | Flask |
| Pinned commit | `6a2f545bfd8ed31e19066a299296917e034aca58` |
| `src/flask/` package `.py` files | 24 |
| Files referenced by at least one query | 13 (54%) |
| Top-level `tests/*.py` files | 41 |
| `docs/*.rst` + `docs/patterns/*.rst` files referenced | 8 (`docs/reqcontext.rst`, `docs/appcontext.rst`, `docs/errorhandling.rst`, `docs/config.rst`, `docs/signals.rst`, `docs/async-await.rst`, `docs/views.rst`, `docs/patterns/urlprocessors.rst`, `docs/patterns/flashing.rst` — 9 distinct pages, some referenced by more than one query) |

## 2. Category distribution

| Category | Count | Share |
|---|---|---|
| bug_fix | 4 | 20% |
| feature_implementation | 4 | 20% |
| refactoring | 3 | 15% |
| testing | 3 | 15% |
| documentation | 2 | 10% |
| api_usage | 2 | 10% |
| code_search | 2 | 10% |

Matches the mission's required 4/4/3/3/2/2/2 distribution exactly.

## 3. Difficulty distribution

| Difficulty | Count | Share |
|---|---|---|
| medium | 9 | 45% |
| easy | 7 | 35% |
| hard | 4 | 20% |

## 4. Average candidate files per query

**avg = 3.10, min = 1, max = 5** (n=20, sum=62), across all four
candidate buckets combined.

| Query | Category | Candidates |
|---|---|---|
| flask-003 | bug_fix | 5 |
| flask-006 | feature_implementation | 5 |
| flask-011 | refactoring | 5 |
| flask-002 | bug_fix | 4 |
| flask-004 | bug_fix | 4 |
| flask-018 | api_usage | 4 |
| flask-001 | bug_fix | 3 |
| flask-005 | feature_implementation | 3 |
| flask-007 | feature_implementation | 3 |
| flask-008 | feature_implementation | 3 |
| flask-010 | refactoring | 3 |
| flask-013 | testing | 3 |
| flask-014 | testing | 3 |
| flask-015 | documentation | 3 |
| flask-009 | refactoring | 2 |
| flask-012 | testing | 2 |
| flask-016 | documentation | 2 |
| flask-017 | api_usage | 2 |
| flask-020 | code_search | 2 |
| flask-019 | code_search | 1 |

Lower overall average than the prior FastAPI pilot run (3.10 vs. 4.05).
`code_search` again has the lowest average (1.5), consistent with a
well-formed Code Search query having a single, specific answer.
`refactoring` (flask-009, flask-010, flask-011) is more bimodal here
than in the FastAPI run: flask-009 and flask-010 deliberately propose
no test/documentation candidates (consistent with the established
convention that a pure, behavior-preserving refactor should be
validated against the broad existing suite, not a guessed narrow
subset), while flask-011 has 5 due to the genuine app/blueprint
teardown asymmetry it targets spanning three source files plus two
plausible (but unconfirmed) test files.

## 5. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count |
|---|---|
| `src/flask/ctx.py` | 8 |
| `src/flask/app.py` | 6 |
| `src/flask/sansio/app.py` | 5 |
| `docs/reqcontext.rst` | 4 |
| `src/flask/sessions.py` | 4 |
| `tests/test_converters.py` | 2 |
| `docs/patterns/urlprocessors.rst` | 2 |
| `tests/test_reqctx.py` | 2 |
| `src/flask/sansio/scaffold.py` | 2 |
| `tests/test_user_error_handler.py` | 2 |
| `src/flask/signals.py` | 2 |
| `tests/test_session_interface.py` | 2 |
| `tests/test_blueprints.py` | 2 |
| `tests/test_async.py` | 2 |
| `docs/async-await.rst` | 2 |

`src/flask/ctx.py` is the single most cross-cutting file in this query
set (8 of 20 queries), substantially ahead of every other file —
directly reflecting how much of this run's query set was grounded in
the confirmed `AppContext`/`RequestContext` merge and the
`copy_current_request_context`/`after_this_request`/context-detection
functions it contains. This concentration is a property of the queries
chosen (several were deliberately written to exploit this file's
rich, recently-changed, well-documented content), not necessarily
representative of `ctx.py`'s share of the codebase by line count
(540 of the package's ~9,500 inspected lines, about 5.7%).

## 6. Frequently suggested packages

| Package/unit | Reference count |
|---|---|
| `src/flask` (top-level, non-sansio files combined) | 26 |
| `docs` (all `.rst` references combined) | 11 |
| `src/flask/sansio` | 8 |
| `docs/patterns` | 3 |

## 7. Weak queries

**0** — see `validation_report.md` §6. Every query has at least one
`Medium` or `High`-confidence candidate.

## 8. Directory candidates

**0** — see `validation_report.md` §8. Every candidate path resolves
to a concrete file.

## 9. Coverage observations

Of the 24 `.py` files in `src/flask/` itself, **13 (54%) were
referenced by at least one query; 11 (46%) were not.**

Untouched files, grouped by why:

- **Thin/leaf utility modules** unlikely to be a primary relevance
  target for most behavioral queries: `src/flask/__init__.py`,
  `src/flask/__main__.py`, `src/flask/typing.py`.
- **Genuinely uncovered functional areas** — worth noting for a future
  query-writing pass: `src/flask/cli.py` (1,127 lines — the entire CLI
  subsystem has no query in this 20-query sample, a notable gap given
  its size), `src/flask/templating.py` (Jinja2 integration),
  `src/flask/testing.py` (the test-client subsystem — ironic, given
  this run is itself about testing, but no query specifically targets
  Flask's *own* testing utilities as opposed to using them),
  `src/flask/logging.py`, `src/flask/debughelpers.py`,
  `src/flask/wrappers.py` (`Request`/`Response` subclasses),
  `src/flask/json/__init__.py` and `src/flask/json/provider.py` (the
  `JSONProvider` abstraction — only `json/tag.py` was touched, via the
  session-signing queries).
- Compare to the prior FastAPI run's 52% coverage figure — the two
  runs land at a similar breadth despite covering different
  subsystems, which is coincidental rather than a designed target (no
  coverage percentage was targeted during query authoring in either
  run).

## 10. Ambiguous queries

Cross-referenced from `annotation_drafts.jsonl`'s `potential_ambiguity`
field (every query has some entry in this field by design — this table
lists only the ones with a *substantive*, non-trivial ambiguity, not
every query):

| Query | Ambiguity |
|---|---|
| flask-001 | A genuine converter-matching bug may live entirely in Werkzeug, outside this repository. |
| flask-002 | Whether the described behavior is a defect vs. already-documented, expected caveat is unresolved. |
| flask-003 | Whether the query concerns handler registration or handler lookup is unresolved — different files. |
| flask-004 | No flash-specific test file was individually located. |
| flask-008 | (Speculative — see `validation_report.md` §7.) Whether Flask itself implements any URL converters at all, vs. Werkzeug entirely, is unresolved. |
| flask-011 | Whether the confirmed app/blueprint teardown asymmetry is an intentional design distinction or a genuine inconsistency is a judgment call, not resolved here. |
| flask-013 | (Speculative — see `validation_report.md` §7.) No actual inconsistent test behavior was confirmed to exist. |
| flask-015 | Whether the two documentation pages are already updated for the 3.2 context merge, or still stale, was not verified by reading their content. |
| flask-016 | "Cleanup code after a request" is ambiguous between `after_this_request` and `teardown_request`, which have different guarantees. |
