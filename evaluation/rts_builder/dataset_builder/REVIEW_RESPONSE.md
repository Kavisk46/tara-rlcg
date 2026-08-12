# Anticipated Review: Dataset Builder Subsystem (RTS Builder, Milestone 7)

Following the discipline established for every prior RTS Builder
milestone, this document self-applies review scrutiny before an
external one happens. This is the final assembly milestone — several
items below concern how it composes the five frozen subsystems, not
just its own new code.

Items 1-6 cover the original milestone build. Items 7-11 were added for
the subsequent Reviewer Minor Revision (`pipeline_digest`/`input_digest`
reproducibility guarantees — Revisions 1-4). Nothing in Items 1-6 was
invalidated by the revision; it added new fields and a new invalidation
gate to existing structures rather than redesigning them, per the
revision's own explicit constraint ("Do NOT redesign the pipeline").

---

## Item 1: Query authoring and relevance annotation are external inputs — isn't that a gap in "generate the dataset"?

**Anticipated comment.** *"The objective says 'Generate the Retrieval
Training Set.' But queries and their ground-truth relevance grades are
just read from a file this subsystem doesn't produce. Doesn't that mean
the actual hard part — deciding what to ask and what's relevant — is
missing?"*

**Response.** By design, and consistent with this project's own
established resolution, restated at this milestone rather than
reinvented: query authoring and relevance annotation are human/LLM
-driven activities (`docs/DATASET_PLAN.md` §10,
`docs/PILOT_EXECUTION_PLAN.md` §4), explicitly out of scope for every
automated RTS Builder stage, including this one — "Do NOT implement:
Task classifier" rules out any automated query-generation or relevance
-labeling heuristic, which is the only way this subsystem could
plausibly produce them itself. "Generate the RTS dataset" here means:
given curated queries and judgments, deterministically produce every
downstream artifact (features, retrieval results, oracle labels, in
three export formats, with statistics) — the orchestration and
data-engineering half of dataset construction, not the annotation half.
`Oracle Utility`'s own `REVIEW_RESPONSE.md` Item 1 made the identical
argument one milestone earlier for the same underlying reason; this
milestone's `QuerySpec`/`RelevanceJudgment` reading is that same
resolution's natural input format, not a new one.

---

## Item 2: Sequential processing only — no parallelism across repositories

**Anticipated comment.** *"Each repository is processed one at a time,
in manifest order. Repository processing is embarrassingly parallel
(nothing about one repository's pipeline run depends on another's) and
checkpoint-safe in principle. Why not parallelize?"*

**Response.** Deliberately out of scope, not overlooked. Sequential
processing was chosen specifically because it makes "Deterministic
execution" trivial to guarantee: every downstream stage (Repository
Loader through Oracle Utility) is already independently deterministic,
so sequential orchestration inherits that property for free, while
concurrent orchestration would need to prove that interleaved
`CheckpointStore`/writer access under concurrency introduces no races —
a nontrivial correctness burden this milestone's explicit
requirements (Python 3.12, deterministic, streaming, checkpointed) do
not ask it to take on. `CheckpointStore` and the streaming writers are
not currently thread/process-safe (single-writer assumption, no file
locking) — parallelizing without addressing that first would be an
actual correctness regression, not a performance-only change. Listed as
a Future Extension Point in `README.md`'s spirit (not restated as its
own entry there, since it is a one-line, self-evident omission once
stated here): a process-per-repository design, each with its own
checkpoint shard merged afterward, is the natural extension.

---

## Item 3: Is the Parquet "directory of part files" design really "streaming," or a workaround?

**Anticipated comment.** *"JSONL/CSV genuinely append a byte at a time
as data arrives. Parquet writes a brand-new file per run and only
finalizes it at `close()`. Is calling this 'streaming' accurate, or is
it just avoiding the problem?"*

