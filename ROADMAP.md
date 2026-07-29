# ROADMAP.md

## TARA: Milestone-Based Implementation Roadmap

**Status legend:** **[Complete]** — implemented, tested, merged. **[Planned]** — designed at the level of `PROJECT_SPEC.md` and `EXPERIMENT_PLAN.md`, not yet implemented; file/class/function names below are the proposed design, not a guarantee of the eventual implementation's exact shape.

**Summary table:**

| # | Milestone | Status | Tests (collected) |
|---|---|---|---|
| M1 | Repository Parser | **[Complete]** | 8 |
| M2 | Repository Context | **[Complete]** | 37 |
| M3 | Task Classifier | **[Complete]** | 144 |
| M4 | Adaptive Router | **[Complete]** | 51 |
| M5 | Lexical Retrieval | **[Planned]** | — |
| M6 | Dense Retrieval | **[Planned]** | — |
| M7 | Graph Retrieval | **[Planned]** | — |
| M8 | Fusion | **[Planned]** | — |
| M9 | Generation | **[Planned]** | — |
| M10 | Evaluation | **[Planned]** | — |

M1–M4 total: **240 passing tests**, verified by direct test collection at the time of writing this document; all four stages are deterministic, LLM-free, and meet their stated latency budgets under a dedicated timing assertion (classification < 10 ms, routing < 2 ms).

---

## Milestone 1 — Repository Parser

### Objectives
Turn a path to a repository on disk into a validated, language-aware structural fact base (files, classes, functions, methods, imports, docstrings), with no semantic interpretation, no network access, and no LLM involvement. Establish the project's cross-cutting infrastructure (configuration, logging, exception hierarchy, shared enums) that every later stage builds on.

### Files
- `src/tara/core/config.py`, `logging.py`, `exceptions.py`, `types.py`
- `src/tara/interfaces/repository_parser.py`
- `src/tara/parsing/models.py`, `language_registry.py`, `repository_parser.py`
- `pyproject.toml`, `.env.example`

### Classes
- `TaraSettings` (environment-driven config), `TaraError` and its subclasses (`RepositoryParsingError`, `UnsupportedLanguageError`, `ConfigurationError`)
- `Language` (enum, 8 members)
- `RepositoryParser` (ABC)
- `TreeSitterRepositoryParser` (concrete implementation)
- `LanguageRegistry`
- `ParsedRepository`, `ParsedFile`, `CodeSymbol`, `ImportStatement`, `ParseError` (Pydantic models), `SymbolKind` (enum)

### Functions
- `configure_logging()`, `get_logger()`
- `RepositoryParser.parse(repository_path)` (abstract)
- `TreeSitterRepositoryParser.parse()`, plus internal `_iter_source_files()`, `_parse_file()`, `_extract_symbols()`, `_extract_imports()`, `_extract_docstring()`, `_extract_name()`, `_resolve_commit_sha()`
- `LanguageRegistry.detect_language()`, `.get_parser()`, `.is_supported()`

### Tests
`tests/parsing/` — 8 tests against a real, temp-directory Git repository fixture (not mocked ASTs): missing-path error handling, file discovery, commit-SHA capture, class/function/method symbol extraction, docstring extraction, import extraction, non-source-file exclusion.

### Expected Outputs
A `ParsedRepository` object: `root_path`, `commit_sha`, `files: list[ParsedFile]` (each with `symbols`, `imports`, byte/line spans), `errors: list[ParseError]` for any file that failed to parse without aborting the whole walk.

