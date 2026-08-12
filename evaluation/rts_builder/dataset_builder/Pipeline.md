# Pipeline.md — RTS Builder Dataset Builder (Milestone 7)

The complete data flow: from a repository manifest and a queries file,
through all six frozen pipeline stages, to the exported RTS dataset.

## 0. Digest computation (Reviewer Minor Revision, runs first)

```mermaid
flowchart TD
    PS["PipelineSettingsSnapshot\n(6 settings objects)"] --> PD
    GC["resolve_git_commit()\n(TARA repo's own HEAD, '-dirty' if uncommitted)"] --> PD
    FS["FeatureVector.model_json_schema()"] --> PD
    OS["StrategyOracleRow.model_json_schema()"] --> PD
    PD["compute_pipeline_digest()\n-> PipelineDigest"]

    MF["RepositoryIterator.manifest_path"] --> ID
    QF["QueryIterator.queries_path"] --> ID
    ID["compute_input_digest()\n-> InputDigest"]

    PD --> DJ["Write digest.json"]
    ID --> DJ
    PD --> CS
    ID --> CS
    CS["CheckpointStore(path, pipeline_digest.digest_hash, input_digest.digest_hash)"]
```

See §3 for what `CheckpointStore` does with these two digests on load.

## 1. End-to-end pipeline

```mermaid
flowchart TD
    M["manifest.json\n(RepositoryIterator)"] --> G
    Q["queries.jsonl\n(QueryIterator)"] --> G
    G["DatasetGenerator.generate()\n(digests computed first -- see §0)"] --> RS

    subgraph RS["Per repository (once)"]
        direction TB
        R1["RepositoryLoader.load_repository()"] --> R2["PythonParserPipeline.parse_repository()"]
    end

    RS --> QS

    subgraph QS["Per pending query (per repository)"]
        direction TB
        Q1["FeatureExtractor.extract()\n-> FeatureVector"] --> Q2["RetrievalExecutor.execute_all()\n-> RetrievalExecutionResult"]
        Q2 --> Q3["OracleUtilityComputer.compute()\n-> OracleUtilityResult (4 rows)"]
    end

    QS --> W1["JsonlRowWriter"]
    QS --> W2["CsvRowWriter"]
    QS --> W3["ParquetRowWriter"]
    QS --> W4["GroupedJsonlWriter"]
    QS --> S["StatisticsAccumulator.update()"]
    W1 & W2 & W3 & W4 --> C["CheckpointStore.mark_complete()"]
    S --> C
    C --> QS

    G -.-> F["DatasetGenerationSummary\n+ dataset_statistics.json"]
```

## 2. Per-repository / per-query split (`PipelineOrchestrator`)

```mermaid
sequenceDiagram
    participant DG as DatasetGenerator
    participant PO as PipelineOrchestrator
    participant RL as RepositoryLoader (frozen)
    participant PP as PythonParserPipeline (frozen)
    participant FE as FeatureExtractor (frozen)
    participant RE as RetrievalExecutor (frozen)
    participant OU as OracleUtilityComputer (frozen)

    DG->>PO: run_repository_stages(repository_spec)
    PO->>RL: load_repository(id, url, sha)
    RL-->>PO: Repository
    PO->>PP: parse_repository(repository)
    PP-->>PO: RepositoryModel
    PO-->>DG: (Repository, RepositoryModel)

    loop for each pending QuerySpec
        DG->>PO: run_query_stages(model, query_spec)
        PO->>FE: extract(model, query_text)
        FE-->>PO: FeatureVector
        PO->>RE: execute_all(model, feature_vector, query_text)
        RE-->>PO: RetrievalExecutionResult
        PO->>OU: compute(execution_result, RelevanceJudgment)
        OU-->>PO: OracleUtilityResult (4 rows)
        PO-->>DG: (FeatureVector, OracleUtilityResult)
    end
```

## 3. Checkpoint validation (on load) and the resume decision flow

