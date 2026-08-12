# Dataset Statistics — Celery Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`annotation_drafts.jsonl` by script (same computation underlying
`validation_report.md`). N = 20 queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | Celery |
| Pinned commit | `f109abf852525b69a1b6eee0457c6cd5561e0529` |
| `.py` files anywhere under `celery/` (all 12 subpackages) | 161 |
| Top-level `celery/*.py` files | 13 |
| Files referenced by at least one query | 14 |
| `t/unit/*.py` files | 144 |
| `docs/userguide/*.rst` files referenced | 5 (`canvas.rst`, `periodic-tasks.rst`, `security.rst`, `extending.rst`, `tasks.rst`) |
| `examples/` files referenced | 1 (`examples/stamping/visitors.py`) |

By far the largest repository processed across this project's five
pilot runs to date (161 package `.py` files vs. 17-48 in the other
four) — see §9 for how this changes the coverage-percentage
comparison.

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
| easy | 4 | 20% |
| hard | 3 | 15% |

Tied with the Click pilot run for the most medium-heavy of the five
runs to date (FastAPI: 45%; Flask: 45%; Requests: 60%; Click: 65%;
Celery: 65%) — see `validation_report.md` §9 for the attributed cause
(large, subsystem-concentrated files).

## 4. Average candidate files per query

**avg = 2.75, min = 1, max = 4** (n=20, sum=55, post-duplicate
-correction and post-Phase-11 resolution of celery-013).

| Query | Category | Candidates |
|---|---|---|
| celery-001 | bug_fix | 4 |
| celery-002 | bug_fix | 4 |
| celery-008 | feature_implementation | 4 |
| celery-013 | testing | 4 |
| celery-017 | api_usage | 4 |
| celery-004 | bug_fix | 3 |
| celery-005 | feature_implementation | 3 |
| celery-006 | feature_implementation | 3 |
| celery-007 | feature_implementation | 3 |
| celery-009 | refactoring | 3 |
| celery-014 | testing | 3 |
| celery-015 | documentation | 3 |
| celery-018 | api_usage | 3 |
| celery-003 | bug_fix | 2 |
| celery-011 | refactoring | 2 |
| celery-012 | testing | 2 |
| celery-016 | documentation | 2 |
| celery-020 | code_search | 2 |
| celery-010 | refactoring | 1 |
| celery-019 | code_search | 1 |

`celery-010` and `celery-019` have the lowest count (1) because they
have unusually precise, single-file, single-class answers, not because
of a search gap. `celery-013` (flaky-test investigation) initially had
only 1 candidate (a mechanism-only confirmation via `pyproject.toml`'s
marker declaration, no specific test located) but was resolved to 4
candidates during the Phase 11 audit after a follow-up search located
the actual `flaky` marker definition and 10+ of its applications in
`t/integration/` — see `README.md`'s Phase 11 audit for the full
account. The table above reflects the final, post-audit state.

## 5. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count |
|---|---|
| `celery/canvas.py` | 6 |
| `docs/userguide/canvas.rst` | 5 |
| `celery/schedules.py` | 4 |
| `celery/backends/base.py` | 4 |
| `celery/app/task.py` | 3 |
| `t/unit/tasks/test_canvas.py` | 2 |
| `t/unit/app/test_schedules.py` | 2 |
| `celery/worker/worker.py` | 2 |
| `celery/app/backends.py` | 2 |
| `examples/stamping/visitors.py` | 2 |
| `celery/exceptions.py` | 2 |
| `t/unit/tasks/test_tasks.py` | 2 |

`celery/canvas.py` is the single most cross-cutting file (6 of 20
queries) — consistent with it being the largest file in the package
(2,443 lines) and the home of the task-composition primitives
(chain/group/chord/map) that ground several queries across different
categories (Bug Fix, Feature, Refactoring, Documentation, API Usage).

## 6. Frequently suggested packages

| Package/unit | Reference count |
|---|---|
| `t/unit` (all test files combined) | 10 |
| `docs/userguide` | 9 |
| `celery/app` (subpackage) | 6 |
| `celery/canvas.py` | 6 |
| `celery/schedules.py` | 4 |
| `celery/backends` (subpackage) | 4 |
| `celery/worker` (subpackage) | 4 |
| `examples/stamping` | 2 |

## 7. Weak queries

**0** by the confidence-based definition, and **0** queries lack a
primary candidate as of the final, post-Phase-11-audit state — see
`validation_report.md` §5 (a related but distinct condition initially
caught `celery-013` during drafting; resolved during the audit).

## 8. Directory candidates

**2** found during search (`t/unit/worker` for `celery-004`,
`docs/getting-started/backends-and-brokers` for `celery-005`), both
correctly excluded from the final relevance-judgment file rather than
guessed at — see `validation_report.md` §7.

## 9. Coverage observations

Of the 161 `.py` files anywhere under `celery/` (across all 12
subpackages), **14 (8.7%) were referenced by at least one query** —
by far the lowest raw-file coverage percentage of the five pilot runs
to date (FastAPI: 52%; Flask: 54%; Requests: 47%; Click: 71%; Celery:
8.7%). **This is an expected consequence of Celery's size, not a
weaker search effort**: 20 queries is a fixed budget regardless of
repository size, and Celery has 3-9x more package files than any
prior pilot repository.

A fairer, size-normalized view: of the **12 top-level subpackages**
under `celery/` (`app`, `apps`, `backends`, `bin`, `concurrency`,
`contrib`, `events`, `fixups`, `loaders`, `security`, `utils`,
`worker`), **4 (33%) had at least one file referenced** (`app`,
`backends`, `security`, `worker`) — plus 6 of the package's top-level,
non-subpackaged modules (`canvas.py`, `beat.py`, `bootsteps.py`,
`exceptions.py`, `result.py`, `schedules.py`) out of 13 top-level
modules (46%).

**Entirely untouched subpackages**: `apps/`, `bin/` (the CLI
subcommand implementations — notable, given every prior pilot run's
own "testing tool/CLI surface went untouched" pattern recurring here
too, see `research_notes.md`), `concurrency/` (the pluggable
execution-pool backends — prefork/eventlet/gevent/solo/thread),
`contrib/` (including the pytest plugin and remote debugger),
`events/` (event dispatch/monitoring), `fixups/` (framework
integrations), `loaders/` (configuration-loading strategies), `utils/`
(23 files of general utilities). A future round targeting this
repository again should consider these seven entirely-unrepresented
subpackages specifically.
