# Dataset Statistics — Click Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`annotation_drafts.jsonl` by script. N = 20 queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | Click |
| Pinned commit | `00e592cea702e0b2caa0dee42489fdb1c22cd845` |
| `src/click/` package `.py` files | 17 |
| Files referenced by at least one query | 12 (71%) |
| Top-level `tests/*.py` files | 22 |
| `docs/**/*.md` files referenced | 9 (`docs/options.md`, `docs/parameter-types.md`, `docs/shell-completion.md`, `docs/contrib.md`, `docs/upgrade-guides.md`, `docs/utils.md`, `docs/api.md`, `docs/complex.md`) |
| `examples/` files referenced | 2 (`examples/complex/complex/cli.py`, `examples/aliases/aliases.py`) |

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
| medium | 13 | 65% |
| easy | 5 | 25% |
| hard | 2 | 10% |

The most medium-heavy of the four pilot runs to date (FastAPI: 45%;
Flask: 45%; Requests: 60%; Click: 65%) — see `validation_report.md`
§10 for a discussion attributing this to `core.py`'s unusual size
concentrating many concerns in one non-trivial file.

## 4. Average candidate files per query

**avg = 2.70, min = 1, max = 4** (n=20, sum=54).

| Query | Category | Candidates |
|---|---|---|
| click-001 | bug_fix | 4 |
| click-003 | bug_fix | 4 |
| click-017 | api_usage | 4 |
| click-002 | bug_fix | 3 |
| click-004 | bug_fix | 3 |
| click-005 | feature_implementation | 3 |
| click-006 | feature_implementation | 3 |
| click-007 | feature_implementation | 3 |
| click-008 | feature_implementation | 3 |
| click-013 | testing | 3 |
| click-014 | testing | 3 |
| click-015 | documentation | 3 |
| click-010 | refactoring | 2 |
| click-011 | refactoring | 2 |
| click-012 | testing | 2 |
| click-016 | documentation | 2 |
| click-018 | api_usage | 2 |
| click-019 | code_search | 2 |
| click-020 | code_search | 2 |
| click-009 | refactoring | 1 |

`click-009` (command-name-derivation refactor) has the single lowest
count (1) — its primary candidate (a specific, directly-confirmed
line in `decorators.py`) is unusually precisely located, needing no
secondary candidates. `click-017` (parent-context API usage) ties for
the highest count (4) and includes the run's single strongest piece of
evidence: a complete, directly-read working example
(`examples/complex/complex/cli.py`'s `make_pass_decorator` usage).

## 5. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count |
|---|---|
| `src/click/core.py` | 9 |
| `src/click/shell_completion.py` | 4 |
| `tests/test_shell_completion.py` | 4 |
| `src/click/types.py` | 4 |
| `src/click/decorators.py` | 4 |
| `src/click/formatting.py` | 3 |
| `tests/test_types.py` | 3 |
| `docs/parameter-types.md` | 3 |
| `examples/complex/complex/cli.py` | 2 |
| `src/click/exceptions.py` | 2 |
| `docs/contrib.md` | 2 |

`src/click/core.py` is the single most cross-cutting file (9 of 20
queries) — reflecting its role as the entire CLI object model
(`Context`/`Command`/`Group`/`Parameter`/`Option`/`Argument`) in one
3,792-line file, the largest single concentration of relevant logic
across all four pilot runs to date.

## 6. Frequently suggested packages

| Package/unit | Reference count |
|---|---|
| `src/click` (all package files combined) | 32 |
| `tests/test_shell_completion.py` | 4 |
| `tests/test_types.py` | 3 |
| `docs/parameter-types.md` | 3 |
| `examples/complex` | 2 |
| `docs/contrib.md` | 2 |

## 7. Weak queries

**0** — see `validation_report.md` §6.

## 8. Directory candidates

**0** in the final artifacts (one was found and resolved to a concrete
file during drafting — see `validation_report.md` §4).

## 9. Coverage observations

Of the 17 `.py` files in `src/click/` itself, **12 (71%) were
referenced by at least one query; 5 (29%) were not** — the highest
coverage fraction of the four pilot runs to date (FastAPI: 52%; Flask:
54%; Requests: 47%; Click: 71%), consistent with Click being the
smallest and most concern-concentrated package inspected so far (17
files vs. 19-48 in the other three).

Untouched files:

- `src/click/__init__.py` — thin, re-export-only, consistent with
  every prior pilot run's `__init__.py` files also going untouched.
- `src/click/_termui_impl.py`, `src/click/_textwrap.py`,
  `src/click/_utils.py` — internal (underscore-prefixed) helper
  modules not individually surfaced by any of the 20 queries.
- `src/click/testing.py` — **notable**: `CliRunner`/`Result`, the
  official public API for testing a Click-based CLI (confirmed and
  described in `repository_summary.md` §3), is entirely untouched by
  this run's 3 Testing-category queries. All three (`click-012`,
  `click-013`, `click-014`) target what's being tested (shell
  completion, terminal/platform behavior, parameter types) rather than
  the testing tool itself — a reasonable but notable gap, echoing the
  Requests run's `api.py`/`exceptions.py` gap and the Flask run's
  `testing.py` gap: the tool a repository provides for testing *other*
  code is a recurring blind spot across this project's query-authoring
  passes so far, worth deliberate attention in a future round.
