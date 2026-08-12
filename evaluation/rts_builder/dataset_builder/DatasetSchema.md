# DatasetSchema.md — RTS Builder Dataset Builder (Milestone 7)

The complete input and output schema for the Dataset Builder subsystem.
Long-format row columns are not re-derived here where they already have
an authoritative reference — see the links below — this document
covers the schema of what is genuinely new at this milestone: the input
files, the grouped format, and the run-level artifacts (checkpoint,
statistics, summary).

## 1. Inputs

### 1.1 Repository manifest (`manifest.json`)

A JSON array, one object per repository. Order is preserved and
processed in that exact order.

| Field | Type | Required | Description |
|---|---|---|---|
| `repository_id` | string | yes | Stable identifier, unique across the manifest. |
| `source_url` | string | yes | Passed directly to `RepositoryLoader.load_repository`. |
| `commit_sha` | string | yes | Passed directly to `RepositoryLoader.load_repository`; must be a full 40-character SHA (Repository Loader's own requirement). |
| `metadata` | object (string → string) | no | Passthrough curation metadata (e.g. `split`, `domain`, `license` — see `docs/DATASET_BUILDER_SPEC.md` §3). Never read or validated by this subsystem. |

```json
[
  {"repository_id": "repo-0001", "source_url": "https://github.com/psf/requests.git", "commit_sha": "<40-char sha>", "metadata": {"split": "train"}}
]
```

### 1.2 Queries file (`queries.jsonl`)

JSON Lines, one object per line, one line per query.

| Field | Type | Required | Description |
|---|---|---|---|
| `repository_id` | string | yes | Must match a `repository_id` in the manifest to be processed. |
| `query_text` | string | yes | The raw developer query. |
| `relevance_grades` | object (string → number) | no (default `{}`) | `file_path → non-negative relevance grade`, exactly `RelevanceJudgment.relevance_grades`'s schema. An empty object is valid (see `README.md`'s Failure Modes: quality degrades to 0.0, not an error). |

```jsonl
{"repository_id": "repo-0001", "query_text": "How does Dog bark?", "relevance_grades": {"app.py": 2.0, "pkg/base.py": 1.0}}
{"repository_id": "repo-0001", "query_text": "fix the bug in helper", "relevance_grades": {"app.py": 1.0}}
```

## 2. Outputs

### 2.1 Long-format dataset — `rts_long.jsonl` / `rts_long.csv` / `rts_long.parquet/part-*.parquet`

One row per `(repository, commit, query, strategy)` — always exactly 4
rows per query. Column set is identical across all three formats,
identical to `DatasetRow.to_flat_dict()`'s merged output:

