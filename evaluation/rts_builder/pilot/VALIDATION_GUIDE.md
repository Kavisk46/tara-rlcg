# VALIDATION_GUIDE.md — RTS Builder Pilot

What `PilotValidator` checks, how each check maps to the pilot's stated
Success Criteria, and how to read `validation_report.md`.

## The four blocking checks (Success Criteria 1-3, plus a general integrity check)

A **blocking** check failing means `ValidationReport.passed = False`,
which (with the default `fail_on_validation_error=True`) makes
`PilotRunner.run` raise `PilotValidationError` before any split file,
`feature_statistics.csv`, figure, or documentation file is written —
Success Criterion 6 ("the dataset is immediately usable for
Learning-to-Rank") is treated as *contingent on* the other criteria,
not a separate check of its own: a dataset that fails any blocking
check is, by definition, not immediately usable.

| Check name | Success Criterion | What it detects | Computed over |
|---|---|---|---|
| `no_missing_values` | 1. "No missing values." | Any column in any row holding `None` or `NaN`. | Every row, every column. |
| `no_duplicate_rows` | (general integrity; implied by "4. Dataset passes validation") | Two rows that are exact duplicates of each other in every column. | Every row (full-row equality). |
| `no_duplicate_query_strategy_pairs` | 2. "No duplicate query-strategy pairs." | The same `(repository_id, commit_sha, query_text, strategy_name)` key appearing more than once. | Every row, grouped by that 4-tuple. |
| `every_query_has_expected_strategy_rows` | 3. "Every query has exactly four strategy rows." | A `(repository_id, commit_sha, query_text)` group whose row count != `PilotSettings.expected_strategy_count` (default `4`). | Every distinct query. |

Success Criterion 5 ("All statistics are exported.") is not a
`ValidationCheck` at all — it's satisfied structurally: `PilotRunner`
only reaches the export step after validation passes, and always
writes `dataset_statistics.json` + `feature_statistics.csv` +
`validation_report.md` together, in one call, with no partial-export
path.

## Reading `validation_report.md`

Generated fresh on every `PilotRunner.run()` call, always reflecting
*this run's* current, digest-filtered row set (see `Architecture.md`
§2) — never a stale prior run's numbers.

- **Overall result** (`PASSED`/`FAILED`) — the single top-line answer;
  `FAILED` here always means at least one row of the "Success Criteria"
  table below shows `FAIL`.
- **Success Criteria table** — one row per blocking check (see above),
  each with a `detail` string that names the actual offending count
  (e.g. `"3 duplicate (repository, commit, query, strategy) pair(s)
  found."`), not just pass/fail.
- **Strategy / Repository / Rank / Split distribution tables** —
  informational, never blocking. A skewed `rank` distribution (e.g. one
  strategy winning `rank=1` far more than 25% of the time) is expected
  and not a validation failure in itself — Oracle Utility's ranking is
  deterministic per query, not uniformly randomized.
- **Averages** — overall and per-strategy mean `utility_score`/
  `latency_ms`/`quality_score`. Useful for a first sanity read (e.g. "is
  `hybrid`'s average latency higher than `lexical`'s, as expected") but
  not itself a pass/fail signal.
- **Distribution histograms** — bin edges and counts for
  `utility_score`/`latency_ms`/`quality_score`, as the same equal-width
  binning `figures.py` uses for the PNG histograms; this table lets a
  reader who can't open the PNGs still see the shape.
- **Feature distributions** — mean/minimum/maximum/count for every
  *numeric* feature column (the same "numeric feature column"
  definition `StatisticsAccumulator` already established: `bool`/`int`/
  `float` values are summarized, `str`-valued categorical columns like
  `repo_dominant_language` are excluded, matching
  `dataset_builder/DatasetSchema.md` §2.4's own convention).

## Interpreting a `FAILED` report

1. Read the `detail` string on each `FAIL`ing row first — it names the
   actual count, not just that something is wrong.
2. `no_missing_values` failing on `quality_*` columns specifically often
   traces back to a query with an empty `relevance_grades` mapping in
   `queries.jsonl` interacting unexpectedly with Oracle Utility's
   metric formulas — check `Oracle_Math.md`'s degenerate-case handling
   first before assuming a Pilot-layer bug.
3. `every_query_has_expected_strategy_rows` failing should not happen
   under normal operation: Retrieval Executor (frozen) always runs
   exactly 4 strategies per query, so a mismatch here usually means
   `expected_strategy_count` was configured to something other than
   `4`, or (rarer) a duplicate/missing `rts_grouped.jsonl` record from
   an unusual Dataset Builder resume scenario — check `digest.json`
   against `dataset_statistics.json` for consistency.
4. `no_duplicate_rows`/`no_duplicate_query_strategy_pairs` failing on a
   *resumed* Dataset Builder output most likely means
   `assembler.load_current_rows`'s digest filter let through rows from
   more than one digest (a symptom, not normally reachable through
   `PilotRunner`'s own code path — worth an issue if seen).
5. To inspect a failing dataset's actual rows without re-running:
   set `PilotSettings(fail_on_validation_error=False)` and re-run — the
   split files are written anyway, alongside a `validation_report.md`
   that still reports `FAILED` and names the same offending checks.

## What is deliberately *not* validated

- **Whether the ground-truth `relevance_grades` in `queries.jsonl` are
  themselves *correct*.** This subsystem (and every RTS Builder
  subsystem before it) treats relevance judgments as externally
  -authored input, never independently assessed for accuracy — see
  `dataset_builder/README.md`'s Inputs section and this subsystem's own
  `DATASET_CARD.md` Limitations section.
- **Statistical significance of any strategy's performance advantage.**
  The averages/distributions in `validation_report.md` are descriptive,
  not inferential — no significance test is run, consistent with "Do
  NOT implement: ... paper writing" (that kind of analysis belongs to a
  later, model-training-adjacent stage, not dataset construction).
- **Cross-run consistency of `dataset_statistics.json`.** This file is
  copied verbatim from `DatasetGenerationSummary.statistics`, already
  Dataset Builder's own tested, cumulative statistics — re-validating
  it here would duplicate, not add, coverage.
