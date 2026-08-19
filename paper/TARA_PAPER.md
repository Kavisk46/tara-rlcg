# TARA: Task-Aware Adaptive Retrieval for Repository-Level Code Generation

**Status of this document.** This is a draft research paper describing TARA's implemented system and evaluation infrastructure as of the current state of the `tara-rlcg` repository. Consistent with the project's own pre-registration discipline (`EXPERIMENT_PLAN.md`) and non-overclaiming commitments (`CONTRIBUTIONS.md`), this draft distinguishes explicitly between (a) architecture and infrastructure that is implemented and tested, (b) hypotheses and research questions that are stated but not yet tested, (c) experimental observations, and (d) future work. **No experiment described in this paper's evaluation design has been executed against real data.** No section of this paper reports a fabricated, estimated, or interpolated number. Where a quantitative claim is made, it is a fact about the implemented system itself (e.g., a passing test count, a unit-test-enforced latency budget) and is labeled as such, never presented as an experimental research finding.

---

## 1. Abstract

Repository-level code generation systems typically retrieve context using a single, fixed mechanism — most commonly dense/embedding similarity search — regardless of what a developer's query is actually asking for. TARA (Task-Aware Adaptive Retrieval Architecture) is a research system that instead classifies a developer query's task intent using a deterministic, LLM-free rule engine, and uses that classification to select a retrieval strategy from a small, enumerable strategy space before any retrieval is executed. The system is implemented as a typed, dependency-inverted pipeline: repository parsing, repository graph/embedding construction, task classification, adaptive routing, multi-modal retrieval (lexical, dense, graph), context fusion, and LLM-based generation. All eight stages are implemented and covered by a passing automated test suite. This paper describes that implementation, the evaluation infrastructure built to test it (a five-baseline comparison suite, eight implemented ablation configurations, a statistical-analysis layer with a protocol fixed before any result exists, and a schema for a purpose-built task-intent query dataset), and the paper's five research questions concerning classification feasibility, retrieval quality, generation quality, efficiency, and explainability. **No annotated evaluation dataset has yet been constructed, no baseline has yet been run, and no ablation has yet been executed against real data; consequently this paper reports no empirical result bearing on whether task-aware routing improves retrieval, generation, efficiency, or explainability outcomes.** All five research questions remain open. This paper's contribution is the system and the evaluation infrastructure that would be required to answer them, together with an explicit account of what remains to produce a first empirical result.

## 2. Introduction

Large language models are increasingly used to generate and modify code inside existing repositories rather than in a blank-file setting. In this regime, output quality is bottlenecked less by raw generation capability than by whether the model is given the right context — the right function definitions, call sites, configuration, and prior art already present in the codebase. Most retrieval-augmented code generation systems address this with a single fixed retrieval mechanism per system, applied uniformly regardless of what the developer is actually trying to do.

TARA investigates a specific, narrow alternative: inserting an explicit, cheap, deterministic classification of a developer query's task intent — is this a search, an explanation request, a bug fix, a refactor, a new feature — before any retrieval occurs, and using that classification to select among a small set of retrieval strategies. The central design bet is that making this selection explicit and inspectable, rather than leaving it implicit inside a single fixed mechanism or an opaque learned system, is worth testing directly.

This paper's contribution is twofold. First, it describes an implemented system: an eight-stage, dependency-inverted pipeline covering repository parsing, context extraction, task classification, adaptive routing, multi-modal retrieval, context fusion, and generation, each stage independently interface-defined and unit-tested. Second, it describes an evaluation infrastructure built to test the system's central hypothesis: a five-baseline comparison suite with an enforced "router isolation" guarantee, eight implemented ablation configurations, a pre-registered statistical-analysis layer, and the schema for a purpose-built task-intent query dataset (TIQS). Neither the system nor the evaluation infrastructure has yet been exercised against real annotated data, and this paper says so plainly wherever that matters, rather than presenting infrastructure as if it were a result.

The remainder of this paper is organized as follows. Sections 3–6 define the problem, motivation, related work, and research gap. Sections 7–12 describe the implemented architecture stage by stage. Sections 13–15 describe the dataset design, experimental setup, and baseline suite. Section 16 restates the paper's five research questions. Sections 17–20 report — honestly, as currently empty — the results, ablation, efficiency, and explainability findings that this infrastructure is designed to eventually produce. Sections 21–22 discuss threats to validity and limitations. Sections 23–24 conclude and describe the reproducibility artifact this paper is accompanied by.

## 3. Problem Definition

Given (a) a source-code repository `R` and (b) a natural-language developer query `q` about that repository, the problem is to select a subset of repository context `C ⊆ R` to condition an LLM's code generation on, such that `C` maximizes the quality of the generated output for `q`, subject to constraints on retrieval latency and token budget.

The dominant existing instantiation of this problem embeds `q`, embeds chunks of `R`, retrieves the top-k by cosine similarity, optionally reranks, and generates — treating retrieval-strategy selection as a constant property of the system, independent of `q`. TARA reformulates this as a two-stage decision process: first classify `q` into an explicit task-intent representation `T(q)`, then select a retrieval strategy `S = f(T(q), R)` from a small, enumerable strategy space, then execute `S` to obtain `C`.

This reformulation raises two distinct sub-problems, addressed by two separate, independently-testable pipeline stages:

1. **Classification.** Can `T(q)` be estimated cheaply and reliably enough — without an LLM call — to serve as a useful routing signal?
2. **Routing.** Does conditioning retrieval strategy on `T(q)` produce a `C` that yields measurably better downstream outcomes than a strategy held constant across all `q`?

## 4. Motivation

