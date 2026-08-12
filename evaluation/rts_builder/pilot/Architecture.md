# Architecture.md — RTS Builder Pilot

The complete data flow: from Dataset Builder's own generation run,
through digest-filtering, splitting, validation, and export, to the
documented pilot dataset.

## 0. Where this subsystem starts (Dataset Builder is frozen and unmodified)

```mermaid
flowchart TD
    M["manifest.json"] --> DG
    Q["queries.jsonl"] --> DG
    DG["DatasetGenerator.generate()\n(frozen -- see dataset_builder/Pipeline.md for its own internals)"] --> GS["DatasetGenerationSummary\n(pipeline_digest, input_digest, statistics)"]
    DG --> GJ["rts_grouped.jsonl\n(one record per query, 4 strategies nested)"]
```

Everything below this line is new at the Pilot subsystem; everything
above is Dataset Builder's own, already-accepted pipeline, invoked
exactly as documented in its own `README.md`/`Pipeline.md`.

## 1. End-to-end pilot pipeline

```mermaid
flowchart TD
    GS["DatasetGenerationSummary"] --> A
    GJ["rts_grouped.jsonl"] --> A
    MD["RepositorySpec.metadata\n(per repository, from RepositoryIterator)"] --> A
    A["assembler.load_current_rows()\nfilter to current pipeline_digest/input_digest,\nflatten, add query_id + metadata"] --> B

    B["QuerySplitter.assign()\nper distinct query"] --> C["rows stamped with split"]
    C --> D["PilotValidator.validate()"]
    D --> E{"report.passed?"}
    E -- "no AND fail_on_validation_error" --> F["raise PilotValidationError\n(no split/figure/doc files written)"]
    E -- "yes, or fail_on_validation_error=False" --> G

    G["exporter: write train/validation/test\n(Parquet + JSONL)"] --> H
    G --> I["exporter.write_feature_statistics_csv()"]
    G --> J["figures.generate_all()\n(6 PNGs)"]
    H["dataset_statistics.json\n(copied from DatasetGenerationSummary.statistics)"] --> K
    I --> K
    J --> K
    K["reporting: validation_report.md,\ndata/README.md, DATASET_CARD.md"] --> L["PilotSummary"]
```

## 2. Row assembly (`assembler.load_current_rows`)

```mermaid
flowchart TD
    A["Read rts_grouped.jsonl line by line"] --> B{"record.pipeline_digest == current AND\nrecord.input_digest == current?"}
    B -- no --> C["Skip (superseded by a later digest-invalidating run --\nsee dataset_builder README's Reproducibility Guarantees)"]
    B -- yes --> D["query_id = compute_query_id(repository_id, commit_sha, query_text)"]
    D --> E["metadata = metadata_by_repository_id[repository_id]"]
    E --> F["for each of the record's 4 StrategyOracleRow:\nDatasetRow(...).to_flat_dict() + query_id + metadata"]
    F --> G["flat rows list"]
```

This is the same digest-filtering Dataset Builder's own `README.md`
documents as the way a downstream consumer recovers the current,
de-duplicated view after a digest-invalidating change non-destructively
appends recomputed rows — the Pilot subsystem is exactly that kind of
downstream consumer.

## 3. Split assignment (`QuerySplitter.assign`)

```mermaid
flowchart TD
    A["(split_seed, repository_id, commit_sha, query_text)"] --> B["SHA-256 digest"]
    B --> C["fraction = int(digest, 16) / 2**256"]
    C --> D{"fraction < train_ratio?"}
    D -- yes --> E["train"]
    D -- no --> F{"fraction < train_ratio + validation_ratio?"}
    F -- yes --> G["validation"]
    F -- no --> H["test"]
```

Pure function of the query's own identity plus the configured seed and
ratios — no shuffling, no in-memory population, no dependency on
processing order or on any other query's presence. All four of a
query's strategy rows call this with identical arguments (strategy is
never a parameter), so they always land in the same split together.

## 4. Validation (`PilotValidator.validate`)

```mermaid
flowchart TD
    R["flat rows"] --> A["group by (repository_id, commit_sha, query_text)"]
    A --> B["no_missing_values:\nany None/NaN in any column?"]
    A --> C["no_duplicate_rows:\nexact-duplicate full row?"]
    A --> D["no_duplicate_query_strategy_pairs:\n(repo, commit, query, strategy) appears > once?"]
    A --> E["every_query_has_expected_strategy_rows:\nlen(group) != expected_strategy_count?"]
    B & C & D & E --> F{"all 4 blocking checks passed?"}
    F --> G["report.passed"]
    A --> H["strategy/repository/rank/split distributions,\naverages overall + by strategy,\nutility/latency/quality histograms,\nfeature_distributions (numeric feature columns only)"]
```

`no_missing_values`/`no_duplicate_rows`/`no_duplicate_query_strategy_pairs`/
`every_query_has_expected_strategy_rows` are the four blocking checks —
see `VALIDATION_GUIDE.md` for how each maps to the pilot's stated
Success Criteria. Everything under `H` is descriptive/informational:
always computed, never blocking.

## 5. Export fan-out

```mermaid
flowchart LR
    R["rows (stamped with split)"] --> S["partition by split"]
    S --> T1["train rows"] --> P1["train.parquet"]
    T1 --> J1["train.jsonl"]
    S --> T2["validation rows"] --> P2["validation.parquet"]
    T2 --> J2["validation.jsonl"]
    S --> T3["test rows"] --> P3["test.parquet"]
    T3 --> J3["test.jsonl"]
```

A single Parquet `pa.Schema` is derived once from the *full* (pre-split)
row set and reused for every split's `write_split_parquet` call — this
is what lets an empty split (possible on a tiny/unbalanced input
population) still produce a validly-typed, zero-row Parquet file
instead of failing on missing columns.

## Design boundary: what this subsystem does not touch

Every box above `A` (§2) is Dataset Builder's own, accepted-and-frozen
machinery, invoked exactly as documented in
`evaluation/rts_builder/dataset_builder/Pipeline.md`. No frozen model
(`DatasetRow`, `GroupedDatasetRecord`, `StrategyOracleRow`,
`FeatureVector`, `PipelineDigest`, `InputDigest`, ...) gains a new
field here — `query_id`/`metadata`/`split` exist only as keys on the
plain `dict` rows this subsystem builds and writes, never as attributes
on any frozen Pydantic model.