### Risks
- Tree-sitter grammar/binding version drift across the 8 supported languages (one deprecation `FutureWarning` already observed from the `tree_sitter_languages` bundle at the pinned version; not yet a functional break).
- The best-effort, per-language regex import-target resolution (used later by M2's graph builder) is a heuristic, not a real module resolver, and can under- or over-resolve cross-file import edges.
- Coverage limited to 8 languages; no fallback behavior defined for unsupported file types beyond silent exclusion.

### Completion Criteria — **Met**
Parses all 8 supported languages; extracts classes/functions/methods with accurate byte/line spans and docstrings; extracts import statements; captures Git commit SHA when available; respects configurable ignore-directory and max-file-size settings; all 8 tests passing; full type hints, Pydantic contracts for every public data object.

---

## Milestone 2 — Repository Context

### Objectives
Turn a `ParsedRepository` into a semantic substrate: a directed graph of Repository/File/Class/Function/Method nodes and their structural relations, a fast symbol index over that graph, and (optionally) dense embeddings for every class/function/method — with no LLM call anywhere in this stage.

### Files
- `src/tara/context/models.py`, `graph_builder.py`, `symbol_index.py`, `embedder.py`, `extractor.py`
- `src/tara/interfaces/context_extractor.py`
- `src/tara/core/config.py` (extended: embedding settings), `exceptions.py` (extended: `GraphBuildError`, `SymbolIndexError`, `EmbeddingError`)

### Classes
- `ContextExtractor` (ABC), `RepositoryContextExtractor` (concrete)
- `GraphBuilder`
- `SymbolIndex`, `SymbolIndexBuilder`, `SymbolRecord` (frozen dataclass)
- `Embedder` (ABC), `SentenceTransformerEmbedder` (concrete), `RepositoryEmbedder` (batching/orchestration service), `EmbeddingInput` (frozen dataclass)
- `RepositoryContext` (Pydantic), `NodeType`, `EdgeRelation` (enums)

### Functions
- `GraphBuilder.build()`, plus internal `_add_repository_node()`, `_add_file_node()`, `_add_symbol_nodes()`, `_add_import_edges()`, `_resolve_import_targets()`
- `build_repository_node_id()`, `build_file_node_id()`, `build_symbol_node_id()` (the shared id scheme reused by the graph, the symbol index, and the embedding store)
- `SymbolIndex.from_graph()`, `.get_by_id()`, `.get_by_name()`, `.get_by_file()`
- `Embedder.embed()`, `.embed_batch()`; `iter_embedding_inputs()`; `RepositoryEmbedder.embed_repository()`
- `RepositoryContextExtractor.extract()`

### Tests
`tests/context/` — 37 tests: graph construction (repository/file/class/function/method nodes, `contains`/`defines`/`imports` edges, relative-import resolution), symbol index lookups (by id/name/file, non-exposure of raw dicts), embedding-text assembly and batching (`Embedder` always mocked — no real model loaded), and full extractor orchestration with both a fake embedder and no embedder configured.

### Expected Outputs
A `RepositoryContext` object: `graph: networkx.DiGraph`, `symbol_index: SymbolIndex`, `embeddings: dict[node_id, vector]`, `embedding_dimension`, `file_count`, `symbol_count`, plus a `graph_summary()` helper for JSON-safe logging/status use.

### Risks
- Embedding model load latency and licensing terms of the default model (`BAAI/bge-small-en-v1.5`) are not yet profiled at repository-corpus scale.
- Graph and symbol-index construction have not been tested against a large (> 50k LOC) repository; scalability is asserted by design (single-pass, O(1)-average lookups) but not yet measured.
- Import-edge accuracy is bounded by M1's heuristic resolution, not by anything new in this stage.

### Completion Criteria — **Met**
Graph, symbol index, and (optional) embeddings all keyed by an identical, shared node-id scheme; every collaborator constructor-injected (no default instantiation inside the extractor); embedder never loaded in tests; all 37 tests passing.

---

## Milestone 3 — Task Classifier

### Objectives
Classify a raw developer query into an explicit, closed task-intent taxonomy plus a coarse retrieval-requirement signal, deterministically and cheaply — no LLM, no ML model, no repository access.

### Files
- `src/tara/classification/models.py`, `heuristics.py`, `features.py`, `rules.py`, `classifier.py`
- `src/tara/interfaces/task_classifier.py`
- `src/tara/core/types.py` (extended: 13-member `TaskType`, new `RetrievalStrategy` enum), `exceptions.py` (extended: `RuleEvaluationError`)

### Classes
- `TaskClassifier` (ABC), `HeuristicTaskClassifier` (concrete)
- `FeatureExtractor`, `QueryFeatures` (frozen dataclass)
- `Rule`, `RuleVote` (frozen dataclasses), `RuleEngine`
- `TaskClassification` (Pydantic)

### Functions
- `tokenize()`, `is_pascal_case()`, `is_camel_case()`, `is_snake_case()`, `is_constant_case()`, `is_acronym()`, `looks_like_identifier()`, `extract_quoted()`, `looks_like_file_path()`, `extract_extension()`, `detect_language()`, `looks_like_explain_question()` (all in `heuristics.py`, compiled/defined once)
- `FeatureExtractor.extract()`
- `RuleEngine.evaluate()`
- `HeuristicTaskClassifier.classify()`, plus internal `_combine_task_type()`, `_select_retriever()`

### Tests
`tests/classification/` — 144 tests: every naming-convention predicate, tokenizer edge cases, symbol/file-path/keyword/language-hint extraction, every rule's independent firing behavior, custom rule injection, rule-evaluation error propagation, every one of the 13 task types individually reachable, every one of the 4 coarse retrieval strategies reachable, all 4 worked routing examples from the specification, confidence-scoring (full agreement, tie-break, zero-signal), dependency injection, edge cases (empty/whitespace/punctuation-only/unicode/very-long queries), and a dedicated timing assertion enforcing < 10 ms.

### Expected Outputs
A `TaskClassification` object: `task_type`, `retriever_kind`, `confidence` (0.0–1.0), `graph_required`/`semantic_required`/`lexical_required`/`reasoning_required` flags, `extracted_keywords`, `detected_symbols`, `detected_file_paths`, `language_hint`, `metadata` (including `fired_rules`).

### Risks
- Heuristics are English/Latin-identifier-centric by construction; behavior on non-English queries or non-Latin naming conventions is untested (stated scope boundary, not a defect).
- Exact-token keyword matching avoids substring false positives but is still vulnerable to genuine lexical ambiguity (e.g., "search" used as an incidental noun rather than a lexical-intent verb).
- The 13-member taxonomy is hand-authored and has not been validated against a large corpus of naturalistic developer queries (pending TIQS, `PROJECT_SPEC.md` §22).

### Completion Criteria — **Met**
All 13 task types and all 4 retrieval strategies reachable and tested; confidence bounded and tie-breaking deterministic; classification never touches repository state; measured latency below the 10 ms budget under a dedicated test; 144 tests passing.

---

## Milestone 4 — Adaptive Router

### Objectives
Decide *what* to retrieve with and *how* — never retrieval itself — by turning a `TaskClassification` plus a `RepositoryContext` into an executable `RetrievalPlan`, deterministically and cheaply.

### Files
- `src/tara/routing/models.py`, `strategy.py`, `policies.py`, `planner.py`, `router.py`
- `src/tara/interfaces/router.py`
- `src/tara/core/types.py` (extended: `RetrieverKind.LEXICAL` added), `exceptions.py` (extended: `PolicyError`, `PlanningError`)

### Classes
- `Router` (ABC), `AdaptiveRouter` (concrete)
- `RoutingStrategy` (enum, 7 members)
- `RoutingPolicy` (ABC), `RoutingDecision` (frozen dataclass), and five concrete policies: `FullPipelinePolicy`, `GraphPolicy`, `HybridPolicy`, `LexicalPolicy`, `SemanticPolicy`
- `RetrievalPlanner`
- `RetrievalPlan` (Pydantic)

### Functions
- `AdaptiveRouter.route()`, internal `_select_policy()`
- `RetrievalPlanner.plan()`, internal `_apply_context_constraints()`, `_order()`
- Each policy's `applies()` / `decide()` pair

### Tests
`tests/routing/` — 51 tests: `RoutingStrategy`/retriever-mapping completeness, every policy's applicability logic across all 8 boolean flag combinations, the `REFACTOR` task-type override, default-policy-chain ordering, planner behavior (sequential vs. parallel, dedup, execution ordering, rerank derivation, top-k/candidate-limit assignment, graph-depth/expand-neighbors assignment, context-capability downgrade to a supported retriever), all 5 worked examples run end-to-end through the *real* classifier, dependency injection (custom policy set, custom planner), typed error propagation, and a dedicated timing assertion enforcing < 2 ms.

### Expected Outputs
A `RetrievalPlan` object: `strategy`, `retrievers`, `execution_order`, `parallel`, `graph_depth`, `expand_neighbors`, `rerank`, `top_k`, `candidate_limit`, `reason`, `metadata` (including the winning policy's name and the classifier's original `retriever_kind` recommendation).

### Risks
- The `REFACTOR` task-type override is a stated design hypothesis, not an empirically validated one — it is designed to be tested by ablation (A2, `EXPERIMENT_PLAN.md` §5) once retrieval/generation exist, and it may not generalize.
- The context-capability downgrade currently only checks two conditions (empty embeddings, trivial graph); it does not yet account for a lexical index's own possible unavailability, since no lexical index exists yet (that gap closes in M5).
- Priority-ordered, first-match-wins policy dispatch is simple and auditable but has not been compared against a weighted/learned alternative.

### Completion Criteria — **Met**
All 7 routing strategies reachable; all 5 worked examples correct end-to-end against the real classifier; policy and planner responsibilities fully separated (no numeric/ordering logic inside a policy); measured latency below the 2 ms budget under a dedicated test; 51 tests passing.

---

## Milestone 5 — Lexical Retrieval

### Objectives
Implement the first concrete retriever: exact/keyword search over repository source text, satisfying the `LEXICAL_ONLY` and every `*_PLUS_LEXICAL`/`HYBRID`/`FULL_PIPELINE`-adjacent strategy's lexical component. Establish the shared retriever interface and the common `RetrievedContext`/`ContextChunk` output contract every later retriever (M6, M7) must also produce.

### Files *(proposed, not yet created)*
- `src/tara/interfaces/retriever.py` *(new — shared across M5–M7)*
- `src/tara/retrieval/__init__.py`, `models.py`, `lexical_index.py`, `lexical_retriever.py`

### Classes *(proposed)*
- `Retriever` (ABC, shared contract: `retrieve(query, plan, context) -> RetrievedContext`)
- `RetrievedContext`, `ContextChunk` (Pydantic, shared — introduced here, reused unchanged by M6/M7)
- `LexicalIndex` (BM25 or equivalent inverted-index structure)
- `LexicalRetriever`

### Functions *(proposed)*
- `LexicalIndex.build(parsed_repository | repository_context)`, `.search(query, top_k)`
- `LexicalRetriever.retrieve()`

### Tests *(proposed)*
`tests/retrieval/test_lexical_index.py`, `test_lexical_retriever.py` — deterministic, against small hand-constructed `ParsedRepository`/`RepositoryContext` fixtures (no real corpus required for unit correctness); exact-match ranking correctness; behavior on `extracted_keywords`/`detected_symbols` preferential matching; empty-index and no-match edge cases.

### Expected Outputs
A `RetrievedContext` populated with `ContextChunk`s tagged `retriever_kind = LEXICAL`, ranked by a lexical relevance score, respecting `RetrievalPlan.top_k`/`candidate_limit`.

### Risks
- Library/license choice for the BM25 implementation is unresolved (`EXPERIMENT_PLAN.md` §13 flags `rank_bm25` or equivalent as **TBD**).
- Index-build strategy (eager at context-extraction time vs. lazy on first lexical query) is undecided; either choice has different latency/staleness trade-offs not yet profiled.
- Tokenizer mismatch risk between the classifier's own tokenization (`tara.classification.heuristics.tokenize`) and whatever tokenization the lexical index uses internally — an inconsistency here would silently degrade retrieval quality without raising an error.

### Completion Criteria
`LexicalRetriever` implements the shared `Retriever` interface; index build and search are both unit-tested against deterministic fixtures with hand-verified expected rankings; integrates cleanly when `RetrievalPlan.retrievers` includes `LEXICAL`, with no change required to `tara.routing`.

---

## Milestone 6 — Dense Retrieval

### Objectives
Implement semantic/embedding-based retrieval over the vectors already produced by M2's `RepositoryContext.embeddings`, reusing the same `Embedder` abstraction (and, critically, the same embedder *instance* used to build the index) so query and document embeddings are guaranteed to share a vector space.

### Files *(proposed)*
- `src/tara/retrieval/dense_index.py`, `dense_retriever.py`

### Classes *(proposed)*
- `DenseIndex` (FAISS-backed nearest-neighbor index over `RepositoryContext.embeddings`)
- `DenseRetriever`

### Functions *(proposed)*
- `DenseIndex.build(embeddings: dict[str, list[float]])`, `.search(query_vector, top_k)`
- `DenseRetriever.retrieve()` (embeds the query via the injected `Embedder`, then queries the index)

### Tests *(proposed)*
`tests/retrieval/test_dense_index.py`, `test_dense_retriever.py` — the `Embedder` is always a deterministic fake (as already established in `tests/context/test_embedder.py`); index correctness verified against small, hand-constructed toy vectors with a known-by-hand nearest-neighbor ordering; no real embedding model or FAISS-scale corpus required for unit correctness.

### Expected Outputs
A `RetrievedContext` populated with `ContextChunk`s tagged `retriever_kind = DENSE`, ranked by cosine similarity, respecting `RetrievalPlan.top_k`/`candidate_limit`.

### Risks
- Query/document embedding-space mismatch if a `DenseRetriever` is ever misconfigured with a different `Embedder` instance/model than the one used at context-extraction time — a correctness-critical invariant that should be enforced (e.g., by comparing `embedding_model_name` at construction) rather than only documented.
- FAISS index memory footprint and build latency at large-repository scale are unprofiled (ties to the M2 residual risk).
- The planner's existing context-capability downgrade (M4) already handles the case of *no* embeddings; it does not yet handle a *partial* embedding set (e.g., some symbols embedded, others not, due to a mid-run failure) — behavior in that case is undefined and should be resolved during this milestone.

### Completion Criteria
`DenseRetriever` implements the shared `Retriever` interface; correctness verified on deterministic toy-vector fixtures; no real model loaded in any unit test; embedding-space consistency between index build and query time is either enforced or explicitly documented as a caller responsibility.

---

## Milestone 7 — Graph Retrieval

### Objectives
Implement retrieval by traversal of `RepositoryContext.graph` from query-matched seed nodes, honoring `RetrievalPlan.graph_depth` and `expand_neighbors`, over the structural (`contains`/`defines`/`imports`) edges M2 already populates.

### Files *(proposed)*
- `src/tara/retrieval/graph_retriever.py`, `graph_traversal.py`

### Classes *(proposed)*
- `GraphRetriever`

### Functions *(proposed)*
- `GraphRetriever.retrieve()`, internal `_resolve_seed_nodes()` (from `TaskClassification.detected_symbols`/`detected_file_paths`, via `RepositoryContext.symbol_index`), `_expand_neighbors()` (bounded BFS to `graph_depth`)

### Tests *(proposed)*
`tests/retrieval/test_graph_retriever.py` — against small, hand-built `RepositoryContext.graph` fixtures (the same construction pattern already used in `tests/routing/conftest.py`'s `rich_context`/`bare_context`); traversal-depth correctness; neighbor-expansion on/off behavior; seed-resolution correctness when a detected symbol matches a graph node exactly; explicit test of the no-seed-match fallback behavior once that behavior is designed (see Risks).

### Expected Outputs
A `RetrievedContext` populated with `ContextChunk`s tagged `retriever_kind = GRAPH`, each carrying its traversal path/relation trail as provenance, respecting `graph_depth`/`expand_neighbors`.

### Risks
- **Seed-node resolution when no detected symbol matches any graph node exactly** is explicitly marked unresolved in `PROJECT_SPEC.md` §19 ("requires design during implementation") — a fallback (e.g., seeding from the top dense/lexical hits instead) must be designed and is the single largest open design question for this milestone.
- The repository graph currently has **no populated call-graph or inheritance edges** (`CALLS`/`INHERITS`/`IMPLEMENTS` are reserved but empty, per `PROJECT_SPEC.md` §10/§35) — graph retrieval in this milestone is therefore limited to containment/definition/import structure, which materially limits its usefulness for the exact use case (e.g., "trace request flow") that motivates `GRAPH_ONLY` routing in the first place. This should be stated as a known limitation of M7's initial scope, not silently underdelivered against the motivating example.
- Traversal cost on densely-connected graphs is unbounded without careful depth/fan-out limiting.

### Completion Criteria
`GraphRetriever` implements the shared `Retriever` interface; seed-resolution fallback behavior is explicitly designed and tested (not left implicit); traversal respects `graph_depth` exactly; the call-graph-edge limitation above is documented in the milestone's own completion notes, not discovered later during evaluation.

---

## Milestone 8 — Fusion

### Objectives
Merge one or more retrievers' `RetrievedContext` outputs into a single, deduplicated, ranked, token-budgeted `FusedContext`, applying reranking only when `RetrievalPlan.rerank` is true.

### Files *(proposed)*
- `src/tara/interfaces/context_fusion.py` *(new)*
- `src/tara/fusion/models.py`, `deduplication.py`, `reranker.py`, `fusion.py`

### Classes *(proposed)*
- `ContextFusion` (ABC), `DefaultContextFusion` (concrete)
- `Deduplicator`
- `Reranker` (ABC), with two concrete variants: `ScoreMergeReranker` (weighted normalized-score merge, the required baseline per `EXPERIMENT_PLAN.md` §5 A6) and `CrossEncoderReranker` (candidate, model **TBD**)
- `FusedContext` (Pydantic)

### Functions *(proposed)*
- `Deduplicator.deduplicate(chunks)` — merges by shared node id (the same id scheme from M2)
- `Reranker.rerank(query, chunks)`
- `DefaultContextFusion.fuse(retrieved_contexts, plan)` — dedup → optional rerank → token-budget truncation

### Tests *(proposed)*
`tests/fusion/` — deduplication correctness on deliberately duplicated node ids across two synthetic retriever outputs; token-budget truncation boundary behavior (`FusedContext.truncated` flag correctness); `ScoreMergeReranker` correctness on hand-computed scores; `CrossEncoderReranker` always mocked in unit tests (no real cross-encoder model loaded), consistent with the `Embedder`-mocking precedent from M2.

### Expected Outputs
A `FusedContext` object: `chunks: list[ContextChunk]`, `total_tokens`, `truncated: bool`, with each chunk's provenance (file path, symbol name, line range) preserved for downstream prompt assembly and for human/paper inspection.

### Risks
- `CrossEncoderReranker`'s latency impact is unprofiled and could plausibly violate the pipeline's stated efficiency goals; per `PROJECT_SPEC.md` §20, the score-merge reranker must be implemented and validated **first**, with the cross-encoder treated strictly as an ablation variant, not assumed superior.
- Token-counting for the budget-truncation step needs a tokenizer; using a tokenizer that doesn't match the eventual generation LLM's own tokenizer (M9) will cause the token budget to be systematically mis-estimated.
- Deduplication by node id will not catch near-duplicate-but-differently-keyed chunks (e.g., two overlapping graph-traversal hits with different path provenance but overlapping source spans) — a known, accepted limitation to document rather than silently miss.

### Completion Criteria
`DefaultContextFusion` implements the shared interface; dedup, rerank, and truncation are each independently unit-tested; `ScoreMergeReranker` ships as the default before any cross-encoder variant is defaulted to; respects `plan.rerank`/`top_k`/`candidate_limit` exactly.

---

## Milestone 9 — Generation

### Objectives
Implement the provider-agnostic LLM interface and at least one concrete provider, assembling a `FusedContext` plus the original query (and, per ablation A9, optionally the `TaskClassification`) into a prompt and producing `GeneratedCode` — the only stage in the pipeline permitted to call an external model at inference time.

### Files *(proposed)*
- `src/tara/interfaces/code_generator.py` *(new)*
- `src/tara/generation/models.py`, `prompt_templates.py`, `llm_client.py`, `generator.py`

### Classes *(proposed)*
- `CodeGenerator` (ABC)
- One concrete provider implementation to start (exact provider **TBD** per `EXPERIMENT_PLAN.md` §8 — a hosted frontier model behind this interface, mirroring the `Embedder` pattern from M2), plus a second, open-weight/local provider implementation specifically for reproducibility (§8's stated reproducibility requirement)
- `PromptBuilder`
- `GeneratedCode` (Pydantic)

### Functions *(proposed)*
- `CodeGenerator.generate(prompt) -> GeneratedCode`
- `PromptBuilder.build(query, fused_context, classification | None)`

### Tests *(proposed)*
`tests/generation/` — `CodeGenerator` always mocked (no live API call in CI, per `PROJECT_SPEC.md` §34); `PromptBuilder` output tested deterministically against fixed inputs for exact template correctness, including both the with- and without-`TaskClassification` prompt variants (A9); provider-selection/config wiring tested without a real network call.

### Expected Outputs
A `GeneratedCode` object: `text`, `model`, `prompt_tokens`, `completion_tokens`, `latency_ms` — with provider, model identifier, and generation parameters always recorded for reproducibility (`PROJECT_SPEC.md` §21).

### Risks
- API cost and rate limits directly constrain how much of the ablation matrix (`EXPERIMENT_PLAN.md` §5) can actually be run — the single largest resource risk in the whole roadmap.
- Prompt template design is explicitly undecided (`PROJECT_SPEC.md` §21, **TBD**) and is the one open design question in this milestone most likely to materially affect downstream generation-quality results; it should be finalized and frozen before any result intended for the paper is produced (`EXPERIMENT_PLAN.md`'s pre-registration discipline applies here directly).
- Nondeterminism at non-zero temperature complicates both testing and result reproducibility; mitigated by defaulting to `temperature = 0` wherever the experimental design permits (§8).
- Provider API/model deprecation risk over the project's timeline — mitigated by requiring a local/open-weight fallback provider, not only a hosted one.

### Completion Criteria
`CodeGenerator` interface and at least two concrete providers implemented (one hosted, one local/open-weight); no fine-tuning performed anywhere in this stage; no CI test depends on a live API key or incurs API cost; the composition root can wire all nine stages (M1–M9) end-to-end and produce a `GeneratedCode` object for at least one smoke-test query against at least one corpus repository.

---

## Milestone 10 — Evaluation

### Objectives
Implement the evaluation harness that turns the now-complete nine-stage pipeline (M1–M9) into the paper's reported numbers: dataset loaders, metric implementations, baseline/ablation runners, statistical tests, and figure/table generation — as specified in `EXPERIMENT_PLAN.md`. This milestone's code is deliberately **research code, not library code** (`PROJECT_SPEC.md` §14, design principle 7): it depends on `tara`, is held to a lighter testing bar than M1–M9, and lives outside `src/tara`.

### Files *(proposed)*
- `evaluation/datasets/tiqs/` (loader + the TIQS data itself once annotated)
- `evaluation/metrics/` (one module per metric family: retrieval, generation, classification, efficiency)
- `evaluation/baselines/` (baseline-variant runner configurations — reusing `AdaptiveRouter` with alternative, restricted policy tuples for B1/B2/B3, per the DI architecture established in M4)
- `evaluation/experiments/` (experiment orchestration)
- `scripts/build_index.py`, `run_experiment.py`, `aggregate_results.py`

### Classes / Functions *(proposed)*
- `TIQSLoader`, `RepositoryCorpusLoader`
- Metric functions: `precision_at_k()`, `recall_at_k()`, `mrr()`, `ndcg_at_k()`, `macro_f1()`, `expected_calibration_error()`, `exact_match()`, `edit_similarity()`, `codebleu()` (wrapper over an existing implementation, per `PROJECT_SPEC.md` §13), `syntactic_validity_rate()` (reusing the M1 Tree-sitter infrastructure), `pass_at_k()` (standard unbiased estimator, `EXPERIMENT_PLAN.md` §3)
- Baseline runner functions constructing a fixed-policy `AdaptiveRouter` per baseline definition (`EXPERIMENT_PLAN.md` §4)
- `ExperimentRunner` (orchestrates: load corpus → build indices → for each TIQS query and each system variant, run the full pipeline → record results)
- Statistical-test wrappers implementing the exact procedures fixed in `EXPERIMENT_PLAN.md` §6 (Wilcoxon signed-rank, BCa bootstrap, Holm–Bonferroni correction, McNemar, Spearman)
- Figure/table generation scripts implementing `EXPERIMENT_PLAN.md` §10–§11 exactly

### Tests *(proposed, lighter bar than M1–M9)*
`tests/evaluation/` (or `evaluation/tests/`) — **every metric function tested against a small, hand-computed synthetic example with a known-by-hand correct value**, per the explicit requirement in `PROJECT_SPEC.md` §34 ("a bug in a metric implementation would silently invalidate reported results"); statistical-test wrappers tested against a toy dataset with a known significance outcome; baseline runners tested for correct policy-tuple wiring, not for empirical outcome. Full unit-test coverage of orchestration/aggregation scripts is explicitly **not** required.

### Expected Outputs
Per-experiment result files (structured, e.g. JSON/CSV) sufficient to regenerate every figure and table in `EXPERIMENT_PLAN.md` §10–§11 from a single script invocation per experiment, with no hand-edited intermediate step.

### Risks
- Metric-implementation bugs are the highest-consequence risk in this milestone specifically because they fail silently (a wrong number, not a crash) — directly mitigated by the mandatory hand-computed-example test requirement above.
- This milestone's actual execution is blocked on TIQS annotation completing (`PROJECT_SPEC.md` §28's highest-likelihood risk) and on M5–M9 all being complete; it cannot be meaningfully started earlier than that, even though its harness code can be scaffolded and unit-tested against synthetic data in parallel.
- Compute/API cost for the full baseline × ablation × TIQS matrix could be substantial; `EXPERIMENT_PLAN.md` §8's cost-disclosure commitment applies directly here and should inform run-order prioritization (main results before the full ablation matrix, per `EXPERIMENT_PLAN.md` §15 Phase 7 before Phase 8).

### Completion Criteria
Every metric in `EXPERIMENT_PLAN.md` §3 implemented and unit-tested against a hand-computed value; every statistical test in §6 implemented exactly as specified (test, correction method, α); at least one full end-to-end experimental run (main results, `EXPERIMENT_PLAN.md` §15 Phase 7) reproducible from a single script against a pinned repository corpus and a sealed TIQS test split; all figures/tables in §10–§11 generated programmatically from archived result files, never hand-edited.
