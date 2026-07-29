# EVALUATION_PROTOCOL.md

## TARA: Evaluation Protocol

**Purpose and relationship to other documents.** `EXPERIMENT_PLAN.md` is the narrative design document — it explains *why* each dataset, baseline, ablation, and metric was chosen. This document is its procedural, checklist-oriented companion: it formalizes the study's variables, pins down mechanics not previously specified in full (random-seed policy, exact reporting templates, coding protocols for error attribution), and ends in a literal pre-submission checklist. Where content already exists in full elsewhere (`PROJECT_SPEC.md` §5–§6, `EXPERIMENT_PLAN.md` §1–§14, `DATASET_PLAN.md`), it is restated compactly here for self-containedness and cross-referenced for full detail, not duplicated at length.

**Status.** No experiment described in this protocol has been run. Every field below is a specification to be satisfied when Phase 7 of `EXPERIMENT_PLAN.md` §15 executes, not a report of results.

---

## 1. Research Questions

| ID | Question | Primary evidence source |
|---|---|---|
| RQ1 | Can a repository-agnostic, LLM-free classifier assign a useful task-intent label with accuracy and calibration sufficient to drive routing? | TIQS test split, classification metrics (§5) |
| RQ2 | Does task-aware routing improve retrieval quality over fixed-strategy baselines, at matched or lower cost? | TIQS test split, retrieval metrics |
| RQ3 | Does context from task-aware routing improve downstream generation quality over task-agnostic retrieval? | TIQS test split (+ executable subset for pass@k) |
| RQ4 | Does task-aware routing reduce retrieval latency/cost relative to an always-maximal strategy, without a significant quality regression? | TIQS test split, efficiency metrics |
| RQ5 *(exploratory)* | Are routing `reason` strings judged sensible by an independent rater? | Explainability rating study (§12) |
| RQ6 | Is classifier confidence correlated with downstream retrieval/generation quality? | TIQS test split, confidence-stratified analysis |

Full statements: `PROJECT_SPEC.md` §5.

## 2. Hypotheses

Each hypothesis is paired with an explicit falsification condition, stated once here so that no hypothesis is judged "confirmed" by an ambiguous or informally-interpreted result.

| ID | Hypothesis | Falsified if |
|---|---|---|
| H1 | Rule-based classifier achieves macro-F1 ≥ 0.75 on TIQS test, with confidence positively correlated (Spearman ρ, α = 0.05) with correctness | macro-F1 < 0.75, **or** ρ is not significantly positive |
| H2 | TARA's Recall@10/MRR ≥ the strongest fixed-strategy baseline, at equal-or-lower retrieval cost | TARA's primary retrieval metric is significantly below the strongest baseline's, **or** cost is not lower when quality is only equal |
| H3 | TARA's generation quality > fixed semantic-only baseline (B1) on the confidence-gated subset (pre-specified threshold, §13/A7) | No significant, non-trivial-effect-size improvement over B1 on that pre-specified subset |
| H4 | TARA's mean end-to-end latency < always-full-pipeline baseline (B2) | Latency is not significantly lower, **or** the fraction of queries routed to single-retriever strategies does not plausibly explain any observed difference |
| H5 | Low-confidence queries (below pre-registered threshold) show significantly lower downstream quality than high-confidence queries | No significant difference between confidence deciles (Figure 9, `EXPERIMENT_PLAN.md` §10) |

Full statements and rationale: `PROJECT_SPEC.md` §6. A hypothesis found false is reported as found false — per `CONTRIBUTIONS.md` §4, a negative result is a valid, reportable outcome of this protocol, not a protocol failure.

## 3. Experimental Variables

**Independent variable (manipulated):** *System Variant* — a categorical factor with levels {TARA (full), B0–B7, and each ablation configuration A1–A10}, defined in `EXPERIMENT_PLAN.md` §4–§5. This is the only variable deliberately manipulated across conditions; every comparison in this protocol is a comparison across levels of this one factor.

**Blocking/stratification variable (observed, not manipulated):** `TaskType` (13 levels). Queries are not randomly assigned a task type — each query naturally has one, determined by its content — so `TaskType` is used to stratify sampling (`DATASET_PLAN.md` §9) and to structure subgroup analysis (`EXPERIMENT_PLAN.md` Table 4), never treated as an experimentally manipulated factor.

**Dependent variables (measured outcomes):**

