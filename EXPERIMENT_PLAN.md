# EXPERIMENT_PLAN.md

## TARA: Experimental Plan (Publication-Ready Design)

**Status.** This is a pre-registration-style experimental design document. It specifies, in advance of any result, exactly what will be measured, against what, using what statistical procedure, and what pattern of outcomes would support or refute each hypothesis in `PROJECT_SPEC.md` §6 (H1–H5). **No experiment described here has been executed.** Retrieval, context fusion, and LLM-based generation (`PROJECT_SPEC.md` §19–§21) are not yet implemented; this plan is written to be executable once they are, and every open implementation decision it depends on is marked **TBD** rather than assumed. This document must be finalized (all TBDs resolved and frozen) before the first result reported in the paper is produced, consistent with the pre-registration discipline described in `PROJECT_SPEC.md` §23.

**Relationship to other project documents.** This document operationalizes `PROJECT_SPEC.md` §22–§29 into paper-section-ready detail (concrete dataset candidates, metric formulas, named statistical tests, figure/table specifications) and should be read alongside it, `CONTRIBUTIONS.md` §4, and `docs/task_taxonomy.md`. Where a decision here narrows a TBD left open in `PROJECT_SPEC.md`, that narrowing should be reflected back into `PROJECT_SPEC.md` in the same revision.

---

## 1. Repository Datasets

**Purpose.** The corpus of real repositories against which queries are issued and against which `RepositoryContext` objects are built. Distinct from the *query/label* benchmark described in §2.

