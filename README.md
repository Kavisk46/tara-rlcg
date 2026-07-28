# TARA — Task-Aware Adaptive Retrieval Architecture

TARA is a repository-level code generation framework that uses explicit
software-engineering task understanding to guide adaptive retrieval
before code generation, instead of retrieving context with a single
fixed strategy regardless of what the developer is actually trying to
do.

## Pipeline

```
Developer Query
      │
      ▼
Repository Parser            ← implemented
      │
      ▼
Repository Context Extractor ← implemented
      │
      ▼
Task Classifier               ← implemented (this increment)
      │
      ▼
Task-Guided Adaptive Router   ← planned
      │
      ▼
┌───────────────┬───────────────┬───────────────┬────────────────┐
│ Graph Retriever│ Dense Retriever│ API Retriever │ Static Analyzer│  ← planned
└───────────────┴───────────────┴───────────────┴────────────────┘
      │
      ▼
Context Fusion                ← planned
      │
      ▼
LLM                           ← planned
      │
      ▼
Generated Code
```

## Repository layout

```
tara-rlcg/
├── pyproject.toml
├── .env.example
├── src/
│   └── tara/
│       ├── core/                  # config, logging, exceptions, shared types
│       ├── interfaces/            # abstract contracts for each pipeline stage
│       ├── parsing/                # Repository Parser stage (implemented)
│       ├── context/                # Repository Context Extractor stage (implemented)
│       └── classification/         # Task Classifier stage (implemented)
└── tests/
    ├── parsing/
    ├── context/
    └── classification/
```

Each pipeline stage lives in its own subpackage of `src/tara/`, depends
on the stage(s) before it only through an `abc.ABC` interface in
`tara.interfaces`, and is unit-testable in isolation. This is Dependency
Inversion applied at the pipeline level: the Task Classifier depends on
`tara.interfaces.context_extractor.ContextExtractor`, never on a
concrete extractor implementation, and the upcoming Task-Guided Adaptive
Router will depend only on `tara.interfaces.task_classifier.TaskClassifier`
— so every implementation can be swapped or mocked freely.

## Implementation status

### Repository Parser (`tara.parsing`) — implemented

Turns a path to a repository on disk into a `ParsedRepository`: a
language-aware structural fact-base (files, symbols, imports) built by
walking each file's Tree-sitter concrete syntax tree. This is the
foundation every later stage builds on — the Context Extractor will
build a code graph from it, the Task Classifier will use it to detect
which files a query concerns, and the retrievers will index it.

- `tara.interfaces.repository_parser.RepositoryParser` — the abstract
  contract (one method: `parse(repository_path) -> ParsedRepository`).
- `tara.parsing.repository_parser.TreeSitterRepositoryParser` — the
  reference implementation, supporting Python, JavaScript, TypeScript,
  Java, Go, Rust, C, and C++.
- `tara.parsing.language_registry.LanguageRegistry` — file-extension to
  language detection plus a cached Tree-sitter parser per language.
- `tara.parsing.models` — the `ParsedRepository` / `ParsedFile` /
  `CodeSymbol` / `ImportStatement` data contracts, defined as Pydantic
  models so they validate at construction time and serialize cleanly
  for every downstream consumer (including a future FastAPI layer).

### Repository Context Extractor (`tara.context`) — implemented

Turns a `ParsedRepository` into a `RepositoryContext`: a directed graph
of Repository/File/Class/Function/Method nodes, a fast symbol index over
that graph, and (optionally) dense embeddings for every class, function,
and method. This is the semantic substrate the Task Classifier, the
Task-Guided Adaptive Router, and every retriever (graph, dense, API,
static analysis) will build on — none of them need to re-derive it from
a `ParsedRepository`. Nothing in this stage calls an LLM.

- `tara.interfaces.context_extractor.ContextExtractor` — the abstract
  contract (one method: `extract(parsed_repository) -> RepositoryContext`).
- `tara.context.extractor.RepositoryContextExtractor` — the reference
  implementation. Pure orchestration: it calls its three injected
  collaborators in order and assembles their outputs. It owns no graph,
  indexing, or embedding logic itself.
- `tara.context.graph_builder.GraphBuilder` — builds the `networkx.DiGraph`.
  Adds `Repository --contains--> File`, `File --defines--> Class/Function`,
  `Class --contains--> Method`, and a best-effort `File --imports--> File`
  edge for imports that resolve to another file in the same repository
  (per-language regex extraction + filename-stem matching; unresolved,
  external, and third-party imports are skipped rather than guessed at).
  `tara.context.models.EdgeRelation` additionally reserves `CALLS`,
  `INHERITS`, `IMPLEMENTS`, and `DEPENDS_ON` so later stages can extend
  this same graph in place instead of building a second one.
- `tara.context.symbol_index.SymbolIndex` / `SymbolIndexBuilder` — O(1)
  average-case lookup by node id, by symbol name, and by file path,
  built in one pass over the graph. Wraps its lookup dicts instead of
  exposing them.
- `tara.context.embedder.Embedder` — the abstract embedding-provider
  contract (`embed` / `embed_batch`), plus `SentenceTransformerEmbedder`
  (lazy-loaded, defaults to `BAAI/bge-small-en-v1.5`, configurable via
  `TaraSettings.embedding_model_name`). Swapping in OpenAI, VoyageAI, or
  any other provider means writing one new `Embedder` subclass.
