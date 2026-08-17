# TIQS Schema Specification

**Status.** This document formalizes `DATASET_PLAN.md`'s already-accepted
TIQS design into a concrete, machine-validatable schema. It resolves
every field-level "exact format TBD" that document leaves open (storage
format, manifest schema, query record schema); it does **not** change
any of `DATASET_PLAN.md`'s methodological decisions (repository
selection, repository-level splitting, annotation protocol, agreement
thresholds). Where this document and `DATASET_PLAN.md` overlap,
`DATASET_PLAN.md` is authoritative on *methodology*; this document is
authoritative on *file format*.

**No TIQS annotation has been performed under this schema.** Every model
in `evaluation/tiqs/models.py` is implemented and tested against
synthetic fixtures only (`evaluation/tiqs/schema_example/`, `evaluation/tiqs/tests/`).
This milestone builds the schema and its validator; it does not collect
data, and does not implement annotation tooling (a form, a CLI, a UI) --
see "Explicitly out of scope" below.

## 1. File layout

Three files, per `DATASET_PLAN.md` §14's diffability requirement (plain
JSON/JSONL, not a binary or proprietary format):

| File | Shape | Model |
|---|---|---|
| `repository_manifest.json` | One JSON object: `{schema_version, entries: [...]}` | `RepositoryManifest` |
| `queries.jsonl` | One JSON object per line | `TIQSQueryRecord` |
| `reproducibility.json` | One JSON object | `ReproducibilityMetadata` |

**Design decision: split lives only on the repository, not the query.**
`TIQSQueryRecord` has no `split` field. Per `DATASET_PLAN.md` §9, a
query inherits its repository's split; a query-level `split` field would
be a second, independently-editable source of truth that could drift
from the manifest and reopen the exact leakage channel §9 exists to
close. `evaluation.tiqs.models.resolve_split(query, manifest)` is the
single place a query's split is ever computed, by joining
`repository_id` against the manifest.

## 2. Repository manifest (`repository_manifest.json`)

`RepositoryManifestEntry` fields, each citing the exact `DATASET_PLAN.md`
section it encodes:

| Field | Type | Source |
|---|---|---|
| `repository_id` | `str` | Stable identifier, unique across the manifest |
| `source_url`, `commit_sha` | `str` | §8 sealing protocol -- `commit_sha` is a validated 40-char lowercase hex SHA |
| `license` | closed enum (`MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`) | §2's exact eligibility list |
| `language` | `tara.core.types.Language` (reused, not redefined) | §3 -- `UNKNOWN` rejected: eligibility requires a determinate language |
| `size_bucket`, `lines_of_code` | enum + `int` | §4 -- a model validator enforces the bucket matches the LOC thresholds |
| `domain` | free `str` | §5 -- deliberately open, since §5 states its taxonomy "is not a claim of completeness" |
| `split` | `train` / `validation` / `test` | §6-§8 |
| `added_at`, `changelog_note` | `datetime`, optional `str` | §14 re-pin/changelog requirement |

## 3. Query record (`queries.jsonl`, one `TIQSQueryRecord` per line)

Self-contained: every field a consumer needs for one query lives on
this one record (no join needed except the manifest, for split
resolution).

| Field | Purpose | `DATASET_PLAN.md` reference |
|---|---|---|
| `query_id`, `repository_id`, `query_text` | Identity and content | §9 |
| `prompt_framing` | Which of the 3 rotated authoring framings produced this query | §10 step 1 |
| `authored_by` | `AnnotatorMetadata`, role=`author` | §10 step 1 |
| `task_type_labels` | List of 1-2 independent `TaskTypeLabel`s (the independent labeler's + the author's blind self-relabel) | §10 steps 2-3 |
| `adjudicated_task_type` + a `field=task_type` entry in `adjudication_records` | The resolved label, only present if the two labels disagreed | §10 step 4 |
| `relevant_context_sets` | 1-2 independent `RelevantContextSet`s (original annotator + 20%-sample spot-checker) | §11-§12 |
| `adjudicated_relevant_context` + a `field=relevant_context` `adjudication_records` entry | The resolved set, only present if the spot-check disagreed materially | §10 step 4, §12 |
| `reference_output` | Optional acceptance-criteria rubric or single canonical-code string | §11 |
| `notes` | Free-text grounding rationale | -- |

`RelevantContextEntry.node_id` reuses `tara.context.models.build_file_node_id`
/ `build_symbol_node_id` exactly, per §11 -- no second, TIQS-specific
identity scheme exists. `relevance_tier` is `Optional[PRIMARY | SECONDARY]`,
left unset by default, honoring §11's own "TBD" framing for graded
relevance rather than forcing a premature choice.

**Schema-enforced invariants** (Pydantic validators, not just
documentation): a `TaskTypeLabel.task_type` can never be `UNKNOWN`
(an annotator has full context and must commit to a substantive
category); `adjudicated_task_type` / `adjudicated_relevant_context` can
never be set without a matching `AdjudicationRecord`; `ReferenceOutput`
of kind `canonical_code` must have exactly one `content` entry.

