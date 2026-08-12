# Dataset Statistics — SQLAlchemy Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`draft_relevance_judgments.jsonl` (post-Phase-11-audit state) by the
validation script. N = 20 queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | SQLAlchemy |
| Pinned commit | `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` |
| Version at this commit | `2.1.0b4` (beta) |
| `.py` files anywhere under `lib/sqlalchemy/` | 255 |
| Top-level subpackages under `lib/sqlalchemy/` | 11 (`connectors`, `dialects`, `engine`, `event`, `ext`, `future`, `orm`, `pool`, `sql`, `testing`, `util`) |
| Built-in dialects | 5 (`mssql`, `mysql`, `oracle`, `postgresql`, `sqlite`) |
| `unreleased_21/` changelog fragments read in full | 12 |

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
| hard | 4 | 20% |
| easy | 4 | 20% |

The highest hard-difficulty share of any pilot run to date (20% vs.
0-15% in FastAPI/Flask/Requests/Click/Celery), reflecting genuinely
more intricate internals (join-condition resolution in
`_JoinCondition`, insertmanyvalues compilation strategy) surfaced by
this repository compared to the five prior ones.

## 4. Average candidate files per query

**avg = 2.8, min = 1, max = 4** (n=20, sum=56, post-Phase-11-audit
resolution of `sqlalchemy-008` and `sqlalchemy-013`).

| Query | Category | Candidates |
|---|---|---|
| sqlalchemy-001 | bug_fix | 4 |
| sqlalchemy-002 | bug_fix | 4 |
| sqlalchemy-011 | refactoring | 4 |
| sqlalchemy-015 | documentation | 4 |
| sqlalchemy-003 | bug_fix | 3 |
| sqlalchemy-004 | bug_fix | 3 |
| sqlalchemy-006 | feature_implementation | 3 |
| sqlalchemy-008 | feature_implementation | 3 |
| sqlalchemy-009 | refactoring | 3 |
| sqlalchemy-013 | testing | 3 |
| sqlalchemy-014 | testing | 3 |
| sqlalchemy-017 | api_usage | 3 |
| sqlalchemy-018 | api_usage | 3 |
| sqlalchemy-005 | feature_implementation | 2 |
| sqlalchemy-007 | feature_implementation | 2 |
| sqlalchemy-010 | refactoring | 2 |
| sqlalchemy-012 | testing | 2 |
| sqlalchemy-016 | documentation | 2 |
| sqlalchemy-019 | code_search | 2 |
| sqlalchemy-020 | code_search | 1 |

`sqlalchemy-020` has the lowest count (1) because it has an unusually
precise, single-file answer (`pool/base.py`'s connection-lifecycle
classes), not because of a search gap. `sqlalchemy-008` and
`sqlalchemy-013` both changed candidate counts during the Phase 11
audit (008: 2→3 after being replaced with a differently-grounded
query; 013: 2→3 after a concrete test file was added) — see
`README.md`'s Phase 11 section for the full account.

## 5. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count |
|---|---|
| `lib/sqlalchemy/orm/relationships.py` | 5 |
| `lib/sqlalchemy/pool/base.py` | 5 |
| `lib/sqlalchemy/sql/compiler.py` | 3 |
| `test/engine/test_pool.py` | 3 |
| `lib/sqlalchemy/pool/impl.py` | 2 |
| `lib/sqlalchemy/sql/schema.py` | 2 |
| `lib/sqlalchemy/engine/reflection.py` | 2 |
| `test/engine/test_reflection.py` | 2 |
| `test/orm/test_relationships.py` | 2 |
| `test/orm/test_validators.py` | 2 |
| `lib/sqlalchemy/orm/mapper.py` | 2 |
| `doc/build/orm/relationships.rst` | 2 |
| `doc/build/orm/basic_relationships.rst` | 2 |
| `doc/build/core/pooling.rst` | 2 |

`orm/relationships.py` and `pool/base.py` are tied as the most
cross-cutting files (5 of 20 queries each) — consistent with
relationship join-condition resolution and connection-pool lifecycle
being two of this repository's most structurally central, frequently
-touched mechanisms across categories (Bug Fix, Refactoring, Feature,
API Usage, Code Search, Documentation).

## 6. Frequently suggested packages/subpackages

| Package/unit | Reference count (distinct files) |
|---|---|
| `lib/sqlalchemy/sql/` | 4 files (`schema.py`, `ddl.py`, `compiler.py`, `type_api.py`) |
| `lib/sqlalchemy/orm/` | 3 files (`relationships.py`, `strategies.py`, `mapper.py`) |
| `lib/sqlalchemy/dialects/` | 4 files (`sqlite/base.py`, `mssql/base.py`, `oracle/base.py`, `postgresql/base.py`) |
| `lib/sqlalchemy/pool/` | 2 files (`base.py`, `impl.py`) |
| `lib/sqlalchemy/engine/` | 3 files (`reflection.py`, `interfaces.py`, `events.py`) |
| `test/orm/` | 3 files |
| `test/engine/` | 2 files |
| `test/sql/` | 2 files |
| `doc/build/orm/` | 3 files |
| `doc/build/core/` | 4 files |

## 7. Weak queries

**0** by the query-length proxy check (`query_text` under 8 words),
and **0** queries lack a primary candidate as of the final,
post-Phase-11-audit state.

## 8. Directory candidates

**1** found during search (`lib/sqlalchemy/event/`, a secondary
candidate for `sqlalchemy-018`), correctly excluded from the final
`draft_relevance_judgments.jsonl` rather than guessed at — see
`validation_report.md` §8.

## 9. Coverage observations

Of the **255** `.py` files anywhere under `lib/sqlalchemy/`, **17
(6.7%) were referenced by at least one query** — comparable to
Celery's 8.7% (also a large, subsystem-rich repository) and well below
FastAPI/Flask/Requests/Click's 47-71%. **This is an expected
consequence of SQLAlchemy's size and internal complexity, not a
weaker search effort**: 20 queries is a fixed budget regardless of
repository size, and SQLAlchemy's 255 package files are 5-15x more
than any of the four smaller pilot repositories.

A fairer, size-normalized view: of the **11 top-level subpackages**
under `lib/sqlalchemy/`, **5 (45%) had at least one file referenced**
(`orm`, `pool`, `engine`, `sql`, `dialects`) — plus 1 of the package's
top-level, non-subpackaged modules (`exc.py`) referenced out of 7
top-level modules (`__init__.py`, `events.py`, `exc.py`,
`inspection.py`, `log.py`, `schema.py`, `types.py`).

**Entirely untouched subpackages**: `connectors/` (DBAPI-connection
helper adapters), `event/` (the generic event framework itself, as
distinct from `engine/events.py`'s specific event names, which
appeared only as an excluded directory-shaped candidate — see §8),
`ext/` (extensions), `future/` (forward-compatibility shims), `util/`
(general utilities), and `testing/` beyond its `requirements.py`
module. A future round targeting this repository again should
consider these subpackages, plus SQLAlchemy's asyncio support
(referenced only indirectly via `13420.rst`'s `oracledb` async cursor
fix in the changelog review, never directly searched in package code)
and the ORM's declarative/dataclass mapping API (`orm/decl_api.py`,
confirmed present in `repository_summary.md` but not the direct
subject of any of this round's 20 queries).