**Response.** Both true, stated as such rather than glossed over.
Within a single `DatasetGenerator` run, `ParquetRowWriter` **is**
streaming in the sense that matters operationally: rows are buffered in
`parquet_batch_size`-sized batches (default 256) and flushed as
row-groups incrementally, so memory stays O(batch size) regardless of
how many queries that run processes — never O(dataset size). What it
cannot do is append new row-groups to an already-`close()`d file from a
*separate* process invocation, because Parquet's footer (schema,
row-group index) is written once, at close, by design of the format
itself — not a limitation specific to `pyarrow` or to this
implementation. The directory-of-part-files pattern is the standard,
correct answer to that constraint (the same one Spark/Dask use for
incrementally-built Parquet datasets), not an avoidance of it: resuming
never needs to touch, reopen, or validate a prior run's part file, and
a downstream reader loads the whole directory as one logical table via
ordinary `pyarrow.parquet.read_table(directory)`/`pandas.read_parquet(directory)`,
with no special handling required on the consumer side.

---

## Item 4: Cumulative statistics reseeding — what if `dataset_statistics.json` is deleted, moved, or hand-edited between sessions?

**Anticipated comment.** *"Cumulative statistics depend on
successfully reading back a JSON file from a prior run. What happens if
it's missing, or corrupted, or someone edits it?"*

**Response.** Two different cases, two different behaviors, both
deliberate:

- **Missing** (`from_existing` returns `None`): treated as "no prior
  data," and the accumulator starts fresh — correct for a genuinely
  first run, and also the correct (if statistically incomplete)
  behavior if a prior `dataset_statistics.json` was intentionally
  removed. This is symmetric with `CheckpointStore`'s own missing-file
  handling.
- **Present but corrupt/unreadable**: `StatisticsAccumulator.from_existing`
  does **not** silently treat this as "no prior data" — `DatasetStatistics.model_validate_json`
  raises, and that exception propagates. This is a deliberate asymmetry
  from `CheckpointStore`'s handling of a malformed *trailing* checkpoint
  line (silently skipped, since a truncated last line is expected,
  benign evidence of an interrupted write): a whole corrupted
  statistics file is not that kind of narrow, expected artifact, and
  silently discarding real prior cumulative statistics would make a
  resumed run's numbers quietly *wrong* (understated) rather than
  cleanly absent. A loud failure here is the safer default; the caller
  can always delete the file explicitly to force a fresh start,
  understanding that as an explicit choice rather than an implicit one
  this subsystem made for them.

A hand-edited (but validly-shaped) `dataset_statistics.json` is
trusted at face value, same as any other input file this subsystem
reads — no provenance/tamper-detection is implemented or claimed.

---

## Item 5: A crash mid-write can leave a duplicate-plus-truncated row — why not a write-ahead log?

**Anticipated comment.** *"README.md admits a crash during a row write
could leave a truncated artifact, and the resumed run's re-processing
of that same query would then also append a fresh, correct copy —
producing a duplicate. For a 'publication-quality' dataset, isn't a
transactional write mechanism warranted?"*

**Response.** Considered and deliberately not built, given the actual
risk/cost tradeoff. The window in which a crash could land mid-write is
a single `write()` + `flush()` system call per row per writer — small
and fast relative to the query-computation work (Feature Extraction
through Oracle Utility) that precedes it, making the exposure narrow in
practice. A write-ahead log or two-phase-commit-style mechanism across
four independent writers (JSONL, CSV, Parquet, grouped-JSONL) plus the
checkpoint store would meaningfully increase this subsystem's
complexity for a failure mode that (a) is rare, (b) leaves detectable,
not silent, evidence (a truncated final line/row, trivially filterable
by a downstream loader or by de-duplicating on the row's own
`(repository_id, commit_sha, query_text, strategy_name)` key, which is
already a natural unique key for every long-format row), and (c) is
explicitly documented rather than hidden. This mirrors the same
proportionality judgment made for the append-based `CheckpointStore` in
this same milestone and the Retrieval Executor's own accepted latency
-write design one milestone earlier.

