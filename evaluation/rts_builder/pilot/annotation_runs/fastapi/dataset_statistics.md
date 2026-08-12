# Dataset Statistics — FastAPI Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`annotation_drafts.jsonl` by script (see `validation_report.md` for the
same underlying computation, focused on correctness rather than
description). N = 20 queries.

## 1. Category histogram

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

## 2. Difficulty histogram

| Difficulty | Count | Share |
|---|---|---|
| medium | 9 | 45% |
| easy | 6 | 30% |
| hard | 5 | 25% |

No target distribution was mandated for difficulty; this reflects each
query's difficulty as assigned during Phase 2, per
`ANNOTATION_HANDBOOK.md`'s difficulty rubric (single-file = easy,
small related group = medium, multi-module/cross-cutting = hard).

## 3. Average candidates per query

**avg = 4.05, min = 1, max = 7** (n=20, sum=81), computed across all
four candidate buckets (primary, secondary, regression tests,
documentation examples) combined.

| Query | Category | Candidates |
|---|---|---|
| fastapi-001 | bug_fix | 7 |
| fastapi-005 | feature_implementation | 6 |
| fastapi-007 | feature_implementation | 6 |
| fastapi-011 | refactoring | 6 |
| fastapi-003 | bug_fix | 5 |
| fastapi-004 | bug_fix | 5 |
| fastapi-006 | feature_implementation | 5 |
| fastapi-008 | feature_implementation | 5 |
| fastapi-009 | refactoring | 5 |
| fastapi-012 | testing | 5 |
| fastapi-002 | bug_fix | 4 |
| fastapi-010 | refactoring | 3 |
| fastapi-015 | documentation | 3 |
| fastapi-016 | documentation | 3 |
| fastapi-017 | api_usage | 3 |
| fastapi-018 | api_usage | 3 |
| fastapi-013 | testing | 2 |
| fastapi-014 | testing | 2 |
| fastapi-020 | code_search | 2 |
| fastapi-019 | code_search | 1 |

Observation: `code_search` queries have the lowest average candidate
count (1.5) by design -- a well-formed Code Search query has a single,
specific answer (§3.7 of `ANNOTATION_HANDBOOK.md`). `bug_fix` and
`feature_implementation` have the highest averages (5.25 and 5.5
respectively), consistent with those categories typically touching an
implementation file, its declaration/entry-point counterpart, tests,
and a documentation example simultaneously.

## 4. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count | Queries |
|---|---|---|
| `fastapi/dependencies/utils.py` | 5 | fastapi-001, fastapi-008, fastapi-010, fastapi-012, fastapi-017 |
| `fastapi/routing.py` | 5 | fastapi-001, fastapi-003, fastapi-007, fastapi-008, fastapi-010 |
| `fastapi/openapi/utils.py` | 3 | fastapi-007, fastapi-016, fastapi-020 |
| `fastapi/applications.py` | 3 | fastapi-008, fastapi-017, fastapi-020 |
| `fastapi/_compat/v2.py` | 2 | fastapi-001, fastapi-004 |
| `fastapi/exceptions.py` | 2 | fastapi-001, fastapi-002 |
| `docs_src/body_nested_models/tutorial006_py310.py` | 2 | fastapi-001, fastapi-016 |
| `fastapi/middleware/cors.py` | 2 | fastapi-002, fastapi-011 |
| `fastapi/background.py` | 2 | fastapi-003, fastapi-015 |
| `docs_src/background_tasks/tutorial001_py310.py` | 2 | fastapi-003, fastapi-015 |
| `fastapi/param_functions.py` | 2 | fastapi-004, fastapi-018 |
| `fastapi/security/base.py` | 2 | fastapi-005, fastapi-009 |
| `fastapi/security/http.py` | 2 | fastapi-005, fastapi-009 |
| `fastapi/security/api_key.py` | 2 | fastapi-005, fastapi-009 |
| `fastapi/openapi/models.py` | 2 | fastapi-005 (as a secondary candidate), fastapi-007 |

`fastapi/dependencies/utils.py` and `fastapi/routing.py` are the two
most cross-cutting files in this query set, tying with 5 appearances
each -- consistent with `repository_summary.md`'s architectural trace
identifying them as the two largest, most central modules (1,053 and
6,447 lines respectively).

