# Dataset Statistics — pandas Pilot Annotation Run

All figures computed directly from `queries.jsonl` and
`draft_relevance_judgments.jsonl` (post-Phase-3-correction state) by
the validation script. N = 20 queries.

## 1. Repository statistics

| | |
|---|---|
| Repository | pandas |
| Pinned commit | `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` |
| Version at this commit | `3.1.0.dev0` (`git describe`: `v3.1.0.dev0-1495-gd0d07d18f9`) |
| Largest single file | `pandas/core/frame.py`, 19,651 lines — the largest file confirmed across all seven of this project's pilot repositories to date |
| `doc/source/whatsnew/v3.1.0.rst` (in-development changelog) | 760 lines, read in full |

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
| medium | 11 | 55% |
| hard | 5 | 25% |
| easy | 4 | 20% |

The highest hard-difficulty share of any pilot run to date (25% vs.
15-20% in the six prior runs), reflecting pandas's genuinely deep,
multi-layer internals (the Block/BlockManager storage hierarchy, the
_MergeOperation inheritance chain) surfaced by this repository.

## 4. Average candidate files per query

**avg = 2.75, min = 2, max = 6** (n=20, sum=55, post-Phase-3
correction of `pandas-006`).

| Query | Category | Candidates |
|---|---|---|
| pandas-014 | testing | 6 |
| pandas-006 | feature_implementation | 4 |
| pandas-009 | refactoring | 4 |
| pandas-002 | bug_fix | 4 |
| pandas-001 | bug_fix | 3 |
| pandas-004 | bug_fix | 3 |
| pandas-007 | feature_implementation | 3 |
| pandas-010 | refactoring | 3 |
| pandas-018 | api_usage | 3 |
| pandas-003 | bug_fix | 2 |
| pandas-005 | feature_implementation | 2 |
| pandas-008 | feature_implementation | 2 |
| pandas-011 | refactoring | 2 |
| pandas-012 | testing | 2 |
| pandas-013 | testing | 2 |
| pandas-015 | documentation | 2 |
| pandas-016 | documentation | 2 |
| pandas-017 | api_usage | 2 |
| pandas-019 | code_search | 2 |
| pandas-020 | code_search | 2 |

`pandas-014` has the highest count (6) because it deliberately spans
all three CSV-parsing engines (C, Python, PyArrow) plus their
dedicated test files, consistent with its "cross-engine investigation"
framing. No query in this run has only 1 candidate, unlike every prior
pilot run — a consequence of pandas's deeply layered architecture,
where even precise code-search answers (e.g. `pandas-019`,
`pandas-020`) plausibly involve two closely related files (a manager
and its block hierarchy; a shared base class and a concrete
subclass).

## 5. Frequently suggested files

Files appearing as a candidate for more than one query:

| File | Query count |
|---|---|
| `pandas/core/reshape/merge.py` | 3 |
| `pandas/core/frame.py` | 3 |
| `pandas/core/groupby/generic.py` | 3 |
| `pandas/core/groupby/groupby.py` | 3 |
| `pandas/core/internals/managers.py` | 3 |
| `pandas/core/internals/blocks.py` | 3 |
| `pandas/core/series.py` | 2 |
| `pandas/core/arrays/base.py` | 2 |
| `pandas/tests/reshape/merge/test_merge_asof.py` | 2 |
| `pandas/tests/frame/methods/test_explode.py` | 2 |
| `pandas/tests/groupby/aggregate/test_aggregate.py` | 2 |
| `doc/source/development/internals.rst` | 2 |

No single file dominates as heavily as `orm/relationships.py`/
`pool/base.py` did in the SQLAlchemy run (5 of 20 queries each) — the
most cross-cutting pandas files here (`merge.py`, `frame.py`,
`groupby/generic.py`, `groupby/groupby.py`, `internals/managers.py`,
`internals/blocks.py`) each appear in 3 of 20, consistent with pandas
core subsystems being large but comparatively more self-contained per
query topic than SQLAlchemy's more tightly interwoven ORM/Core layers.

## 6. Frequently suggested packages/subpackages

| Package/unit | Reference count (distinct files) |
|---|---|
| `pandas/core/reshape/` | 3 files (`merge.py`, `concat.py`, and its test dir) |
| `pandas/core/groupby/` | 2 files (`generic.py`, `groupby.py`) |
| `pandas/core/internals/` | 2 files (`managers.py`, `blocks.py`) |
| `pandas/io/` | 4 files (`parquet.py`, `formats/csvs.py`, 4 `parsers/` files) |
| `pandas/core/arrays/` | 3 files (`base.py`, `arrow/array.py`, `datetimelike.py`, `datetimes.py`) |
| `doc/source/development/` | 2 files (`extending.rst`, `internals.rst`) |
| `pandas/tests/` | 15 files across `frame/`, `series/`, `indexes/`, `groupby/`, `io/`, `reshape/`, `internals/`, `extension/` |

## 7. Weak queries

**0** by the query-length proxy check (`query_text` under 8 words),
and **0** queries lack a primary candidate.

## 8. Directory candidates

**0** found during search — every candidate resolved to a concrete
file, the first pilot run with no directory-shaped candidates.

## 9. Coverage observations

pandas's `pandas/core/` package alone spans well over a dozen
subpackages and dozens of large top-level modules (`frame.py`,
`series.py`, `generic.py` totaling 42,709 lines between just those
three files) — an order of magnitude larger than any prior pilot
repository's core package. A precise total-`.py`-file coverage
percentage was not computed for this run (unlike prior runs' explicit
`package_py_files_total` counts), since a full recursive count of
`pandas/`, `pandas/_libs/` (Cython), and `pandas/tests/` combined was
judged disproportionate to this run's fixed 20-query budget; the
`repository_summary.md` §9 already establishes qualitatively that
pandas is the largest repository processed in this project's seven
pilot runs. Subpackages referenced by at least one query: `core/frame`
+ `core/series` + `core/generic` (as `NDFrame`), `core/groupby/`,
`core/internals/`, `core/reshape/`, `core/indexes/`, `core/arrays/`,
`io/`, `io/parsers/`, `io/formats/` — 10 of `core/`'s well over a
dozen subpackages/major modules, plus 3 of `io/`'s major areas.
**Entirely untouched areas**: `pandas/core/computation/` (the
`eval`/`query` engine), `pandas/core/window/` (rolling/expanding/EWM),
`pandas/core/dtypes/` beyond the one `concat.py` reference,
`pandas/tseries/`, `pandas/plotting/`, `pandas/_libs/` (Cython
internals), and most of `pandas/io/` (Excel, JSON, SQL, HDF5, SAS,
Stata, XML, HTML, clipboard, ORC, Iceberg, pickle, feather — only
Parquet, CSV parsing, and generic CSV formatting were touched). A
future round targeting this repository again should consider these
areas specifically, given pandas's exceptional size relative to any
single 20-query round.