---

## Item 6: `repositories_failed`/`queries_failed` in the summary are per-run, but `statistics` is cumulative — is that inconsistent?

**Anticipated comment.** *"`DatasetGenerationSummary.statistics` is
cumulative across every session, but `repositories_processed`/`_failed`
and `queries_processed`/`_failed` only describe the current
invocation. Why the asymmetry?"*

**Response.** Because they answer different questions, not because of
an oversight. `statistics` describes *the dataset* — a property of
everything durably written to the output directory so far, which is
inherently a cumulative, standing fact, not something tied to any one
process invocation. `repositories_processed`/`_failed` and
`queries_processed`/`_failed` describe *this run* — "what did invoking
`generate()` just now actually do," which is inherently per-invocation
(a caller asking "did my last command make progress, or fail
immediately" needs the answer for *that command*, not a running total
that would obscure whether this specific run did anything at all). Both
are documented explicitly in `DatasetSchema.md` §2.5 with this
distinction stated, not left for a reader to infer from the field
names alone.

---

## Item 7: Checkpoint invalidation started as per-entry, and that was a real bug, not a style choice — why whole-file?

**Anticipated comment.** *"A digest mismatch on one line naturally
suggests invalidating that one line, recomputing just that query. Why
does one changed input invalidate the entire checkpoint, discarding
even entries whose own recorded digests still match?"*

**Response.** Because per-entry invalidation was tried first, during
this revision's own implementation, and found to silently corrupt
cumulative statistics — not a hypothetical, a bug actually reproduced
and fixed before this revision was considered done. `input_digest` is a
whole-file hash of `queries.jsonl`; appending a second query changes
the hash for *every* query in that file, including ones whose
individual content didn't change. Under a first implementation that
keyed `CheckpointStore` on `(repository_id, commit_sha, query_text,
pipeline_digest, input_digest)`, the pre-existing query's checkpoint
entry (recorded under the *old* `input_digest`) was correctly seen as
stale and recomputed — but `StatisticsAccumulator` was still
unconditionally reseeding from the prior session's
`dataset_statistics.json`, which already counted that same query once.
The recomputation added its row on top of the stale seed: a smoke test
of "add one query between two sessions" produced `query_count=3`,
`row_count=12` for what was actually 2 distinct queries — real double
-counting, not a cosmetic issue. The fix, reflected in the shipped code:
`pipeline_digest`/`input_digest` each describe the entire run's
configuration/inputs, not any single query's, so a mismatch in either
must invalidate the checkpoint's trustworthiness as a whole — if
`CheckpointStore._load_existing` finds *any* stale entry, it discards
the entire loaded set (`stale_entry_count` still reports how many were
actually stale, for the summary and for `DatasetGenerator` to gate
statistics reseeding on — see Item 8). This also matches the literal,
singular wording of the revision itself: "the checkpoint becomes
invalid," "invalidate checkpoint," never "invalidate checkpoint
entries."

---

## Item 8: Adding a single query recomputes the *entire* checkpoint, not just the new query — isn't that wasteful?

**Anticipated comment.** *"In the common workflow of incrementally
growing a queries file, whole-file invalidation means every previously
-completed query gets reprocessed too, even though nothing about that
query's own inputs changed. That seems like a significant efficiency
regression versus a narrower, per-query digest."*

**Response.** A real, deliberate tradeoff, chosen for correctness and
literal fidelity to the revision's spec over throughput, and stated
plainly here rather than left implicit. A narrower scheme — hashing
each query's own line, or diffing the queries file — would avoid the
recomputation, but it is not what was asked for: Revision 2 specifies
one `input_digest` covering the input files as a whole, and Revision 4
says a differing `input_digest` invalidates *the checkpoint*, not
"invalidates the affected entries." Inventing a finer-grained,
per-record digest to preserve incremental efficiency would be exactly
the kind of pipeline redesign the revision's preamble explicitly
forbids ("Do NOT redesign the pipeline"), in exchange for solving a
workflow (incremental query-set growth) the revision never actually
requested. The cost is real but bounded and legible: recomputation
means re-running Feature Extraction through Oracle Utility for
previously-completed queries — not re-cloning or re-parsing
repositories, since `PipelineOrchestrator.run_repository_stages` is
still gated on Parser's own frozen `repository_model.json` cache,
independent of this checkpoint. `README.md`'s Reproducibility
Guarantees documents this tradeoff explicitly so a caller planning a
large, incrementally-grown query set can factor it in, rather than
discovering it as a surprise.

