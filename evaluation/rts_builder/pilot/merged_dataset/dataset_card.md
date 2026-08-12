# Dataset Card — TARA RTS Pilot Dataset v1.0

## Purpose

This dataset supports the TARA (Task-Aware Repository-Adaptive
Retrieval) research project's investigation of retrieval-augmented
software engineering assistance: given a natural-language developer
task description (a GitHub-issue-style query) grounded in a real,
pinned-commit open-source repository, which source files should a
retrieval system surface as relevant context? It is a **pilot-scale
Retrieval Training Set (RTS)**, combining 160 repository-grounded
developer queries across 8 widely-used Python open-source projects
with AI-drafted candidate-file relevance judgments awaiting human
adjudication. It is intended to seed the annotation and evaluation
pipeline for a downstream retrieval-training/evaluation dataset, not
to be used as a finished, human-validated ground truth in its current
form.

## Collection methodology

Each of the 8 repositories went through an identical 11-phase
annotation workflow (documented in each repository's own
`annotation_runs/<repo>/README.md`), executed independently in 8
separate sessions over the course of this project:

1. **Repository inspection** — architecture, package layout, and
   commit-specific findings (including a changelog/whatsnew review to
   identify already-fixed bugs and already-implemented features, so
   Bug Fix/Feature queries would not describe already-resolved
   behavior) documented in `repository_summary.md`.
2. **Query generation** — exactly 20 developer-intent queries per
   repository, GitHub-issue style, distributed 4 Bug Fix / 4 Feature /
   3 Refactoring / 3 Testing / 2 Documentation / 2 API Usage / 2 Code
   Search, with no filenames or implementation hints, grounded in
   actual confirmed repository content (never invented).
3. **Repository search** — for every query, the repository was
   searched for existing candidate files only; nothing was guessed.
4. **Annotation drafting** — candidate files organized into primary/
   secondary/regression-test/documentation-example buckets, each with
   a confidence level, reasoning, related symbols, and explicit
   uncertainty notes.
5. **Draft relevance judgment scaffolding** — a flat, one-row
   -per-`(query, file)` file with every grade set to the placeholder
   `"TO_BE_ASSIGNED"` (no AI-assigned final relevance grade exists
   anywhere in this dataset).
