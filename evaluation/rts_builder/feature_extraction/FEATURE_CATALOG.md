# Feature Catalog — RTS Builder Feature Extraction (Milestone 4)

Every feature `FeatureExtractor.extract` produces, grouped exactly as
in `models.py`. `Flat key` is the column name under
`FeatureVector.to_flat_dict()`. All features are deterministic for a
fixed `(RepositoryModel, query_text, FeatureExtractionSettings)` triple.

## Query Features (`FeatureVector.query`)

Computed once per query, independent of the repository.

| Feature | Flat key | Type | Range | Formula / Definition |
|---|---|---|---|---|
| Query length | `query_length` | int | `[0, ∞)` | `len(query_text)` (character count). |
| Identifier count | `query_identifier_count` | int | `[0, ∞)` | Count of tokens (via `tara.classification.heuristics.tokenize`) where `looks_like_identifier(token)` is True (snake_case, camelCase, PascalCase, CONSTANT_CASE, or a 2+-letter acronym). |
| API token count | `query_api_token_count` | int | `[0, ∞)` | Count of tokens containing `"."` (a dotted compound reference, e.g. `os.path`, `requests.get`). Disjoint from identifier count by construction — see `README.md`. |
| Has question keyword | `query_has_question_keyword` | bool | — | Any token (case-insensitive) in `{how, why, what, where, explain, does}`. |
| Has bug keyword | `query_has_bug_keyword` | bool | — | Any token in `{bug, fix, error, exception, crash, fail, failing, broken}`. |
| Has test keyword | `query_has_test_keyword` | bool | — | Any token in `{test, tests, testing, pytest, unittest}`. |
| Has refactor keyword | `query_has_refactor_keyword` | bool | — | Any token in `{refactor, rename, cleanup, simplify, restructure}`. |
| Query complexity | `query_complexity` | float | `[0, 1]` | `w_len·min(words/N_len,1) + w_id·min(ids/N_id,1) + w_clause·min((clauses-1)/N_clause,1)`, weights/norms configured (default `w=0.4/0.3/0.3`, `N=25/5/3`); `clauses = 1 + count of " and "/" or "/" then "/";"/","`. See `README.md`. |

## Repository Features (`FeatureVector.repository`)

Computed once per repository (independent of the query).

| Feature | Flat key | Type | Range | Formula / Definition |
|---|---|---|---|---|
| File count | `repo_file_count` | int | `[0, ∞)` | `len(model.files)`. |
| Function count | `repo_function_count` | int | `[0, ∞)` | `len(model.functions)` (includes methods). |
| Class count | `repo_class_count` | int | `[0, ∞)` | `len(model.classes)`. |
| Module count | `repo_module_count` | int | `[0, ∞)` | Distinct top-level packages/modules (first path segment of each file's path). Coarser than file count — see `README.md`. |
| Average file size | `repo_avg_file_size_bytes` | float | `[0, ∞)` | `sum(size_bytes) / file_count`, or `0.0` if no files. |
| Dominant language | `repo_dominant_language` | enum (`Language`) | — | `PYTHON` if `file_count > 0`, else `UNKNOWN`. Parser V1 is Python-only — see `README.md`. |

## Graph Features (`FeatureVector.graph`)

Computed once per repository from `import_graph`/`call_graph`/`inheritance_graph`.

| Feature | Flat key | Type | Range | Formula / Definition |
|---|---|---|---|---|
| Import graph density | `graph_import_density` | float | `[0, ∞)` | `len(import_graph) / max(file_count, 1)`. |
| Call graph density | `graph_call_density` | float | `[0, ∞)` | `len(call_graph) / max(function_count, 1)`. |
| Inheritance graph density | `graph_inheritance_density` | float | `[0, ∞)` | `len(inheritance_graph) / max(class_count, 1)`. |
| Connected components | `graph_connected_components` | int | `[0, ∞)` | `networkx.number_connected_components` of the combined, undirected, file-level projection of all three graphs (`0` if no files). |
| Average degree | `graph_avg_degree` | float | `[0, ∞)` | `2 · edges / nodes` of that same combined graph (`0.0` if no files). |

## Structural Features (`FeatureVector.structural`)

Computed once per repository.

| Feature | Flat key | Type | Range | Formula / Definition |
|---|---|---|---|---|
| Average functions per file | `structural_avg_functions_per_file` | float | `[0, ∞)` | `function_count / max(file_count, 1)`. |
| Average classes per file | `structural_avg_classes_per_file` | float | `[0, ∞)` | `class_count / max(file_count, 1)`. |
| Docstring coverage | `structural_docstring_coverage_ratio` | float | `[0, 1]` | Fraction of `functions + classes` with a non-empty `docstring`; `0.0` if there are none. |
| Comment coverage | `structural_comment_coverage_ratio` | float | `[0, 1]` | Mean, per-file fraction of source lines that are `#` comment lines (via `tokenize.generate_tokens`, not a naive regex), re-read from disk. `0.0` if disabled or the source is inaccessible. See `README.md`. |

## Resource Features (`FeatureVector.resource`)

Computed once per repository.

| Feature | Flat key | Type | Range | Formula / Definition |
|---|---|---|---|---|
| Estimated repository tokens | `resource_estimated_repository_tokens` | int | `[0, ∞)` | `round(total_size_bytes / chars_per_token_estimate)`, default ratio `4.0`. A tokenizer-independent approximation, not an exact count. |
| Repository size category | `resource_repository_size_category` | enum (`small`/`medium`/`large`) | — | `SMALL` if `file_count ≤ small_threshold` (default 50); `LARGE` if `file_count > large_threshold` (default 500); else `MEDIUM`. |

## Provenance fields (not features)

Present on `FeatureVector` but excluded from `to_flat_dict()`:
`repository_id`, `commit_sha`, `query_text`, `computed_at`.