---

## Item 9: `PipelineSettingsSnapshot` has to be passed in and kept in sync by the caller — what stops it silently going stale?

**Anticipated comment.** *"`compute_pipeline_digest` hashes whatever
`PipelineSettingsSnapshot` it's given, defaulting to
`PipelineSettingsSnapshot()` (every subsystem's default settings) if
the caller passes none. If a caller constructs a `DatasetGenerator`
with actual non-default settings for, say, `RetrievalExecutor`, but
forgets to also thread those same settings into the
`PipelineSettingsSnapshot`, the digest would silently describe a run
that isn't the one actually happening. Isn't that a correctness trap?"*

**Response.** Yes, and not fully closeable without a scope of change
this revision doesn't authorize — stated here rather than hidden.
`DatasetGenerator` does not currently accept, store, or forward
individual per-subsystem settings objects to Repository Loader/Parser/
Feature Extraction/Retrieval Executor/Oracle Utility as constructor
arguments in a way that could be introspected and auto-assembled into a
`PipelineSettingsSnapshot`; the frozen milestones' own orchestration
wiring (each subsystem constructed independently, mostly with its own
defaults, at whatever call site builds the pipeline) predates this
revision and is explicitly off-limits to touch ("Do NOT modify any
other subsystem"). Auto-deriving the snapshot from live state would
require exactly that kind of cross-subsystem wiring change. Given that
constraint, `pipeline_settings` is an explicit, documented parameter:
the caller's responsibility to keep in sync with whatever settings
objects were actually used to construct the pipeline's other stages,
stated as a caller contract in `README.md`'s Configuration section
rather than silently assumed. This is consistent with the general
principle applied throughout this project — an explicit, documented gap
is preferable to a heuristic that appears to close it but cannot be
guaranteed correct.

---

## Item 10: Why are `feature_schema_version`/`oracle_schema_version` content hashes instead of manually-maintained version strings like `"v2"`?

**Anticipated comment.** *"Most schema-versioning schemes use a small
human-assigned integer or semver string, bumped by a developer when the
schema changes. Why hash `model_json_schema()` instead?"*

**Response.** Because a manually-maintained version string is a
promise a developer has to remember to keep, and this project has
already seen that class of mistake elsewhere (documented in this same
revision's own build history: an unrelated local-import anti-pattern
introduced and self-caught twice). A content hash of
`FeatureVector.model_json_schema()`/`StrategyOracleRow.model_json_schema()`
cannot go stale — if a field is added, renamed, retyped, or removed in
either frozen model, the hash changes automatically, with no separate
bump step to forget. The cost is that the version string itself is
opaque (a hex prefix, not a human-readable "v3"), which is an
acceptable tradeoff for a value whose only consumers are (a) another
run's own digest comparison, machine-only, and (b) a human debugging a
checkpoint-invalidation event, who needs "did the schema change,
yes/no" (answered by hash equality) far more than "which numbered
version was this" (which the hash doesn't answer, but a manual string
could). `PIPELINE_VERSION` in `digest.py` remains a manually-maintained
string deliberately, by contrast, since it is meant to convey a
human-assigned release identity for the *pipeline as a whole*, not
derived from any single model's shape — the two versioning strategies
coexist because they answer different questions.

---

## Item 11: The revision names three input files (`repository_manifest.json`, `queries.json`, `relevance_judgments.json`), but `input_digest` only hashes two — is that a gap?

**Anticipated comment.** *"Revision 2 lists `repository_manifest.json`,
`queries.json`, and `relevance_judgments.json` as the three files
`input_digest` must cover. The shipped `InputDigest` model only has
`repository_manifest_hash` and `queries_hash`. Where's the third?"*

**Response.** Not a gap — the revision's own wording anticipated this
exact situation with "(or equivalent files)," and this pipeline's
already-established, frozen input schema (`DatasetSchema.md` §1.2, set
at the original Milestone 7 build, unchanged by this revision) is the
equivalent: `queries.jsonl`'s `QuerySpec.relevance_grades` field already
carries each query's ground-truth relevance judgments inline, one
object per query line, rather than as a separate
`relevance_judgments.json` file keyed some other way. There is no
second file to hash because relevance judgments were never split out as
one in this pipeline's design — introducing a redundant, separately
-tracked `relevance_judgments.json` purely to give `input_digest` a
third field to hash would itself be a pipeline redesign ("Do NOT
redesign the pipeline"), changing an established input format to match
a generic three-file description rather than adapting that generic
description to the pipeline that actually exists. `queries_hash`
already covers relevance-judgment changes as a consequence: editing any
query's `relevance_grades` changes `queries.jsonl`'s bytes, which
changes `queries_hash`, which changes `input_digest.digest_hash` —
the invalidation guarantee Revision 2 asks for is preserved under the
2-file reality, just not under the literal 3-file file list.

---

## Summary

| # | Concern | Status |
|---|---|---|
| 1 | Query/relevance authoring is external, not generated | By design; consistent with Oracle Utility's own established resolution |
| 2 | No parallel/multi-process repository processing | Deliberate scope boundary; would require checkpoint/writer concurrency-safety not currently guaranteed |
| 3 | Parquet's "streaming" is directory-of-part-files, not true single-file append | Accurate within-run streaming; the standard, correct pattern for Parquet's finalized-footer constraint across runs |
| 4 | Cumulative statistics depend on reading back a prior JSON file | Missing file = fresh start (safe); corrupt file = loud failure (safe); silent data loss avoided in both directions |
| 5 | Crash-mid-write can leave a duplicate/truncated artifact | Accepted, documented, narrow-window risk; not solved via a heavier transactional mechanism, consistent with proportionality judgments made elsewhere in this project |
| 6 | Run-level counts vs. cumulative statistics in the same summary object | Deliberate: different questions ("this run" vs. "the dataset"), both needed, both documented |
| 7 (Minor Revision) | Checkpoint invalidation is whole-file, not per-entry | Corrected from an initial per-entry design after it was caught double-counting statistics during this revision's own testing; whole-file is both the fix and the literal reading of the spec |
| 8 (Minor Revision) | Whole-file invalidation recomputes previously-completed queries too | Deliberate, documented tradeoff — correctness and spec fidelity over incremental-growth efficiency |
| 9 (Minor Revision) | `PipelineSettingsSnapshot` must be kept in sync by the caller | Explicit, documented caller contract; cannot be safely auto-derived without touching frozen subsystem wiring |
| 10 (Minor Revision) | Schema versions are content hashes, not manual version strings | Cannot go stale, unlike a manually-bumped version; deliberate tradeoff of readability for correctness |
| 11 (Minor Revision) | `input_digest` hashes 2 files, spec lists 3 | Spec's own "(or equivalent files)" clause; relevance judgments are already inline in `queries.jsonl` in this pipeline's established schema, not a separate file |

No code outside `evaluation/rts_builder/dataset_builder/` (and its
tests) was modified by either the original milestone build or this
revision. Repository Loader, Parser, Feature Extraction, Retrieval
Executor, and Oracle Utility were not touched.
`tests/rts_builder/dataset_builder/` has 66 tests (49 from the original
build, 17 added by this revision), all passing alongside the full
existing project suite.
