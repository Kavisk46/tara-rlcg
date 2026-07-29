# PROJECT_SPEC.md

## TARA: Task-Aware Adaptive Retrieval for Repository-Level Code Generation

**Status:** Living specification. Sections describing already-implemented stages (§9–§18) reflect the current codebase as of this writing. Sections describing not-yet-implemented stages (§19–§21) are design proposals and are explicitly marked as such. This document is versioned alongside the codebase; material changes to architecture or research design should be accompanied by an update to this file in the same pull request.

**Document owner:** TARA maintainers.
**Audience:** Engineers implementing TARA, and researchers evaluating or extending it.

---

## 1. Executive Summary

TARA (Task-Aware Adaptive Retrieval Architecture) is an open-source research framework for repository-level code generation. Its central design bet is that **explicit, cheap, deterministic classification of a developer's task intent** — e.g., is this query asking to *find* something, *explain* something, *debug* something, or *refactor* something — can drive a **retrieval strategy selection** step that is more precise, more efficient, and more explainable than retrieval pipelines that either (a) always use a single fixed strategy (e.g., dense/embedding retrieval only) or (b) learn strategy selection implicitly and opaquely inside a larger neural system.

TARA is structured as a five-stage pipeline: **Repository Parser → Repository Context Extractor → Task Classifier → Task-Guided Adaptive Router → Retrieval/Fusion/Generation**. The first four stages are implemented, unit-tested, and require no LLM call and no learned model at inference time for classification or routing (the Context Extractor optionally uses a sentence-embedding model, not an LLM). The final stages — concrete retrievers, context fusion, and LLM-based generation — are specified in this document as the next implementation phase.

The research contribution under test is narrow and falsifiable: **does inserting an explicit, interpretable task-classification-and-routing layer before retrieval improve retrieval quality, generation quality, latency/cost efficiency, or explainability, relative to task-agnostic retrieval baselines?** TARA does not claim to advance code-generation model quality itself; it claims to advance *how retrieval context is selected* before generation.

## 2. Motivation

Large language models are increasingly used to generate and modify code inside existing repositories rather than in a blank-file setting. In this regime, the model's output quality is bottlenecked less by raw generation capability and more by whether it was given the *right context*: the right function definitions, the right call sites, the right configuration files, the right prior art within the same codebase.

Most retrieval-augmented code generation systems retrieve context using a single, fixed mechanism per system — typically dense/embedding similarity search over chunked source code — regardless of what the developer is actually trying to do. This is a reasonable default, but it is not universally correct:

- A query like *"Find `parse_repository`"* is best served by exact lexical/symbol lookup; dense retrieval over paraphrastic similarity is unnecessary overhead and can retrieve semantically-similar-but-wrong symbols.
- A query like *"Trace the login flow"* is fundamentally a graph-traversal problem (call/import/control relationships), not a similarity-search problem.
- A query like *"Refactor `RepositoryParser`"* plausibly needs all three: exact location, semantic understanding of intent, and a dependency map of blast radius.

Treating all three queries identically wastes retrieval budget, can degrade precision, and — critically for a research artifact — makes it hard to explain *why* a given chunk of context was retrieved. TARA's motivating premise is that a cheap, explicit, upstream classification step can make these decisions instead of leaving them implicit inside a single retrieval model or leaving them to a human to hand-tune per query.

## 3. Research Problem

**Problem statement.** Given (a) a source-code repository `R` and (b) a natural-language developer query `q` about that repository, select a subset of repository context `C ⊆ R` to condition an LLM's code generation on, such that `C` maximizes the quality of the LLM's generated output for `q`, subject to constraints on retrieval latency and token budget.

Existing systems generally instantiate this as: embed `q`, embed chunks of `R`, retrieve top-k by cosine similarity, optionally rerank, generate. This treats retrieval-strategy selection as a **constant function of the system**, not a function of `q`. TARA reformulates the problem as a **two-stage decision process**: first classify `q` into an explicit task-intent representation `T(q)`, then select a retrieval strategy `S = f(T(q), R)` from a small, enumerable strategy space, then execute `S` to obtain `C`.

The research problem is therefore twofold:
1. **Classification problem:** can `T(q)` be estimated cheaply and reliably enough (without an LLM call) to be useful as a routing signal?
2. **Routing problem:** does conditioning retrieval strategy on `T(q)` produce a `C` that yields measurably better downstream outcomes than a strategy held constant across all `q`?

## 4. Research Gap

The related systems named for this project each address adjacent but distinct problems:

