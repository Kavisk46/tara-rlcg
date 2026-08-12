# Dataset Statistics — Requests Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`annotation_drafts.jsonl` by script (same computation underlying
`validation_report.md`). N = 20 queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | Requests |
| Pinned commit | `1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e` |
| `src/requests/` package `.py` files | 19 |
| Files referenced by at least one query | 9 (47%) |
| Top-level `tests/*.py` files | 11 |
| `docs/**/*.rst` files referenced | 4 (`docs/user/advanced.rst`, `docs/user/authentication.rst`, `docs/dev/contributing.rst`) |

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
| medium | 12 | 60% |
| easy | 5 | 25% |
| hard | 3 | 15% |

Notably more medium-heavy than either prior pilot run (FastAPI: 45%
medium; Flask: 45% medium) — see `validation_report.md` §10 for a
discussion (attributed to Requests' smaller, more uniformly-scoped
codebase producing fewer natural "trivial" or "deeply cross-cutting"
extremes).

## 4. Average candidate files per query

**avg = 2.35, min = 1, max = 4** (n=20, sum=47) — the lowest of the
three pilot runs to date (FastAPI: 4.05; Flask: 3.10).

| Query | Category | Candidates |
|---|---|---|
| requests-005 | feature_implementation | 4 |
| requests-001 | bug_fix | 3 |
| requests-002 | bug_fix | 3 |
| requests-008 | feature_implementation | 3 |
| requests-013 | testing | 3 |
| requests-016 | documentation | 3 |
| requests-018 | api_usage | 3 |
| requests-003 | bug_fix | 2 |
| requests-004 | bug_fix | 2 |
| requests-006 | feature_implementation | 2 |
| requests-007 | feature_implementation | 2 |
| requests-009 | refactoring | 2 |
| requests-010 | refactoring | 2 |
| requests-012 | testing | 2 |
| requests-014 | testing | 2 |
| requests-015 | documentation | 2 |
| requests-017 | api_usage | 2 |
| requests-019 | code_search | 2 |
| requests-020 | code_search | 2 |
| requests-011 | refactoring | 1 |

`requests-011` (the auth-class-consistency refactor) has the single
lowest count in this run (1) -- its primary candidate (`auth.py`) is
extremely well-grounded (a directly-confirmed structural asymmetry),
but no test or documentation candidate was proposed, consistent with
the established convention that behavior-preserving refactors are
validated against the broad suite rather than a guessed subset. The
smaller average overall reflects Requests' smaller codebase (§1) —
fewer distinct files plausibly touch any one query's subsystem than in
either prior, larger repository.

## 5. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count |
|---|---|
| `src/requests/sessions.py` | 10 |
| `docs/user/advanced.rst` | 7 |
| `src/requests/models.py` | 4 |
| `tests/test_adapters.py` | 3 |
| `src/requests/cookies.py` | 3 |
| `src/requests/auth.py` | 3 |
| `src/requests/adapters.py` | 2 |
| `docs/user/authentication.rst` | 2 |
| `src/requests/utils.py` | 2 |
| `src/requests/certs.py` | 2 |

`src/requests/sessions.py` is the single most cross-cutting file (10
of 20 queries, half the entire query set) -- reflecting `Session`'s
role as the library's central, stateful orchestration point (request
preparation, adapter selection, cookie/auth/proxy merging all pass
through it, each independently confirmed during Phase 3).
`docs/user/advanced.rst` is the single most-referenced documentation
file (7 queries) -- Requests has only 4 `docs/user/*.rst` pages total,
so this concentration partly reflects the small number of pages
available, not unusual query clustering.

## 6. Frequently suggested packages

| Package/unit | Reference count |
|---|---|
| `src/requests` (all package files combined) | 28 |
| `docs/user` | 9 |
| `tests/test_adapters.py` | 3 |
| `docs/dev` | 1 |

## 7. Weak queries

**0** — see `validation_report.md` §6.

## 8. Directory candidates

**0** — see `validation_report.md` §8.

## 9. Coverage observations

Of the 19 `.py` files in `src/requests/` itself, **9 (47%) were
referenced by at least one query; 10 (53%) were not** — the lowest
coverage fraction of the three pilot runs to date (FastAPI: 52%;
Flask: 54%).

Untouched files, grouped by why:

- **Thin/leaf modules**: `src/requests/__init__.py`,
  `src/requests/__version__.py`, `src/requests/packages.py`.
- **Internal/typing-only support**: `src/requests/_internal_utils.py`,
  `src/requests/_types.py`, `src/requests/compat.py`.
- **Genuinely uncovered functional areas** — worth noting for a future
  query-writing pass: `src/requests/api.py` (the module-level
  `get()`/`post()`/etc. convenience functions most users interact with
  first — despite being prominently described in
  `repository_summary.md` §3, no query in this 20-query sample targets
  it directly); `src/requests/exceptions.py` (the 20-class exception
  hierarchy, also prominently described in `repository_summary.md`
  §3, entirely untouched); `src/requests/status_codes.py`;
  `src/requests/structures.py` (`CaseInsensitiveDict`/`LookupDict`).

The `api.py`/`exceptions.py` gap is worth flagging explicitly: both
were identified as architecturally significant during Phase 1 but did
not end up grounding any of the 20 queries actually written in Phase
2 — a reminder that `repository_summary.md`'s architectural coverage
and `queries.jsonl`'s actual query coverage are two different
things, and a future round targeting this repository again should
consider these two files specifically.