6-11. Human-annotation checklist generation, self-executed
   programmatic validation, per-repository statistics, machine
   -readable metrics, research notes, and a self-audit ("Publication
   Audit") re-verifying every claim against the pinned commit before
   that repository's run was marked complete.

This merged v1.0 dataset (the present artifact) is the product of a
**separate, ninth session**: a pure assembly task that consumed the 8
completed repositories' output artifacts, merged them into unified
`queries_master.jsonl`/`draft_relevance_master.jsonl` files, validated
the merge, computed dataset-wide statistics, produced a deterministic
train/validation/test split, and audited the result — without
re-inspecting any repository's source code except to re-verify pinned
-commit SHAs and to re-confirm file existence for every merged
relevance judgment.

## Repositories

| Repository | Domain | Pinned commit | Queries |
|---|---|---|---|
| [fastapi](https://github.com/tiangolo/fastapi) | Web API framework | `a375f6b948b99fa4260129856bbf11d037f363ef` | 20 |
| [flask](https://github.com/pallets/flask) | Web framework | `6a2f545bfd8ed31e19066a299296917e034aca58` | 20 |
| [requests](https://github.com/psf/requests) | HTTP client library | `1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e` | 20 |
| [click](https://github.com/pallets/click) | CLI framework | `00e592cea702e0b2caa0dee42489fdb1c22cd845` | 20 |
| [celery](https://github.com/celery/celery) | Distributed task queue | `f109abf852525b69a1b6eee0457c6cd5561e0529` | 20 |
| [sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) | SQL toolkit / ORM | `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` | 20 |
| [pandas](https://github.com/pandas-dev/pandas) | Data analysis library | `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` | 20 |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | Machine learning library | `9b9be3abddd88675c5dc2e3623e652cb7545a26c` | 20 |

Chosen to span a range of domains (web frameworks, an HTTP client, a
CLI toolkit, a task queue, an ORM, and two large scientific-Python
libraries) and repository scales (fastapi/flask/requests/click's
single-digit-thousands-of-lines core modules through pandas's
19,651-line `frame.py`, the largest single file across all 8
repositories).

## Schema

### `queries_master.jsonl` (160 rows)

```json
{"query_id": "", "repository_id": "", "category": "", "difficulty": "", "query_text": "", "notes": ""}
```

- `query_id`: globally unique, `<repository_id>-<NNN>` (e.g. `pandas-014`).
- `repository_id`: one of the 8 values in the table above.
- `category`: one of `bug_fix`, `feature_implementation`, `refactoring`, `testing`, `documentation`, `api_usage`, `code_search`.
- `difficulty`: one of `easy`, `medium`, `hard` (self-assessed per query during annotation, no fixed distribution required).
- `query_text`: the GitHub-issue-style developer query itself.
- `notes`: the query author's grounding rationale — what confirmed repository evidence the query is based on, and (where relevant) which already-resolved changelog entries were checked to avoid describing fixed behavior as open.

**Note on schema normalization**: this canonical schema was produced
by normalizing two different field-naming conventions used across the
8 source repositories' `queries.jsonl` files (`query`+`repository_id`
vs. `query_text` with no `repository_id`) — see
`schema_validation_report.md` §2 for the full disclosure.

### `draft_relevance_master.jsonl` (439 rows)

```json
{"query_id": "", "repository": "", "file": "", "grade": "TO_BE_ASSIGNED", "reason": ""}
```

One row per candidate file suggested for a query. `grade` is
**always** `"TO_BE_ASSIGNED"` in this v1.0 release — no human or AI
final relevance judgment has been made. `file` is a repository-relative
path, independently verified to exist in the corresponding pinned
-commit clone.

**Note on schema normalization**: fastapi's source
`draft_relevance_judgments.jsonl` used a structurally different,
nested (one-row-per-query) schema; it was deterministically flattened
to match the other 7 repositories' flat schema, recovering the
per-file `reason` field from fastapi's `annotation_drafts.jsonl` — see
`schema_validation_report.md` §3 and `relevance_merge_report.md` for
the full disclosure of this transformation.

### `train.jsonl` / `validation.jsonl` / `test.jsonl` (112 / 24 / 24 rows)

```json
{"query_id": "", "repository_id": "", "category": "", "difficulty": "", "query_text": "", "notes": "", "candidates": [{"file": "", "grade": "TO_BE_ASSIGNED", "reason": ""}]}
```

Each row is a **self-contained query record**: the full query metadata
plus its nested list of candidate-file judgments (sorted by file
path), so a consumer can use any one split file without needing to
join against `queries_master.jsonl`/`draft_relevance_master.jsonl`
separately. This nested-per-query shape was a deliberate design choice
for this assembly (the mission did not specify an exact split-file
schema) — see `reproducibility.md` for the split methodology and
random seed.

## Annotation protocol

Every candidate file in `annotation_drafts.jsonl` (per repository,
upstream of this merge) was located by direct repository search
(`Grep`/`Read`/directory listing against the pinned commit) — never
guessed, never invented, never answered from general knowledge of the
library. Directory-shaped candidates (a search that resolves to a
directory rather than a specific file) were explicitly excluded from
`draft_relevance_judgments.jsonl` and flagged for human resolution
rather than arbitrarily narrowed. Queries whose grounding rested on an
absence claim (e.g. "this feature doesn't exist yet") that could not
be conclusively verified were marked with a `"STRONG FLAG"` in later
runs' `ambiguity_notes` and, wherever feasible, resolved with a
follow-up search before the run was finalized — this practice was
introduced partway through the project (see Known Limitations below).
Full protocol details are in each repository's own
`annotation_runs/<repo>/human_annotation_checklist.md` and the
project's `ANNOTATION_HANDBOOK.md` / `RELEVANCE_ANNOTATION_HANDBOOK.md`.

## Quality control

- **Per-repository**: each of the 8 annotation runs executed an actual
  validation script (not manual assertion) checking duplicate queries,
  duplicate candidate files, broken/invalid paths, category/difficulty
  balance, and schema conformance, with results disclosed in that
  repository's own `validation_report.md` — including corrections made
  where errors were found (e.g. fastapi corrected 1 broken regression
  -test path; celery corrected 1 duplicate candidate file and resolved
  1 query's missing primary candidate during its Phase 11 audit).
- **This assembly (dataset-wide)**: a second, independent validation
  pass re-checked duplicate IDs, duplicate `(query, file)` pairs,
  schema drift, category/repository balance, and — going beyond what
  any individual repository could check — re-verified all 249 distinct
  `(repository, file)` pairs referenced across the merged dataset
  against the actual pinned-commit repository clones on disk. See
  `validation_report.md`.
- **No relevance grade in this dataset has been assigned by a human.**
  Every one of the 439 rows in `draft_relevance_master.jsonl` (and,
  by extension, every `candidates` entry in the split files) carries
  `grade: "TO_BE_ASSIGNED"`. This is explicitly a **pre-human-review
  draft**, not a finished ground-truth dataset.

## Known limitations

1. **2 of the 8 repositories' per-repository `annotation_metrics.json`
   files are incomplete**: fastapi's is missing entirely; flask's is
   present but lacks the `schema_version` field. Both are the two
   earliest repositories processed in this project's sequential pilot
   runs, reflecting the annotation-metrics convention (including
   `schema_version` specifically) being tightened partway through the
   project. Neither affects the merged query/judgment data itself —
   see `repository_inventory.md` and `schema_validation_report.md` §4.
2. **fastapi's relevance-judgment data required a structural
   transformation to merge**, since its source schema was
   fundamentally different (nested, one row per query) from the other
   7 repositories (flat, one row per candidate file). The
   transformation is disclosed in full and is lossless for `grade`/
   `file`, with `reason` recovered from a second source file — but it
   is a transformation, not a direct pass-through, and a reviewer
   should independently spot-check a sample against
   `annotation_runs/fastapi/draft_relevance_judgments.jsonl` and
   `annotation_drafts.jsonl` before relying on it.
3. **5 of 160 queries (3.1%) are flagged by their own source
   repository as "speculative"** — grounded in an absence claim that
   was not conclusively resolved before that repository's run was
   finalized (flask: `flask-008`, `flask-013`; requests: 2 unnamed in
   its summary metrics; click: 1). These predate the practice,
   introduced in later runs, of actively following up on such flags
   before finalizing. See `dataset_statistics.md` §8.
4. **`queries.jsonl` used two different field-naming conventions**
   across the 8 source repositories, and **`draft_relevance_judgments.jsonl`
   used two different structural schemas** (flat vs. nested for
   fastapi) — both normalized for this merge with full disclosure (see
   `schema_validation_report.md`), but downstream consumers relying on
   the original per-repository files directly (rather than this
   merged dataset) will encounter the un-normalized drift.
5. **No code was executed and no test was run** during any of the 8
   annotation runs or this assembly — all grounding is static
   repository inspection (file/symbol existence, docstring/comment
   content, changelog cross-referencing). A candidate file's relevance
   has not been behaviorally confirmed.
6. **Development-snapshot commits**: 3 of the 8 repositories
   (sqlalchemy `2.1.0b4`, pandas `3.1.0.dev0`, scikit-learn `1.10.dev0`)
   are pinned at pre-release/development versions, not tagged stable
   releases; APIs referenced may change before an actual release.
7. **Coverage is necessarily shallow relative to each repository's
   size**: 20 queries per repository is a fixed budget regardless of
   repository size, so large repositories (pandas: 255 `.py` files
   under `pandas/core/`; scikit-learn: dozens of algorithm-family
   subpackages) have far lower raw file-coverage percentages than
   smaller ones (see each repository's own `dataset_statistics.md` §9
   "Coverage observations" for specifics).

## Threats to validity

- **Single AI annotator, single pass, no independent cross-check** —
  every one of the 8 repository runs and this assembly were performed
  by the same AI assistant across separate sessions; no second
  reviewer or second independent AI pass has yet validated any part of
  this dataset.
- **Grounding-search absence claims are inherently harder to verify
  than presence claims** — several Feature-category queries in the
  later repository runs rest on "this capability does not exist"
  premises checked via targeted grep rather than an exhaustive read of
  every relevant file; two such premises were found to be false and
  corrected during their respective runs (SQLAlchemy's `sqlalchemy-008`,
  pandas's `pandas-006`), disclosed in those repositories' own
  `research_notes.md`, but a similarly-flawed premise surviving
  undetected elsewhere in the dataset cannot be ruled out.
- **Methodological evolution across the 8 sequential runs**: later
  runs (SQLAlchemy onward) applied more rigorous changelog
  cross-referencing and multi-term absence verification than earlier
  runs (fastapi, flask), a direct consequence of lessons learned
  mid-project — meaning grounding rigor is not perfectly uniform
  across the 160 queries. This is disclosed transparently rather than
  retroactively smoothed over.
- **This assembly's own design choices are not dictated by a prior
  specification**: the exact schema of `train.jsonl`/`validation.jsonl`/
  `test.jsonl` (a nested per-query record) and the stratification
  strategy for the deterministic split (by repository only, not by
  category, due to small per-category counts) were judgment calls made
  during this assembly session — documented in `reproducibility.md`,
  not asserted as the unique correct design.

## License considerations

This dataset's `query_text`, `notes`, and `reason` fields are
AI-generated derivative annotations describing the 8 source
repositories' publicly available code (all 8 are open-source projects
with permissive licenses — BSD-3-Clause for fastapi/flask/celery/
sqlalchemy/pandas/scikit-learn, Apache-2.0 for requests, BSD-3-Clause
for click; license text was not independently re-verified during this
assembly and should be confirmed against each repository's own
`LICENSE`/`COPYING` file before redistribution). The dataset itself
does not embed any repository source code beyond file paths and short
quoted excerpts (function/class names, brief docstring fragments) used
for grounding rationale in the `notes`/`reason` fields. Any downstream
use should independently verify license compatibility with each of the
8 source repositories' actual license terms.