## 5. Frequently suggested packages

Counting every candidate's containing package/top-level module
(directory, or the file itself when not nested):

| Package/module | Reference count |
|---|---|
| `fastapi/security` | 9 |
| `tests/test_tutorial` | 7 |
| `fastapi/middleware` | 7 |
| `fastapi/dependencies` | 6 |
| `fastapi/routing.py` | 5 |
| `fastapi/openapi` | 5 |
| `fastapi/applications.py` | 3 |

`fastapi/middleware`'s count of 7 is almost entirely attributable to a
single query (fastapi-011) whose candidates were all `Low` confidence
-- see §6 and `research_notes.md` §3. It should not be read as "the
middleware package is a hotspot of genuine query relevance" without
that context.

## 6. Potential ambiguity hotspots

- **fastapi-011** (refactor middleware error handling): all 6
  candidates are `Low` confidence. 4 of 5 named middleware files are
  confirmed single-line Starlette re-exports with no custom logic. This
  query has the weakest grounding of the 20.
- **fastapi-013** (intermittent concurrency test): only 2 candidates,
  both `Low` confidence. No file or test matching "concurrent" was
  found anywhere in `tests/`. Second-weakest grounding.
- **fastapi-014** (multiple security schemes on one route): only 2
  candidates, one `Medium`/`Low`. No existing test combining two
  distinct schemes was found by name across 39 security test files.
- **fastapi-002** (CORS + exception handler headers): primary
  candidate confirmed relevant to exception handling, but the CORS
  logic itself is entirely outside this repository (in Starlette) --
  a structural ambiguity about whether this repository can even
  contain the fix.
- **fastapi-017** (dependency created once per application): the
  "obvious" keyword match (`use_cache`) was directly verified to be
  per-request-scoped, not per-application-scoped -- a subtle mismatch
  between query wording and the nearest matching code that a naive
  keyword-only search would miss entirely.
- **fastapi-001 / fastapi-016** and **fastapi-003 / fastapi-015**: pairs
  of queries sharing a domain (nested-model schema representation;
  background-tasks+streaming) across different categories (bug_fix/
  documentation; bug_fix/documentation). Not flagged as duplicates
  (different intents, confirmed in `validation_report.md` §1), but an
  annotator should keep their `relevance_grades` for the shared files
  consistent in *reasoning* even though the two queries' relevant sets
  may legitimately differ in scope.

## 7. Coverage analysis

Of the 48 `.py` files in the `fastapi/` package itself (excluding
`tests/` and `docs_src/`), **25 (52%) were referenced as a candidate by
at least one query; 23 (48%) were not referenced by any query.**

Untouched files, grouped by why:

- **Re-export shims with no logic of their own** (would rarely be a
  genuine relevance target regardless of query): `staticfiles.py`,
  `templating.py`, `testclient.py`, `websockets.py`, `requests.py`,
  `sse.py` (partial -- has real logic, just not queried this round).
- **Package `__init__.py` files** (`fastapi/__init__.py`,
  `_compat/__init__.py`, `dependencies/__init__.py`,
  `middleware/__init__.py`, `openapi/__init__.py`,
  `security/__init__.py`): expected to be low-relevance for most
  behavioral queries; they only re-export public names.
- **Genuinely uncovered functional areas** -- worth noting for a future
  query-writing pass, not necessarily a defect in this round:
  `fastapi/security/open_id_connect_url.py` and
  `fastapi/security/utils.py` (no OpenID Connect or security-utility
  -specific query was written); `fastapi/utils.py`,
  `fastapi/datastructures.py`, `fastapi/types.py`,
  `fastapi/openapi/docs.py`, `fastapi/openapi/constants.py`,
  `fastapi/logger.py`, `fastapi/cli.py` (no query touched CLI,
  logging, or the docs-UI-serving endpoints specifically).

This 52% coverage figure describes **candidate-set breadth**, not
relevance-grade coverage (which does not exist yet -- see
`human_annotation_checklist.md`). A future pilot round targeting more
of the untouched areas (OpenID Connect, CLI, docs UI serving) would
increase repository breadth at the cost of this round's depth on
request-handling/validation/security, which was this round's de facto
focus given the 20-query budget.