```mermaid
flowchart TD
    A0["CheckpointStore.__init__(path, pipeline_digest, input_digest)"] --> A1["Read every existing entry"]
    A1 --> A2{"Any entry's recorded\npipeline_digest/input_digest\n!= this run's?"}
    A2 -- yes --> A3["Log WARNING with the mismatch count.\nWHOLE FILE invalidated: self._completed = {}\n(even entries that DID match are discarded --\nsee README.md's Reproducibility Guarantees\nfor why this must be whole-file, not per-entry)"]
    A2 -- no --> A4["self._completed = every loaded (repo_id, commit_sha, query_text)"]
    A3 --> B
    A4 --> B

    B["For each RepositorySpec in manifest order"] --> C["queries = QueryIterator.queries_for(repository_id)"]
    C --> D["pending = [q for q in queries if NOT CheckpointStore.is_complete(repo_id, commit_sha, q.query_text)]"]
    D --> E{"pending empty?"}
    E -- yes --> F["Skip repository entirely\n(no clone, no parse, no query work)"]
    E -- no --> G["run_repository_stages()\n(clone/parse -- cheap if Parser's own\nrepository_model.json cache already hits)"]
    G --> H["For each query in pending"]
    H --> I["run_query_stages()"]
    I --> J{"raised?"}
    J -- yes --> K["Log, queries_failed += 1,\nnot checkpointed -> retried next run"]
    J -- no --> L["Write pipeline_digest/input_digest-tagged row(s)\nto every enabled writer\n+ StatisticsAccumulator.update()"]
    L --> M{"write/checkpoint raised?"}
    M -- yes --> N["Propagate -- aborts the run\n(infrastructure failure, not a data failure)"]
    M -- no --> O["CheckpointStore.mark_complete()\n-> durable proof this query's output exists on disk,\nrecorded under the current digests"]
```

## 4. Cumulative statistics across sessions

```mermaid
flowchart TD
    Z{"checkpoint_store.stale_entry_count > 0?\n(whole checkpoint was invalidated -- see §3)"}
    Z -- yes --> Y["seed = None\n(every query is being recomputed fresh this run;\nreseeding would double-count -- see README.md)"]
    Z -- no --> A["dataset_statistics.json\n(from a prior session, if any)"]
    A -->|"StatisticsAccumulator.from_existing()"| B["seed: DatasetStatistics | None"]
    Y --> C
    B -->|"StatisticsAccumulator(seed=...)"| C["Running sums/counts/min/max\nreconstructed exactly via sum = mean * count"]
    D["Newly processed queries\nthis session"] -->|".update() per query"| C
    C -->|".build_statistics()"| E["Cumulative DatasetStatistics\n(written back to dataset_statistics.json)"]
```

Reseeding is exact, not approximate, because every mean this module
tracks is losslessly reconstructible from `(mean, count)`:
`sum = mean * count`. `repository_ids` (not just `repository_count`) is
what makes reseeding exact for that one field specifically — without
the actual set, a repository partially processed in one session and
completed in a later one would be double-counted.

The `stale_entry_count` gate (Reviewer Minor Revision) is what keeps
this exact even across a digest-invalidating change: without it, a
recomputed query's contribution would be counted twice -- once already
baked into the stale seed, once fresh. See `README.md`'s Reproducibility
Guarantees and `REVIEW_RESPONSE.md` for the full account of why this
gate exists.

## 5. Export fan-out

Every query's `(FeatureVector, OracleUtilityResult)` pair fans out to
every *enabled* writer independently — none of the four writers depends
on another's success or failure ordering:

```mermaid
flowchart LR
    A["OracleUtilityResult.rows (4)"] --> B["DatasetRow(..., pipeline_digest, input_digest)\n.to_flat_dict() per row"]
    B --> C1["JsonlRowWriter\n(rts_long.jsonl)"]
    B --> C2["CsvRowWriter\n(rts_long.csv)"]
    B --> C3["ParquetRowWriter\n(rts_long.parquet/part-*.parquet)"]
    A2["GroupedDatasetRecord(..., pipeline_digest, input_digest)"] --> C4["GroupedJsonlWriter\n(rts_grouped.jsonl)"]
```

Every row/record carries the digests of the run that produced it
(Reviewer Minor Revision) -- see `README.md`'s Reproducibility
Guarantees for why this matters specifically when a digest change
causes rows to be recomputed and appended alongside a prior run's
now-superseded ones.
