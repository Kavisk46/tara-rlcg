# DESIGN_DECISIONS.md

## TARA: Architecture Decision Record

**Purpose.** This document records every major architectural decision made in the TARA project, in a consistent, comparative format: the decision itself, the problem it solves, the alternatives weighed against it, the pros and cons of the chosen option specifically, why it was selected over the alternatives, and how it could be replaced later without destabilizing the rest of the system. It supersedes the lighter-weight "ADR" practice proposed in `PROJECT_SPEC.md` §33 by consolidating decisions into one document rather than one file per decision; if per-decision files under `docs/adr/` are adopted later, this document should be treated as their initial content, split out rather than duplicated.

**Status convention.** Each entry states whether the decision is already implemented or design-only (pending implementation, per `ROADMAP.md`). A design-only decision is still a real, deliberated decision — it governs what will be built — but has not yet been validated by running code or by experiment.

---

## 1. Rule-Based Task Classifier

**Status:** Decided and implemented (`tara.classification`).

**Decision:** Classify a developer query into a task-intent category using a deterministic, hand-authored rule engine over lexical/orthographic query features — with no ML model and no LLM call — rather than a learned or LLM-prompted classifier.

**Problem:** The pipeline needs to classify a raw query into one of 13 task-intent categories cheaply, deterministically, and without confounding the project's central efficiency and explainability research questions, which depend on the classification step itself being negligible in cost relative to the retrieval/generation it gates.

**Alternatives Considered:**
- *LLM-prompted classification* (call an LLM to classify the query) — most flexible, but expensive in latency and cost, and even at `temperature=0` reintroduces a dependency on an external model into a stage the rest of the pipeline keeps fully local; would also make it impossible to cleanly attribute a later efficiency gain to routing rather than to classification overhead.
- *Fine-tuned small ML classifier* (e.g., a lightweight transformer or a TF-IDF/logistic-regression model) — requires a labeled training set, which did not exist at the start of the project (TIQS, `PROJECT_SPEC.md` §22, is itself a downstream deliverable, not a precondition) — a bootstrapping problem.
- *Embedding-based nearest-neighbor classification against labeled exemplars* — also requires labeled exemplars per category, adds a dependency on the embedding model to a stage that otherwise needs none, and is less directly explainable than exact rule attribution.
- *Deterministic rule engine* (chosen) — buildable with zero labeled data, fully explainable by construction.

**Pros:** measured latency under 10 ms (enforced by a dedicated test); fully deterministic and reproducible; every classification is auditable via `metadata.fired_rules`, directly supporting the explainability research question (RQ5); no model-serving, versioning, or GPU/CPU allocation burden; classifier development could proceed before any annotated dataset existed.

**Cons:** accuracy ceiling is bounded by hand-authored keyword coverage and cannot improve from data without manual rule authoring; brittle to phrasing outside the anticipated vocabulary; heuristics are English/Latin-identifier-centric by construction; the same people who authored the rules are, at least initially, also involved in evaluating the system, a circularity risk requiring the independent-annotator mitigation described in `PROJECT_SPEC.md` §22.

**Reason for Selection:** The classifier's own cost and quality needed to be a negligible, non-confounding factor relative to the research question of whether *explicit routing itself* is worth its complexity — using an LLM or a trained model here would have entangled "is the classifier good" with "does routing help," two separate questions this project needs to keep separable. A deterministic engine also let the rest of the pipeline (Router, and eventually Retrieval/Fusion/Generation) be developed and tested before any labeled dataset existed.

**Future Replacement Possibility:** Explicitly the top-priority future-work item (`CONTRIBUTIONS.md` §7, `PROJECT_SPEC.md` §35): a learned or LLM-based classifier should be built and compared head-to-head against this rule engine once TIQS exists, substituted purely through the existing `TaskClassifier` ABC with no change to any downstream stage.

---

## 2. Task-Aware Router

**Status:** Decided and implemented (`tara.routing`).

**Decision:** Select a retrieval strategy via a fixed, priority-ordered chain of isolated policies, evaluated in order, with the first applicable policy's decision winning — rather than a weighted-voting mechanism (as used by the classifier), a flat decision table, or a learned/ML-based router.

**Problem:** A `TaskClassification` (13 task types plus three independent boolean signals) must be mapped deterministically onto one of 7 `RoutingStrategy` values, with predictable, auditable conflict resolution when multiple signals are present simultaneously, and with room for a documented task-type-specific exception (the `REFACTOR` override).