## 4. Reproducibility (`reproducibility.json`)

`ReproducibilityMetadata`: `dataset_version` (e.g. `v0.1-pilot`, `v1.0`),
`guideline_version`, `tara_git_commit`, `created_at`, and an append-only
`changelog` of `ChangelogEntry` objects -- directly implementing §14's
immutable-versioning rule (a correction ships as a new version with a
changelog entry, never a silent edit).

## 5. Mapping to RQ1-RQ5

| RQ | What TIQS supplies | Which field(s) |
|---|---|---|
| **RQ1** (Classification feasibility) | Held-out, human-annotated `TaskType` ground truth to compute macro-F1 and confidence-correlation against the rule-based classifier's output. | `task_type_labels` / `adjudicated_task_type`, joined against the repository's `split` |
| **RQ2** (Retrieval quality) | Ground-truth relevant-context sets to compute Precision@k/Recall@k/MRR for each routing strategy. | `relevant_context_sets` / `adjudicated_relevant_context` (`node_id`s comparable directly against retriever output, same id scheme) |
| **RQ3** (Generation quality) | Reference outputs (rubric or canonical code) to score generated code against, for the subset of queries where a reference is feasible. | `reference_output` |
| **RQ4** (Efficiency) | Indirectly: TIQS defines the query population efficiency is measured over (which queries route to which strategy, at what cost) -- no new field of its own beyond `query_text` and the repository/split it's evaluated against. | `repository_id` -> `RepositoryManifestEntry.split` |
| **RQ5** (Explainability, exploratory) | Not directly supported by this schema. RQ5 evaluates whether a router's `reason` string is judged sensible -- that is a property of the *routing system's output*, not of a TIQS query record. `prompt_framing`/`notes` provide query-authoring context a future explainability-rating protocol could reuse, but no dedicated field is added here since `PROJECT_SPEC.md` §21 marks RQ5's evaluation protocol itself as "requires future validation." |

RQ6 (confidence calibration) reuses RQ1's `task_type_labels` ground
truth the same way RQ1 does; not listed separately since it needs no
additional TIQS field.

## 6. Relationship to `evaluation/rts_builder/`

`evaluation/rts_builder/pilot/` already contains a large amount of
adjacent, independently-built infrastructure -- a repository corpus (8
repositories: fastapi, flask, requests, click, celery, sqlalchemy,
pandas, scikit-learn), 160 AI-authored queries, and 439 draft relevance
judgments. **This is not TIQS and does not satisfy `DATASET_PLAN.md`'s
protocol**, for reasons disclosed in its own `merged_dataset/dataset_card.md`:

- Its category taxonomy (`bug_fix`, `feature_implementation`,
  `refactoring`, `testing`, `documentation`, `api_usage`, `code_search`)
  does not match `TaskType`'s 13 members (no `EXPLAIN`, `ARCHITECTURE`,
  `SECURITY`, etc.; `api_usage`/`code_search` have no `TaskType` analog).
- Every one of its 439 relevance grades is the placeholder
  `"TO_BE_ASSIGNED"` -- "No relevance grade in this dataset has been
  assigned by a human," per its own dataset card.
- It used a flat 70/15/15 query-level split, not `DATASET_PLAN.md`
  §6-§9's repository-level 40/25/35 split this schema requires.
- Queries were authored by "the same AI assistant across separate
  sessions... no second reviewer or second independent AI pass" -- not
  the independent double-annotation `DATASET_PLAN.md` §10 requires.

The two projects share nothing at the schema level and are not
compatible without a lossy remapping (different taxonomy, no genuine
relevance grades, wrong split granularity). `evaluation/rts_builder/`'s
*repository corpus* (the 8 cloned repositories already present in this
project's working tree) is plausibly reusable as a starting point for
TIQS's own corpus selection (§2-§5), but that reuse decision, and any
actual annotation, is future work -- not performed here.

## 7. Explicitly out of scope for this milestone

- **Annotation tooling** (a form, CLI, or UI for annotators to actually
  produce `TIQSQueryRecord`s) -- per this milestone's own instruction to
  explain the schema first.
- **Any real annotated query.** `evaluation/tiqs/schema_example/` is
  synthetic fixture data only, clearly marked as such.
- **Inter-annotator agreement computation** (Cohen's κ for `TaskType`,
  Jaccard for relevant-context spot-checks, §13). The validator checks
  *structural* independence (distinct `annotator_id`s, correct roles,
  unresolved disagreements flagged) but does not compute the agreement
  statistics themselves -- that requires a real double-labeled corpus to
  run against, which does not yet exist.
- **Repository corpus selection** against §2-§5's actual criteria (license,
  maintenance, per-language/per-domain quotas). The schema can *represent*
  a selected corpus; it does not select one.