A query like "find `parse_repository`" is best served by exact lexical/symbol lookup; dense retrieval over paraphrastic similarity is unnecessary overhead and risks retrieving semantically-similar-but-wrong symbols. A query like "trace the login flow" is fundamentally a graph-traversal problem over call/import/control relationships, not a similarity-search problem. A query like "refactor `RepositoryParser`" plausibly needs all three modalities at once: exact location, semantic understanding of intent, and a dependency map of blast radius. Treating all three queries identically wastes retrieval budget, can degrade precision, and — for a research artifact specifically — makes it difficult to explain why a given piece of context was retrieved.

An independent semantic analysis of six software-engineering task categories (bug fix, feature implementation, refactoring, API usage, documentation, and test generation), conducted separately from and prior to any routing-implementation work, identified concrete, category-specific differences in what context each task type actually needs and which retrieval failure modes are characteristic of it (for example: refactoring tasks are dominated by the need for *exhaustive* recall of exact-symbol occurrences, where a single missed call site is a correctness risk, whereas documentation tasks need only the *one* definition site plus design rationale). This analysis is a semantic reference document, not a routing specification — it does not by itself demonstrate that automated task-aware routing improves outcomes, but it does establish that the underlying premise (different task types have different, task-specific retrieval needs) is at least a defensible, articulable claim independent of TARA's own implementation, rather than an assumption invented solely to justify the system's design.

TARA's motivating premise is that a cheap, explicit, upstream classification step can make retrieval-strategy decisions instead of leaving them implicit inside a single retrieval model, or leaving them to a human to hand-tune per query.

## 5. Related Work

The following systems are named in this project's internal planning documents as addressing adjacent problems. **These characterizations have not been independently re-verified against current publications as part of drafting this paper**, and should be read as the project's own working understanding rather than as a freshly conducted literature review; a literature-verification pass was planned but has not been performed (see Section 21).

- **AIRCoder** — adaptive/iterative retrieval for repository-level completion; understood, within this project's planning, as the closest prior system to TARA's motivation, with its routing signal believed to be derived primarily from retrieval-internal signals (e.g., retrieval confidence, iterative refinement) rather than from an explicit, human-readable task-intent taxonomy computed before any retrieval occurs. This is the specific distinction TARA's design is intended to test, and it is treated in this project as an unconfirmed assumption pending direct comparison, not an established fact.
- **RepoGraph** — constructs a repository-level dependency graph for retrieval/context construction. TARA's context-extraction stage performs a related but narrower graph-construction step (structural containment/definition/import edges; call-graph and inheritance-graph edges are reserved in the schema but not yet resolved) and treats the graph as one of several retrieval modalities selected by the router, not the sole retrieval mechanism.
- **RepoFormer** — repository-level code completion with retrieval, understood as primarily dense-retrieval-centric; serves as a natural conceptual analog to a fixed semantic-only retrieval baseline.
- **AllianceCoder** — collaborative/ensemble retrieval-augmented code generation; a natural conceptual analog to always combining every available retriever without task-conditioning.
- **STALL+** — a comparison point for retrieval-augmentation strategy design in code LLMs generally; its exact mechanism is explicitly unverified in this project's own documentation and would require a dedicated literature review before any baseline design could rely on it.
- **CodeRAG-Bench** — a benchmark and analysis of retrieval-augmented code generation across multiple retrieval strategies; the most directly reusable prior work for this project's evaluation methodology and metric selection, treated as a methodological reference rather than a system to reproduce.

## 6. Research Gap

Within the scope of the systems named in Section 5 as currently understood by this project, none is known to perform an explicit, deterministic, pre-retrieval classification of query task-intent into a fixed taxonomy, and to use that classification to select among a small enumerable set of retrieval-strategy combinations in a way that is fully inspectable — every routing decision TARA produces carries a machine-generated natural-language `reason` string identifying which policy decided the strategy and why. This is stated as the project's working understanding of the gap, **subject to the literature-verification pass noted in Section 5 and Section 21 as not yet performed**, and it is a claim about system design — explicit, inspectable, pre-retrieval task classification driving strategy selection — not a claim of superior end-task accuracy, which is precisely the open empirical question this paper's infrastructure (Sections 13–20) is built to test and has not yet tested.

## 7. TARA Architecture

TARA is implemented as one Python package (`tara`), organized as one subpackage per pipeline stage plus two cross-cutting subpackages, following a strict Dependency Inversion discipline: every stage depends only on the abstract interface of the stage before it, never on a concrete implementation, and every stage's collaborators are constructor-injected rather than internally instantiated. All eight pipeline-relevant subpackages listed below are implemented and covered by an automated test suite (Section 24); no stage described in this section is a design proposal.

```
Developer Query
      │
      ▼
Repository Parser              (tara.parsing)
      │
      ▼
Repository Context Extractor   (tara.context)
      │
      ▼
Task Classifier                (tara.classification)
      │
      ▼
Task-Guided Adaptive Router    (tara.routing)
      │
      ▼
┌────────────────┬────────────────┬────────────────┐
│Lexical Retriever│ Dense Retriever│ Graph Retriever │
└────────────────┴────────────────┴────────────────┘
      │
      ▼
Context Fusion                 (tara.fusion)
      │
      ▼
Code Generator                 (tara.generation)
      │
      ▼
Generated Code
```