**Alternatives Considered:**
- *Weighted voting*, reusing the classifier's own rule-engine pattern — unnecessary complexity for a decision this small (effectively 3 booleans plus one named override) and would require tuning weights for a target space that is already fully enumerable without them.
- *A flat lookup/decision table* mapping flag combinations to strategies — simple, but does not cleanly accommodate a task-type-conditioned exception without becoming an ad hoc special case bolted onto the table, and does not localize each decision rule as its own independently named, testable unit.
- *A learned/ML router*, trained on (classification, ideal strategy) pairs — no such labeled data exists, and building it would require running the very system this router is meant to enable first; also undermines the explainability goal a hand-authored, inspectable chain directly supports.
- *Priority-ordered policy chain, first-match-wins* (chosen) — every policy is independently named, independently testable, and conflicts are resolved by an explicit, version-controlled list order.

**Pros:** every routing decision traces to exactly one named policy; adding, removing, or reordering a policy requires no change to any other policy; the `REFACTOR` override is expressible as an ordinary policy condition, not a special mechanism; trivially supports the project's baseline-construction methodology (a fixed-strategy baseline is just an `AdaptiveRouter` constructed with a one-policy tuple).

**Cons:** policy list order is load-bearing, hidden "configuration" that must be curated carefully as policies are added — an easy thing to get subtly wrong; unlike a weighted or learned system, the current chain gives a low-confidence classification exactly the same treatment as a high-confidence one, with no graceful degradation built in (this gap is the explicit motivation for the A7 confidence-threshold ablation, `EXPERIMENT_PLAN.md` §5).

**Reason for Selection:** The routing decision space is small and fully enumerable, which makes a simple, fully-auditable dispatch mechanism both sufficient and preferable to a heavier alternative — consistent with the project's "deterministic and cheap before probabilistic and expensive" principle (`PROJECT_SPEC.md` §14), and it keeps the router's own internal decisions directly ablatable (A1, A2) rather than opaque.

**Future Replacement Possibility:** A confidence-gated fallback mechanism is already scoped as a near-term, small extension (A7). A learned strategy-selection function is conceivable once enough (classification, repository state, chosen strategy, downstream outcome) tuples exist from running full experiments, but is explicitly not planned before that data exists — building it earlier would repeat the same bootstrapping problem noted in Decision 1.

---

## 3. Repository Graph

**Status:** Decided and implemented (`tara.context.graph_builder`), with a stated, currently-unaddressed limitation.

**Decision:** Represent repository structure as an in-memory `networkx.DiGraph` populated only with containment, definition, and best-effort import edges — with call, inheritance, and implementation edge types reserved on the same schema but currently unpopulated — rather than a full static-analysis-derived call graph, a persisted graph database, or no graph at all.

**Problem:** Graph-based retrieval needs a structural representation of the repository, but building one must not require a heavyweight, language-specific static-analysis pass per one of the 8 supported languages, nor introduce an external graph-database service into a research prototype.

**Alternatives Considered:**
- *A full static-analysis-derived call graph* (actual resolved function calls, not just syntactic containment), per language — the most directly useful representation for the motivating "trace login flow" scenario, but requires a dedicated static analyzer per language, an engineering scope explicitly excluded from v1 (`PROJECT_SPEC.md` §8).
- *A persisted graph database* (e.g., Neo4j) — adds an external service, deployment, and licensing burden disproportionate to the corpus sizes targeted (≤200,000 LOC) and to the project's local-reproducibility goals.
- *No graph at all* — simplest, but eliminates the entire graph-retrieval strategy family (`GRAPH_ONLY`, `GRAPH_PLUS_SEMANTIC`, `LEXICAL_PLUS_GRAPH`, `FULL_PIPELINE`) central to the research question.
- *In-memory `networkx.DiGraph`, structural edges only, with an extensible edge-type schema* (chosen) — buildable directly from data the Repository Parser already extracts, with no additional analysis pass.

**Pros:** built directly from Tree-sitter output with no separate static-analysis infrastructure; fully in-process, no external service; `networkx`'s O(1) node/edge-count operations are exactly what the Router's context-capability check relies on; the `EdgeRelation` enum already reserves `CALLS`/`INHERITS`/`IMPLEMENTS`/`DEPENDS_ON`, so a future call-graph pass can populate the *same* graph object rather than requiring a second graph and a merge step.

**Cons:** without call-graph edges, graph retrieval cannot yet support genuine call/data-flow tracing — the single use case ("trace request flow") most associated with `GRAPH_ONLY` routing is only partially served today, by structural containment, not actual call relationships; import-edge resolution is a per-language regex-plus-filename-stem heuristic, not a real module resolver, and will miss or occasionally mis-resolve edges; scalability above the current corpus-size cap is unverified.

