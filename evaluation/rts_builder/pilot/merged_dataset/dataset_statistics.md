# Dataset Statistics — RTS Dataset v1.0

Phase 6 of the merged-dataset assembly. All figures computed directly
from `queries_master.jsonl` and `draft_relevance_master.jsonl` (or,
where noted, from individual repositories' own `annotation_metrics.json`
files where present).

## 1. Overview

| | |
|---|---|
| Total repositories | 8 |
| Total queries | 160 |
| Total relevance-judgment rows | 439 |
| Schema version | 1.0 |
| Grades assigned | 0 (all 439 rows `"TO_BE_ASSIGNED"` — this is a draft dataset pending human annotation) |

## 2. Queries per repository

| Repository | Queries | Share |
|---|---|---|
| fastapi | 20 | 12.5% |
| flask | 20 | 12.5% |
| requests | 20 | 12.5% |
| click | 20 | 12.5% |
| celery | 20 | 12.5% |
| sqlalchemy | 20 | 12.5% |
| pandas | 20 | 12.5% |
| scikit-learn | 20 | 12.5% |
| **Total** | **160** | **100%** |

Perfectly balanced by construction — every repository contributed
exactly 20 queries, per the mission's requirement enforced identically
across all 8 individual annotation runs.

## 3. Category distribution

| Category | Count | Share |
|---|---|---|
| bug_fix | 32 | 20.0% |
| feature_implementation | 32 | 20.0% |
| refactoring | 24 | 15.0% |
| testing | 24 | 15.0% |
| documentation | 16 | 10.0% |
| api_usage | 16 | 10.0% |
| code_search | 16 | 10.0% |

Every one of the 8 repositories independently hit the required
4/4/3/3/2/2/2 per-repository distribution (verified directly — see
`query_merge_report.md` §"Category distribution"), so the dataset-wide
distribution is exactly proportional with no skew introduced by
repository size or content differences.

## 4. Difficulty distribution

### Dataset-wide

| Difficulty | Count | Share |
|---|---|---|
| medium | 92 | 57.5% |
| easy | 39 | 24.4% |
| hard | 29 | 18.1% |

### Per repository

| Repository | easy | medium | hard |
|---|---|---|---|
| fastapi | 6 | 9 | 5 |
| flask | 7 | 9 | 4 |
| requests | ~ | ~ | ~ (see repo `dataset_statistics.md`; requests skewed 60% medium per its own report) |
| click | ~ | ~ | ~ (65% medium per its own report) |
| celery | 4 | 13 | 3 |
| sqlalchemy | 4 | 12 | 4 |
| pandas | 4 | 11 | 5 |
| scikit-learn | 4 | 13 | 3 |

(Rows marked "~" reflect that this assembly recomputed the
dataset-wide totals directly from `queries_master.jsonl` rather than
re-deriving every repository's individual easy/medium/hard split from
scratch; the dataset-wide totals in the table above this one **are**
the direct, fully recomputed sum across all 160 queries. Consult each
repository's own `dataset_statistics.md` for its individual
easy/medium/hard breakdown if needed.)

### Category × difficulty cross-tabulation (dataset-wide)

| Category | easy | medium | hard |
|---|---|---|---|
| bug_fix | 4 | 21 | 7 |
| feature_implementation | 2 | 28 | 2 |
| refactoring | 0 | 12 | 12 |
| testing | 8 | 8 | 8 |
| documentation | 8 | 8 | 0 |
| api_usage | 2 | 14 | 0 |
| code_search | 15 | 1 | 0 |

Notable, expected patterns: `code_search` is overwhelmingly `easy`
(15/16), `refactoring` is evenly split between `medium` and `hard`
with 0 `easy` refactors, and `documentation`/`api_usage` never reach
`hard` — all consistent with the intrinsic difficulty character of
each category rather than an artifact of the merge.

## 5. Candidate-file distribution (from `draft_relevance_master.jsonl`)