- **AIRCoder** (closest work) — adaptive/iterative retrieval for repository-level completion; the closest prior system to TARA's motivation. **ASSUMPTION:** AIRCoder's routing signal is derived primarily from retrieval-internal signals (e.g., retrieval confidence, iterative refinement) rather than from an explicit, human-readable task-intent taxonomy computed *before* any retrieval occurs. This distinction is the crux of TARA's proposed contribution and **requires direct comparison to confirm** (see §24, Baselines).
- **RepoGraph** — constructs a repository-level dependency graph for retrieval/context construction. TARA's Repository Context Extractor performs a related but narrower graph-construction step (structural containment/definition/import edges only, no call-graph resolution at present — see §10) and treats the graph as one of several retrieval modalities selected by the router, not the sole retrieval mechanism.
- **RepoFormer** — repository-level code completion with retrieval; **ASSUMPTION:** primarily dense-retrieval-centric. Serves as a natural "semantic-only" baseline family.
- **AllianceCoder** — collaborative/ensemble retrieval-augmented code generation. Relevant as a possible baseline for "always combine multiple retrievers" (TARA's `FULL_PIPELINE` strategy without task-conditioning).
- **STALL+** — relevant as a comparison point for retrieval-augmentation strategy design in code LLMs generally; exact mechanism **requires literature review before final baseline design** (marked TBD, see §24).
- **CodeRAG-Bench** — a benchmark and analysis of retrieval-augmented code generation across multiple retrieval strategies. This is the most directly reusable prior work for TARA's evaluation methodology (§22–§25) and should be treated as a candidate source of benchmark tasks and as a methodological reference for metric selection, not as a system to reproduce.

**Stated gap:** No system in this list is known (as of this document's writing, and **subject to a literature-verification pass before publication**) to perform an explicit, deterministic, pre-retrieval classification of query task-intent into a fixed taxonomy, and to use that classification to select among a small enumerable set of retrieval-strategy combinations (lexical/semantic/graph and their unions) in a way that is fully inspectable (every routing decision carries a machine-generated natural-language `reason` string). TARA's contribution is this explicit routing layer and the empirical question of whether it is worth the added system complexity. **This is a claim about system design, not a claim of superior end-task accuracy, and must not be overstated in the paper** (see §36).

## 5. Research Questions

- **RQ1 (Classification feasibility):** Can a repository-agnostic, LLM-free, rule-based classifier assign a useful task-intent label to a developer query with accuracy and confidence-calibration sufficient to drive downstream routing decisions?
- **RQ2 (Retrieval quality):** Does task-aware adaptive routing improve retrieval precision/recall/MRR over (a) a fixed single-strategy baseline and (b) a fixed always-hybrid baseline, at matched or lower retrieval cost?
- **RQ3 (Generation quality):** Does context assembled via task-aware routing improve downstream code-generation quality (functional correctness where measurable, edit similarity, syntactic validity) relative to task-agnostic retrieval baselines, holding the generation LLM constant?
- **RQ4 (Efficiency):** Does task-aware routing reduce retrieval latency and/or retrieval cost (number of retriever invocations, embedding calls, tokens retrieved) relative to an always-hybrid strategy, without a statistically significant quality regression relative to the best-performing baseline?
- **RQ5 (Explainability):** Do the natural-language routing `reason` strings produced by TARA's policies correspond, under human or LLM-judge evaluation, to routing decisions that domain experts would independently endorse as sensible given the query? **(This RQ is exploratory and its evaluation protocol requires future validation — see §25.)**
- **RQ6 (Confidence calibration):** Is task-classification confidence (as produced by the Task Classifier, §17) correlated with downstream retrieval/generation quality, such that low-confidence classifications identify queries where routing is less reliable?

## 6. Hypotheses

Each hypothesis is stated to be falsifiable and is paired with its research question.

- **H1 (↔ RQ1):** The rule-based Task Classifier achieves ≥ 0.75 macro-F1 against a held-out, human-annotated task-intent label set (see §22, TIQS), and its `confidence` output is positively correlated (Spearman ρ > 0, two-sided test, α = 0.05) with classification correctness.
- **H2 (↔ RQ2):** Task-aware routing achieves retrieval Recall@10 and MRR at least as high as the strongest single-strategy baseline, and strictly higher than a random-routing control, at equal or lower mean retrieval cost.
- **H3 (↔ RQ3):** Code generated using TARA-routed context achieves higher mean quality score (composite of exact-match/edit-similarity/syntactic-validity; pass@k where executable test suites are available) than generation using a fixed dense-only retrieval baseline, on the subset of queries where the Task Classifier assigns a non-`SEMANTIC_ONLY` strategy with confidence above a pre-registered threshold.
- **H4 (↔ RQ4):** Mean end-to-end retrieval latency under task-aware routing is lower than under an always-`FULL_PIPELINE` baseline, because a nontrivial fraction of real-world queries route to single-retriever strategies.
- **H5 (↔ RQ6):** Queries where the Task Classifier reports low confidence (below a pre-registered threshold, proposed 0.5) show significantly lower downstream retrieval quality than high-confidence queries, supporting confidence as a usable reliability signal for future selective/fallback routing.

**H3 in particular requires a working generation stage and is contingent on §19–§21 being implemented; it cannot be tested against the current codebase.**

## 7. Scope

In scope for the TARA v1 research artifact:

- Repository parsing and structural fact extraction for a fixed set of languages (Python, JavaScript, TypeScript, Java, Go, Rust, C, C++ — as already implemented; see §10).
- Construction of a repository-level structural graph (containment, definition, best-effort same-repository import edges) and an optional dense embedding index over classes/functions/methods.
- A closed, enumerable taxonomy of developer task intents (13 categories, §17) and a deterministic classifier over that taxonomy.
- A closed, enumerable taxonomy of retrieval strategies (7 categories, §18) and a deterministic policy-based router mapping classification → strategy.
- Concrete retriever implementations for lexical, semantic (dense), and graph retrieval modes (planned, §19).
- A context-fusion step that merges and ranks multi-retriever output into a bounded context window (planned, §20).
- A provider-agnostic LLM interface for final code generation, used only at inference time with **no fine-tuning of the generation model** (planned, §21).
- An evaluation harness, a small human-annotated query/task-intent dataset (§22), and an experimental protocol (§23–§26) sufficient to test H1–H5.
- Reproducibility artifacts: pinned dependencies, seeds, configuration files, and scripts to regenerate all reported results.

## 8. Out of Scope

Explicitly excluded from TARA v1, to keep the research question tractable:

- Training or fine-tuning any LLM used for generation. Only inference-time prompting via a provider-agnostic interface is in scope.
- Fine-tuning the sentence-embedding model used for dense retrieval. Off-the-shelf models only (configurable, default `BAAI/bge-small-en-v1.5`).
- Multi-turn conversational agents, tool-use loops, or agentic planning beyond the single classify → route → retrieve → fuse → generate pass.
- Code execution sandboxes / CI integration for automatic test execution as part of the core pipeline. Execution-based metrics (e.g., pass@k) are **conditionally in scope for evaluation only**, where a benchmark already provides a safe execution harness (e.g., a subset of an existing benchmark); TARA will not build its own sandboxed executor in v1.
- IDE plugins, editor integrations, or any production-facing service beyond a minimal FastAPI wrapper for demonstration purposes.
- Cross-repository retrieval (retrieving context from a repository other than the one containing the query). TARA v1 operates on a single target repository per session.
- Support for languages beyond the eight listed in §7. Additional Tree-sitter grammars are future work (§35).
- Online/continual learning from user feedback. All components are static at inference time within an experimental run.
- Formal security auditing of generated code. Security-task-type queries (`TaskType.SECURITY`) are classified and routed like any other task type but TARA makes no claim of improving code security outcomes.

## 9. High-Level Architecture

```
Developer Query
      │
      ▼
Repository Parser              (implemented)
      │
      ▼
Repository Context Extractor   (implemented)
      │
      ▼
Task Classifier                (implemented)
      │
      ▼
Task-Guided Adaptive Router    (implemented)
      │
      ▼
┌────────────────┬────────────────┬────────────────┬─────────────────┐
│Lexical Retriever│ Dense Retriever│  API Retriever  │ Static Analyzer │   (planned)
└────────────────┴────────────────┴────────────────┴─────────────────┘
      │
      ▼
Context Fusion                 (planned)
      │
      ▼
LLM (Code Generator)           (planned)
      │
      ▼
Generated Code
```

Each stage consumes the immediately preceding stage's typed output and produces a new typed output; no stage reaches backward into an earlier stage's internals. Each stage is defined by an abstract interface (`tara.interfaces.*`) that downstream stages and downstream research code depend on, so that any stage's concrete implementation can be swapped (e.g., a future learned classifier replacing the rule-based one) without touching any other stage. This is Dependency Inversion applied at the pipeline level and is treated as a hard architectural constraint, not a stylistic preference (§14).

## 10. Complete System Architecture

The system is organized as one Python package (`tara`) with one subpackage per pipeline stage, plus two cross-cutting subpackages (`core`, `interfaces`).

**`tara.core`** — infrastructure with no dependency on any other `tara` subpackage: environment-driven configuration (`TaraSettings`), process-wide logging setup, the exception hierarchy every stage raises through, and shared enums (`Language`, `TaskType`, `RetrieverKind`, `RetrievalStrategy`).

**`tara.interfaces`** — one `abc.ABC` per pipeline stage (`RepositoryParser`, `ContextExtractor`, `TaskClassifier`, `Router`, and — pending implementation — a retrieval-stage interface and a generation-stage interface). Each interface depends only on `tara.core` and on the *input/output data models* of adjacent stages, never on a concrete implementation.

**`tara.parsing`** *(implemented)* — `RepositoryParser` → `ParsedRepository`. Walks a repository on disk (respecting a configurable ignore list and a max-file-size cutoff), parses each supported source file with Tree-sitter, and extracts per-file structural facts: classes, functions, methods (with docstrings and byte/line spans), and import statements. Also records the current Git commit SHA for provenance when the target directory is a Git repository. This stage performs **no semantic interpretation** — it is a syntactic fact extractor.

**`tara.context`** *(implemented)* — `ContextExtractor` → `RepositoryContext`. Consumes a `ParsedRepository` and produces: (a) a `networkx.DiGraph` with one node per repository/file/class/function/method and `contains`/`defines`/`imports` edges (with `calls`/`inherits`/`implements`/`depends_on` reserved for future population on the same graph, so later work never needs a second graph); (b) a `SymbolIndex` providing O(1) average-case lookup by node id, symbol name, and file path; (c) optionally, dense embedding vectors for every class/function/method, produced by an injected `Embedder` (default: a lazily-loaded `sentence-transformers` model) and keyed by the same node id used in the graph and symbol index, so all three representations of a symbol are trivially correlatable.

**`tara.classification`** *(implemented)* — `TaskClassifier` → `TaskClassification`. Consumes the raw query string only (does **not** consume `RepositoryContext` — classification is repository-agnostic by design, see §17) and produces a structured classification: task type, recommended coarse retrieval strategy, a confidence score, four boolean retrieval-requirement flags, extracted keywords/symbols/file paths, and a detected programming-language hint. Implemented as a deterministic rule engine with no ML model and no network call (§17).

**`tara.routing`** *(implemented)* — `Router` → `RetrievalPlan`. Consumes both a `TaskClassification` and a `RepositoryContext` and produces an executable retrieval plan: which retriever kinds to run, in what order, sequentially or in parallel, with what top-k/candidate-pool size, whether to rerank, and (if applicable) graph traversal depth. Performs no retrieval itself; the `RepositoryContext` is consulted only for O(1) capability checks (are embeddings present? is the graph non-trivial?), never traversed (§18).

**`tara.retrieval`** *(planned, §19)* — will consume a `RetrievalPlan` plus `RepositoryContext` plus the original query and produce a `RetrievedContext`: a ranked, deduplicated set of candidate context chunks, one execution path per retriever kind named in the plan, executed sequentially or in parallel per `RetrievalPlan.parallel`.

**`tara.fusion`** *(planned, §20)* — will consume one or more `RetrievedContext` objects (one per retriever that ran) plus the `RetrievalPlan`'s `rerank`/`top_k` settings and produce a single `FusedContext`: a token-budgeted, ranked, deduplicated context payload ready for prompt assembly.

**`tara.generation`** *(planned, §21)* — will consume a `FusedContext`, the original query, and the `TaskClassification` (for prompt templating) and produce `GeneratedCode` via a provider-agnostic LLM interface.

**`tara.api`** *(planned)* — a thin FastAPI service exposing the end-to-end pipeline for demonstration and for driving the evaluation harness over HTTP where useful; not a production deployment target (§8).

**`tara.evaluation`** *(planned, new for the research artifact, not previously scoped in the engineering roadmap)* — dataset loaders, metric implementations, experiment runners, and result-aggregation utilities used to produce the paper's tables and figures. Kept structurally separate from `tara`'s library code so that research/evaluation code churn does not destabilize the reusable framework (§14, §31).

## 11. Module Responsibilities

| Package | Responsible for | Explicitly not responsible for |
|---|---|---|
| `tara.core` | Config, logging, exceptions, shared enums | Any pipeline logic |
| `tara.interfaces` | Stage contracts (ABCs) | Any concrete behavior |
| `tara.parsing` | Syntactic fact extraction via Tree-sitter | Semantic interpretation, graph construction |
| `tara.context` | Graph construction, symbol indexing, embedding generation | Query understanding, retrieval strategy selection |
| `tara.classification` | Query → task-intent + coarse retrieval signal | Any repository access, any retrieval |
| `tara.routing` | Task-intent + repository capability → executable retrieval plan | Any retrieval execution |
| `tara.retrieval` *(planned)* | Executing a `RetrievalPlan` against a `RepositoryContext` | Deciding which retrievers to run (that is the router's job) |
| `tara.fusion` *(planned)* | Merging/ranking/budgeting multi-retriever output | Retrieval execution, generation |
| `tara.generation` *(planned)* | Prompt assembly + LLM invocation | Retrieval, fusion, fine-tuning |
| `tara.api` *(planned)* | HTTP exposure of the pipeline | Business logic (delegates to the library) |
| `tara.evaluation` *(planned)* | Datasets, metrics, experiment orchestration, reporting | Library/runtime pipeline logic |

## 12. Repository Structure

```
tara-rlcg/
├── PROJECT_SPEC.md
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── src/
│   └── tara/
│       ├── core/
│       │   ├── config.py
│       │   ├── logging.py
│       │   ├── exceptions.py
│       │   └── types.py
│       ├── interfaces/
│       │   ├── repository_parser.py
│       │   ├── context_extractor.py
│       │   ├── task_classifier.py
│       │   ├── router.py
│       │   ├── retriever.py            (planned)
│       │   └── code_generator.py       (planned)
│       ├── parsing/
│       │   ├── models.py
│       │   ├── language_registry.py
│       │   └── repository_parser.py
│       ├── context/
│       │   ├── models.py
│       │   ├── graph_builder.py
│       │   ├── symbol_index.py
│       │   ├── embedder.py
│       │   └── extractor.py
│       ├── classification/
│       │   ├── models.py
│       │   ├── heuristics.py
│       │   ├── features.py
│       │   ├── rules.py
│       │   └── classifier.py
│       ├── routing/
│       │   ├── models.py
│       │   ├── strategy.py
│       │   ├── policies.py
│       │   ├── planner.py
│       │   └── router.py
│       ├── retrieval/                  (planned)
│       │   ├── models.py
│       │   ├── lexical_retriever.py
│       │   ├── dense_retriever.py
│       │   ├── graph_retriever.py
│       │   ├── api_retriever.py
│       │   ├── static_analyzer.py
│       │   └── orchestrator.py
│       ├── fusion/                     (planned)
│       │   ├── models.py
│       │   ├── deduplication.py
│       │   ├── reranker.py
│       │   └── fusion.py
│       ├── generation/                 (planned)
│       │   ├── models.py
│       │   ├── prompt_templates.py
│       │   ├── llm_client.py
│       │   └── generator.py
│       └── api/                        (planned)
│           └── app.py
├── tests/
│   ├── parsing/
│   ├── context/
│   ├── classification/
│   ├── routing/
│   ├── retrieval/                      (planned)
│   ├── fusion/                         (planned)
│   └── generation/                     (planned)
├── evaluation/                          (planned, research-only code)
│   ├── datasets/
│   │   └── tiqs/                        (Task-Intent Query Set, §22)
│   ├── metrics/
│   ├── experiments/
│   ├── baselines/
│   └── notebooks/
├── benchmarks/                          (planned)
│   └── repositories/                    (checked-out or vendored benchmark repos, or fetch scripts)
├── scripts/                             (planned)
│   ├── build_index.py
│   ├── run_experiment.py
│   └── aggregate_results.py
├── docs/
│   ├── adr/                             (Architecture Decision Records, §33)
│   └── figures/
└── paper/                               (planned)
    ├── main.tex or main.md
    └── figures/
```

## 13. Technology Stack

**Core library (implemented / already in `pyproject.toml`):** Python ≥ 3.10; FastAPI + Uvicorn (API layer, planned use); Pydantic + `pydantic-settings` (all public data contracts and configuration); PyTorch (embedding-model backend); `sentence-transformers` (dense embeddings, default `BAAI/bge-small-en-v1.5`); FAISS (`faiss-cpu`, planned use for dense retrieval index); NetworkX (repository graph); `tree-sitter` + `tree-sitter-languages` (multi-language parsing); GitPython (commit provenance); Transformers (reserved for any future learned-model component, not currently invoked at inference).

**Development tooling (already in use):** pytest + `pytest-cov` (testing), Ruff (linting), mypy (static typing, strict mode).

**Planned additions for retrieval/fusion/generation:** an LLM provider SDK behind a provider-agnostic interface (**ASSUMPTION:** initial target providers are Anthropic and OpenAI, selected via configuration; exact provider(s) used for reported experiments **must be pinned and disclosed in the paper**); `rank_bm25` or equivalent for lexical retrieval (**TBD**, candidate libraries to be evaluated for license and performance before selection); an optional cross-encoder reranker (**TBD**, candidate: a `sentence-transformers` cross-encoder model, to be selected during §20 implementation).

**Planned additions for evaluation (`tara.evaluation`, not part of the core library's dependency footprint):** pandas (result aggregation); matplotlib and/or plotly (figures); `scipy.stats` (significance testing); a code-similarity metric library for CodeBLEU/edit-similarity (**TBD**, candidate: `codebleu` package or an in-house implementation, to be decided during §25 implementation); optionally Weights & Biases or a local equivalent for experiment tracking (**explicitly optional**, not a hard dependency of the reproducibility artifact — all results must also be reproducible from flat files/scripts without a tracking service).

All dependency versions used to produce any reported result must be pinned (via `pyproject.toml` and a lockfile) and archived alongside the corresponding experiment's configuration (§29 Deliverables).

## 14. Design Principles

1. **Dependency Inversion at the pipeline level.** Every stage depends on the interface of the stage(s) before it, never on a concrete implementation. This is already enforced (`RepositoryParser`, `ContextExtractor`, `TaskClassifier`, `Router` ABCs) and must be extended identically to the retrieval, fusion, and generation stages.
2. **Constructor-injected dependencies; no hidden singletons.** Every component that has a collaborator (an embedder, a rule engine, a set of policies, a planner) receives it through `__init__`. No component constructs a default dependency it doesn't own the decision to construct silently in a way that can't be substituted in tests.
3. **Typed public contracts.** Every inter-stage data object is a Pydantic model (validated at construction, serializable) or, for genuinely internal/ephemeral value objects (e.g., a single rule's vote), a frozen `dataclass`. Raw dicts are not used as inter-stage contracts.
4. **Deterministic-and-cheap before probabilistic-and-expensive.** Parsing, context extraction (excluding the optional embedding step), classification, and routing are all deterministic and designed to complete in low-single-digit milliseconds (classification: <10ms tested; routing: <2ms tested). The LLM call is the single, isolated point of nondeterminism and cost in the pipeline. This ordering is intentional: it means the majority of the pipeline is unit-testable without mocking a model and without incurring API cost.
5. **Explicit failure modes.** Every stage raises through a stage-specific subclass of a single `TaraError` base, never a bare `Exception`. Failures are attributable to a specific component (e.g., `PolicyError` identifies the failing policy by name).
6. **No premature abstraction.** Interfaces are introduced when a second implementation or a testing need justifies them, not speculatively. The current codebase has exactly one concrete implementation per interface; this is expected and acceptable, not a sign of over-abstraction, because each interface exists specifically to allow controlled substitution in tests and in future research variants (e.g., swapping the rule-based classifier for a learned one).
7. **Research code is not library code.** Anything that exists to produce a paper result (dataset loaders, metric scripts, experiment orchestration) lives under `evaluation/` and `scripts/`, depends on `tara` (never the reverse), and is held to a lighter documentation/testing bar than `src/tara` (§34).
8. **Reproducibility is a first-class requirement, not an afterthought.** Every experiment that produces a number reported in the paper must be re-runnable from a checked-in configuration and a pinned environment (§29).

## 15. Data Flow

The pipeline's data flow, stage by stage, with the concrete type produced at each step:

1. `Path` (repository root) → **Repository Parser** → `ParsedRepository { root_path, commit_sha, files: [ParsedFile], errors: [ParseError] }`, where each `ParsedFile` carries `symbols: [CodeSymbol]` and `imports: [ImportStatement]`.
2. `ParsedRepository` → **Context Extractor** → `RepositoryContext { graph: DiGraph, symbol_index: SymbolIndex, embeddings: {node_id: vector}, embedding_dimension, file_count, symbol_count }`.
3. `str` (raw query) → **Task Classifier** → `TaskClassification { task_type, retriever_kind, confidence, graph_required, semantic_required, lexical_required, reasoning_required, extracted_keywords, detected_symbols, detected_file_paths, language_hint, metadata }`. Note this step does **not** consume `RepositoryContext`.
4. `(TaskClassification, RepositoryContext)` → **Adaptive Router** → `RetrievalPlan { strategy, retrievers, execution_order, parallel, graph_depth, expand_neighbors, rerank, top_k, candidate_limit, reason, metadata }`.
5. `(RetrievalPlan, RepositoryContext, query)` → **Retrievers** *(planned)* → `RetrievedContext` per retriever kind that ran, each a ranked list of candidate chunks with a source retriever tag and a raw score.
6. `[RetrievedContext]` → **Context Fusion** *(planned)* → `FusedContext { chunks: [ContextChunk], total_tokens, truncated: bool }`.
7. `(FusedContext, query, TaskClassification)` → **LLM Interface** *(planned)* → `GeneratedCode { text, model, prompt_tokens, completion_tokens, latency_ms }`.

At every arrow, the object on the left is fully sufficient to produce the object on the right; no stage reaches further upstream than its immediate input (e.g., the Router never reads `ParsedRepository` directly, only `RepositoryContext`).

## 16. Component Interaction

The pipeline is composed at a single composition root (the planned `tara.api` entrypoint, and equivalently the planned `evaluation/experiments` runner for offline evaluation). The composition root is responsible for constructing every concrete implementation and wiring it into the next stage's constructor; no stage constructs its own upstream collaborator. Concretely, an orchestrating caller:

1. Constructs a `TreeSitterRepositoryParser` and calls `.parse(repository_path)` once per repository (or reuses a cached `ParsedRepository` — caching strategy is **planned, not yet implemented**, and should key on `commit_sha` plus file content hashes already present on `ParsedFile`).
2. Constructs a `GraphBuilder`, a `SymbolIndexBuilder`, and (optionally) a `RepositoryEmbedder` wrapping a `SentenceTransformerEmbedder`; injects all three into a `RepositoryContextExtractor` and calls `.extract(parsed_repository)`.
3. Constructs a `HeuristicTaskClassifier` (itself composed from a `FeatureExtractor` and a `RuleEngine`) and calls `.classify(query)`.
4. Constructs an `AdaptiveRouter` (composed from `DEFAULT_POLICIES` and a `RetrievalPlanner`) and calls `.route(classification, context)`.
5. *(Planned)* Constructs a retrieval orchestrator, injects the concrete retrievers named in the `RetrievalPlan`, and executes them per `plan.execution_order` / `plan.parallel`.
6. *(Planned)* Constructs a fusion component and passes it the retrieval outputs plus the plan's `rerank`/`top_k`/`candidate_limit`.
7. *(Planned)* Constructs an LLM client behind the generation interface and passes it the fused context.

No stage holds a reference to a stage more than one hop away. The composition root is the only place that knows the full pipeline shape; this is intentional so that the evaluation harness can substitute alternative wiring (e.g., a fixed-strategy router in place of `AdaptiveRouter`, for baseline comparisons in §24) without modifying any pipeline stage.

## 17. Task Classifier Design

**Design decision (already implemented and load-bearing for the research claim in §4):** the Task Classifier does not call an LLM and does not use a trained ML model. It is a deterministic rule engine over lexical/orthographic features of the raw query string. This is a deliberate choice, not a placeholder for a future learned classifier, for three reasons: (1) it keeps the classification step's cost and latency negligible relative to the eventual LLM generation call, so any measured efficiency gain from routing is not confounded by classifier cost; (2) it makes every classification fully explainable by construction (the `metadata.fired_rules` field lists exactly which rules fired); (3) it establishes a transparent, reproducible baseline before any future work introduces a learned classifier (§35), which is itself a fair scientific comparison to make later.

**Taxonomy (`TaskType`, 13 members, closed set):** `SEARCH`, `EXPLAIN`, `DEBUG`, `BUG_FIX`, `REFACTOR`, `GENERATE`, `TEST`, `DOCUMENTATION`, `ARCHITECTURE`, `DEPENDENCY_ANALYSIS`, `SECURITY`, `PERFORMANCE`, `UNKNOWN`. **ASSUMPTION:** this taxonomy is believed to cover the majority of realistic repository-level developer queries but has not been validated against a large-scale corpus of real queries; §22 proposes the minimum validation needed before the taxonomy is treated as final for publication.

**Pipeline internal to this stage:**
1. **Feature extraction** (`FeatureExtractor`): tokenizes the query, lower-cases a token-set copy for matching, and extracts (a) naming-convention-based probable code symbols (PascalCase, camelCase, snake_case, CONSTANT_CASE, bare acronyms), (b) probable file paths/filenames by extension, (c) quoted phrases (treated as literal search terms regardless of naming convention), (d) stop-word-filtered keywords, and (e) a single best-effort programming-language mention.
2. **Rule evaluation** (`RuleEngine` over `DEFAULT_RULES`): each rule is an isolated, pure function of the extracted features that optionally casts a weighted vote for a `TaskType` and/or asserts one or more of four boolean retrieval-requirement flags (`graph_required`, `semantic_required`, `lexical_required`, `reasoning_required`). Rules never observe each other's output.
3. **Combination** (performed only by the classifier, never by a rule): the winning `task_type` is the one with the highest summed vote weight, ties broken by a fixed, documented priority order; `confidence` is the winning type's share of total vote weight (full agreement → 1.0; a query with no votes at all → `UNKNOWN` at confidence 0.0). The four boolean flags are combined by logical OR across all fired rules. The coarse `retriever_kind` (`LEXICAL` / `SEMANTIC` / `GRAPH` / `HYBRID`) is derived from the flags (two or more flags set → `HYBRID`; exactly one → that strategy; none → `SEMANTIC` as the safe default).

**Explicitly out of scope for this stage:** any use of repository content. The classifier's output must be identical for the same query string regardless of which repository it will later be routed against; this separation is what allows classification to be tested and reasoned about independently of any specific repository (already reflected in the test suite, which never constructs a `RepositoryContext` to test the classifier).

## 18. Adaptive Router Design

**Taxonomy (`RoutingStrategy`, 7 members, closed set):** `LEXICAL_ONLY`, `SEMANTIC_ONLY`, `GRAPH_ONLY`, `HYBRID`, `GRAPH_PLUS_SEMANTIC`, `LEXICAL_PLUS_GRAPH`, `FULL_PIPELINE`. This is a strict refinement of the classifier's coarser 4-value `retriever_kind` recommendation; the router is permitted to reach a different, more specific conclusion than the classifier's coarse recommendation (see the `REFACTOR` override below), and the classifier's original recommendation is preserved in `RetrievalPlan.metadata` for observability rather than discarded.

**Decision procedure:** a fixed, ordered tuple of `RoutingPolicy` objects (`FullPipelinePolicy → GraphPolicy → HybridPolicy → LexicalPolicy → SemanticPolicy`) is evaluated in order; the **first policy whose `applies()` predicate returns true** decides the strategy. Policy order is itself the conflict-resolution mechanism — more specific policies are listed first, and `SemanticPolicy` is an unconditional catch-all listed last. Each policy is a pure function of `TaskClassification` alone; policies never observe the `RepositoryContext` or each other.

One policy, `FullPipelinePolicy`, additionally fires whenever `task_type is REFACTOR`, independent of the three boolean flags — this is a deliberate, documented exception to pure flag-based routing, justified by the argument that safely refactoring a known symbol requires locating it exactly (lexical), understanding its purpose (semantic), and mapping everything that depends on it (graph) simultaneously. **This is a hand-authored design decision, not a learned one, and its correctness is an empirical question the evaluation in §23–§26 should test directly** (e.g., via ablation: REFACTOR routing with vs. without the override).

**Planning:** a separate `RetrievalPlanner` component (never a policy) converts the winning policy's coarse decision into an executable plan: deduplicates retriever kinds, orders them cheapest-first for sequential execution, sets `parallel = True` whenever more than one retriever kind is selected, sets `rerank = True` whenever `parallel` is true or the classification's `reasoning_required` flag is set, assigns a strategy-specific default `top_k` and a reranking-dependent `candidate_limit`, and sets `graph_depth`/`expand_neighbors` together whenever a graph retriever participates. The planner is also the single place that checks whether the concrete `RepositoryContext` can actually support a policy's recommendation (e.g., no embeddings computed yet → drop the dense retriever; a graph with no indexed files → drop the graph retriever; falling back to lexical retrieval as the universal safety net if nothing else is supported). This check uses only O(1) metadata already computed by the Context Extractor and never traverses the repository, preserving the stage's sub-2ms latency budget.

**Explicitly not decided at this stage:** anything about how a retriever actually fetches results. The router's output is a plan, not an execution.

## 19. Retrieval Modules *(planned — design proposal, not yet implemented)*

Four retriever kinds are enumerated in `RetrieverKind` (`LEXICAL`, `GRAPH`, `DENSE`, plus `API` and `STATIC_ANALYSIS` reserved for future work) and must each implement a shared retriever interface (**to be added as `tara.interfaces.retriever.Retriever`**) with a single method taking `(query: str, plan: RetrievalPlan, context: RepositoryContext) -> RetrievedContext`.

- **`LexicalRetriever`** — exact/keyword search over source text (candidate approach: BM25 over a pre-built inverted index of symbol source spans; index-build strategy **TBD**, to be decided during implementation, candidates include building the index eagerly during context extraction vs. lazily on first lexical query). Consumes `TaskClassification.extracted_keywords` / `detected_symbols` preferentially over the raw query string.
- **`DenseRetriever`** — cosine-similarity search over `RepositoryContext.embeddings` using a FAISS index built over those vectors (index-build timing **TBD**: eagerly during context extraction, given `context.embeddings` is already fully computed at that point, is the current leading candidate). Embeds the query with the same `Embedder` used to build the context, injected identically to how `RepositoryContextExtractor` receives its embedder, to guarantee query/document embedding-space consistency.
- **`GraphRetriever`** — traverses `RepositoryContext.graph` from the nodes matched by `detected_symbols`/`detected_file_paths` (falling back to the top dense/lexical hits as seed nodes if no direct symbol match exists — **TBD, requires design during implementation**), to `RetrievalPlan.graph_depth`, optionally expanding neighbors per `RetrievalPlan.expand_neighbors`.
- **`APIRetriever`** and **`StaticAnalyzer`** — reserved by the existing `RetrieverKind` enum and by TARA's original architectural diagram, but **no design is committed in this document**; they are out of scope for the v1 research artifact (§8) unless a specific research need for them emerges during evaluation.

Each retriever must return results in a common `RetrievedContext` shape (candidate chunk, source location, retriever-internal score, retriever kind) so that Context Fusion (§20) can operate over heterogeneous retriever output without per-retriever special-casing. Execution ordering/parallelism is dictated entirely by `RetrievalPlan.execution_order` / `.parallel`; the retrieval orchestrator does not make its own scheduling decisions.

## 20. Context Fusion *(planned — design proposal, not yet implemented)*

Consumes one `RetrievedContext` per retriever that ran and the originating `RetrievalPlan`, and produces one `FusedContext`. Responsibilities:

1. **Deduplication** — candidate chunks that refer to the same underlying symbol (matched by node id, using the same id scheme already shared by the graph/symbol index/embeddings) are merged rather than duplicated, even when returned by more than one retriever.
2. **Reranking** — applied only when `RetrievalPlan.rerank` is true. **Candidate approach (TBD):** a lightweight cross-encoder reranking the union of candidates against the raw query; must be evaluated for latency impact before being made a hard default, given the pipeline's efficiency goals. A simpler fallback (weighted merge of normalized per-retriever scores) should be implemented first as a baseline reranking strategy, with the cross-encoder as an ablation variant (§26), not assumed superior a priori.
3. **Token budgeting** — chunks are ranked and truncated to fit a configurable maximum context-token budget (**value TBD**, must be chosen relative to the target generation model's context window and reported explicitly per experiment), with `FusedContext.truncated` recording whether truncation occurred, for later analysis of whether truncation correlates with generation quality loss.
4. **Formatting** — chunks are annotated with enough provenance (file path, symbol name, line range) to be both human-inspectable in logs/qualitative analysis and machine-parseable for prompt assembly in §21.

## 21. LLM Interface *(planned — design proposal, not yet implemented)*

A provider-agnostic interface (**to be added as `tara.interfaces.code_generator.CodeGenerator`**), deliberately mirroring the existing `Embedder` abstraction pattern already used in `tara.context.embedder` (an abstract `embed`/`embed_batch` contract with a concrete `SentenceTransformerEmbedder`): an abstract `generate(prompt) -> GeneratedCode` contract with one or more concrete provider implementations selected via `TaraSettings`.

**Prompt design (TBD, requires dedicated design work before implementation):** the prompt must include, at minimum, the original query, the `FusedContext` payload with provenance, and — as a deliberate ablation lever (§26) — optionally the `TaskClassification` itself (task type and routing reason), to test whether surfacing the classification to the LLM (not just using it to select context) provides additional benefit.

**Hard constraints:**
- No fine-tuning of the generation model (§8).
- Deterministic settings (e.g., `temperature=0`) should be used for any experiment where reproducibility of the exact output is claimed; where sampling is used, the number of samples and aggregation method must be pre-registered (§23).
- Provider, model identifier, and all generation parameters used for any reported result must be recorded in `GeneratedCode.metadata` and archived with the experiment configuration (§29).

## 22. Dataset Strategy

TARA's evaluation requires two distinct kinds of data, and the strategy differs for each:

**(a) Repository corpus.** A small, fixed set of real, permissively-licensed open-source repositories, selected to span TARA's supported languages (§7) and a range of sizes. **ASSUMPTION:** initial selection should prioritize repositories already used by an existing benchmark (candidate: repositories underlying CodeRAG-Bench or a comparable existing repository-level benchmark) to maximize comparability and to avoid the cost of building a new repository corpus from scratch. **Final repository list is TBD and must be finalized and frozen (with pinned commit SHAs) before any reported experiment**, to guarantee reproducibility.

**(b) Task-Intent Query Set (TIQS) — a new, small-scale contribution proposed by this project.** No existing benchmark known to the authors labels queries with an explicit task-intent taxonomy matching §17. TIQS is proposed as a modest (**target size TBD, proposed initial target: 300–600 queries**, subject to revision based on annotation throughput) human-annotated set of realistic developer queries against the frozen repository corpus, each labeled with: (i) a `TaskType` ground-truth label, (ii) a ground-truth relevant-context set (file paths and/or symbol ids), used for retrieval-quality metrics (§25), and, where feasible, (iii) a reference or acceptable-output description usable for generation-quality metrics.

**Annotation protocol (proposed, requires finalization before data collection):**
- Queries authored by at least two independent annotators per repository, drawing on realistic developer scenarios (issue-tracker-style requests, code-review comments, onboarding questions) rather than synthetically generated from the taxonomy itself, to avoid circularity between the classifier's rule vocabulary and the evaluation labels.
- Each query double-labeled for `TaskType`; inter-annotator agreement must be reported (**Cohen's κ, target ≥ 0.6 treated as acceptable, below that requires taxonomy or guideline revision before proceeding**).
- Disagreements adjudicated by a third annotator or by discussion, with the adjudicated label used as ground truth.
- Ground-truth relevant-context sets constructed by the annotator with reference to the actual repository (not from memory), and spot-checked by a second annotator on a random sample (**sample fraction TBD, proposed 20%**).

**This entire dataset-construction effort is a project deliverable in its own right (§30) and a prerequisite for RQ1–RQ3; none of §23–§26 can be executed against real numbers until TIQS (or an equivalent existing labeled resource, if one is identified during the literature-verification pass in §4) exists.**

## 23. Experimental Design

**Design type:** within-subjects comparison across system variants, evaluated on the same fixed query set (TIQS) and the same fixed, pinned repository corpus, so that all variants are compared on identical inputs.

**Independent variable:** system variant — TARA (full), each named baseline (§24), and each ablation configuration (§26).

**Controlled variables:** the generation LLM and its parameters (held constant across all variants within a given experimental run, so that only the *retrieval/routing* mechanism differs — this is essential to isolate TARA's contribution per §4's non-overclaiming requirement); the repository corpus and commit SHAs; the token budget available to the fused context; the embedding model, when a variant uses dense retrieval.

**Dependent variables:** the metrics in §25, computed per query and aggregated per `TaskType` and overall.

**Repetitions and stochasticity:** classification and routing are deterministic and require no repetition. Retrieval is deterministic given a fixed index. Generation, if run at non-zero temperature, requires **n ≥ 3 samples per query (exact n TBD, to be fixed before the first reported experiment and held constant thereafter)** with mean and confidence interval reported; if run at `temperature=0`, a single sample is sufficient but this must be stated explicitly wherever results are reported.

**Statistical testing:** paired comparisons between TARA and each baseline on the same query set, using a paired non-parametric test (**candidate: Wilcoxon signed-rank test**, appropriate given metric distributions are not assumed normal) with a pre-registered significance threshold (**α = 0.05, Bonferroni or Holm correction across the family of baseline comparisons — exact correction method TBD but must be fixed before running the comparisons**, not chosen post hoc).

**Environment reporting:** hardware (CPU/GPU, if any used for embedding/reranking), software versions (pinned per §13/§29), and LLM provider/model/parameters must be reported for every experimental run that produces a number appearing in the paper.

## 24. Baselines

- **B0 — No retrieval.** The LLM generates directly from the query with no repository context. Establishes the floor.
- **B1 — Fixed semantic-only.** Every query routed to `SEMANTIC_ONLY` regardless of classification (equivalent to disabling the Task Classifier and Router entirely and hard-coding the router's default fallback). Represents the dominant existing-practice retrieval strategy this project's motivation (§2) argues against.
- **B2 — Fixed full-pipeline.** Every query routed to `FULL_PIPELINE` regardless of classification. Represents "retrieve everything, always," isolating whether task-aware *selection* (as opposed to simply having more retrieval modalities available) is where TARA's value, if any, comes from.
- **B3 — Random routing.** Strategy selected uniformly at random from the 7-member `RoutingStrategy` space per query, as a sanity-check lower bound distinguishing "routing helps" from "any routing looks better than a naive baseline by chance."
- **B4 — AIRCoder (reproduction).** **Status: contingent on public code/artifact availability, TBD.** If a reproducible implementation is not available, this baseline is replaced by a best-effort re-implementation of its retrieval strategy as described in its publication, explicitly labeled as a re-implementation (not a reproduction) in any reported comparison, or omitted with the omission justified in the paper's limitations section.
- **B5 — RepoFormer-style dense retrieval.** **Status: TBD**, same reproducibility caveat as B4.
- **B6 — AllianceCoder-style ensemble retrieval.** **Status: TBD**, same reproducibility caveat as B4; likely to closely resemble B2 if AllianceCoder's ensemble strategy is non-adaptive, in which case B2 may substitute for it with that equivalence stated explicitly.

**Explicit acknowledgment:** faithful reproduction of external systems (B4–B6) is a known project risk (§28) and is treated as best-effort. The core scientific claims (H1–H5) do not depend on successfully reproducing any external system; B0–B3 alone are sufficient to test H1–H5, and B4–B6 are included for contextualization against related work, not as a requirement for publication.

## 25. Evaluation Metrics

**Classification quality (RQ1/H1):** macro-F1 and per-class F1 against TIQS `TaskType` labels; confidence calibration via Expected Calibration Error (ECE) and a reliability diagram; Spearman correlation between `confidence` and per-query classification correctness.

**Retrieval quality (RQ2/H2):** Precision@k, Recall@k, and Mean Reciprocal Rank against TIQS ground-truth relevant-context sets, for k values matching each variant's actual `top_k` (comparisons must be made at matched k, or k must be held constant across variants and stated explicitly). NDCG reported where a graded-relevance judgment is feasible (**TBD, depends on whether TIQS annotation captures graded relevance or only binary relevance — decide during §22 annotation-protocol finalization**).

**Generation quality (RQ3/H3):** exact match and an edit-similarity metric (**candidate: normalized Levenshtein or token-level edit distance, exact choice TBD**) against a reference where one exists; syntactic validity (parses without error, checked via the same Tree-sitter infrastructure already used by the Parser stage — a natural reuse, not a new dependency); pass@k **conditionally in scope**, computed only for the subset of TIQS queries (if any) drawn from a source benchmark that already provides an executable test harness, per the §8 constraint against building a new sandboxed executor.

**Efficiency (RQ4/H4):** wall-clock latency per stage (parsing and context extraction reported once per repository, amortized; classification and routing per query, already unit-tested against their respective <10ms/<2ms budgets; retrieval and fusion per query, budget **TBD, to be set once §19–§20 are implemented and profiled**); retrieval cost proxies (number of retriever invocations, number of embedding calls, total tokens retrieved and total tokens sent to the LLM).

**Explainability (RQ5, exploratory):** human or LLM-judge rating (**protocol TBD, requires future validation**) of whether a routing `reason` string, shown alongside the query and the selected strategy, is judged sensible/justified by an independent rater; inter-rater agreement must be reported if this evaluation is run, using the same annotation-agreement standard as §22.

## 26. Ablation Studies

- **A1 — No Task Classifier / no Router** (equivalent to B1, listed here as an ablation as well as a baseline, since it isolates the entire routing layer's contribution in one step).
- **A2 — Router without the REFACTOR override.** Tests whether `FullPipelinePolicy`'s task-type-based exception (§18) contributes measurably, versus routing REFACTOR queries purely by their raw classification flags.
- **A3 — Router without graph retrieval available** (graph retriever disabled at the retrieval layer regardless of what the plan requests, forcing the planner's context-capability-downgrade path). Tests the value of graph retrieval specifically.
- **A4 — Fixed top-k across all strategies** (disables the planner's per-strategy top-k differentiation, §18). Tests whether strategy-specific result-count tuning matters independent of strategy selection itself.
- **A5 — No reranking** (`rerank` forced false regardless of plan). Isolates reranking's contribution within Context Fusion.
- **A6 — Cross-encoder reranking vs. simple score-merge reranking** (§20). Two variants of A5's complement, compared against each other.
- **A7 — Classification-confidence threshold sweep.** Varies the confidence threshold at which TARA defers to a fallback strategy (e.g., `SEMANTIC_ONLY`) instead of trusting a low-confidence classification, sweeping the threshold and reporting the resulting quality/coverage trade-off. **Note:** this requires a fallback mechanism not yet present in the implemented Router (§18 has no confidence-based fallback today) — implementing this ablation requires a small, explicitly-scoped extension to the Router, to be treated as part of the evaluation-harness work, not a silent change to the production routing logic.
- **A8 — Embedding model swap.** Repeats the dense-retrieval-involving conditions with an alternative embedding model (**candidate TBD**) to check sensitivity of results to the specific embedding model choice.
- **A9 — Surfacing `TaskClassification` to the LLM prompt vs. not** (§21). Tests whether the classification itself is a useful generation-time signal beyond its use in retrieval.

## 27. Threats to Validity

**Internal validity:** TIQS labels are produced by a small number of annotators (§22) and may encode annotator bias toward the taxonomy's own vocabulary, especially if annotators are also the taxonomy's authors — the annotation protocol's use of independent annotators and inter-annotator agreement reporting is the primary mitigation, but residual bias should be assumed and disclosed. The rule-based classifier's keyword sets were authored with the same taxonomy in mind and may be tuned, consciously or not, toward that taxonomy's boundary cases; this is a known circularity risk that TIQS's independent-annotator protocol is specifically designed to detect (a classifier that only performs well on its own author's mental model of the taxonomy, but poorly against independently-annotated data, would surface as a low F1 in §25).

**External validity:** results are obtained on a small, fixed repository corpus and a fixed query set; generalization to repositories of substantially different size, language mix, or domain (e.g., heavily configuration-driven repositories, monorepos, or repositories with unconventional naming conventions that defy the classifier's naming-convention heuristics, §17) is not established by this study design and must be stated as a limitation, not inferred. The rule-based classifier's language-mention and naming-convention heuristics are English/Latin-alphabet-centric by construction; behavior on non-English queries or non-Latin identifier naming conventions is untested and should be explicitly out of claimed scope.

**Construct validity:** retrieval metrics (Precision/Recall/MRR) are a proxy for "useful context," not a direct measure of generation quality; H2 and H3 are deliberately kept as separate, both-tested hypotheses specifically so that a retrieval-quality improvement is not assumed to imply a generation-quality improvement without direct evidence. Edit-similarity and exact-match metrics for generation quality are known to be imperfect proxies for functional correctness; pass@k, where available, is the preferred metric and its conditional availability (§25) should be treated as a genuine limitation of the study, not glossed over.

**Conclusion validity:** the ablation and baseline comparisons in §24/§26 constitute a sizeable family of statistical comparisons; the multiple-comparisons correction specified in §23 is mandatory, and any result not surviving correction must be reported as such rather than selectively omitted. TIQS's target size (§22, 300–600 queries) is modest by NLP-benchmark standards and statistical power for smaller per-`TaskType` subgroup analyses (13 task types) may be limited; per-subgroup results with small n must be reported with explicit sample sizes and should not be over-interpreted.

## 28. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| External baseline systems (AIRCoder, RepoFormer, AllianceCoder) are not reproducible from public artifacts | Medium–High | Medium | Best-effort re-implementation with explicit labeling, or principled omission with justification (§24) |
| TIQS annotation throughput is slower than planned, delaying all downstream experiments | Medium | High | Start annotation early, in parallel with §19–§21 implementation; treat TIQS target size as adjustable (§22) rather than fixed |
| LLM API cost or rate limits constrain the number of generation-stage experiments/ablations that can be run | Medium | Medium | Prefer `temperature=0` single-sample runs where the hypothesis permits; budget API spend explicitly before running the full ablation matrix (§26) |
| The rule-based classifier's coverage/accuracy on real (non-synthetic) queries is materially lower than on the queries used during its own unit-test development | Medium | High (directly threatens H1) | TIQS is deliberately constructed from realistic, non-taxonomy-derived queries specifically to surface this risk early (§22) |
| The REFACTOR override (§18) or other hand-authored routing exceptions do not generalize and are effectively overfit to the five illustrative examples used during development | Medium | Medium | A2 ablation (§26) directly tests this; result must be reported honestly regardless of outcome |
| Hybrid/graph retrieval does not outperform a strong dense-only baseline, i.e., the core hypothesis is falsified | Low–Medium | High (but scientifically valid) | The study design (§23) is constructed to produce a valid, publishable negative result if this occurs; this is not treated as a project failure mode, only as a possible finding |
| Tree-sitter grammar/version drift across the eight supported languages causes parsing regressions | Low | Low–Medium | Pin `tree-sitter`/`tree-sitter-languages` versions (§13); parsing already has unit-test coverage that would catch regressions |
| Scope creep into building a full retrieval-augmented coding *product* rather than a research artifact | Medium | Medium | §8 (Out of Scope) is treated as binding; any expansion requires an explicit PROJECT_SPEC.md revision, not ad hoc implementation |

## 29. Milestones

**ASSUMPTION:** durations below are engineering-effort estimates for a small team (1–3 engineers) and are explicitly provisional; they are not commitments and should be revisited once §19 implementation begins.

| Milestone | Scope | Status |
|---|---|---|
| M1 | Repository Parser (`tara.parsing`) | **Done** |
| M2 | Repository Context Extractor (`tara.context`) | **Done** |
| M3 | Task Classifier (`tara.classification`) | **Done** |
| M4 | Task-Guided Adaptive Router (`tara.routing`) | **Done** |
| M5 | Retriever interface + `LexicalRetriever` + `DenseRetriever` | Planned, next |
| M6 | `GraphRetriever` + retrieval orchestrator (sequential/parallel execution per plan) | Planned |
| M7 | Context Fusion (dedup, score-merge rerank baseline, token budgeting) | Planned |
| M8 | LLM Interface + at least one provider implementation + prompt templates | Planned |
| M9 | Repository corpus finalized (pinned commits) + TIQS v1 annotation complete + inter-annotator agreement reported | Planned |
| M10 | Baselines B0–B3 implemented against the composition root (§16); B4–B6 attempted, status resolved (reproduced / re-implemented / omitted) | Planned |
| M11 | Full evaluation harness (`tara.evaluation`) producing all §25 metrics; H1–H5 tested with statistical results | Planned |
| M12 | Ablations A1–A9 executed and reported | Planned |
| M13 | Paper draft complete; all reported numbers traceable to an archived, reproducible experiment run (§30) | Planned |
| M14 | Camera-ready: code, TIQS, and reproducibility artifacts publicly released | Planned |

## 30. Deliverables

1. The open-source `tara` library (`src/tara`), MIT-licensed (per existing `LICENSE`), covering all implemented and planned stages.
2. This document, `PROJECT_SPEC.md`, maintained as a living specification.
3. `README.md`, maintained as the user/developer-facing quickstart and status summary (already maintained per-milestone in the existing repository).
4. The Task-Intent Query Set (TIQS): queries, `TaskType` labels, ground-truth relevant-context sets, and the annotation protocol/guidelines used to produce them, released as a standalone artifact.
5. All experiment configurations, seeds, and result files backing every number reported in the paper, organized so that any reported number can be regenerated by re-running a single named script against a pinned environment.
6. A pinned dependency specification (already present via `pyproject.toml`; to be supplemented with a full lockfile before M9) sufficient to reconstruct the exact software environment used for reported experiments.
7. The paper manuscript itself (`paper/`), with figures generated programmatically from the same result files released in (5), not hand-edited.
8. A minimal FastAPI demonstration service (`tara.api`), explicitly framed as a demonstration artifact, not a production deliverable (§8).

## 31. GitHub Branching Strategy

- `main` is protected: no direct pushes. All changes land via pull request.
- Library feature work uses `feat/<stage>-<short-description>` branches (e.g., `feat/retrieval-lexical`), scoped to a single pipeline stage or cross-cutting concern per branch, mirroring the milestone structure in §29.
- Bug fixes use `fix/<short-description>`.
- Research/evaluation work that does not modify `src/tara` uses `research/<short-description>` branches (e.g., `research/tiqs-annotation-round-1`), kept separate from library feature branches so that exploratory evaluation-script churn never blocks or conflates with library review.
- Every milestone in §29 that reaches "Done" is tagged (`v0.<milestone-number>`) at the merge commit that completes it, so that any later experiment can pin its environment to a specific milestone's exact code state.
- Pull requests require: passing CI (lint, type-check, full test suite), and a self-review checklist (or peer review, if team size permits) confirming adherence to §14 and §32 before merge. This applies uniformly regardless of team size; a solo contributor still performs and records the checklist pass.
- No experiment result is reported in the paper from a branch that has not been merged to `main` and tagged; uncommitted or unmerged code must never be the source of a reported number.

## 32. Coding Standards

These standards are already in force for the implemented stages and must be applied identically to all planned stages:

- Full type hints on every function/method signature and every class attribute; the codebase must remain mypy-clean under the project's configured (strict) settings.
- Every public class has a docstring stating its responsibility; every public function/method has a docstring stating its behavior, arguments, return value, and the exceptions it can raise. Docstrings explain *why* non-obvious design decisions were made where relevant, not merely *what* the code does when that is already evident from naming.
- Ruff-clean under the project's configured lint rules; no lint suppressions without an inline justification comment.
- SOLID principles, with Dependency Inversion (§14) treated as the most architecturally important of the five for this project's multi-stage pipeline shape.
- All collaborators are constructor-injected (§14); no stage or component instantiates a default dependency it does not own the decision to construct in a way that cannot be substituted by a caller or a test.
- Public inter-stage contracts are Pydantic models; internal, ephemeral value objects may be frozen dataclasses. Raw dicts/tuples are not used as public contracts.
- Exceptions are raised through the project's typed exception hierarchy (`tara.core.exceptions`), never as bare `Exception`; new stages that need a new failure mode add a narrowly-scoped subclass rather than reusing an unrelated existing one or introducing an untyped error path.
- No dead code, no commented-out code blocks, no placeholder implementations left silently in place — an unimplemented planned component is represented by its absence (and its status in this document), not by a stub that appears functional but is not.

## 33. Documentation Standards

- `README.md` is kept current with every completed milestone, documenting each implemented stage's responsibility, its concrete implementation(s), and its test coverage, consistent with the existing pattern already established in the repository.
- `PROJECT_SPEC.md` (this document) is the authoritative source for research design, architecture, and scope; any pull request that changes architecture, scope, or research design must update this document in the same PR.
- **Architecture Decision Records (ADRs), proposed as a new practice** under `docs/adr/`: a short, dated record for any decision that (a) deviates from or extends this specification, or (b) resolves one of this document's marked TBD items (e.g., the final choice of lexical-search library in §19, the final reranking strategy in §20, the final LLM provider(s) in §21). Each ADR states the decision, the alternatives considered, and the reasoning, so that the eventual paper's methodology section can cite a precise, dated record rather than relying on institutional memory.
- Docstrings follow the style already established in the codebase (a summary line; `Args`/`Returns`/`Raises` sections for anything non-trivial); this document does not mandate a specific tool (e.g., Sphinx) for rendering docstrings, and adopting one is left as an open, non-blocking decision.
- Paper-writing content lives in `paper/` and is treated as a separate documentation stream from code documentation; figures embedded in the paper must be generated by a script under `evaluation/` or `scripts/` and regenerable from released result files (§30), never hand-drawn or manually edited after generation.

## 34. Testing Strategy

- Every implemented library stage has unit tests that are deterministic, isolated, and require no network call and no live external model — already the pattern in place (context-extraction tests mock the `Embedder`; classification and routing tests never load an ML model). This pattern is mandatory for the planned retrieval, fusion, and generation stages as well: retrieval tests must not require a live FAISS build over a real corpus or a live LLM call (mock the embedder/LLM client, as already done for `Embedder` in `tara.context`); generation-stage tests must mock the LLM provider interface.
- Integration tests spanning two adjacent stages (e.g., classifier → router, already present in the codebase, running the real classifier against the real router) are encouraged wherever the combination is cheap and deterministic, to catch contract drift between stages; they are not a substitute for each stage's own isolated unit tests.
- Performance-budget tests are required for every stage with a stated latency budget: classification (<10ms, already tested) and routing (<2ms, already tested) must remain covered by an explicit timing assertion in CI; retrieval and fusion budgets (§19–§20, values TBD) must gain equivalent timing assertions once those budgets are set.
- A minimum coverage target is set at **85% line coverage for `src/tara`** (measured via `pytest-cov`), enforced in CI. This target explicitly does **not** apply to `evaluation/`, `scripts/`, or `paper/`, which are held to a lighter standard (must run without error against a small fixture; full unit-test coverage is not required) consistent with §14's research-code/library-code separation.
- Evaluation-harness correctness (metric implementations in particular) is tested against small, hand-computed synthetic examples (e.g., a metric implementation is tested against a toy retrieval result with a known-by-hand Precision@k value) before being trusted to produce numbers for the paper — this is treated as a testing requirement, not an optional nicety, because a bug in a metric implementation would silently invalidate reported results.
- No CI job depends on a live LLM API key or incurs API cost; any test that would otherwise require one is either mocked or explicitly marked and excluded from the default CI run.

## 35. Future Extensions

Explicitly deferred beyond the v1 research artifact, listed to distinguish "not yet done" from "considered out of scope forever":

- A learned (fine-tuned or few-shot LLM-based) task classifier, evaluated as a direct comparison against the rule-based classifier described in §17, rather than as its replacement — motivated directly by the A7-style confidence analysis and by RQ1's framing as a feasibility question, not a final-answer question.
- Call-graph and inheritance-graph resolution (the `CALLS`/`INHERITS`/`IMPLEMENTS` edge types already reserved but unpopulated in `tara.context.models.EdgeRelation`), enabling genuinely multi-hop graph retrieval rather than the current containment/definition/import structure only.
- Multi-hop, iterative, or agentic retrieval (deciding to retrieve again based on an intermediate result), explicitly excluded from v1 (§8) but a natural next research direction once single-pass task-aware routing has been evaluated on its own terms.
- Cross-repository retrieval (e.g., retrieving from a shared internal library repository referenced by, but not contained in, the target repository).
- Additional language grammars beyond the current eight, gated on Tree-sitter grammar availability and on evidence of research or user demand.
- Cost-aware and budget-constrained routing, where the router optimizes not only for expected retrieval quality but for a stated latency or dollar-cost budget per query.
- An active-learning loop where low-confidence or misrouted queries (identified via the confidence-calibration analysis in §25) are used to iteratively refine the rule taxonomy or, eventually, to construct training data for the learned-classifier extension above.
- A production-grade API/service layer with authentication, multi-tenancy, and horizontal scaling — the planned `tara.api` (§12) is explicitly a demonstration artifact, not a foundation this extension is assumed to build directly on without redesign.

## 36. Expected Contributions

Stated conservatively, consistent with this document's requirement not to exaggerate novelty:

1. **An open-source, modular reference implementation** of a repository-level code-generation pipeline with an explicit, independently-testable stage for task-intent classification and retrieval-strategy routing, released alongside the paper. The individual stages (parser, context extractor, classifier, router) are also usable independently of the full pipeline, given their strict Dependency-Inversion-based decoupling (§9–§11).
2. **An explicit, small, closed taxonomy of repository-level developer task intents** (§17) and, contingent on successful execution of §22, **a released, human-annotated evaluation resource (TIQS)** labeled against that taxonomy — proposed as a reusable evaluation resource for future work on this problem, independent of whether TARA's own routing approach proves beneficial.
3. **A deterministic, fully-explainable routing algorithm** (§18) as a concrete, evaluable alternative point in the design space to both (a) always-fixed retrieval strategies and (b) opaque, learned routing — with the explicit, falsifiable empirical question of whether this approach's simplicity and explainability come at an acceptable, or no, cost relative to the alternatives, tested via H1–H5.
4. **An empirical study** (§23–§26) directly comparing task-aware adaptive routing against task-agnostic retrieval baselines on matched inputs, reporting quality, efficiency, and (exploratorily) explainability outcomes — including, honestly, the possibility of a null or negative result on some or all of H1–H5, which this specification treats as a valid and reportable scientific outcome, not a project failure.

**This project explicitly does not claim:** state-of-the-art code-generation accuracy (the generation model itself is an off-the-shelf, unmodified LLM); a solved or general task-intent taxonomy for software engineering (§17's taxonomy is a specific, documented design choice, not asserted to be complete or universally optimal); or definitive superiority over AIRCoder, RepoGraph, RepoFormer, AllianceCoder, or STALL+ absent a successful, faithful reproduction of each (§24, §28) — comparisons to these systems, where reproduction is not achievable, will be presented as qualitative architectural comparisons only, clearly distinguished from empirical results.