- `tara.context.embedder.iter_embedding_inputs` /
  `RepositoryEmbedder` — assembles the text embedded for each symbol
  from its file path, name, signature, docstring, *and* source code
  (never just the name), and batches calls to the injected `Embedder`.
  A generator, so a large repository's source is never all held in
  memory at once; only classes, functions, and methods are embedded.
- `tara.context.models.RepositoryContext` — the Pydantic aggregate
  returned by the extractor (graph, symbol index, embeddings, and
  repository metadata), with a `graph_summary()` helper for the parts
  that need to be JSON-serializable (the graph and index themselves are
  arbitrary Python objects, not JSON — use `networkx.node_link_data` for
  the full graph on the wire).

All three collaborators are injected through
`RepositoryContextExtractor.__init__`, so tests substitute a fake/mock
`Embedder` and never load a real model.

### Task Classifier (`tara.classification`) — implemented

Analyzes a raw developer query and decides what kind of task it is,
which retrieval strategy is likely to serve it best, and what to
actually search for — all **without calling an LLM or any ML model**.
Classification is deterministic (the same query always produces the
same result) and cheap (every regex/keyword set is compiled once at
import time; a typical query classifies in well under 1ms). This is the
signal set the upcoming Task-Guided Adaptive Router and every retriever
will consume.

- `tara.interfaces.task_classifier.TaskClassifier` — the abstract
  contract (one method: `classify(query: str) -> TaskClassification`).
- `tara.classification.classifier.HeuristicTaskClassifier` — the
  reference implementation. Pure orchestration over two injected
  collaborators (a `FeatureExtractor` and a `RuleEngine`); it owns no
  regex, keyword-set, or rule logic itself.
- `tara.classification.heuristics` — every compiled regex and keyword
  set used anywhere in this stage, defined exactly once: tokenization,
  naming-convention predicates (`is_pascal_case`, `is_camel_case`,
  `is_snake_case`, `is_constant_case`, `is_acronym`), quoted-phrase
  extraction, file-path/extension detection, language-mention
  detection, and the per-task-type intent keyword sets (matched as
  exact tokens, never substrings or per-query regex).
- `tara.classification.features.FeatureExtractor` — turns a raw query
  into an immutable `QueryFeatures` bundle (tokens, detected symbols,
  detected file paths, extracted keywords, language hint) that every
  rule reads and none can mutate.
- `tara.classification.rules` — a small, isolated rule engine. Each
  `Rule` is a pure `QueryFeatures -> RuleVote | (nothing)` function with
  no visibility into other rules; `RuleEngine.evaluate` runs the fixed
  rule set (`DEFAULT_RULES`, injectable) once and returns every vote
  that fired. `HeuristicTaskClassifier` is the only place votes are
  combined — into a weighted `task_type` decision (ties broken by a
  documented priority order) and an OR over the `graph_required` /
  `semantic_required` / `lexical_required` / `reasoning_required` flags,
  which are in turn combined into one `RetrievalStrategy` recommendation
  (`HYBRID` whenever two or more flags are set).
- `tara.classification.models.TaskClassification` — the Pydantic result
  contract: `task_type` (`tara.core.types.TaskType`, 13 members —
  `SEARCH`, `EXPLAIN`, `DEBUG`, `BUG_FIX`, `REFACTOR`, `GENERATE`,
  `TEST`, `DOCUMENTATION`, `ARCHITECTURE`, `DEPENDENCY_ANALYSIS`,
  `SECURITY`, `PERFORMANCE`, `UNKNOWN`), `retriever_kind`
  (`tara.core.types.RetrievalStrategy` — `LEXICAL` / `SEMANTIC` /
  `GRAPH` / `HYBRID`, deliberately distinct from `RetrieverKind`, which
  enumerates concrete retriever *implementations* rather than a
  strategy), a `confidence` in `[0.0, 1.0]`, the four requirement flags,
  and the extracted keywords/symbols/file paths/language hint.

Both collaborators are injected through
`HeuristicTaskClassifier.__init__`, so a caller can supply a
domain-specific `RuleEngine` (e.g. with extra rules appended) without
touching this class, and tests can inject a single fake `Rule` to
exercise the combination logic in isolation.

### Planned next

1. **Task-Guided Adaptive Router** (`tara.routing`) — maps a
   `TaskClassification` to a weighted combination of retrievers.
2. **Retrievers** (`tara.retrieval`) — `GraphRetriever` (traverses
   `RepositoryContext.graph`), `DenseRetriever` (embeddings already in
   `RepositoryContext.embeddings` + FAISS), `APIRetriever`,
   `StaticAnalyzer`.
3. **Context Fusion** (`tara.fusion`) — merges retriever outputs into a
   single ranked context window under a token budget.
4. **Code Generator** (`tara.generation`) — prompts the configured LLM
   with the fused context and returns generated code.
5. **API** (`tara.api`) — a FastAPI service exposing the end-to-end
   pipeline.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"
pytest
```

Configuration is environment-driven; see `.env.example` for every
tunable (all have defaults, so no `.env` file is required to run the
test suite).