| Repository | Judgment rows | Queries | Avg candidates/query | Min | Max |
|---|---|---|---|---|---|
| fastapi | 74 | 20 | 3.70 | 1 | 7 |
| flask | 62 | 20 | 3.10 | 1 | 5 |
| requests | 47 | 20 | 2.35 | 1 | 4 |
| click | 54 | 20 | 2.70 | 1 | 4 |
| celery | 53 | 20 | 2.65 | 1 | 4 |
| sqlalchemy | 56 | 20 | 2.80 | 1 | 4 |
| pandas | 55 | 20 | 2.75 | 2 | 6 |
| scikit-learn | 38 | 20 | 1.90 | 1 | 3 |
| **Dataset-wide** | **439** | **160** | **2.74** | **1** | **7** |

fastapi has both the highest average (3.70) and the highest single
-query maximum (7, for fastapi-001) — consistent with fastapi's own
`validation_report.md` §10 reporting the same figures before this
merge (4.05 avg over its 4 candidate *buckets* combined per query
differs slightly from the 3.70 recomputed here over the *flattened,
deduplicated* `(query, file)` pairs actually in the merged relevance
file — the two numbers measure slightly different things: bucket
-membership count vs. distinct-file count — and the flattened figure
is the one used dataset-wide for consistency with the other 7
repositories' methodology). scikit-learn has the lowest average
(1.90), consistent with its own `research_notes.md` finding that its
flat, one-estimator-per-file architecture produces less cross-cutting,
more precisely-targeted candidate sets than the other repositories.

**0 queries have zero candidate files** — every one of the 160 queries
has at least 1 grounded candidate.

## 6. Repository distribution — file-reference footprint

The 439 relevance-judgment rows reference 249 distinct `(repository,
file)` pairs, all independently verified to exist in their respective
pinned-commit repository clones (see `relevance_merge_report.md`
§"File-existence verification").

## 7. Weak query count

**0 weak queries dataset-wide**, recomputed directly against all 160
merged queries using the same proxy definition used throughout this
project (`query_text` under 8 words). This matches every individual
repository's own self-reported `weak_queries: 0` (available for the 7
repositories with `annotation_metrics.json`; recomputed directly for
fastapi in the absence of that file, also 0).

## 8. Speculative query count

| Repository | Speculative queries (final, post-audit) | Source |
|---|---|---|
| fastapi | Not tracked under this name in this run's methodology (predates the convention) — closest equivalent is 7 disclosed, unresolved directory-level candidates, none of which reached `draft_relevance_judgments.jsonl` (see `annotation_runs/fastapi/validation_report.md` §4) | fastapi's own `validation_report.md` |
| flask | 2 (`flask-008`, `flask-013`) | `annotation_metrics.json` |
| requests | 2 | `annotation_metrics.json` |
| click | 1 | `annotation_metrics.json` |
| celery | 0 (1 resolved during that run's Phase 11 audit) | `annotation_metrics.json` |
| sqlalchemy | 0 (2 resolved during that run's Phase 11 audit / drafting) | `annotation_metrics.json` |
| pandas | 0 (2 resolved during drafting) | `annotation_metrics.json` |
| scikit-learn | 0 (first run with none from the start) | `annotation_metrics.json` |
| **Known total** | **5** (flask + requests + click; fastapi's 7 directory-level candidates are a related but methodologically distinct category, not double-counted here) | |

**This dataset-wide figure carries forward a genuine, disclosed
limitation**: `speculative_queries` as a tracked, explicitly-resolved
concept (with a `"STRONG FLAG"` marker convention and, in later runs,
an active Phase 11 follow-up search to resolve it) was introduced
partway through this project's 8 sequential annotation runs. flask
(2) and requests (2) and click (1) — the 2nd, 3rd, and 4th
repositories processed — each still carry unresolved speculative
queries in their final `annotation_metrics.json`, meaning **5 of the
160 merged queries (3.1%) are flagged by their own source repository
as resting on incomplete grounding evidence**, requiring priority
attention during human review (see
`human_annotation_checklist.md`-equivalent guidance for each affected
repository). This is disclosed prominently in `dataset_card.md`'s
Known Limitations section as well.

## 9. Validation summary

See `validation_report.md` for the full dataset-wide validation. In
brief: 0 duplicate queries, 0 duplicate IDs, 0 duplicate candidate
files, 0 missing repositories, 0 missing files among the actually
-merged data (2 disclosed per-repository metadata gaps that do not
affect the merged data itself), 0 empty required fields, exact
category balance, and perfect 20/20/20/20/20/20/20/20 repository
balance.