- **Feature columns** (identical across a query's 4 rows) — see [`../feature_extraction/FEATURE_CATALOG.md`](../feature_extraction/FEATURE_CATALOG.md) for every `query_*`, `repo_*`, `graph_*`, `structural_*`, `resource_*` column's exact definition.
- **Label columns** (vary per strategy) — see [`../oracle_utility/Oracle_Math.md`](../oracle_utility/Oracle_Math.md) §5 for `repository_id`, `commit_sha`, `query_text`, `strategy_name`, `latency_ms`, `latency_normalized`, `context_token_count`, `utility_score`, `rank`, `is_best_strategy`, `label_confidence`, `tied_with`, and every `quality_*` column's exact definition.
- **Provenance columns** (Reviewer Minor Revision, identical across a query's 4 rows) — `pipeline_digest`, `input_digest`: each the `digest_hash` of the run that computed this row (see §2.6 for `digest.json`'s own schema). Present specifically so a consumer can recover the current, de-duplicated view of the long-format files after a digest-invalidating change causes rows to be recomputed and appended alongside a prior run's now-superseded ones — filter to the values in the current `digest.json`. Not part of `FeatureVector`/`StrategyOracleRow`'s own schemas (both frozen); appended by `DatasetRow.to_flat_dict` itself.

Column order (identical in every row, and reused as the CSV header /
Parquet schema field order): every feature column first (in
`FeatureVector.to_flat_dict`'s group order: query, repo, graph,
structural, resource), then every label column (in
`StrategyOracleRow.to_flat_dict`'s field order), then `pipeline_digest`,
then `input_digest`.

`tied_with` is serialized as a comma-joined string of strategy names
(e.g. `"dense,hybrid"`, or `""` if empty) in all three formats — a
literal JSON/Arrow list column would be natural for JSONL/Parquet but
not for CSV, and this subsystem deliberately keeps one column
representation across all three long-format exports rather than three
different encodings of the same field.

### 2.2 Grouped dataset — `rts_grouped.jsonl` (JSONL only, see `README.md`)

One JSON object per line, one line per query:

```json
{
  "feature_vector": { "...": "the full FeatureVector, nested, unflattened" },
  "oracle_result": {
    "repository_id": "...", "commit_sha": "...", "query_text": "...",
    "rows": [ "...four StrategyOracleRow objects, already sorted by rank ascending..." ],
    "computed_at": "..."
  },
  "pipeline_digest": "<digest_hash>",
  "input_digest": "<digest_hash>"
}
```

`pipeline_digest`/`input_digest` (Reviewer Minor Revision): see §2.1's
provenance-column entry — identical reasoning applies here.

### 2.3 Checkpoint — `checkpoint.jsonl`

Append-only JSON Lines. One line per successfully, durably completed
query, **as of the pipeline_digest/input_digest recorded on that line**
(Reviewer Minor Revision):

```jsonl
{"commit_sha": "...", "query_text": "...", "repository_id": "...", "pipeline_digest": "<digest_hash>", "input_digest": "<digest_hash>"}
```

Keys are written in sorted order (`json.dumps(..., sort_keys=True)`)
for deterministic, diff-friendly output. A malformed trailing line
(evidence of a crash mid-write) is skipped on load, not fatal — see
`README.md`'s Failure Modes. A line missing `pipeline_digest`/
`input_digest` entirely (a pre-Revision checkpoint file) is treated as
belonging to neither digest — i.e. as stale — never as a `KeyError`.

**Validation on load** (Revision 4): if *any* loaded line's
`pipeline_digest`/`input_digest` differs from the current run's, the
*entire* checkpoint is treated as invalid for this run (every query
recomputed), not just the mismatched lines — see `README.md`'s
Reproducibility Guarantees for why this must be whole-file, not
per-entry. Nothing is deleted or rewritten; new lines are still
appended under the current digests, and a future run under the
*original* digests would recognize the old lines as valid again.

### 2.4 Dataset statistics — `dataset_statistics.json`

One JSON object, the serialized `DatasetStatistics` model, **cumulative
across every session that has ever contributed to this output
directory** (see `Pipeline.md` §4):

| Field | Type | Description |
|---|---|---|
| `repository_count` | int | `len(repository_ids)`. |
| `repository_ids` | string[] | Every distinct `repository_id` represented, sorted. |
| `query_count` | int | Distinct `(repository, query)` pairs. |
| `row_count` | int | Total long-format rows (`query_count * 4`). |
| `best_strategy_distribution` | object (string → int) | `strategy_name → count of queries where that strategy was rank 1`. |
| `average_utility_overall` / `average_utility_by_strategy` | float / object (string → float) | Mean `utility_score`, overall and per strategy. |
| `average_latency_ms_overall` / `average_latency_ms_by_strategy` | float / object (string → float) | Mean `latency_ms`, overall and per strategy. |
| `average_quality_overall` / `average_quality_by_strategy` | float / object (string → float) | Mean `quality.quality_score`, overall and per strategy. |
| `feature_statistics` | object (string → `FeatureStatistic`) | `{mean, minimum, maximum, count}` for every *numeric* feature column (categorical columns — `repo_dominant_language`, `resource_repository_size_category` — are excluded, not summarizable by mean/min/max). |

### 2.5 Generation summary — `DatasetGenerator.generate`'s return value (not written to disk automatically)

| Field | Type | Description |
|---|---|---|
| `repositories_processed` / `repositories_skipped` / `repositories_failed` | int | This run's counts (not cumulative — see `README.md`). |
| `queries_processed` / `queries_skipped` / `queries_failed` | int | This run's counts (not cumulative). |
| `queries_invalidated_by_digest_change` (Reviewer Minor Revision) | int | `checkpoint_store.stale_entry_count` — how many previously-checkpointed entries this run discarded (and is now recomputing) because `pipeline_digest`/`input_digest` no longer matched. `0` on a clean resume or a from-scratch run; see `README.md`'s Reproducibility Guarantees. |
| `pipeline_digest` (Reviewer Minor Revision) | `PipelineDigest` | This run's computed pipeline digest — see §2.6. |
| `input_digest` (Reviewer Minor Revision) | `InputDigest` | This run's computed input digest — see §2.6. |
| `statistics` | `DatasetStatistics` | Cumulative — see §2.4. |
| `output_paths` | object (string → string) | Logical name → absolute path, for every enabled output artifact — now including `"digest": "<output_dir>/digest.json"`. |
| `started_at` / `finished_at` | datetime | This run's wall-clock bounds. |

Callers that want a durable, cumulative summary should persist
`dataset_statistics.json` (already automatic) and/or serialize the
returned `DatasetGenerationSummary` themselves; only the statistics
file and `digest.json` are written automatically, since a *run*
summary is inherently per-invocation, not cumulative, by definition.

### 2.6 Digest file — `digest.json` (Reviewer Minor Revision)

Written once per run, before any repository or query work begins (see
`Pipeline.md` §0). One JSON object, the current run's `pipeline_digest`
and `input_digest`, nested and unflattened:

```json
{
  "pipeline_digest": {
    "pipeline_version": "1.0.0",
    "git_commit": "<40-char sha, or '<sha>-dirty' if the TARA repo has uncommitted changes, or 'unknown' outside a git repo>",
    "feature_schema_version": "<16-hex-char prefix of sha256(FeatureVector.model_json_schema())>",
    "oracle_schema_version": "<16-hex-char prefix of sha256(StrategyOracleRow.model_json_schema())>",
    "configuration_hash": "<sha256 of all 6 PipelineSettingsSnapshot settings objects, model_dump(mode=\"json\")>",
    "digest_hash": "<sha256 of the above 5 fields together>"
  },
  "input_digest": {
    "repository_manifest_hash": "<sha256 of manifest.json's raw bytes>",
    "queries_hash": "<sha256 of queries.jsonl's raw bytes>",
    "digest_hash": "<sha256 of the above 2 fields together>"
  }
}
```

Every field is a plain string (hex digest or version string) — no
nested objects beyond this one level. `pipeline_digest.digest_hash` and
`input_digest.digest_hash` are exactly the two values threaded through
every checkpoint entry (§2.3), every long-format row's provenance
columns (§2.1), and every grouped record (§2.2) as
`pipeline_digest`/`input_digest`. This file is overwritten (not
appended) on every run — it always reflects only the *current* run's
digests, never a history of past ones; that history lives implicitly
in the checkpoint and output rows themselves via their own
per-line/per-row digest fields.