Each stage consumes the immediately preceding stage's typed output and produces a new typed output; no stage reaches backward into an earlier stage's internals. Inter-stage contracts are Pydantic models, validated at construction and serializable; internal, ephemeral value objects (e.g., a single routing rule's vote) may be frozen dataclasses, but raw dictionaries are never used as public inter-stage contracts.

**Correction relative to this project's own specification document.** `PROJECT_SPEC.md` — this project's living architecture specification — describes retrieval (`tara.retrieval`), context fusion (`tara.fusion`), and generation (`tara.generation`) as "planned, not yet implemented" design proposals, and its own milestone table marks the corresponding milestones (M5–M8) as "Planned." That status is stale relative to the code actually present in the repository at the time this paper was drafted: all three stages exist as concrete packages (`src/tara/retrieval/`, `src/tara/fusion/`, `src/tara/generation/`) with passing tests. This paper describes the system as actually implemented, not as `PROJECT_SPEC.md`'s own currently-unrevised status table describes it; `PROJECT_SPEC.md` itself states that it should be revised in the same pull request as any material architecture change, and that revision had not yet occurred as of this paper's drafting.

A single node-id scheme (`build_file_node_id` / `build_symbol_node_id`) is used consistently across the repository graph, the symbol index, the embedding store, and every retrieved-context/ground-truth representation downstream, so that a given code symbol is trivially correlatable across every representation of it in the system without a translation layer.

## 8. Task Classification

The Task Classifier (`tara.classification`) consumes only the raw query string — it does not consume repository context, and its output is required to be identical for the same query string regardless of which repository it will later be routed against. This is a deliberate design choice, not an incidental property: it allows classification to be tested and reasoned about independently of any specific repository, and it is reflected directly in the test suite, which never constructs a repository context object to test the classifier.

The classifier is a deterministic rule engine — it calls no LLM and uses no trained ML model at inference time. This is a load-bearing design decision for three stated reasons: it keeps classification cost negligible relative to the eventual LLM generation call, so that any measured efficiency effect of routing is not confounded by classifier cost; it makes every classification fully explainable by construction, since the classifier's metadata records exactly which rules fired; and it establishes a transparent, reproducible reference point before any future work introduces a learned classifier, which is itself treated as a fair comparison to make later, not as an implicit admission that the rule-based approach is a placeholder.

**Taxonomy.** A closed, 13-member `TaskType` enumeration: `SEARCH`, `EXPLAIN`, `DEBUG`, `BUG_FIX`, `REFACTOR`, `GENERATE`, `TEST`, `DOCUMENTATION`, `ARCHITECTURE`, `DEPENDENCY_ANALYSIS`, `SECURITY`, `PERFORMANCE`, `UNKNOWN`. This taxonomy is hand-authored and is believed, but not validated against a large-scale corpus of real developer queries, to cover the majority of realistic repository-level developer queries.

**Internal pipeline.** (1) *Feature extraction* tokenizes the query and extracts probable code symbols by naming convention (PascalCase, camelCase, snake_case, CONSTANT_CASE, bare acronyms), probable file paths/filenames, quoted literal phrases, stop-word-filtered keywords, and a best-effort programming-language mention. (2) *Rule evaluation* runs an ordered set of isolated, pure-function rules, each of which may cast a weighted vote for a `TaskType` and/or assert one or more of four boolean retrieval-requirement flags (`graph_required`, `semantic_required`, `lexical_required`, `reasoning_required`); rules never observe each other's output. (3) *Combination*, performed only by the classifier itself, selects the task type with the highest summed vote weight (ties broken by a fixed, documented priority order), computes `confidence` as the winning type's share of total vote weight, and combines the four boolean flags by logical OR across all fired rules.

**Measured, unit-test-enforced property.** Classification latency is covered by a dedicated timing-assertion test enforcing a sub-10-millisecond budget. This is a fact about the implemented component under test, not a claim about performance at production or corpus scale.

A separate, six-category semantic taxonomy (Section 4; `docs/task_taxonomy.md`) exists alongside `TaskType` for a different purpose — articulating retrieval-relevant task semantics independent of any routing implementation — and is deliberately not reconciled with `TaskType` in the current system; that reconciliation is unresolved and is listed as future work (Section 22).

## 9. Adaptive Routing

The Adaptive Router (`tara.routing`) consumes both a `TaskClassification` and a repository context object and produces an executable `RetrievalPlan`: which retriever kinds to run, in what order, sequentially or in parallel, at what candidate-pool size, whether to rerank, and, where applicable, graph traversal depth. The router performs no retrieval itself.

**Taxonomy.** A closed, 7-member `RoutingStrategy` enumeration: `LEXICAL_ONLY`, `SEMANTIC_ONLY`, `GRAPH_ONLY`, `HYBRID`, `GRAPH_PLUS_SEMANTIC`, `LEXICAL_PLUS_GRAPH`, `FULL_PIPELINE`. This is a strict refinement of the classifier's coarser 4-value `retriever_kind` recommendation; the router may reach a different, more specific conclusion than the classifier's coarse recommendation, and the classifier's original recommendation is preserved in the resulting plan's metadata for observability rather than discarded.

**Decision procedure.** A fixed, ordered tuple of policy objects (`FullPipelinePolicy → GraphPolicy → HybridPolicy → LexicalPolicy → SemanticPolicy`) is evaluated in order; the first policy whose applicability predicate returns true decides the strategy. Policy order is itself the conflict-resolution mechanism: more specific policies are listed first, and the semantic policy is an unconditional catch-all listed last. Each policy is a pure function of the classification alone; policies never observe the repository context or each other, and every routing decision carries a natural-language `reason` string identifying which policy fired and why.

**The `REFACTOR` override.** One policy additionally fires whenever the task type is `REFACTOR`, independent of the three boolean flags, selecting the most thorough retrieval strategy regardless of the raw classification signals — justified by the argument that safely refactoring a known symbol requires locating it exactly, understanding its purpose, and mapping everything that depends on it, simultaneously. This is explicitly a hand-authored design hypothesis, not a learned or empirically-derived one, and its correctness is precisely the kind of question this project's ablation design (Section 18, A2) exists to test — it has not yet been tested.

**Planning.** A separate `RetrievalPlanner` component (never itself a policy) converts a policy's coarse strategy decision into an executable plan: deduplicating retriever kinds, ordering them cheapest-first, setting parallel execution whenever more than one retriever kind is selected, setting rerank whenever execution is parallel or the classification's `reasoning_required` flag is set, assigning a strategy-specific default `top_k`, and assigning graph depth/neighbor-expansion together whenever a graph retriever participates. The planner is also the single place that checks whether the concrete repository context can actually support a policy's recommendation — for example, dropping the dense retriever if no embeddings have been computed, or dropping the graph retriever if the graph is trivial — using only cheap, already-computed O(1) metadata, never a repository traversal, preserving the stage's latency budget. This separation — policies decide *what* strategy, the planner decides *how* to execute it — is architectural, not incidental: it means an ablation that changes only top-k behavior (Section 18, A4) or only reranking behavior (A5) can be implemented as a planner variant without touching policy logic at all.

**Measured, unit-test-enforced property.** Routing latency is covered by a dedicated timing-assertion test enforcing a sub-2-millisecond budget.

## 10. Retrieval Modules

Three retriever kinds are implemented (`tara.retrieval`), each executing against a `RetrievalPlan` and a repository context:

- **Lexical retriever** — keyword/exact-match retrieval over a BM25 index built over indexed symbol source spans.
- **Dense retriever** — cosine-similarity search over the repository context's precomputed embedding vectors, using the same injected embedding model used to build those vectors at context-extraction time, so that query and document embeddings are guaranteed to share an embedding space.
- **Graph retriever** — traversal of the repository graph from nodes matched by the classifier's detected symbols/file paths, to the routing plan's specified graph depth, with optional neighbor expansion.

An orchestrator executes the retriever kinds named in a given plan according to that plan's specified execution order and parallelism, and does not make its own scheduling decisions — scheduling is entirely dictated by the router (Section 9). Each retriever returns results in a common shape (candidate chunk, source location, retriever-internal score, retriever kind), so that context fusion (Section 11) can operate over heterogeneous retriever output without per-retriever special-casing.

A fourth and fifth retriever kind (`API`, `STATIC_ANALYSIS`) are reserved in the system's `RetrieverKind` enumeration and in the project's original architectural diagram but have no implementation and no committed design; they remain out of scope for the current system.

## 11. Context Fusion

Context Fusion (`tara.fusion`) consumes one retrieved-context object per retriever that ran, plus the originating retrieval plan, and produces a single fused context payload. The pipeline is: **deduplication** (candidate chunks referring to the same underlying symbol, identified via the shared node-id scheme, are merged rather than duplicated, even when returned by more than one retriever) → **score merge** (a weighted average of normalized per-retriever scores; this is the currently implemented reranking baseline) → **optional rerank** (applied only when the plan's `rerank` flag is set) → **top-k cut** → **token-budget cut**, with the resulting object recording whether truncation occurred, to support later analysis of whether truncation correlates with quality loss.

**Explicitly not implemented.** A cross-encoder reranker was proposed in this project's design documents as an alternative to the score-merge baseline (intended to be evaluated, not assumed superior a priori). No `CrossEncoderReranker` component exists in the current codebase. Any ablation or comparison contingent on a cross-encoder reranker (Section 18, A6) is consequently unsupported by the current implementation, not merely unexecuted.

## 12. Generation Pipeline

The generation stage (`tara.generation`) is defined by a provider-agnostic `CodeGenerator` abstract interface, mirroring the same injected-abstraction pattern already used for embeddings in the context-extraction stage. A `PromptBuilder` assembles a prompt from the fused context, the original query, and — as a deliberate, switchable ablation lever — optionally the task classification itself, via two named prompt templates: `BASELINE` (task classification omitted) and `WITH_TASK_CLASSIFICATION` (task type and routing reason surfaced to the prompt). This directly implements the ablation described in Section 18 (A9) as configuration, not as a source-code fork.

**The only implemented `CodeGenerator` is `FakeCodeGenerator`.** No real LLM provider is integrated, and no API credentials for any LLM provider are configured anywhere in this project. `FakeCodeGenerator` exists specifically so that the generation stage's interface, prompt assembly, and downstream harness plumbing (Section 14) can be exercised deterministically in unit tests, with no network call, no API cost, and no nondeterminism — consistent with this project's stated testing discipline that no test may depend on a live model or a live network call. It does not produce code of any interesting quality, and no result in this paper is based on its output being representative of a real LLM's behavior. Consequently, **no claim about end-to-end generation quality can currently be made**, and none is made anywhere in this paper.

## 13. Dataset / TIQS

TARA's evaluation design specifies two distinct kinds of data: a fixed corpus of real repositories, and the Task-Intent Query Set (TIQS) — a purpose-built, human-annotated set of developer queries labeled with task-intent and ground-truth relevant context, proposed because no existing benchmark known to this project's authors labels queries against an explicit task-intent taxonomy matching Section 8's thirteen-category scheme.

**Current status: schema only.** A TIQS data model and validation logic exist (`evaluation/tiqs/`), together with a documented schema (`TIQS_SCHEMA.md`) and a schema example, and this schema is covered by unit tests confirming that a well-formed record validates and a malformed one is rejected. **Zero real annotated queries currently exist.** No repository corpus has been selected or pinned to commit SHAs, no annotation guideline has been piloted, and no inter-annotator agreement figure exists, because no annotation has occurred.

The design this schema is built against (documented in `DATASET_PLAN.md`, refining `PROJECT_SPEC.md` §22 and `EXPERIMENT_PLAN.md` §1–§2) specifies: a target of 480 queries stratified across the 13 `TaskType` categories (approximately 37 per category); a repository-level, not merely query-level, train/validation/test split, closing a specific leakage channel that a flat query-level split would not; double-blind `TaskType` labeling with third-annotator adjudication and a pre-registered Cohen's κ ≥ 0.6 acceptability threshold; ground-truth relevant-context sets keyed to the same node-id scheme used throughout the implemented system, verified to actually exist in the pinned repository before a query is accepted; and a spot-check protocol for relevant-context agreement using Jaccard similarity with a proposed (unvalidated) target of ≥ 0.5. None of this protocol has been executed. It is documented here as the design this project has committed to, not as a completed step.

A pre-existing, separately-scoped tree in this repository (`evaluation/rts_builder/`, and the associated `evaluation/experiments/ltr/` code) addresses a different, learning-to-rank-focused evaluation approach and predates TIQS's design; it is not part of TARA's evaluated system as described in this paper and is not drawn on for any claim in this paper.

## 14. Experimental Setup

An evaluation harness (`evaluation/harness/`) is implemented, orchestrating the full query → routing → retrieval → fusion → generation → metrics pipeline for a given query against a given system variant. Its design properties, all covered by unit tests: per-stage wall-clock latency is captured via `time.perf_counter()` around each stage boundary; a single query's failure (an exception in any stage) is isolated and does not abort the rest of a batch run; and a `Variant` abstraction (carrying, among other fields, an optional `router_factory`) allows a baseline or an ablation configuration to be substituted into the same harness without modifying the harness itself or any pipeline stage.

**No experimental run has been executed against real data.** The harness has been exercised only against synthetic, hand-constructed fixture data in its own test suite, specifically to verify the harness's own correctness (error isolation, latency capture, result aggregation) independent of any question about TARA's retrieval quality. Running the harness against TIQS and a real repository corpus to produce Table-ready results is not possible until Section 13's dataset work is completed and at least one real `CodeGenerator` implementation exists (Section 12); neither precondition is currently satisfied.

Per this project's experimental design (`PROJECT_SPEC.md` §23), the intended controlled variables across any future comparison are: the generation LLM and its parameters, held constant across all variants within a run so that only the retrieval/routing mechanism differs; the repository corpus and pinned commit SHAs; the token budget available to fused context; and the embedding model, for any variant using dense retrieval. The intended primary statistical procedure — paired Wilcoxon signed-rank tests between TARA and each baseline, with Holm–Bonferroni correction within each comparison family, BCa bootstrap confidence intervals (10,000 resamples), and rank-biserial effect sizes — is implemented and tested (Section 18, Section 21) but has, correspondingly, never been run against a real result set.

## 15. Baselines

Five baseline configurations are implemented (`evaluation/baselines/`), each constructed via `build_fixed_plan`, which builds a `RetrievalPlan` directly through the `RetrievalPlanner` fed a hand-built `RoutingDecision` — **never** through `AdaptiveRouter.decide()` or any `RoutingPolicy`. This "router isolation" property is enforced, not merely documented: a dedicated spy test asserts that `AdaptiveRouter.route()` is called exactly zero times for every baseline, individually and across a full baseline sweep. An earlier implementation constructed each baseline as an `AdaptiveRouter` with a single fixed-strategy policy, which behaved identically but was rejected during development specifically because it would still technically construct and call the real adaptive-routing machinery, which this project's own task instructions for baseline construction explicitly prohibit.

| ID | Configuration | Purpose |
|---|---|---|
| B0 | No retrieval — the generator receives no repository context | Absolute floor |
| B1 | Fixed semantic-only retrieval, classifier and router bypassed | Represents the dominant existing-practice retrieval strategy this project's motivation (Section 4) argues against |
| B2 | Fixed lexical-only retrieval | Isolates the lexical retriever's standalone contribution |
| B3 | Fixed graph-only retrieval | Isolates the graph retriever's standalone contribution |
| B4 | Always full-pipeline (lexical + semantic + graph, every query) | Isolates "more retrieval, always" from "adaptive selection of retrieval" |

**This numbering deviates from both of this project's own planning documents.** `PROJECT_SPEC.md` §24 and `EXPERIMENT_PLAN.md` §4 each define a different B2–B4 (a fixed full-pipeline baseline, a random-routing control, and either an AIRCoder reproduction or an oracle-retrieval upper bound, depending on which document). The deviation is disclosed in full, with a stated rationale, in `evaluation/baselines/BASELINE_DISCREPANCIES.md`; it is repeated here because it directly affects how any future Table 3-style result from this baseline suite should be read against this project's own specification documents. Neither a random-routing control (B3 in both planning documents) nor an oracle-retrieval upper bound (proposed in `EXPERIMENT_PLAN.md` §4) is implemented in the current baseline suite.

**B5/B6 (external system baselines) are explicitly unavailable, not merely unrun.** Both AIRCoder-, RepoFormer-, and AllianceCoder-style reproductions are marked `TBD` in this project's own planning documents, contingent on public artifact availability and a literature-verification pass that has not been performed. Constructing a "best-effort re-implementation" without first confirming a system's actual published methodology would mean attributing a retrieval strategy to a named external system without having verified it — a step this project's own instructions treat as indistinguishable from fabrication. This status is recorded machine-readably (`evaluation.baselines.definitions.UNAVAILABLE_BASELINES`), not only in prose, so that any future harness run can enumerate and report it without re-deriving the justification.

## 16. Research Questions

The following five research questions are this paper's confirmatory targets, restated exactly as posed. **All five are currently open.** No evidence, of any kind, bearing on any of them is reported anywhere in this paper.

- **RQ1 (Classification feasibility).** Can a repository-agnostic, LLM-free, rule-based classifier assign a useful task-intent label to a developer query with accuracy and confidence-calibration sufficient to drive downstream routing decisions?
- **RQ2 (Retrieval quality).** Does task-aware adaptive routing improve retrieval precision/recall/MRR over a fixed single-strategy baseline and a fixed always-hybrid/full-pipeline baseline, at matched or lower retrieval cost?
- **RQ3 (Generation quality).** Does context assembled via task-aware routing improve downstream code-generation quality relative to task-agnostic retrieval baselines, holding the generation model constant?
- **RQ4 (Efficiency).** Does task-aware routing reduce retrieval latency and/or retrieval cost relative to an always-full-pipeline strategy, without a statistically significant quality regression relative to the best-performing baseline?
- **RQ5 (Explainability).** Do the natural-language routing `reason` strings produced by TARA's policies correspond, under human or LLM-judge evaluation, to routing decisions that domain experts would independently endorse as sensible given the query?

Each research question is paired, in this project's specification (`PROJECT_SPEC.md` §6), with a specific, falsifiable hypothesis and a named statistical test (Section 14); RQ3 in particular is explicitly contingent on a real generation model, which does not currently exist in this system (Section 12), and RQ5 is explicitly exploratory, with no finalized human-evaluation protocol. Answering any of these five questions requires, at minimum, a completed TIQS annotation (Section 13) and at least one non-fake `CodeGenerator` implementation for RQ3 specifically; neither exists as of this paper.

## 17. Results

**No results are reported in this section, and none are implied elsewhere in this paper.** No baseline has been run against real data. No TIQS query has been annotated. No statistical comparison in Section 14's protocol has been executed against a real result set. Any table of Recall@10, MRR, exact-match, edit-similarity, or latency figures comparing TARA against B0–B4 would, at this stage of the project, necessarily be invented, and this paper does not invent one.

What exists instead is the infrastructure that would produce such a table: the metrics implementations described in Section 19 and Section 20, the baseline suite in Section 15, and the statistical-analysis layer in Section 18 and Section 21 — all implemented, all unit-tested against small, hand-computed synthetic examples with known-by-hand correct values, none yet pointed at a real dataset. Producing this section's content is future work (Section 22), contingent specifically on TIQS annotation (Section 13) and, for any generation-quality figure, on integrating a real `CodeGenerator` implementation (Section 12).

## 18. Ablation Studies

Eight of the nine ablations named in this project's specification (`PROJECT_SPEC.md` §26) have supporting configuration implemented in an ablation matrix (`evaluation/ablations/`, including a serialized `ablation_matrix.json`); one is explicitly unsupported by the current implementation, and none has been executed against real data.

| ID | Ablation | Implementation status |
|---|---|---|
| A1 | No Task Classifier / no Router | Implemented (equivalent to baseline B1, Section 15) |
| A2 | Router without the `REFACTOR` override | Implemented |
| A3 | Graph retrieval disabled | Implemented |
| A4 | Fixed top-k across all strategies | Implemented |
| A5 | No reranking | Implemented |
| A6 | Cross-encoder vs. score-merge reranking | **Not supported** — no `CrossEncoderReranker` exists (Section 11) |
| A7 | Classification-confidence threshold sweep | Implemented — required a small, explicitly-scoped extension to the router (a confidence-gated fallback not present in the router as originally specified) |
| A8 | Embedding model swap | Implemented as configuration |
| A9 | `TaskClassification` surfaced to LLM prompt vs. not | Implemented (Section 12's `BASELINE` / `WITH_TASK_CLASSIFICATION` prompt templates) |

The ablation matrix includes validation logic that rejects an accidental comparison between two runs that differ in repository, query set, LLM, token budget, or embedding model when those variables are supposed to be held fixed — implemented as an explicit configuration-consistency check, not left to manual discipline.

**No ablation result is reported.** Every row above describes what configuration exists and can, in principle, be run; none describes an outcome, because none has been run. As with Section 17, producing ablation results is contingent on the same unmet preconditions: a real TIQS dataset and, for any ablation touching generation (A9 in particular), a real `CodeGenerator`.

## 19. Efficiency Analysis

Two efficiency-relevant facts about the implemented system are real, measured, and reportable, and are reported here precisely because they are unit-test-enforced properties of the code, not experimental findings requiring TIQS or a real generator:

- **Task classification** is covered by a dedicated timing-assertion test enforcing a sub-10-millisecond budget.
- **Adaptive routing** is covered by a dedicated timing-assertion test enforcing a sub-2-millisecond budget.

These figures describe two specific, deterministic, CPU-only components in isolation, on whatever machine the test suite happens to run on; they are not end-to-end latency figures, they are not measured under any particular reference hardware disclosure (which this project's own experimental design requires for any reported comparative latency claim), and they say nothing about retrieval, fusion, or generation latency, none of which has a profiled budget, because none has been run against a real workload.

The efficiency metrics this project's evaluation design specifies — per-stage p50/p95/p99 wall-clock latency for retrieval and fusion, retriever-invocation counts, embedding-call counts, total tokens retrieved, and total tokens sent to generation — are implemented in the harness's metrics layer (`evaluation/metrics/efficiency.py`) and captured automatically whenever the harness runs a query. None of them has a reported value in this paper, because the harness has not been run against real data (Section 14), and because `FakeCodeGenerator` (Section 12) has no latency profile representative of a real LLM call, making any end-to-end figure computed against it meaningless as a proxy for real generation latency even if it were reported. **RQ4 (efficiency) is open** in the same sense as every other research question in this paper.

## 20. Explainability Analysis

Every `RetrievalPlan` produced by the router carries a `reason` field: a natural-language string, generated by the policy that decided the strategy, stating which policy fired and why. This is an architectural property of the system, verifiable by inspecting any routing decision's output, and it is what this project's design intends to make RQ5 answerable in principle — a routing decision is never a black box in the sense that no explanation exists for it.

That an explanation exists is not the same claim as that the explanation is *good* — sensible to an independent human or LLM judge, in the sense RQ5 actually asks. No evaluation protocol for judging `reason` strings has been finalized (this project's own specification marks the explainability evaluation protocol as requiring future validation before it can be treated as a primary metric), no rating has been collected, and no inter-rater agreement figure exists. **This paper reports no explainability finding.** The mechanism that would need to exist for RQ5 to be testable exists; the evaluation of it does not.

## 21. Threats to Validity

**Internal validity.** The classifier's rule set and TIQS's design taxonomy share the same authors and the same conceptual vocabulary; a classifier that performs well only against its own authors' mental model of the taxonomy, but poorly against independently-annotated queries, is a known circularity risk that TIQS's double-blind, independent-annotator protocol (Section 13) is specifically designed to detect once annotation actually occurs — it cannot detect anything before annotation occurs, which is the current state.

**External validity.** Any future result would be obtained on a small, fixed repository corpus (not yet selected) and a fixed query set (not yet annotated); generalization beyond that corpus's language mix, size range, and domain composition would not be established by this study design and would need to be stated as a limitation, not inferred. The classifier's naming-convention and language-mention heuristics are English/Latin-alphabet-centric by construction and are untested outside that setting.

**Construct validity.** Retrieval metrics (precision/recall/MRR) are a proxy for "useful context," not a direct measure of generation quality — this project's design deliberately keeps RQ2/RQ3 as separate, independently-tested questions specifically so a retrieval-quality result is never assumed to imply a generation-quality result without direct evidence. Edit-similarity and exact-match metrics for generation quality are known to be imperfect proxies for functional correctness; this project's metrics implementation includes an execution-based `pass@k` estimator function, but has no code-execution sandbox, so `pass@k` can only ever be computed on a subset of queries drawn from an external benchmark that already provides a safe execution harness — no such benchmark has been integrated.

**Conclusion validity.** The baseline and ablation comparisons specified in Sections 15 and 18 constitute a sizeable family of statistical comparisons; the Holm–Bonferroni correction implemented in this project's statistics layer (`evaluation/statistics/`) is applied automatically within each comparison family specifically to guard against this, but a correction procedure implemented and tested against synthetic data provides no protection until it is actually applied to a real result set, which has not occurred.

**Reproduction-dependent validity.** Any future comparative claim relative to an external system (Section 5) would only be as strong as the fidelity of its reproduction; since no such reproduction has been attempted (Section 15), this threat is currently moot but would apply immediately upon any future attempt.

**Specification-drift validity, specific to this project.** As documented in Section 7 and Section 15, this project's own specification documents (`PROJECT_SPEC.md`, `EXPERIMENT_PLAN.md`) are, in places, stale relative to the actually-implemented system (architecture status) or diverge from the actually-implemented system by deliberate choice with disclosed rationale (baseline numbering). A reader relying solely on the specification documents without cross-checking against this paper or the codebase would form an inaccurate picture of both what is implemented and what a given baseline ID means.

## 22. Limitations

Stated candidly, extending this project's own contributions-and-limitations statement (`CONTRIBUTIONS.md` §6) to the system's current, more advanced implementation state:

- **No empirical evidence exists yet for the central hypothesis or for any of the five research questions in Section 16.** This paper should not be read, and must not be cited, as evidence that task-aware routing works, or that it does not — only as evidence that a system and an evaluation infrastructure capable of testing whether it works have been built.
- **The two task taxonomies (the 13-member routing taxonomy and the 6-category semantic reference taxonomy) are hand-authored**, not derived from a large-scale corpus of real developer queries, and not validated against prior taxonomic work in software-engineering task modeling at scale. Their completeness, mutual exclusivity, and construct validity relative to how real developers actually phrase requests are unverified. Reconciling the two taxonomies is unresolved.
- **The classifier's rule-based design is a deliberate choice, not a demonstrated optimum.** This project shows that a cheap, deterministic classifier of this kind is implementable and testable; it does not show that this approach generalizes better, or worse, than a learned or LLM-based classifier, because that comparison has not been run.
- **No dataset has been annotated.** Zero real TIQS queries exist (Section 13). Every quantitative claim this project's evaluation design would eventually produce is contingent on this work being completed, and none of it has begun beyond schema definition.
- **No real LLM is integrated.** `FakeCodeGenerator` is the only implemented generator (Section 12); no claim about generation quality, and specifically no evidence bearing on RQ3, currently exists or can currently be made.
- **The baseline suite deviates from this project's own specification documents**, by deliberate choice with disclosed rationale (Section 15), and omits a random-routing sanity-check control and an oracle-retrieval upper bound that this project's own planning documents call for. Any future result should be interpreted with this substitution in mind.
- **External baseline reproduction (AIRCoder, RepoFormer, AllianceCoder) has not been attempted**, and a literature-verification pass confirming whether a reproducible public artifact exists for any of them has not been performed.
- **Generalization beyond a small, fixed, not-yet-selected repository corpus and the eight currently-supported languages is unverified**, and by design will remain so, since this project's scope explicitly excludes support for additional languages and cross-repository retrieval.
- **The `REFACTOR` routing override and any other hand-authored routing exception are stated design hypotheses**, justified by argument, not evidence, at the time of writing, pending the A2 ablation (Section 18), which is implementable but has not been run.
- **This project's own specification documents contain unresolved internal inconsistencies** (Section 21) between the architecture-status table in `PROJECT_SPEC.md`, the baseline numbering in `PROJECT_SPEC.md` versus `EXPERIMENT_PLAN.md` versus the actually-implemented baseline suite, and the ablation numbering in `PROJECT_SPEC.md` (A1–A9) versus `EXPERIMENT_PLAN.md`'s later, expanded A1–A10 set (which adds a rule-attribution ablation and an oracle baseline not implemented here). This paper follows the actually-implemented system throughout and flags each divergence where it matters, but a reader consulting the underlying planning documents directly should expect to find them not fully synchronized with either the code or with each other.

## 23. Conclusion

This paper described TARA as actually implemented: an eight-stage, dependency-inverted, fully unit-tested pipeline that classifies a developer query's task intent using a deterministic rule engine, routes retrieval strategy selection through an inspectable, policy-based adaptive router, executes lexical, dense, and graph retrieval according to that routing decision, fuses the results into a token-budgeted context, and generates code through a provider-agnostic interface currently backed only by a deterministic fake implementation. Alongside the system, this paper described a substantial evaluation infrastructure built specifically to test whether this design is worth its added complexity relative to task-agnostic retrieval: a five-baseline comparison suite with an enforced router-isolation guarantee, eight of nine specified ablation configurations, a pre-registered statistical-analysis layer whose test selection is a pure function of metric type rather than of observed data, and the schema for a purpose-built task-intent query dataset.

**None of this infrastructure has yet been used to produce an empirical result.** No dataset has been annotated, no baseline has been run, no ablation has been executed, and no real language model has been integrated. All five research questions posed in Section 16 remain open. This paper's contribution is the system and the machinery that would be required to answer them, together with a candid account, distributed throughout Sections 17–22, of exactly what stands between the current state of this project and a first defensible empirical finding. Whether task-aware adaptive routing is, in fact, worth its complexity relative to a well-tuned fixed-strategy baseline remains an open, falsifiable question this project is positioned — but has not yet attempted — to answer.

## 24. Reproducibility / Artifact Availability

**License.** The `tara` package is released under the MIT License (`LICENSE`, copyright 2026).

**Test suite.** As of this paper's drafting, running the project's automated test suite — covering the core `tara` library (`tests/`) together with every `evaluation/` package described in this paper (`tiqs`, `baselines`, `metrics`, `statistics`, `harness`, `ablations`) — produces **543 passed, 0 failed** (a small number of `scipy`/`tree_sitter` deprecation and degenerate-input runtime warnings are emitted and do not indicate a failure; they arise from an intentionally degenerate test case exercising a tied-sample edge condition in the Wilcoxon test wrapper, and from a library-level deprecation notice unrelated to test correctness). This figure is a fact about the current repository state, reproducible by any party with the pinned Python environment (below) via `pytest tests evaluation/tiqs/tests evaluation/baselines/tests evaluation/metrics/tests evaluation/statistics/tests evaluation/harness/tests evaluation/ablations/tests`, and is cited here as a statement about implementation completeness and test coverage, never as an experimental result.

**Dependency management.** `pyproject.toml` declares minimum-version dependency bounds (Python ≥ 3.10; FastAPI, Pydantic, PyTorch, `sentence-transformers`, `faiss-cpu`, NetworkX, `tree-sitter` + `tree-sitter-languages`, GitPython, Transformers, `pyarrow`, `matplotlib`, among others) but **no dependency lockfile currently exists** in this repository. Exact resolved versions used to produce any future reported result are consequently not yet pinned, which this project's own specification (`PROJECT_SPEC.md` §13, §29) identifies as a prerequisite that must be satisfied before any experiment's result is treated as reproducible; it has not yet been satisfied.

**Evaluation code organization.** Research/evaluation code lives under `evaluation/`, organized as one importable, independently-tested Python package per concern (`tiqs`, `baselines`, `metrics`, `statistics`, `harness`, `ablations`), depending on `tara` but never the reverse. **No `scripts/` directory or standalone experiment-runner script (e.g., a `run_experiment.py`) currently exists**; running an evaluation currently means importing and composing these packages directly (as their own test suites already do against synthetic fixtures), not invoking a single packaged CLI entry point. Building such an entry point is unstarted future work, not a completed but undocumented deliverable.

**What is and is not archived.** No experiment configuration, seed, or result file exists for any TIQS-based or baseline-comparison run, because no such run has occurred (Sections 17–20). What is archived and version-controlled in this repository is: the full source of every implemented pipeline stage and evaluation package; the full test suite backing the 543-passed figure above; the TIQS schema and a schema-conformant example (`evaluation/tiqs/TIQS_SCHEMA.md`, `evaluation/tiqs/schema_example`); the ablation matrix configuration (`evaluation/ablations/ablation_matrix.json`); the baseline-numbering discrepancy disclosure (`evaluation/baselines/BASELINE_DISCREPANCIES.md`); and this project's full planning-document set (`PROJECT_SPEC.md`, `EXPERIMENT_PLAN.md`, `DATASET_PLAN.md`, `CONTRIBUTIONS.md`, `docs/task_taxonomy.md`), each of which this paper has cited and, where necessary, corrected against the actual codebase state.

**Next concrete steps toward a reproducible first result**, in the dependency order this paper's own sections imply: (1) freeze a dependency lockfile; (2) select and pin a repository corpus; (3) execute the TIQS annotation protocol described in Section 13 to produce a first sealed dataset version; (4) integrate at least one real `CodeGenerator` implementation behind the existing interface (Section 12); (5) run the harness (Section 14) against the sealed dataset for TARA and each implemented baseline (Section 15); (6) run the eight implementable ablations (Section 18); (7) apply the existing, already-tested statistical-analysis layer to the resulting data and populate Sections 17, 18, 19, and 20 of this paper with their actual output.