**Reason for Selection:** Building the graph purely from the parser's existing syntactic output kept the Context Extractor's cost and scope proportionate to what the current research question needs to test first — whether *having* a graph-retrieval option and routing to it adaptively is worth it at all — rather than over-investing in call-graph resolution before that more basic question has an answer.

**Future Replacement Possibility:** Explicitly reserved future work (`PROJECT_SPEC.md` §35, `ROADMAP.md` M7): populating `CALLS`/`INHERITS`/`IMPLEMENTS` on the same graph, via either a per-language static-analysis pass or a coarser same-file/same-import-graph heuristic, is the direct next step once the current, structurally-limited graph has been shown (or not) to make routing worthwhile.

---

## 4. Tree-Sitter Parser

**Status:** Decided and implemented (`tara.parsing`).

**Decision:** Use Tree-sitter, via `tree_sitter` and `tree_sitter_languages`, as the single parsing backend across all 8 supported languages, rather than 8 separate native per-language parsers, a regex-based extractor, or an LSP-server-based approach.

**Problem:** Structural facts (classes, functions, methods, imports, docstrings, byte/line spans) must be extracted consistently from source files across 8 languages, with one shared extraction algorithm, without maintaining 8 independent, differently-shaped parser integrations.

**Alternatives Considered:**
- *Native per-language parsers* (e.g., Python's `ast`, plus 7 other language-specific libraries) — most accurate per language, but requires 8 separate extraction code paths with different APIs and node vocabularies, and no shared symbol-extraction logic; behavioral inconsistency across languages would itself confound any cross-language comparison.
- *Regex-based structural extraction* — dependency-free and fast, but rejected outright: cannot reliably handle nested scopes, multi-line signatures, or keyword-like text inside strings/comments, and downstream correctness (graph edges, symbol ids, retrieval) depends on accurate spans.
- *LSP-server-based extraction* (running a language server per language, querying it for symbols) — the most semantically accurate option, but requires managing 8 separate server processes, is heavyweight for a research prototype, and provides type-level accuracy this stage does not need (semantic interpretation is explicitly a later stage's responsibility).
- *Tree-sitter, one consistent Python binding, all 8 languages* (chosen) — one shared extraction algorithm (a generic tree-walk keyed by a per-language node-type-to-`SymbolKind` table).

**Pros:** one consistent extraction algorithm and API surface for all 8 languages, not 8 separate ones; fast, in-process, no external server per language; mature, actively-used grammar bundle covering all 8 target languages; purely syntactic scope matches exactly this stage's stated responsibility, with no accidental over-reach into semantic analysis.

**Cons:** purely syntactic — cannot resolve cross-file call targets or type-driven relationships, which is precisely why the repository graph (Decision 3) currently lacks call-graph edges; the pinned `tree_sitter_languages` bundle already emits a deprecation `FutureWarning`, an early signal of version-drift maintenance risk; Python's grammar gives methods and functions the same node type, requiring the parser to infer "is this a method" from the parent node's kind rather than from a distinct node type, unlike JS/TS/Java.

**Reason for Selection:** Tree-sitter was the only candidate letting one shared pipeline cover all 8 languages without either an 8x per-language engineering burden or regex-level fragility — and its syntax-only scope is the *correct* scope for this stage, not an incidental limitation, given the project's explicit stage-responsibility separation (syntactic extraction here, semantic interpretation later).

**Future Replacement Possibility:** Not expected to be replaced; more likely to be supplemented — a future call-graph-resolution pass (Decision 3's future work) sits downstream of Tree-sitter's output, not in place of it. Grammar version pinning should be revisited periodically to manage drift risk; additional language support is bounded only by grammar availability (`PROJECT_SPEC.md` §35).

---

## 5. Sentence Embeddings

**Status:** Decided and implemented (`tara.context.embedder`), default model `BAAI/bge-small-en-v1.5`.

**Decision:** Produce dense symbol embeddings using a small, general-purpose, locally-run `sentence-transformers`-compatible model, accessed through an abstract `Embedder` interface, rather than a larger/higher-capacity model, a code-specialized embedding model as the default, or a hosted embedding API.

**Problem:** Dense/semantic retrieval needs vector representations of repository symbols, produced in a way that is optional (not mandatory for the rest of the pipeline to function), cheap enough to run repeatedly during development, and not tied to a single vendor.

**Alternatives Considered:**
- *A larger, higher-capacity embedding model* — likely better retrieval quality, but far more expensive to run at whole-repository symbol scale, disproportionate to a research prototype's compute budget and to the CPU-feasibility goal held for the framework's core stages.
- *A code-specialized embedding model as the default* — plausibly a better semantic fit for code specifically, but deliberately deferred to an explicit ablation variant (A8) rather than baked in as an unexamined default, so the default configuration stays a well-known, easily-reproducible baseline.
- *A hosted embedding API* — removes local compute cost, but introduces a network dependency, per-call cost, and rate limits into a stage the project otherwise keeps fully local, and would have broken the "never load a real model in unit tests" testing discipline used throughout.
- *No embeddings at all* — forecloses the entire `SEMANTIC`/`HYBRID`/`FULL_PIPELINE` strategy family.
- *A small, local, general-purpose model behind an abstract `Embedder` interface, embeddings optional and lazily loaded* (chosen).

**Pros:** small model size keeps CPU-only operation genuinely feasible; lazy loading means constructing a `RepositoryContextExtractor` never implicitly triggers a download or resource allocation; the `Embedder` ABC (`embed`/`embed_batch`) makes provider substitution a one-class change, already exercised in the test suite via a fake implementation that never loads a real model.

**Cons:** a general-purpose sentence-embedding model is not code-specialized and may under-perform a code-domain-tuned alternative on code-semantic similarity specifically — exactly what A8 is designed to test; smaller model size trades away some retrieval-quality ceiling for speed and cost; the default was chosen as a reasonable, defensible starting point, not validated as empirically optimal.

**Reason for Selection:** A small, local, general-purpose model kept this optional stage consistent with the rest of the framework's cost/latency discipline, avoided a network dependency in a stage run repeatedly during development, and — because the model is fully abstracted behind `Embedder` — is not architecturally load-bearing: the specific model choice is a swappable default, with the swap itself already a pre-registered experiment (A8), not an afterthought.

**Future Replacement Possibility:** Explicitly designed for replacement without architectural change — a code-specialized model, a larger model, or a hosted API each requires only a new `Embedder` subclass, the same pattern deliberately reused for the LLM Interface (Decision 9).

---

## 6. Dense Retrieval

**Status:** Design decided, implementation pending (`ROADMAP.md` M6).

**Decision:** Implement Dense Retrieval as a FAISS-backed nearest-neighbor index built over the already-computed `RepositoryContext.embeddings`, using the identical `Embedder` instance/model to embed the query at retrieval time — rather than a hosted/managed vector database, a brute-force linear scan with no index abstraction, or re-embedding documents at query time.

**Problem:** Dense retrieval needs an efficient nearest-neighbor search mechanism over potentially thousands of pre-computed symbol vectors, guaranteed to operate in the same vector space those vectors were produced in, without introducing a persistent external service.

**Alternatives Considered:**
- *A hosted/managed vector database* — offers scale and persistence, but introduces network dependency, cost, and operational complexity disproportionate to the target corpus scale (thousands, not millions, of vectors) and complicates local reproducibility.
- *A brute-force linear scan, no index* — simple and exactly accurate, and plausibly fast enough at target scale, but set aside in favor of FAISS's flat (exact) index, which is a strict superset of brute-force at negligible added complexity and leaves headroom to move to an approximate index later without an interface change.
- *Re-embedding documents at query time instead of reusing `RepositoryContext.embeddings`* — wasteful, since the Context Extractor already computed these once, and risks embedding-space inconsistency if a different code path were used for query vs. document embedding.
- *FAISS over existing embeddings, same `Embedder` instance for the query* (chosen).

**Pros:** FAISS is a mature, already-declared dependency (`faiss-cpu`) requiring no external service; reuses already-computed vectors rather than recomputing them; reusing the identical `Embedder` instance closes the query/document embedding-space-mismatch risk by construction, not merely by documentation.

**Cons:** FAISS's flat/exact index does not scale indefinitely, and an approximate-index variant is not yet planned; index-build timing (eager during context extraction vs. lazy on first query) remains an open, unresolved decision with different latency/staleness trade-offs; FAISS is a native-code dependency with its own platform/installation considerations.

**Reason for Selection:** At the corpus scale targeted by the initial evaluation, FAISS's simplest index mode already provides exact search at negligible overhead over brute-force, while leaving room to add approximate search later without changing the retriever's interface — deferring that complexity until there is evidence it is needed.

**Future Replacement Possibility:** Switching to an approximate FAISS index type for larger corpora is a parameter change, not an architectural one. A fully external/hosted vector database remains possible if cross-repository or persistent cross-session indexing becomes a requirement (`PROJECT_SPEC.md` §35), but is not currently justified by the project's single-repository, single-session scope.

---

## 7. Lexical Retrieval

**Status:** Design decided, implementation pending (`ROADMAP.md` M5); exact library **TBD**.

**Decision:** Implement Lexical Retrieval as a BM25-style ranked inverted-index search over repository symbol source text and identifiers, rather than unranked substring/grep matching, an external full-text search engine, or a sparse/TF-IDF variant folded into the dense-retrieval infrastructure.

**Problem:** The pipeline needs an exact/keyword-oriented retrieval mechanism, genuinely distinct from semantic similarity, specifically for queries where the classifier has flagged `lexical_required` (e.g., a query naming an exact symbol or acronym), and it must produce a ranked result respecting `RetrievalPlan.top_k`/`candidate_limit`.

**Alternatives Considered:**
- *Naive substring/grep matching, no ranking* — simplest and exact, but provides no relevance ordering across multiple matches, which the shared `RetrievedContext` contract requires every retriever to produce.
- *An external full-text search engine* (e.g., a hosted or self-hosted search service) — powerful, but a heavyweight external dependency wholly disproportionate to searching a single, already-in-memory repository, and complicates local reproducibility and CI testing, mirroring the reasoning against a hosted vector database in Decision 6.
- *A sparse/TF-IDF vector approach reusing the dense-retrieval index machinery* — architecturally tempting (one index abstraction for both retrievers), but conflates two conceptually distinct retrieval semantics behind one implementation, contrary to the project's principle of keeping each retriever narrow and independently ablatable.
- *BM25 over an in-process inverted index* (chosen).

**Pros:** BM25 is a standard, well-studied, parameter-light ranking function purpose-built for lexical relevance ranking, not just presence/absence matching; in-process, no external service; genuinely different retrieval semantics from dense retrieval, directly supporting the project's premise that different task types need different retrieval mechanisms, not variations on one mechanism.

**Cons:** exact library choice is unresolved (`EXPERIMENT_PLAN.md` §13 flags `rank_bm25` or an equivalent, pending license/performance evaluation); index-build timing is an open decision shared with Decision 6; a tokenizer mismatch between the Task Classifier's own tokenization and whatever the lexical index uses internally is a real, currently-unresolved risk that could silently degrade quality.

**Reason for Selection:** BM25 is the minimal-complexity, standard solution to "rank documents by lexical relevance," and serves exactly the role Lexical Retrieval is meant to play in TARA — a fast, exact-match-oriented complement to dense retrieval, not a general-purpose search-engine replacement.

**Future Replacement Possibility:** The BM25 implementation/library is swappable without changing the `Retriever` interface. A more sophisticated mechanism (fuzzy/edit-distance-tolerant matching for typo resilience, or a suffix-array/regex structure for pattern queries) could supplement or replace it if evaluation shows BM25's term-frequency model is a poor statistical fit for code identifiers specifically.

---

## 8. Context Fusion

**Status:** Design decided, implementation pending (`ROADMAP.md` M8).

**Decision:** Implement Context Fusion as a fixed three-stage pipeline — deduplicate by shared node id, then optionally rerank, then truncate to a token budget — with a simple weighted score-merge reranker shipped as the default and a cross-encoder reranker as an explicit, separately-evaluated ablation variant, rather than a single combined merge-and-truncate step, a learned end-to-end fusion model, or defaulting immediately to the cross-encoder.

**Problem:** Outputs from multiple, heterogeneously-scored retrievers (lexical, dense, graph) must be combined into one bounded, non-redundant context payload, without conflating "remove genuine duplicates," "reorder by relevance," and "fit a token budget" — three distinct concerns with three distinct correctness criteria.

**Alternatives Considered:**
- *A single combined merge-and-truncate step, no explicit reranking stage* — simplest, but provides no principled way to reconcile retrievers whose native scores are not on the same scale (a BM25 score and a cosine similarity are not comparable), risking a token budget spent on whichever retriever happens to produce numerically larger scores.
- *A learned, trained fusion/reranking model* — potentially the highest quality, but requires relevance-judgment training data that does not yet exist (the same bootstrapping problem as Decisions 1 and 2), and reintroduces a model-serving burden the project otherwise avoids where possible.
- *Defaulting immediately to a cross-encoder reranker* — plausibly higher quality, but its latency impact is unprofiled and could directly work against the project's efficiency research question (RQ4); adopting it as the unexamined default would confound that question.
- *Three separated stages, score-merge reranker as the default, cross-encoder as an ablation variant* (chosen).

**Pros:** deduplication, reranking, and truncation are each independently unit-testable against distinct correctness criteria; the reranker sits behind an abstract interface (mirroring `Embedder`), so reranking strategy is a swappable, ablatable decision, not an architectural commitment; the cheap default keeps the pipeline's base-configuration efficiency claims uncontaminated by an unvalidated, potentially expensive reranking step.

**Cons:** node-id-based deduplication will not catch near-duplicate-but-differently-keyed chunks (e.g., overlapping source spans reached via different retrieval paths) — an accepted, documented limitation, not a solved problem; token-budget truncation needs a tokenizer choice that must match the eventual generation LLM's own tokenizer to avoid systematic budget mis-estimation, and this matching is not yet mechanically enforced; three stages is more moving parts than one, trading simplicity for testability.

**Reason for Selection:** Context Fusion sits exactly where the project's efficiency and quality research questions are most easily confounded by an unexamined implementation choice (specifically, reranker cost) — the design deliberately keeps the cheap default and the more expensive alternative as two explicitly separate, both-evaluated options, consistent with the project's "deterministic and cheap before probabilistic and expensive" principle and its pre-registration discipline.

**Future Replacement Possibility:** The reranker interface already anticipates future variants — a learned fusion model is a natural longer-term candidate once labeled data exists from running the evaluation itself. The deduplication mechanism could move from exact node-id matching to fuzzier overlap detection if the near-duplicate limitation proves material during evaluation.

---

## 9. LLM Interface

**Status:** Design decided, implementation pending (`ROADMAP.md` M9); exact provider(s) **TBD**.

**Decision:** Define code generation behind an abstract `CodeGenerator` interface (`generate(prompt) -> GeneratedCode`), with at least two concrete provider implementations (one hosted API, one local/open-weight), deliberately mirroring the `Embedder` pattern (Decision 5), and explicitly excluding any fine-tuning of the generation model — rather than hard-coding a single provider, building an in-house generation model, or fine-tuning an existing one on TARA-specific data.

**Problem:** The generation stage must invoke an LLM without tying the project's findings to one vendor, must remain reproducible even if a hosted provider's model changes or is deprecated, and must keep the generation model a held-constant, controlled variable across every system-variant comparison rather than a moving part.

**Alternatives Considered:**
- *Hard-coding a single hosted provider inline* — simplest to write first, but ties every future comparison to that provider's availability, pricing, and versioning, and makes a future provider comparison a refactor rather than a substitution.
- *Fine-tuning an existing model on TARA-specific or repository-specific data* — could plausibly improve output quality, but explicitly excluded (`PROJECT_SPEC.md` §8) because it would confound the central research question: whether *retrieval/routing* improves outcomes holding generation capability constant. A fine-tuned model breaks that apples-to-apples comparison to task-agnostic baselines.
- *Building or training a custom in-house generation model* — entirely out of scope; would consume engineering and compute budget on a question orthogonal to the one under study.
- *A provider-agnostic `CodeGenerator` ABC, no fine-tuning, generation parameters pinned and disclosed per run* (chosen).

**Pros:** generation-model choice becomes a configuration decision, not an architectural one, directly supporting the requirement that it be held constant as a controlled variable (`EXPERIMENT_PLAN.md` §8); requiring a local/open-weight provider guarantees at least one fully reproducible experimental condition independent of any paid API's continued availability; reuses a pattern already validated by Decision 5, reducing design risk.

**Cons:** maintaining two provider implementations is more engineering effort than committing to one; a local/open-weight model may lag a frontier hosted model's raw capability, meaning "reproducible" and "highest-quality" may not be the same experimental condition, which the paper must state explicitly; prompt-template design remains a separate, currently unresolved decision likely to matter as much as provider choice itself.

**Reason for Selection:** Because TARA's contribution is about *what context is retrieved*, not *which LLM generates from it*, the generation stage needed to be the most deliberately unopinionated, swappable part of the pipeline — a provider-agnostic interface with pinned, disclosed parameters is a precondition for the paper's central TARA-vs-baseline comparisons to be valid at all.

**Future Replacement Possibility:** New providers are additive (a new `CodeGenerator` subclass), never a redesign. A future line of work studying the interaction between routing and generation-model fine-tuning would be a deliberate, separately-scoped extension of the research question, not a silent change to this decision's no-fine-tuning constraint.

---

## 10. Provider-Agnostic Design

**Status:** Decided and implemented as a standing cross-cutting pattern (demonstrated by `Embedder`; specified identically for `CodeGenerator`, Decision 9).

**Decision:** Wrap every third-party model or external service dependency behind a minimal, capability-specific abstract interface with externally-swappable concrete implementations, rather than allowing any pipeline stage to call a specific vendor's SDK inline, and rather than collapsing unrelated capabilities (embeddings, generation) into one shared interface.

**Problem:** Several pipeline stages depend on external, evolving, commercially-provided models whose availability, pricing, licensing, and quality can change independent of TARA's own code — and the research design needs to be able to substitute any of them for controlled comparison or ablation purposes (Decisions 5, 6, 9; ablations A8, A9) without modifying the stage that uses them.

**Alternatives Considered:**
- *Direct, inline provider SDK calls within each stage's core logic* — fastest to write, but ties correctness testing to network availability and API cost, violating the project's "no CI test depends on a live API key" discipline, and turns every future provider comparison into a refactor.
- *One generic "model client" interface shared across all external-model types* — over-generalizes two genuinely different capabilities (a fixed-dimension vector output vs. an open-ended text output) into one interface, likely forcing awkward, type-unsafe accommodations.
- *Configuration-only provider selection (an if/else on a config string, no formal interface)* — avoids defining an ABC, but gives tests no clean seam for injecting a fake implementation and gives future contributors no explicit contract to implement against.
- *One dedicated abstract interface per capability, concrete providers selected via dependency injection at the composition root* (chosen).

**Pros:** every external-model-dependent stage is testable with a fully deterministic fake, no network call, no model load — already demonstrated throughout the Context Extractor's test suite; provider substitution for future comparison work is additive, not a refactor; the pattern is now established once and repeated, reducing design risk each time a new external dependency needs wrapping (Decision 9 reused this pattern directly rather than inventing a new one).

**Cons:** adds one layer of indirection (an ABC plus at least one concrete class) for every external dependency, unnecessary overhead if a component genuinely never needs a second implementation; choosing the right minimal method surface up front requires real judgment (e.g., deciding `Embedder` needs both `embed` and `embed_batch` for throughput, not just the former) — getting this wrong early would force a later breaking interface change.

**Reason for Selection:** The evaluation methodology explicitly requires holding the embedding model and the generation model constant as controlled variables while separately ablating each (A8, A9), and requires no test suite depend on a live model — provider-agnostic design was a direct precondition for that methodology being executable, not an optional engineering nicety layered on top of it.

**Future Replacement Possibility:** A standing pattern, not a single decision subject to replacement — expected to be applied again to any future external dependency (a hosted vector database, per Decision 6; a cross-encoder reranking model, per Decision 8). Its main risk is a future contributor bypassing it under time pressure, a process/discipline risk rather than an architectural one.

---

## 11. Dependency Injection

**Status:** Decided and implemented as a standing cross-cutting pattern across all four implemented stages; specified identically for all planned stages.

**Decision:** Require every component with a collaborator to receive it through its constructor, with no component permitted to instantiate a default collaborator that is not also exposed as an overridable constructor parameter — rather than a global/singleton service locator, silent internal default-construction with no override path, or a full inversion-of-control framework.

**Problem:** The pipeline must support two things simultaneously: every stage testable in isolation without incurring the cost or nondeterminism of its real collaborators, and every stage's behavior substitutable for ablation and baseline construction (`EXPERIMENT_PLAN.md` §4–§5) without modifying that stage's source code.

**Alternatives Considered:**
- *A global/singleton service locator* — avoids verbose constructor signatures, but hides a component's actual dependencies from its own interface, and makes substituting a collaborator for one test or one experiment require mutating shared global state — rejected specifically because the project's testing discipline requires fully isolated, deterministic tests, and mutable global state is a direct source of test pollution and experiment cross-contamination.
- *Silent internal default-construction with no override path* — simplest call sites, but makes every override require monkeypatching or subclassing rather than passing an argument, directly undermining the ablation methodology, which depends on constructing variants purely through constructor arguments (e.g., baseline B1 is an `AdaptiveRouter` built with a restricted policy tuple, not a code fork).
- *A full inversion-of-control framework/container* — provides more machinery than the project's shallow, linear dependency graph actually needs; judged disproportionate to the wiring problem being solved.
- *Plain constructor injection, defaults allowed only as a documented, always-overridable convenience, no framework* (chosen).

**Pros:** every collaborator substitution the ablation program requires (disabling reranking, swapping the embedding model, restricting the policy set) is expressible as "construct this stage with different arguments," with zero source changes to the stage itself; every one of the existing 240 unit tests constructs its subject with fully controlled, often fake, collaborators, none depending on hidden global state; a constructor signature is a complete, honest declaration of what a component depends on.

**Cons:** constructor signatures for a stage with several collaborators are more verbose than a service-locator or auto-wired alternative; the composition root must know how to wire every stage correctly by hand, since no framework does it automatically — an accepted cost (`PROJECT_SPEC.md` §16 names the composition root as the one place required to know the full pipeline shape) rather than one solved with additional machinery.

**Reason for Selection:** The evaluation methodology fundamentally depends on constructing many pipeline *variants* without forking code, and constructor injection is the simplest mechanism making every such variant expressible as "different arguments to the same class." A heavier DI framework would solve a wiring-convenience problem the project's shallow dependency graph doesn't actually have; a service locator would actively work against the isolation and substitutability the experimental design requires.

**Future Replacement Possibility:** Not expected to change. If the dependency graph grows substantially deeper or more branching later (e.g., a multi-provider retrieval orchestrator with many optional collaborators), a lightweight wiring helper — not a full framework — might be introduced purely to reduce composition-root boilerplate, without altering the underlying principle that every dependency stays constructor-injected and explicit.

---

## 12. SOLID Architecture

**Status:** Decided and implemented as the project's governing architectural stance; Dependency Inversion specifically treated as primary among the five principles.

**Decision:** Structure the entire pipeline around one `abc.ABC` interface per stage, with every downstream stage and every piece of research/evaluation code depending only on these interfaces — never on a concrete implementation class — and treat Dependency Inversion as the single most architecturally important SOLID principle for this project, ahead of the other four.

**Problem:** A research framework whose central purpose is to support *comparison between alternative implementations of its own stages* (a learned classifier vs. a rule-based one; a cross-encoder reranker vs. a score-merge reranker; alternative routers for baseline construction) needs an architecture where swapping an implementation is a first-class, low-cost operation, not an incidental side effect of otherwise-tidy code.

**Alternatives Considered:**
- *A single monolithic pipeline module implementing all stages inline* — faster to write initially and easier to read end-to-end for one fixed configuration, but makes every baseline/ablation variant require duplicating or branching the whole pipeline instead of substituting one stage — directly working against the evaluation methodology.
- *Interfaces defined but not consistently depended upon* (concrete classes imported directly "for convenience" at some call sites) — a common real-world compromise, explicitly rejected as a project convention: every constructor parameter and every composition-root wiring point is typed against the interface, so depending on implementation-specific behavior becomes a type-level inconsistency, not merely a style lapse.
- *Applying all five SOLID principles with equal emphasis, none designated primary* — a defensible general default, but this project's own design principles (`PROJECT_SPEC.md` §14) name Dependency Inversion specifically as most important here, because it is the one principle whose absence would most directly break the ablation/baseline methodology.
- *One ABC per stage, strict interface-only cross-stage dependency, Dependency Inversion treated as primary* (chosen).

**Pros:** every stage substitution named anywhere in the project's roadmap (a future learned classifier, a future learned router, alternative rerankers, alternative embedding/LLM providers) is architecturally pre-authorized by an existing interface, not dependent on a future refactor; the pattern is uniform across all four implemented stages and specified identically for the remaining planned ones, so a new contributor or a paper reviewer encounters the same substitutability guarantee at every stage boundary.

**Cons:** with currently exactly one concrete implementation per interface, the interface layer can read as premature abstraction to someone unfamiliar with the project's methodology — a cost explicitly acknowledged in `PROJECT_SPEC.md` §14 ("every interface exists specifically to allow controlled substitution in tests and in future research variants," where the "second implementation" justifying each interface is an existing test fake or an explicitly planned future/ablation variant, not a hypothetical); still, the extra interface file and indirection is a real, if modest, cost paid at every stage regardless of whether that stage ever gets a second concrete implementation.

**Reason for Selection:** Because the project's two central research instruments — the ablation program and the baseline-construction methodology — both work by substituting a stage's implementation while holding everything else fixed, an architecture without strict Dependency Inversion at every stage boundary would have made the evaluation methodology itself more expensive and more error-prone to execute, not merely made the codebase less tidy. Treating this one principle as primary is a direct consequence of what the research design needs.

**Future Replacement Possibility:** A standing commitment, applied to every current and future stage, not a decision expected to be reversed. The risk to monitor is scope creep in what a given stage's interface should expose as new capabilities are added (e.g., a future confidence-gated Router extension, A7, needing a materially different method signature would require a deliberate, documented interface revision, not an ad hoc addition) — a governance concern about how interfaces evolve, not a reason to abandon the pattern.