| Family | Variables |
|---|---|
| Classification | macro-F1, per-class F1, ECE, confidence–correctness correlation |
| Retrieval | Precision@k, Recall@k, MRR, NDCG@k (conditional) |
| Generation | exact match, edit similarity, CodeBLEU, syntactic validity rate, pass@k (conditional, executable subset only) |
| Efficiency | per-stage and end-to-end latency (p50/p95/p99), retriever invocation count, embedding call count, tokens retrieved, tokens sent to the LLM |
| Explainability *(exploratory)* | human/LLM-judge sensibility rating of routing `reason` strings |

Full metric definitions: §5 below and `EXPERIMENT_PLAN.md` §3.

## 4. Controlled Variables

Held constant within every comparison unless a variable is itself the object of a specific ablation (in which case it is held constant everywhere *except* that one ablation's conditions):

- **Generation LLM and its parameters** (provider, model identifier/version, temperature, max tokens, prompt template version) — held constant across every System Variant comparison except where the LLM itself is not yet invoked (H1/H2 evaluation, which precedes generation).
- **Embedding model** — held constant at the pipeline default (`BAAI/bge-small-en-v1.5`) except within ablation A8, where it is the manipulated variable.
- **Repository corpus and pinned commit SHAs** (`DATASET_PLAN.md` §6–§8) — identical across every condition; no repository is re-fetched or updated mid-study.
- **TIQS query set, split, and ground truth** — identical set of queries and labels evaluated against every System Variant; this is a within-subjects design (`EXPERIMENT_PLAN.md` §23), so every comparison is paired on the same query.
- **Token budget available to fused context** — held constant across variants unless the ablation under test is specifically about token-budget/truncation behavior.
- **Hardware** (§8) — every latency comparison across variants is only valid if measured on identical hardware within the same run; a hardware change between runs invalidates cross-run latency comparison and must be disclosed if it occurs.
- **Random seeds** (§7) — identical seed policy applied across variants for any shared source of stochasticity (e.g., bootstrap resampling uses the same seed regardless of which variant is being evaluated).

## 5. Metrics

Restated compactly from `EXPERIMENT_PLAN.md` §3; full formulas there. **Primary metric per hypothesis is designated explicitly** so that only one confirmatory statistical test is run per hypothesis (§6) — this is a pre-registration commitment against metric-shopping, not a suggestion.

| Hypothesis | Primary metric | Secondary/exploratory metrics |
|---|---|---|
| H1 | Macro-F1 | Per-class F1, ECE |
| H2 | Recall@10 | Precision@k (other k), MRR, NDCG@k |
| H3 | Generation composite score (or pass@k where the executable subset permits) | Exact match, edit similarity, CodeBLEU, syntactic validity |
| H4 | Mean end-to-end latency | p95/p99 latency, retriever invocation count, token counts |
| H5 | Spearman ρ (confidence vs. downstream quality) | Confidence-decile binned means (Figure 9) |
| RQ5 | *(none — exploratory only)* | Rating mean, inter-rater agreement |

Any metric not listed as primary for a given hypothesis may be reported and discussed but must not be presented as if it independently confirms or refutes that hypothesis.

## 6. Statistical Tests

Restated from `EXPERIMENT_PLAN.md` §6; the protocol commitment here is procedural: **exactly one statistical test, on the pre-designated primary metric (§5), constitutes the confirmatory test of each hypothesis.**

- **Paired comparisons** (TARA vs. each baseline): Wilcoxon signed-rank, two-sided, α = 0.05, with matched-pairs rank-biserial effect size reported alongside every p-value.
- **Multiple-comparisons correction:** Holm–Bonferroni, applied within each pre-declared comparison family (the B0–B3 family and the B5–B7 family corrected separately, per `EXPERIMENT_PLAN.md` §6's reasoning).
- **Confidence intervals:** BCa bootstrap, 10,000 resamples, for every point estimate in the main results and ablation tables.
- **Paired binary outcomes** (e.g., per-query pass@1 success/failure): McNemar's test, also used directly in Failure Analysis (§10).
- **Correlation tests** (H1, H5): Spearman's ρ, two-sided, same α and CI convention.
- **Agreement statistics:** Cohen's κ (categorical) or Krippendorff's α (ordinal/Likert), used for TIQS annotation agreement (`DATASET_PLAN.md` §13), error-coding agreement (§11 below), and the explainability rating study (§12), each with its own disclosed value — these are not interchangeable across uses and each must be reported separately.
- **Power caveat:** per-`TaskType` subgroup comparisons are explicitly exploratory, not confirmatory, given TIQS's size (`EXPERIMENT_PLAN.md` §6, `DATASET_PLAN.md` §17).

## 7. Random Seeds

**Sources of stochasticity requiring a seed policy**, enumerated so none is left implicit:

| Source | Where it occurs | Seed requirement |
|---|---|---|
| B3 random-routing baseline | Strategy sampled uniformly per query | Fixed seed, disclosed |
| LLM sampling (temperature > 0) | pass@k with n samples per query (`EXPERIMENT_PLAN.md` §8) | One seed (or seed offset) per sample index, disclosed per query batch |
| BCa bootstrap resampling | Every CI computation (§6) | Fixed seed, identical across all variants being compared |
| Stratified failure-case sampling | §10, drawing failures for qualitative review | Fixed seed |
| Explainability case-study selection | §12 | Fixed seed, applied to the pre-specified selection rule, not used to hand-pick a favorable example |

**Policy:** a single master seed is fixed **before** any confirmatory (test-split) run — proposed default `42`, to be confirmed or replaced during Phase 0 of `EXPERIMENT_PLAN.md` §15 and then held fixed for the remainder of the study. Component-level seeds are derived deterministically from the master seed (exact derivation scheme **TBD** at implementation time — e.g., a fixed per-component offset), not chosen ad hoc per run. Every stochastic result reported in the paper must disclose the exact seed(s) used to produce it, in the archived experiment configuration (§14), such that re-running the same script with the same seed reproduces the same sample set exactly.

**Non-random by design, noted for completeness:** the repository train/validation/test split (`DATASET_PLAN.md` §6–§8) is deliberately curated, not randomly assigned, and therefore has no associated seed.

## 8. Hardware Reporting

Every reported latency or throughput number must be accompanied by a disclosure containing, at minimum:

- CPU model and core count
- RAM
- GPU model, VRAM, and count (state "none" explicitly if a run is CPU-only — this is itself already demonstrated for the four implemented stages, `DESIGN_DECISIONS.md` §1–§4)
- Operating system
- Relevant accelerator driver/toolkit version (e.g., CUDA version), if a GPU is used
- Which specific pipeline components ran on which hardware, if mixed (e.g., embedding-index construction on GPU, classification/routing on CPU)

Candidate reference hardware and its rationale: `EXPERIMENT_PLAN.md` §7 (exact instance type **TBD**, to be fixed and disclosed once Phase 3 of `EXPERIMENT_PLAN.md` §15 begins). Any hardware change between an earlier development run and the final confirmatory run must be disclosed explicitly, since latency comparisons are only valid across identical hardware (§4).

## 9. LLM Reporting

Every use of an LLM anywhere in the study (generation, and the explainability-rating study if an LLM judge is used, §12) must disclose:

- Provider name
- Exact model identifier/version string; if the provider does not expose a stable version identifier, the exact access date is disclosed as a fallback provenance marker, since hosted models can change silently behind a stable name
- Temperature and all other generation parameters (max tokens, top-p, etc.)
- The exact prompt template version used (cross-referencing the versioned artifact described in `DESIGN_DECISIONS.md` §9; prompt design itself is still **TBD**)
- Number of samples per query (`n`) and the corresponding seeds (§7), for any sampling-based metric
- Aggregate token usage and aggregate API cost for the full experimental program (`EXPERIMENT_PLAN.md` §8's cost-disclosure commitment)
- For the local/open-weight provider (required per `DESIGN_DECISIONS.md` §9 for reproducibility): exact model weights version/checkpoint and the inference framework/version used to run it

## 10. Failure Analysis

**Definition (quantitative, threshold-based):** a query is coded as a **retrieval failure** if the primary retrieval metric (Recall@10) equals zero for that query, and as a **generation failure** if pass@1 is unsuccessful on the executable subset, or, for the non-executable majority, if syntactic validity is false. These thresholds are fixed here, before any result exists, specifically so "failure" is not defined post hoc around whatever pattern the data happens to show.

**Procedure:** for every System Variant, the failure rate (fraction of TIQS test-split queries meeting the failure definition) is computed per `TaskType` and overall (a table, paralleling `EXPERIMENT_PLAN.md` Table 4's structure). Whether TARA's failure rate differs significantly from each baseline's is tested using **McNemar's test** on the paired binary fail/pass indicator per query (§6) — this is the confirmatory statistical treatment of failure analysis, distinct from the purely descriptive failure-rate table.

**Output:** a failure-rate table (system variant × TaskType) plus the McNemar comparison results, feeding directly into the qualitative case selection in §12 and the error-coding sample in §11.

## 11. Error Analysis

Distinct from Failure Analysis (§10, *whether* a query failed): Error Analysis attributes *why*, at the pipeline-stage level, via a formal coding protocol.

**Sampling:** drawn from the failure set identified in §10, stratified by `TaskType`, 5 failures per `TaskType` where available (target 65 total, per `EXPERIMENT_PLAN.md` §13).

**Codebook (fixed categories, one implicated stage per failure):**

| Stage | Example root-cause categories |
|---|---|
| Classification | keyword collision; ambiguous multi-intent query; out-of-scope query (non-English/non-Latin identifiers) |
| Routing | technically-correct-but-unhelpful strategy (e.g., an over-broad `REFACTOR` override); context-capability downgrade forcing a degraded plan |
| Retrieval | missed causally-upstream context; incomplete recall of usages; topically-similar-but-irrelevant match; missing rationale-bearing context |
| Fusion | token-budget truncation removing the most relevant chunk; incorrect deduplication merge |
| Generation | correct/sufficient context provided, but the LLM output is nonetheless incorrect — used specifically to separate TARA's contribution (context correctness) from generation-model capability (`CONTRIBUTIONS.md` §1) |

Full category descriptions: `EXPERIMENT_PLAN.md` §13 (the codebook above formalizes that section's descriptive list into a fixed coding scheme).

**Coding procedure:** each sampled failure is independently coded by at least one author against the codebook; **30% of the sample is double-coded** by a second author. Inter-coder agreement is computed (Cohen's κ, same threshold convention as elsewhere in the project, κ ≥ 0.6) and disclosed alongside the resulting error-category frequency table (`EXPERIMENT_PLAN.md` Table 8). Disagreements are adjudicated by discussion, not by majority default.

## 12. Qualitative Analysis

Broader and not restricted to failures — this section governs the paper's interpretive, illustrative material.

- **Case studies (Figure 10):** at least one **success** case and one **failure** case per `TaskType` where feasible, each selected by the same pre-specified, non-cherry-picking rule stated in `EXPERIMENT_PLAN.md` §10 (e.g., "the median-scoring query for the task type with the largest measured effect size"), applied separately to the success-case and failure-case pools so neither set is manually hand-picked for favorability. Including a success case alongside every failure case is a deliberate balance requirement: a qualitative section built only from failures would misrepresent the system's actual behavior even if the quantitative results are favorable overall.
- **Explainability rating study (RQ5):** human or LLM-judge rating of routing `reason` strings, protocol **TBD** per `EXPERIMENT_PLAN.md` §3/§25 pending future validation; if run, raters are shown the query, the selected strategy, and the `reason` string, and asked a fixed rating question (exact wording **TBD**), with inter-rater agreement computed and disclosed using the same convention as §11.
- **Synthesis with the task taxonomy:** quantitative subgroup patterns (Table 4) are discussed in light of the qualitative, per-task-type retrieval-need reasoning already documented in `docs/task_taxonomy.md` (e.g., a recall-dominant task type underperforming should be discussed against that document's stated expectation that recall matters most for exactly that task type) — this connects a numeric pattern to a pre-existing, independently-authored explanation rather than inventing a post hoc one.
- **Reporting constraint:** qualitative material illustrates and grounds the quantitative results; it introduces no new unquantified claim not already supported by a table or figure (mirrors the Results-vs-Discussion discipline in `PAPER_OUTLINE.md` §8–§9).

## 13. Ablation Strategy

Full ablation definitions: `EXPERIMENT_PLAN.md` §5 (A1–A10). This section adds **run-order prioritization**, needed because the full ablation matrix is compute/time-constrained (`PROJECT_SPEC.md` §28) and may not complete in full before a submission deadline.

| Tier | Ablations | Rationale |
|---|---|---|
| Tier 1 — must-run | A1 (no classifier/router), A2 (no `REFACTOR` override), A3 (no graph retrieval), A5 (no reranking) | Each directly tests a named, specific design decision recorded in `DESIGN_DECISIONS.md`; omitting these would leave the paper's central architectural claims untested |
| Tier 2 — valuable, run if budget permits | A4 (fixed top-k), A6 (reranker variant), A8 (embedding model swap), A9 (classification surfaced to LLM), A10 (rule-family leave-one-out) | Informative and cheap (A10 in particular requires no LLM call), but not load-bearing for the paper's central claims |
| Tier 3 — requires additional scoping | A7 (confidence-threshold fallback) | Requires a small, explicitly-scoped Router extension not present in the current implementation (`EXPERIMENT_PLAN.md` §5); run last, after Tier 1–2 confirm the base system is worth this additional investment |

**Procedure:** any ablation involving a threshold or configuration choice (A4, A6, A7) is first swept on the **validation** repository split (`DATASET_PLAN.md` §7) to select its configuration; the frozen configuration is then evaluated once on the **test** split, exactly as the main results are (§4's controlled-variable discipline applies identically here). Ablations with no tunable configuration (A1, A2, A3, A5, A8, A9, A10) are evaluated directly on the test split.

## 14. Reproducibility

Consolidated from commitments stated across `PROJECT_SPEC.md` §14/§29/§30, `EXPERIMENT_PLAN.md`, and `DESIGN_DECISIONS.md`, restated here as one binding checklist-adjacent statement:

- All dependencies pinned via `pyproject.toml` and a full lockfile, archived per reported result.
- Every experiment run (main results, each ablation, each baseline) is produced by a single, named, version-controlled script, invoked with an archived configuration file (seeds, hardware, model identifiers, hyperparameters) — no manually-run, manually-edited, or undocumented intermediate step ever contributes to a reported number.
- Raw result files (per-query metric values, not only aggregates) are archived alongside each run, sufficient to regenerate every table and figure without re-running the experiment.
- Figures and tables are generated programmatically from archived result files (`PROJECT_SPEC.md` §33) — never hand-edited after generation.
- Code, TIQS (per the release plan in `DATASET_PLAN.md` §15), and all archived configurations/results are released publicly, license terms per `CONTRIBUTIONS.md` §5.
- Every stochastic result discloses its exact seed(s) (§7).
- Every hardware- and LLM-dependent result discloses the exact environment (§8, §9).

## 15. Replication Checklist

To be completed and attached to the paper submission. Every item is a verifiable claim, not an aspiration — an unchecked item must be either resolved or explicitly justified in the paper's limitations section (`CONTRIBUTIONS.md` §6), never silently omitted.

**Dataset**
- [ ] Repository corpus fully specified: source, license, pinned commit SHA, language, size bucket, domain, split — for every corpus repository (`DATASET_PLAN.md` §14 manifest)
- [ ] TIQS construction protocol, guideline document (all versions), and inter-annotator agreement values disclosed (`DATASET_PLAN.md` §10, §13)
- [ ] TIQS release location, format, and license disclosed (`DATASET_PLAN.md` §15)
- [ ] Any external benchmark subset reused (e.g., for pass@k) is named, versioned, and its exact subset size disclosed

**Code and Environment**
- [ ] Full source code released at a permanent, versioned location, tagged at the exact commit used to produce reported results
- [ ] Dependency versions pinned and archived (lockfile included in the release)
- [ ] Hardware disclosed per §8, for every latency-bearing result
- [ ] LLM(s) disclosed per §9, including the local/open-weight reproducibility provider

**Experimental Design**
- [ ] Every hypothesis's primary metric is stated and matches what was actually tested (§5)
- [ ] Controlled variables (§4) are stated explicitly and were verifiably held constant (spot-checked against archived configs)
- [ ] All random seeds disclosed (§7), sufficient to exactly reproduce every stochastic result
- [ ] Train/validation/test repository split respected throughout — no test-split repository or query contributed to any threshold, rule, or prompt decision (`DATASET_PLAN.md` §8)

**Statistical Reporting**
- [ ] Every significance claim reports the exact test used, the p-value, the effect size, and whether multiple-comparisons correction was applied (§6)
- [ ] Every point estimate reports a confidence interval (BCa bootstrap, §6)
- [ ] Subgroup (per-`TaskType`) results explicitly labeled exploratory, with exact `n` disclosed (§6)
- [ ] No result is reported as confirmatory using a non-primary metric not designated in §5

**Compute and Cost**
- [ ] Total API spend and total generation calls for the full experimental program disclosed (§9)
- [ ] Total wall-clock compute time for the full experimental program disclosed
- [ ] Ablation-tier prioritization (§13) and, if the full matrix did not complete, which tiers were and were not run, disclosed explicitly

**Ethics**
- [ ] Annotator compensation/credit disclosed per `DATASET_PLAN.md` §16
- [ ] Data-contamination risk (pretraining overlap with the corpus) discussed, even if not conclusively resolved (`EXPERIMENT_PLAN.md` §14)
- [ ] Dual-use and representativeness limitations stated (`DATASET_PLAN.md` §16, `CONTRIBUTIONS.md` §6)

**Final Consistency**
- [ ] Every number in the Abstract and Conclusion traces to a specific table or figure in Results (`PAPER_OUTLINE.md` §1, §12)
- [ ] Every claim of superiority over an external system (AIRCoder, RepoFormer, AllianceCoder, RepoGraph, STALL+) is qualified by that system's reproduction status (`EXPERIMENT_PLAN.md` Table 6)
- [ ] This checklist itself is included in the submission's supplementary material, filled in, not merely referenced