**Selection criteria (fixed in advance):**
- Permissive license (MIT, Apache-2.0, or BSD), to permit redistribution of any derived artifacts (indices, extracted context snippets) alongside the paper.
- Actively maintained at time of selection (commit activity within the preceding 12 months), to reduce the chance of a repository representing abandoned or unidiomatic practice.
- Coverage of all eight languages TARA's Repository Parser supports: Python, JavaScript, TypeScript, Java, Go, Rust, C, C++.
- A spread of repository sizes, stratified into three size buckets by lines of code (LOC): **small** (< 5,000 LOC), **medium** (5,000–50,000 LOC), **large** (50,000–200,000 LOC). Repositories above 200,000 LOC are excluded from v1 to keep context-extraction and index-build time tractable within the experimental timeline (§15).
- Presence of an existing automated test suite, preferred but not mandatory per-repository (test-suite presence gates eligibility for pass@k computation on that repository's queries, per §3, not eligibility for the corpus overall).

**Candidate repository list (illustrative; final list is TBD and must be frozen with pinned commit SHAs before §15 Phase 3 begins):**

| Language | Candidate repository | Size bucket (approx.) | Rationale |
|---|---|---|---|
| Python | `psf/requests` | Small–Medium | Widely known, well-tested, idiomatic Python |
| Python | TARA itself (`tara-rlcg`) | Small | Self-referential dogfooding case; the worked examples already used throughout `PROJECT_SPEC.md`/`README.md` reference its own symbols (`RepositoryParser`, `GraphBuilder`) |
| JavaScript | `expressjs/express` | Small–Medium | Canonical, widely studied Node.js codebase |
| TypeScript | A mid-size, actively maintained TS application repository | Medium | Exact repository **TBD** |
| Java | A mid-size Java library (e.g., in the `apache/commons-*` family) | Medium | Exact repository **TBD**; avoid full `google/guava`-scale repos in v1 (exceeds size cap) |
| Go | `spf13/cobra` | Small | Well-known CLI framework, compact, idiomatic Go |
| Rust | `BurntSushi/ripgrep` | Medium | Well-tested, idiomatic Rust, active community |
| C++ | `nlohmann/json` | Small–Medium | Single-purpose, well-documented, widely used |
| C | A small, well-scoped C library | Small | Exact repository **TBD** |

**ASSUMPTION:** including TARA's own repository as one corpus member is methodologically acceptable *only* if TIQS queries against it are authored by annotators without access to this experimental plan or to the routing source code's internal reasoning, to avoid circularity between the system under test and its own evaluation data; this constraint must be enforced procedurally during TIQS annotation (§2) and stated explicitly in the paper's limitations section.

**Per-repository statistics to record and report (Table 1, §11):** language, LOC, file count, symbol count (classes/functions/methods, as counted by the Repository Parser), commit count, contributor count, and a popularity proxy (star count) at the time the commit SHA was pinned.

**Freezing protocol:** every repository is checked out at a single, recorded commit SHA before any query authoring or index building begins. No repository is re-fetched or updated mid-experiment. This is required for reproducibility (`PROJECT_SPEC.md` §29) and for construct validity (§14): a repository that changes underneath a fixed query set would silently invalidate ground-truth relevant-context labels.

## 2. Benchmark Datasets

Two distinct benchmark resources are used, serving different evaluation needs.

**(a) TIQS — Task-Intent Query Set (primary, newly constructed).** Described at the design level in `PROJECT_SPEC.md` §22; this section fixes its construction parameters.

- **Target size:** 480 queries total (proposed; TBD pending annotation throughput, per `PROJECT_SPEC.md` §28 risk register), stratified to target **≈37 queries per `TaskType`** across the 13 categories (`PROJECT_SPEC.md` §17), rather than left to emerge from unconstrained natural sampling — this is a deliberate choice to guarantee sufficient per-category statistical power for the per-TaskType breakdown in Table 4 (§11), at the cost of not reflecting the *natural* frequency distribution of task types among real developer queries (itself a threat to validity, §14).
- **Query authorship:** at least two independent annotators per repository, instructed to author realistic queries as if they were a developer working in that repository (drawing on plausible issue-tracker-style requests, code-review comments, and onboarding questions), explicitly **not** derived from or checked against the rule-based classifier's own keyword vocabulary (`tara.classification.heuristics`), to avoid the circularity risk flagged in `CONTRIBUTIONS.md` §6.
- **Labels per query:** (i) a ground-truth `TaskType` label, double-annotated with disagreements adjudicated by a third annotator; (ii) a ground-truth relevant-context set (file paths and/or symbol ids, verified against the actual pinned repository, not authored from memory); (iii) where feasible, a reference output or an acceptable-output description for generation-quality scoring.
- **Inter-annotator agreement:** Cohen's κ computed on the double-annotated `TaskType` labels; **κ ≥ 0.6 is the pre-registered acceptability threshold** — below this, the taxonomy or annotation guidelines are revised and a re-annotation pass is run before proceeding, per `PROJECT_SPEC.md` §22.
- **Held-out split:** TIQS is split 70/15/15 into development/validation/test partitions at authoring time (not after the fact), with the test partition sealed and unused for any design decision (rule tuning, threshold selection, ablation configuration choice) until final evaluation.

**(b) External benchmark reuse (secondary, for pass@k and for contextualizing against prior work).** **Status: TBD, contingent on license and scope compatibility.** Candidates under consideration:
- **CodeRAG-Bench** — the most directly relevant prior benchmark methodologically (`PROJECT_SPEC.md` §4); candidate source of additional retrieval-augmented-generation queries and a methodological reference for metric selection, not assumed to provide `TaskType` labels compatible with TARA's taxonomy without adaptation.
- **A subset of an existing executable benchmark** (candidate: a small slice of SWE-bench Lite or an equivalent benchmark with a safe, pre-built execution harness) — used **only** to obtain pass@k on the subset of queries with an available, safe test-execution environment, per the `PROJECT_SPEC.md` §8 constraint against building a new sandboxed executor. If no compatible executable subset is identified during Phase 3 (§15), pass@k is reported as **not computed**, not approximated, and this is stated as a limitation rather than substituted with a proxy metric silently.

**Data-contamination note (see also §14):** any external benchmark or repository under consideration must be checked, to the extent practical, against the likely pretraining cutoff of the candidate generation LLMs (§8); this is noted here as a dataset-selection constraint, not only as a downstream validity threat.

## 3. Evaluation Metrics

Metrics are grouped by what they evaluate. All formulas below use standard definitions; no novel metric is introduced by this project.

**Classification metrics (against TIQS `TaskType` labels):**
- **Macro-F1** and **per-class F1**, standard multiclass definitions, computed on the sealed TIQS test split only.
- **Expected Calibration Error (ECE)**: queries are bucketed into `B` equal-width confidence bins (**B = 10**, standard choice); ECE = Σ over bins of `(|bin|/N) · |accuracy(bin) − mean_confidence(bin)|`. Reported alongside a reliability diagram (Figure 4, §10).
- **Spearman rank correlation (ρ)** between classifier `confidence` and a binary per-query correctness indicator, with a two-sided significance test (H1, H5).

**Retrieval metrics (against TIQS ground-truth relevant-context sets):**
- **Precision@k** = (relevant items in top-k) / k.
- **Recall@k** = (relevant items in top-k) / (total relevant items for the query).
- **Mean Reciprocal Rank (MRR)** = mean over queries of `1 / rank of first relevant item` (0 if none retrieved within the evaluated cutoff).
- **NDCG@k**, computed **only if** TIQS annotation captures graded (not merely binary) relevance — this is a TBD annotation-protocol decision (§2); if only binary relevance is captured, NDCG@k is reported as not applicable rather than computed from an artificially graded proxy.
- All retrieval metrics are computed **at matched k** across system variants wherever variants differ in `top_k` (per `PROJECT_SPEC.md` §25); where matching is not possible without distorting a variant's natural configuration, both the matched-k and native-k results are reported.

**Generation metrics (against TIQS reference/acceptable-output descriptions, where available):**
- **Exact match** (normalized whitespace/formatting).
- **Edit similarity**: normalized token-level edit distance, `1 − (edit_distance / max(len(candidate), len(reference)))`. **Exact tokenizer TBD**, to be fixed during Phase 4 implementation (§15) and held constant across all variants and metrics for a given experimental run.
- **CodeBLEU** (standard code-aware BLEU variant combining n-gram match, weighted n-gram match, AST match, and data-flow match), using an existing open-source implementation rather than a custom one, per `PROJECT_SPEC.md` §13.
- **Syntactic validity rate**: fraction of generated outputs that parse without error under the same Tree-sitter infrastructure already used by the Repository Parser (`tara.parsing`) — a deliberate reuse of existing, tested infrastructure rather than a new dependency.
- **pass@k**, using the standard unbiased estimator (Chen et al. 2021 / Codex-style): given `n` samples per query and `c` of them correct, `pass@k = 1 − C(n−c, k) / C(n, k)`. **Computed only** on the subset of queries with an available safe execution harness (§2b); reported with the exact subset size (`n_exec`) disclosed alongside any pass@k figure, never presented as if computed over the full TIQS set.

**Efficiency metrics:**
- **Per-stage latency**, reported as p50/p95/p99 wall-clock milliseconds, separately for: context extraction (amortized per repository), classification (already unit-test-enforced at < 10 ms), routing (already unit-test-enforced at < 2 ms), retrieval (budget **TBD**, to be set once §19 is implemented and profiled), fusion (budget **TBD**), and generation (dominated by LLM API latency, reported but not treated as a TARA-attributable cost).
- **Retrieval cost proxies**: number of retriever invocations per query, number of embedding calls, total candidate tokens retrieved, total tokens sent to the LLM.
- **End-to-end latency**, sum of the above, reported per query and aggregated.

**Explainability metric (exploratory, RQ5):**
- Human or LLM-judge binary/Likert rating of whether a routing `reason` string is judged sensible given the query and the selected strategy, **protocol TBD** (§14 explicitly flags this as requiring future validation before being treated as a primary metric); if run, inter-rater agreement (Cohen's κ or Krippendorff's α for Likert) is reported using the same acceptability threshold convention as §2.

## 4. Baselines

Restated from `PROJECT_SPEC.md` §24 with execution-level precision added.

| ID | Name | Configuration | Purpose |
|---|---|---|---|
| B0 | No retrieval | LLM generates directly from the query, no repository context | Absolute floor |
| B1 | Fixed semantic-only | Every query forced to the semantic-only retrieval strategy, Task Classifier and Router bypassed | Represents current dominant practice (§`PROJECT_SPEC.md` §2) |
| B2 | Fixed full-pipeline | Every query forced to the most thorough (lexical + semantic + graph) retrieval strategy | Isolates "more retrieval, always" from "adaptive selection of retrieval" |
| B3 | Random routing | Strategy sampled uniformly at random from the 7-member strategy space per query, fixed random seed disclosed | Sanity-check lower bound |
| B4 | Oracle retrieval (upper-bound reference, not a competing system) | Context assembled directly from TIQS's ground-truth relevant-context labels, bypassing all retrieval | Establishes a ceiling: the best any retrieval mechanism could plausibly achieve on this benchmark, useful for interpreting how much headroom remains |
| B5 | AIRCoder (reproduction or re-implementation) | **Status TBD**, contingent on public artifact availability (`PROJECT_SPEC.md` §24, §28) | Closest related system; primary external comparison point |
| B6 | RepoFormer-style dense retrieval | **Status TBD** | External comparison, dense-retrieval family |
| B7 | AllianceCoder-style ensemble retrieval | **Status TBD**; likely near-equivalent to B2 if its ensemble strategy is non-adaptive, in which case B2 substitutes with the equivalence stated explicitly | External comparison, ensemble-retrieval family |

**B4 (Oracle) is a new addition relative to `PROJECT_SPEC.md` §24**, included here specifically to support the "expected analysis" framing in §12: without an oracle reference, a null result on H2/H3 is ambiguous between "task-aware routing doesn't help" and "TIQS's ground-truth labels don't actually predict good generations, so no retrieval mechanism could score well" — B4 disambiguates these.

## 5. Ablation Studies

Restated and finalized from `PROJECT_SPEC.md` §26.

| ID | Ablation | What is varied | Tests |
|---|---|---|---|
| A1 | No Task Classifier / no Router | Equivalent to B1; listed as an ablation as well as a baseline | Entire routing layer's contribution |
| A2 | No `REFACTOR` override | `FullPipelinePolicy`'s task-type exception disabled; REFACTOR queries routed purely by raw classification flags | The specific hand-authored exception flagged in `CONTRIBUTIONS.md` §2 |
| A3 | Graph retrieval disabled | Graph retriever forced unavailable regardless of plan (forces the planner's context-capability-downgrade path) | Marginal value of graph retrieval specifically |
| A4 | Fixed top-k | Per-strategy top-k differentiation disabled; a single constant top-k used across all strategies | Whether strategy-specific result-count tuning matters independent of strategy selection |
| A5 | No reranking | `rerank` forced false regardless of plan | Reranking's contribution within Context Fusion |
| A6 | Reranker variant | Cross-encoder reranking vs. simple normalized-score-merge reranking (both variants run; neither assumed superior a priori) | Which reranking approach is worth its cost |
| A7 | Confidence-threshold fallback sweep | A confidence threshold (swept over {0.3, 0.4, 0.5, 0.6, 0.7}) below which the router defers to `SEMANTIC_ONLY` instead of trusting a low-confidence classification | Quality/coverage trade-off from confidence-gated fallback; **requires a small, explicitly-scoped Router extension not present in the current implementation**, per `PROJECT_SPEC.md` §26 |
| A8 | Embedding model swap | Default `BAAI/bge-small-en-v1.5` vs. `sentence-transformers/all-MiniLM-L6-v2` vs. a code-domain-specific embedding model (candidate: `jinaai/jina-embeddings-v2-base-code`, **final choice TBD**) | Sensitivity of results to embedding model choice |
| A9 | Classification surfaced to LLM prompt | `TaskClassification` (task type + routing reason) included in the generation prompt vs. omitted | Whether the classification is useful beyond its use in retrieval selection |
| A10 *(new)* | Rule-subset ablation | The rule engine run with each individual keyword-set rule category removed one at a time (leave-one-rule-family-out) | Attribution of classifier accuracy to specific rule families, informing which parts of the taxonomy/heuristics are load-bearing vs. redundant |

A10 is a new addition beyond `PROJECT_SPEC.md` §26, included because the rule-based classifier (`tara.classification.rules.DEFAULT_RULES`) is itself composed of many small, individually swappable rules — a leave-one-out analysis is cheap to run (deterministic, no LLM cost) and directly supports the classifier-design discussion in `CONTRIBUTIONS.md` §2/§6.

## 6. Statistical Tests

All tests, thresholds, and correction procedures are fixed here in advance, per the pre-registration discipline stated at the top of this document.

- **Primary paired comparisons** (TARA vs. each baseline, on the same TIQS queries): **Wilcoxon signed-rank test**, chosen because per-query metric differences are not assumed normally distributed and the comparison is paired (same query, different system). Two-sided, α = 0.05.
- **Multiple-comparisons correction**: **Holm–Bonferroni**, applied within each family of comparisons (e.g., the family "TARA vs. {B0, B1, B2, B3}" is one family; "TARA vs. {B5, B6, B7}" is a separate family, corrected separately, since the latter's comparisons are contingent on reproduction success and should not inflate the correction burden on the former). Holm–Bonferroni is chosen over plain Bonferroni for its uniformly higher power at equivalent family-wise error control.
- **Effect size**: **matched-pairs rank-biserial correlation** reported alongside every Wilcoxon result (not merely the p-value), so that statistical significance is never reported without a corresponding magnitude estimate.
- **Confidence intervals**: **bias-corrected and accelerated (BCa) bootstrap**, 10,000 resamples, for every point estimate reported in Tables 3–5 (§11), including metrics not directly amenable to a closed-form CI (e.g., macro-F1, ECE).
- **Paired binary outcomes** (e.g., per-query pass@1 success/failure, where pass@k is computable): **McNemar's test**, appropriate for paired nominal/binary data, in place of Wilcoxon for this specific metric type.
- **Correlation tests** (H1: confidence vs. correctness; H5: confidence vs. downstream quality): **Spearman's ρ**, two-sided, with the same α = 0.05 and BCa bootstrap CI convention as above.
- **Annotation agreement**: **Cohen's κ** for binary/categorical labels (`TaskType`), **Krippendorff's α** if any Likert-scale rating is collected (explainability evaluation, §3).
- **Statistical power note**: with TIQS's proposed size (480 total, ≈37 per `TaskType`), per-`TaskType` subgroup comparisons (Table 4, §11) are likely underpowered to detect small effects; subgroup results are reported with exact `n` and are explicitly framed as descriptive/exploratory rather than confirmatory, distinct from the overall (pooled) comparisons which are the confirmatory tests of H1–H5. This is a stated limitation (§14), not a justification for omitting subgroup analysis, which retains diagnostic value regardless of power.

## 7. Hardware

**Reference environment (to be disclosed exactly as run, per `PROJECT_SPEC.md` §23):**

- **Stages already implemented and profiled (Parser, Context Extractor, Classifier, Router):** demonstrated to run correctly and within their stated latency budgets on a standard CPU-only development machine (no GPU required); this has already been validated during development via the project's existing timing-assertion unit tests. This is disclosed here as an existing, demonstrated property, not a projection.
- **Dense embedding generation and indexing (Context Extractor's optional embedding step; planned Dense Retriever, §19):** benefits from GPU acceleration but is not assumed to require it; the default embedding model (`BAAI/bge-small-en-v1.5`) is a small model (≈33M parameters) chosen partly for CPU feasibility. **Proposed reference hardware for reported experiment timing:** a single machine with ≥ 16 CPU cores, ≥ 64 GB RAM, and one GPU with ≥ 16 GB VRAM (candidate: a single NVIDIA A10 or equivalent), used for embedding-index construction and any cross-encoder reranking (A6). **Exact instance type TBD**, to be fixed and disclosed once Phase 3 (§15) begins.
- **LLM generation:** if a hosted API provider is used (§8), no local GPU is required for generation itself; if a local open-weight model is used as one of the candidate generators, hardware requirements scale with model size and are **TBD** pending final model selection.
- **All reported latency numbers must state the exact hardware they were measured on**, per `PROJECT_SPEC.md` §23; latency comparisons across system variants are only valid when measured on identical hardware within the same experimental run.

## 8. LLMs

**Role:** the generation-stage LLM (`PROJECT_SPEC.md` §21) is held **constant across all system variants and baselines within a given experimental run** — this is a controlled variable (`PROJECT_SPEC.md` §23), not something that varies per condition, so that any measured difference is attributable to retrieval/routing, not to generation-model choice.

**Candidate models (final selection TBD, to be fixed before Phase 4, §15):**
- A hosted frontier model accessed via API (candidates: a current Anthropic Claude model or a current OpenAI GPT model), selected for generation quality and provider-agnostic-interface compatibility (`tara.interfaces.code_generator`, planned per `PROJECT_SPEC.md` §21).
- An open-weight code-specialized model runnable locally (candidates: a Code Llama, StarCoder2, or DeepSeek-Coder family model at a size compatible with the hardware in §7), included specifically to produce a fully reproducible experimental condition with **no dependency on a paid API or on a provider whose model version may change or be deprecated** — this is treated as a reproducibility requirement, not an optional nicety, given `PROJECT_SPEC.md` §14's stated priority on reproducibility.

**Fixed generation parameters (to be pinned exactly, disclosed in the paper's experimental setup section):**
- `temperature = 0` for the primary reported results, to maximize determinism and reproducibility.
- Where sampling-based metrics (pass@k for k > 1) require non-zero temperature, **n = 5 samples per query** (proposed, TBD) at a disclosed non-zero temperature, with mean and BCa bootstrap CI reported.
- Maximum output tokens, system prompt (if any), and exact prompt template (`PROJECT_SPEC.md` §21) are fixed once and archived as a versioned artifact, never adjusted per-baseline or per-condition.

**Cost and rate-limit disclosure:** total API spend and total generation calls for the full experimental program are tracked and disclosed in the paper's reproducibility statement, consistent with the risk noted in `PROJECT_SPEC.md` §28.

## 9. Embedding Models

**Default (already the implemented configuration default, `TaraSettings.embedding_model_name`):** `BAAI/bge-small-en-v1.5`, used for all primary (non-ablation) results involving dense/semantic retrieval.

**Ablation variants (A8, §5):**
- `sentence-transformers/all-MiniLM-L6-v2` — the framework's original default prior to the current configuration, included as a smaller/faster reference point.
- A code-domain-specific embedding model, candidate `jinaai/jina-embeddings-v2-base-code` (final choice **TBD**, alternatives to be evaluated include a `Salesforce/codet5p-embedding`-family model), included to test whether a code-specialized embedding space measurably improves dense-retrieval quality relative to a general-purpose sentence embedding model.

**Consistency requirement:** whichever embedding model is active for a given experimental condition, the **same** model instance is used to embed both the repository's indexed symbols (at context-extraction time) and the query (at retrieval time) — this is already an architectural guarantee in the implemented `Embedder` interface pattern (`tara.context.embedder`) and must be preserved identically in the planned Dense Retriever (§19).

## 10. Expected Figures

Each figure is specified with its intended content and the analytical question it answers, so that figure generation can be implemented as a deterministic script against archived result files (`PROJECT_SPEC.md` §33), not produced ad hoc.

- **Figure 1 — Pipeline architecture diagram.** A polished version of the stage diagram in `PROJECT_SPEC.md` §9, annotated with which stages are deterministic/LLM-free (Parser through Router) versus which involve a learned model (embedding) or an LLM call (generation).
- **Figure 2 — TIQS composition.** Bar chart of query count per `TaskType` (13 bars), confirming the stratified-sampling target (§2) was met, with the train/validation/test split shown as stacked segments within each bar.
- **Figure 3 — Classifier confusion matrix.** 13×13 heatmap of predicted vs. ground-truth `TaskType` on the sealed TIQS test split, answering: which task types are most confusable, and does confusion concentrate along semantically adjacent categories (e.g., `DEBUG` vs. `BUG_FIX`) or occur unpredictably?
- **Figure 4 — Confidence calibration reliability diagram.** Predicted-confidence bin (x-axis, 10 bins) vs. empirical accuracy within that bin (y-axis), with the diagonal as a perfect-calibration reference and ECE annotated on the plot, directly supporting H1/H5.
- **Figure 5 — Retrieval quality by system variant and task type.** Grouped bar chart, one group per `TaskType`, bars within a group = {TARA, B0–B7 as applicable}, y-axis = Recall@10 (or the pre-registered primary retrieval metric), answering: does TARA's advantage (if any) concentrate in specific task types, consistent with the task-specific retrieval-priority reasoning in `docs/task_taxonomy.md`?
- **Figure 6 — Latency by routing strategy.** Box plot of end-to-end retrieval latency, one box per `RoutingStrategy` (7 boxes) plus one for each fixed-strategy baseline, answering: does adaptive routing achieve a lower *typical* latency than always-full-pipeline, by virtue of routing a meaningful fraction of queries to cheaper single-retriever strategies (H4)?
- **Figure 7 — Generation quality by system variant.** Grouped bar or violin plot, overall and faceted by `TaskType`, y-axis = composite generation-quality score (and, on the executable-subset facet only, pass@k), with B4 (Oracle) shown as a ceiling reference line (H3).
- **Figure 8 — Ablation forest plot.** One row per ablation (A1–A10), x-axis = effect size (paired rank-biserial correlation) relative to full TARA with 95% BCa CI as horizontal error bars, a single figure summarizing the entire ablation program (§5) at a glance.
- **Figure 9 — Confidence vs. downstream quality.** Binned line plot: mean downstream retrieval/generation quality (y-axis) as a function of classifier confidence decile (x-axis), directly testing H5's claim that low confidence predicts lower downstream quality.
- **Figure 10 — Qualitative case study.** A single annotated example (one query, shown side-by-side across TARA and the strongest baseline): the query, the `TaskClassification`, the `RetrievalPlan` with its `reason` string, the retrieved context, and the generated output for each system — included specifically to make the explainability contribution (RQ5, `PROJECT_SPEC.md` §5) concrete and inspectable rather than only statistically summarized. **Example selection criterion:** chosen post hoc from the test split as a representative, not cherry-picked best-case, instance — the selection procedure itself (e.g., "the median-scoring query for the task type with the largest measured TARA-vs-baseline effect size") is fixed in advance to avoid post hoc cherry-picking.

## 11. Expected Tables

- **Table 1 — Repository corpus statistics.** Rows = repositories (§1); columns = language, size bucket, LOC, file count, symbol count, commit SHA, star count.
- **Table 2 — TIQS dataset statistics.** Rows = `TaskType` categories; columns = query count, inter-annotator κ (computed per category if sample size permits, else overall), mean query length (tokens).
- **Table 3 — Main results.** Rows = system variants (TARA, B0–B7); columns = Recall@10, MRR, generation composite score, pass@k (with `n_exec` disclosed), mean end-to-end latency (ms), mean total tokens retrieved. Statistically significant differences from TARA marked (Wilcoxon, Holm–Bonferroni-corrected, §6), with effect size in parentheses.
- **Table 4 — Per-task-type breakdown.** Rows = 13 `TaskType` categories; columns = the same primary metrics as Table 3, restricted to {TARA, strongest baseline}, with exact per-cell `n` disclosed given the subgroup-power caveat in §6.
- **Table 5 — Ablation results.** Rows = A1–A10; columns = metric delta vs. full TARA, Wilcoxon p-value (Holm–Bonferroni-corrected within the ablation family), rank-biserial effect size, BCa 95% CI.
- **Table 6 — External baseline reproduction status.** Rows = {AIRCoder, RepoFormer, AllianceCoder, RepoGraph, STALL+}; columns = status (reproduced / re-implemented / omitted), justification, and, where applicable, results.
- **Table 7 — Classifier performance.** Macro-F1, per-class F1 (13 rows), ECE, Spearman ρ (confidence vs. correctness) with 95% CI.
- **Table 8 — Failure taxonomy.** Rows = failure categories identified in the qualitative analysis (§13); columns = frequency (count and % of sampled failures), representative example, implicated pipeline stage.

## 12. Expected Analysis

This section states, in advance, the analytical narrative for each research question and what pattern of results would support versus refute each hypothesis — the pre-registration discipline extended from statistics (§6) to interpretation.

**RQ1 / H1 (classification feasibility).** Supported if macro-F1 ≥ 0.75 on the sealed TIQS test split **and** Spearman ρ between confidence and correctness is positive and significant (Table 7, Figure 4). If macro-F1 is high but confidence is poorly calibrated (or vice versa), this is reported as a partial result — classification and calibration are analytically separated, not collapsed into a single pass/fail verdict, since a well-calibrated-but-inaccurate classifier and an accurate-but-overconfident one have different downstream implications for the confidence-gated fallback in A7.

**RQ2 / H2 (retrieval quality).** Supported if TARA's Recall@10/MRR (Table 3) exceeds B1 and is not significantly worse than B2, at significantly lower cost (fewer retriever invocations, lower latency) than B2 — i.e., the target finding is "TARA matches the best fixed-strategy baseline's quality at lower cost," not necessarily "TARA strictly beats every baseline on quality alone." Figure 5's per-task-type breakdown is used to check whether an aggregate null result masks task-type-specific wins (e.g., TARA outperforming on `SEARCH`/`REFACTOR`-heavy subsets even if the pooled result is flat), which would be a meaningful, reportable finding distinct from a uniform null.

**RQ3 / H3 (generation quality).** Contingent entirely on §19–§21 being implemented (`CONTRIBUTIONS.md` §4). Supported if TARA's generation composite score (Table 3, Figure 7) exceeds B1 with a significant, non-trivial effect size, specifically on the subset of queries where the classifier's confidence exceeds the pre-registered threshold (A7's threshold value) — this is a deliberately pre-specified subgroup, not a post hoc high-confidence filter chosen after seeing results, to avoid the well-known failure mode of only reporting a hypothesis as confirmed on a data-dependently-selected favorable subset.

**RQ4 / H4 (efficiency).** Supported if mean end-to-end latency under TARA (Figure 6) is significantly lower than B2's, driven specifically by the fraction of TIQS queries routed to single-retriever strategies (`LEXICAL_ONLY`/`SEMANTIC_ONLY`/`GRAPH_ONLY`) — this fraction itself is reported as a descriptive statistic supporting the causal story, not assumed.

**RQ5 (explainability, exploratory).** Reported descriptively (mean rating, inter-rater agreement) without a pre-registered pass/fail threshold, consistent with its status as an exploratory RQ (`PROJECT_SPEC.md` §5); Figure 10's case study is the primary vehicle for this analysis, supplemented by the aggregate rating if the rating protocol (§3) is finalized in time.

**RQ6 / H5 (confidence calibration as a reliability signal).** Supported if Figure 9 shows a monotonic-or-near-monotonic positive relationship between confidence decile and downstream quality, with the lowest confidence decile scoring significantly below the highest (paired test on the corresponding query subsets). This result, if confirmed, directly motivates A7 (confidence-gated fallback) as a worthwhile future default, not only an ablation curiosity.

**Cross-cutting analysis — A10 (rule attribution).** Regardless of H1's headline outcome, the leave-one-rule-family-out results are used to identify which rule families are load-bearing versus redundant, informing a concrete, evidence-based simplification or extension recommendation for the classifier's rule set in future work (`CONTRIBUTIONS.md` §7).

**On a fully negative result across H1–H5:** per `CONTRIBUTIONS.md` §4, this is reported as a primary finding, with the analysis section structured to distinguish *why* — e.g., "classification is accurate (H1 holds) but doesn't propagate to retrieval gains (H2 fails)" points to a routing-design problem, whereas "classification itself is inaccurate (H1 fails)" points to a taxonomy or feature-extraction problem — so that a negative result is diagnostically useful rather than merely reported as "no effect found."

## 13. Failure Cases

**Protocol.** A stratified random sample of failed or low-scoring queries is drawn after the main results (§11) are computed — stratified by `TaskType` and, where attributable, by which pipeline stage's output is implicated (misclassification; routing to an unhelpful strategy despite correct classification; retrieval miss despite correct routing; fusion truncation removing needed context; generation error despite adequate context). **Sample size:** 5 failures per `TaskType` where available (target 65 total), manually annotated by at least one author with the root-cause categories below, cross-checked by a second author on a random 30% subsample (agreement reported using the same convention as §2/§6).

**Anticipated failure categories (informed by the task-specific failure-mode analysis already documented in `docs/task_taxonomy.md`; final taxonomy is expected to be refined once real failures are observed, not treated as closed in advance):**

- **Classification errors:** keyword collision between task-type vocabularies (e.g., a query using "search" as an incidental noun rather than a lexical-intent verb, per the false-positive risk already noted in `tara.classification.heuristics`); ambiguous multi-intent queries genuinely spanning two task types with no single correct label; non-English or non-Latin-identifier-convention queries falling outside the classifier's design envelope (`CONTRIBUTIONS.md` §6).
- **Routing errors:** a routing decision technically consistent with the classification but empirically unhelpful for the specific query (e.g., a `REFACTOR` query where the `FULL_PIPELINE` override retrieves excessive, diluting context rather than helping — directly relevant to A2); a context-capability downgrade (missing embeddings or a trivial graph) forcing a degraded plan on a query that genuinely needed the downgraded retriever.
- **Retrieval errors** (once §19 exists): missing the causally-upstream root cause on a Bug Fix query while correctly retrieving the symptom location; missing an indirect/reflective usage on a Refactoring query (incomplete recall); retrieving a topically-similar-but-architecturally-irrelevant exemplar on a Feature Implementation query; retrieving code without co-located rationale on a Documentation query.
- **Fusion errors** (once §20 exists): truncation removing the single most relevant chunk due to token-budget pressure, particularly likely on `FULL_PIPELINE`-routed queries with the largest candidate pools; deduplication merging two distinct-but-similarly-named symbols incorrectly.
- **Generation errors:** correct, sufficient context provided but the LLM nonetheless produces an incorrect or non-compiling output — used to distinguish TARA's contribution (getting the *context* right) from the generation model's own capability, an important distinction for not overclaiming (`CONTRIBUTIONS.md` §1).

**Reporting:** Table 8 (§11) presents category frequencies; a small number (3–5) of illustrative examples are included in the paper's qualitative analysis section, drawn from, but not limited to, the Figure 10 case study.

## 14. Threats to Validity

Extends `PROJECT_SPEC.md` §27 with items specific to this experimental design.

**Internal validity:** TIQS's stratified-by-`TaskType` sampling (§2) guarantees per-category statistical power but means TIQS's task-type distribution does not reflect the *natural* frequency of task types among real developer queries — any claim about "how often" a given task type occurs in practice is out of scope for results computed on TIQS. Annotator-authored queries, even when instructed to avoid the classifier's own vocabulary, may still unconsciously reflect it, especially for annotators who are also project contributors (mitigated, not eliminated, by the independent-annotator and third-party-adjudication protocol in §2).

**External validity:** results generalize only to the frozen repository corpus (§1) and its language mix; the size cap (≤ 200,000 LOC) means findings may not transfer to very large monorepos, where graph and symbol-index scale characteristics differ substantially from anything tested here. The English/Latin-identifier-centric design of the classifier's heuristics (`tara.classification.heuristics`) means TIQS itself, and therefore all results, are implicitly scoped to that setting; this is stated as a hard scope boundary, not merely a caveat.

**Construct validity:** retrieval metrics (Precision/Recall/MRR) are a proxy for "useful context," motivating the deliberate separation of H2 (retrieval) and H3 (generation) as independently tested hypotheses (`PROJECT_SPEC.md` §27); the addition of the Oracle baseline (B4, §4) is specifically intended to strengthen construct validity here by establishing whether TIQS's ground-truth labels themselves predict good generations at all, independent of any retrieval mechanism's ability to find them.

**Conclusion validity:** the Holm–Bonferroni correction (§6) and TIQS's modest, fixed size jointly limit the number of comparisons that can be confidently resolved at conventional significance; per-`TaskType` subgroup findings (Table 4) are explicitly exploratory, not confirmatory, as stated in §6.

**Data contamination (new, specific to this experimental design):** the candidate LLM generators (§8), if hosted frontier models, may have been pretrained on some or all of the selected repositories (§1) and possibly on portions of any external benchmark reused (§2b), which would inflate generation-quality metrics for reasons unrelated to retrieval quality. **Mitigation:** (i) prefer, where feasible, repositories or specific files/commits created or substantially modified after the candidate model's disclosed training cutoff, explicitly checked and documented per repository; (ii) report results separately for the open-weight local model candidate (§8), whose training data is more inspectable, as a contamination-robustness check against the hosted-model results; (iii) disclose this threat explicitly in the paper regardless of whether concrete contamination is detected, since absence of detected contamination is not proof of its absence.

**Reproduction-dependent validity:** any comparative claim relative to B5–B7 (external systems) is only as strong as the fidelity of their reproduction/re-implementation (§4); Table 6's explicit status disclosure exists precisely so that readers can weight these comparisons appropriately rather than treating a re-implementation as equivalent to a faithful reproduction.

## 15. Timeline

**ASSUMPTION:** durations are engineering- and research-effort estimates for a small team (1–3 people), explicitly provisional, and not tied to any specific venue deadline (none is currently targeted; if one is adopted, this timeline must be revisited and reconciled against it before Phase 1 begins).

| Phase | Scope | Depends on | Estimated duration |
|---|---|---|---|
| Phase 0 | Finalize all TBDs in this document (repository list with pinned SHAs, external-benchmark decision, embedding/LLM candidate short-lists, confidence-threshold sweep values, tokenizer choice for edit similarity) | — | 1–2 weeks |
| Phase 1 | Implement Retrieval (`tara.retrieval`, `PROJECT_SPEC.md` M5–M6) | Phase 0 (repository corpus needed for integration testing) | 3–5 weeks |
| Phase 2 | Implement Context Fusion (`tara.fusion`, M7) and LLM Interface (`tara.generation`, M8) | Phase 1 | 3–4 weeks |
| Phase 3 | Repository corpus finalized; index-building infrastructure validated on full corpus (M9, first half) | Phase 0, Phase 1 | 1–2 weeks (parallelizable with Phase 1–2) |
| Phase 4 | TIQS annotation: guideline finalization, query authoring, double-labeling, adjudication, inter-annotator agreement computed and, if needed, a revision pass (M9, second half) | Phase 3 | 4–8 weeks (highest schedule-risk phase, per `PROJECT_SPEC.md` §28) |
| Phase 5 | Baselines B0–B4 implemented against the composition root; B5–B7 attempted, status resolved (M10) | Phase 2 | 2–4 weeks |
| Phase 6 | Evaluation harness (`tara.evaluation`) implemented: all §3 metrics, §6 statistical tests, figure/table generation scripts (§10–§11) (M11, infrastructure) | Phase 2 | 2–3 weeks (parallelizable with Phase 5) |
| Phase 7 | Full experimental run: main results (Tables 3–4, Figures 5–7) against the sealed TIQS test split | Phase 4, Phase 5, Phase 6 | 1–2 weeks compute + analysis time |
| Phase 8 | Ablations A1–A10 executed (M12) | Phase 7 | 2–3 weeks |
| Phase 9 | Qualitative failure analysis (§13), explainability evaluation (§3 RQ5) if protocol finalized | Phase 7 | 1–2 weeks |
| Phase 10 | Paper drafting, figure/table finalization, internal review, reproducibility-artifact packaging (M13–M14) | Phase 7, 8, 9 | 3–4 weeks |

**Total estimated duration from Phase 0 start to paper draft complete: approximately 5–8 months**, dominated by Phase 4 (dataset annotation) and by the cumulative implementation work in Phases 1–2, both of which are explicitly flagged as the project's primary schedule risks in `PROJECT_SPEC.md` §28. This estimate should be treated as a planning input, not a commitment, and revisited at the start of each phase.
