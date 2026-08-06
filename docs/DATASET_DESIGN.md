# DATASET_DESIGN.md

## The Router Training Set (RTS): Dataset Design for a Learned Retrieval Router

**Status.** Prospective specification. Nothing described here has been built, and — critically — this dataset's primary labeling method (§4, Oracle Retrieval) **cannot fully execute until Milestones 5–7 (Retrieval) exist**, and ideally not until Milestone 9 (Generation) exists either, per `ROADMAP.md`. This document is written now so the dataset's shape is fixed in advance of that work, not designed reactively around whatever the retrieval stages happen to produce.

**Relationship to `DATASET_PLAN.md` — read this before anything else.** This is **not** a second, independent dataset. The Router Training Set (RTS) is defined as an *extension* of the existing Task-Intent Query Set (TIQS, `DATASET_PLAN.md` §9): it reuses TIQS's repository corpus, TIQS's repository-level train/validation/test splits (`DATASET_PLAN.md` §6–§8), and, where possible, TIQS's own queries — adding new *output* label fields (best strategy, confidence, explanation) that TIQS does not currently capture. Building RTS on a separate split would create a direct leakage channel: a repository could be `test` under TIQS but `train` under RTS, contaminating the classifier-evaluation results with router-training influence or vice versa. Reusing TIQS's splits exactly closes that channel by construction. Every general dataset-construction concern already resolved in `DATASET_PLAN.md` (repository selection criteria, annotator qualification, versioning, release policy, ethical considerations) applies here unchanged and is not re-derived in this document.

**Why a learned router at all.** This dataset exists to enable the top-priority future-work comparison named in `CONTRIBUTIONS.md` §7 and `docs/methodology/Adaptive_Retrieval_Definition.md` §7 (Assumption 4) and §10 (open question 6): whether a model trained on labeled routing outcomes outperforms TARA's current deterministic, rule-based `AdaptiveRouter` (`tara.routing`). It is explicitly **not** a dataset for training a large model from scratch or fine-tuning an LLM — both excluded per `PROJECT_SPEC.md` §8's scope boundaries. The learned router this dataset is meant to support is expected to be a lightweight, feature-based model (see §8, Limitations).

---

## 1. Dataset Objective

RTS exists to answer one question empirically: **given a query and a set of signals about it and the repository it targets, can a trained model predict which retrieval strategy will perform best, and does that prediction outperform TARA's current deterministic policy chain?**

Three consequences follow directly from this objective and shape every section below:

1. **RTS's input schema must be a superset of what the deterministic router currently uses**, not merely equivalent to it. The deterministic router today consumes only `TaskClassification` and a narrow repository-capability check (`docs/methodology/Adaptive_Retrieval_Definition.md` §4). If RTS's inputs were limited to exactly the same signals, a learned router trained on it could at best *re-derive* the existing rules, not exceed them. RTS therefore also captures the currently-unused "candidate routing inputs" that document's §4 identifies (query complexity, richer repository characteristics) specifically so the comparison is a fair test of whether a *richer* input space helps, not only whether a *learned* function of the *same* inputs helps.
2. **RTS's primary output label (best retrieval strategy) must be defined over the same discrete taxonomy the deterministic router already uses** (`tara.routing.strategy.RoutingStrategy`, 7 members), so that a learned router's predictions are directly substitutable for the deterministic router's `RoutingDecision` output and the comparison requires no adapter layer. This is a stated scope boundary, not an oversight — see §8.
3. **RTS must support evaluating explanation quality, not only strategy accuracy**, because explainability is part of TARA's own stated contribution (`CONTRIBUTIONS.md` §1). A learned router that predicts the right strategy but cannot justify it would be, by this project's own standard, a partial regression relative to the deterministic router's `reason` string — not a strict improvement, even if raw accuracy were higher.

## 2. Input Schema

Every field below is available (or will be available) per query, keyed to the same query identifiers TIQS already uses.

### Query

The raw query text, reused verbatim from TIQS. No paraphrasing or normalization beyond what `tara.classification.features.FeatureExtractor` already applies when the query is processed.

### Repository Metadata

The general descriptive record already captured in TIQS's repository manifest (`DATASET_PLAN.md` §14): source, pinned commit SHA, domain category, and split assignment. Included here as a coarse identifier and provenance field, distinct from the more specific, feature-oriented fields below.

### Programming Language

Called out as its own field, distinct from the general repository metadata above, because language is expected to be an unusually predictive feature on its own (e.g., naming-convention heuristics and import-resolution behavior already differ measurably by language in the implemented classifier and context extractor, `DESIGN_DECISIONS.md` §4). Sourced from `tara.core.types.Language`, matching the file the query's relevant symbols live in.

### Repository Size

The same three-bucket scheme already defined for corpus stratification (`DATASET_PLAN.md` §4: small / medium / large by LOC), plus the raw underlying counts (`RepositoryContext.file_count`, `RepositoryContext.symbol_count`) as continuous features a learned model can use more finely than the bucket label alone permits.

### Task Label

The full, already-implemented `TaskClassification` object (`tara.classification.models`), reused as an input feature set, not only as a categorical label: `task_type` (13-way), `confidence`, `graph_required` / `semantic_required` / `lexical_required` / `reasoning_required`, `extracted_keywords`, `detected_symbols`, `detected_file_paths`, and `language_hint`. Including the full object, not only `task_type`, matters directly for the objective stated in §1: the deterministic router already uses the three boolean flags, so a learned router given *only* `task_type` would be working with strictly less information than the system it is meant to be compared against.

### Structural Features

The genuinely new input material relative to what the deterministic router uses today, corresponding directly to the currently-unused "candidate routing inputs" identified in `docs/methodology/Adaptive_Retrieval_Definition.md` §4:

- **Query-complexity proxies**: token count (pre- and post-stop-word-filtering), detected-symbol count, quoted-identifier count, and a coarse multi-clause indicator (e.g., presence of coordinating conjunctions joining two distinct verb phrases) — engineered features standing in for the "query complexity" input that document's §4 flags as proposed-but-unbuilt.
- **Repository graph statistics**: node count, edge count, and a simple density measure (`edges / max(nodes, 1)`) from `RepositoryContext.graph`, exposing *proactively*, as a feature, the same graph-availability signal the deterministic planner currently only consults *reactively* as a downgrade check.
- **Embedding availability**: a boolean, `bool(RepositoryContext.embeddings)`, for the same reason.
- **Latency budget, token budget**: **explicitly excluded from RTS v1.** Per `docs/methodology/Adaptive_Retrieval_Definition.md` §4, neither concept is operationalized anywhere in the current pipeline — there is no mechanism yet to generate a meaningful ground-truth value for either, and inventing a synthetic one for dataset-construction purposes alone would be fabricating a signal this project has no actual measurement process for. If a future extension implements either input, RTS should be revised to include it rather than backfilled with a placeholder now.

## 3. Output Schema

### Best Retrieval Strategy

The primary supervised-learning target: one value from `tara.routing.strategy.RoutingStrategy` (`LEXICAL_ONLY`, `SEMANTIC_ONLY`, `GRAPH_ONLY`, `HYBRID`, `GRAPH_PLUS_SEMANTIC`, `LEXICAL_PLUS_GRAPH`, `FULL_PIPELINE`). Reusing the existing enum, rather than defining a new one for RTS, is what keeps a trained model's output directly substitutable for `RoutingDecision.strategy` without a translation layer.

### Confidence

**A label-quality signal, not a model output.** This field records how confident the *labeling process* was in the assigned best-strategy value for a given example — derived per §4 from the margin between the top two candidate strategies' oracle scores, and/or from agreement across the three labeling methods. It is emphatically **not** the same thing as a trained model's own predicted confidence at inference time; conflating the two would be a category error. RTS supplies this field so a downstream training procedure *may* use it (e.g., down-weighting low-confidence-labeled examples during training, or as a soft target for a model that also predicts its own confidence), not because it is assumed to be the right training signal.

### Explanation

A natural-language rationale for the assigned best strategy, structurally analogous to `RoutingDecision.reason` in the deterministic router. Sourced from whichever labeling method produced the strategy label for a given example (§4), with provenance recorded per example (§5) so a downstream consumer can weight a human-written explanation more heavily than an LLM-drafted one if desired.

## 4. Label Generation Methods

Three methods, each with a distinct role, cost, and reliability profile. None is treated as sufficient alone; §5 defines how disagreement across methods is surfaced and resolved.

### Human Annotation

**Role: gold-standard calibration, not primary-scale labeling.** An annotator reads the query and the repository context and judges the best strategy directly, following a protocol with the same rigor as TIQS's existing `TaskType` annotation (`DATASET_PLAN.md` §10): independent labeling by two annotators, adjudication of disagreement by a third, and an inter-annotator agreement threshold (Cohen's κ ≥ 0.6, the same convention used throughout this project's other annotation efforts) before proceeding to scale.

Human annotation is reserved for a **gold subset** of RTS, not the full training set — running two-annotator-plus-adjudication labeling across a training-set-scale query volume is cost-prohibitive relative to what the other two methods can produce, and is not the differentiator RTS actually needs at scale (§6 discusses the resulting size asymmetry across splits explicitly). Human-annotated examples also supply the highest-confidence `explanation` text and serve as the calibration reference the other two methods are validated against.

### Oracle Retrieval

**Role: the primary, scalable source of the `best_strategy` label, once available.** For a query with an existing ground-truth relevant-context set (already part of TIQS, `DATASET_PLAN.md` §11), each of the seven `RoutingStrategy` values is executed directly against the repository, and the resulting retrieval-quality metric (Recall@k against the TIQS ground truth, per `EXPERIMENT_PLAN.md` §3) is compared across strategies. The empirically best-performing strategy becomes the label; the margin between the best and second-best strategy's metric becomes the primary input to the `Confidence` field (§3).

Where generation (Milestone 9) is also available, a generation-quality-based oracle variant is preferred over the retrieval-metric-only variant when both exist, since it is one step closer to the outcome that actually matters (downstream generation quality), consistent with `EXPERIMENT_PLAN.md` §12's own distinction between retrieval-quality and generation-quality evidence.

**Named limitations, stated here rather than deferred to §7 because they directly shape the labeling method's design:**
- Oracle labels are only as trustworthy as the ground-truth relevant-context set they are measured against, and therefore inherit that label's own subjectivity (`DATASET_PLAN.md` §17).
- **Tie-breaking convention**: when two or more strategies' oracle metrics are within a small margin (exact threshold **TBD**, to be set empirically once real oracle-metric distributions are observed), the *cheaper* strategy (per `RETRIEVER_EXECUTION_PRIORITY`, `tara.routing.strategy`) is preferred as the label, consistent with TARA's general "cheap unless there is a demonstrated reason for more" design stance (`docs/methodology/Adaptive_Retrieval_Definition.md` §7, Assumption 7) — an explicit, documented policy choice, not an arbitrary tie-break.
- **Sequencing dependency**: this method cannot run at all until Milestones 5–7 (and ideally 9) exist. It is not merely *expensive* before then — it is *impossible*, which is why §6's training-split scaling plan is explicitly conditional on that dependency.

### LLM-Assisted Labeling

**Role: scaling explanation-text generation, and a supplementary strategy signal only where oracle retrieval is unavailable.** An LLM, given the query and a summary of the repository context, is prompted to suggest a best strategy and draft an explanation. Two distinct uses, with different reliability implications:

1. **Explanation drafting for oracle-labeled examples.** Once oracle retrieval has determined the `best_strategy` label, an LLM drafts the `explanation` text justifying *that already-determined* label (not proposing its own), which a human then spot-checks (§5) rather than writes from scratch. This is the primary way RTS affords a natural-language explanation for every example without human-authoring all of them.
2. **Fallback strategy labeling** for examples where oracle retrieval cannot be computed (e.g., during the period before Milestones 5–7 exist, or for a query lacking a safe execution environment for a generation-quality oracle). These labels are marked with a distinct, lower provenance tier (§5) and are not used for the sealed test split under any circumstances — only oracle- or human-derived labels are trusted for confirmatory evaluation.

**Named risk specific to this method, requiring an explicit mitigation:** an LLM asked to suggest a routing strategy risks reflecting whatever it has learned about "how RAG systems typically route" from its own pretraining, or — worse — reflecting TARA's *own* publicly documented taxonomy and strategy definitions if those are visible to it, which would reproduce the exact circularity risk already flagged for TIQS itself (`DATASET_PLAN.md` §16, `CONTRIBUTIONS.md` §6). **Mitigation:** the LLM-labeling prompt must not include TARA's own strategy names, taxonomy descriptions, or design documents — only the query, the repository context summary, and a domain-neutral description of what each of the seven mechanisms *does* (e.g., "exact keyword matching," "semantic similarity search," "graph traversal") without naming TARA's own enum values, so a resulting suggestion cannot be traced back to having read this project's own reasoning about itself.

## 5. Data Quality Checks

- **Cross-method agreement.** For every example with labels from more than one method, disagreement is computed and surfaced; a disagreement between oracle and human labels is a stronger quality signal than a disagreement involving only the LLM-assisted method, and is escalated to human adjudication rather than resolved automatically.
- **Label-plausibility sanity check.** A `best_strategy` label is flagged for review (not automatically rejected) if it is inconsistent with the query's own `TaskClassification` flags in a way with no plausible explanation — e.g., a `LEXICAL_ONLY` label for a query the classifier scored `graph_required=True` with high confidence. Flagged, not rejected, because such disagreements are exactly the cases most informative about whether the deterministic router's flag-derived logic is actually correct (the premise Assumption 1, `docs/methodology/Adaptive_Retrieval_Definition.md` §7, is under test) — silently discarding them would bias RTS toward confirming the existing rules.
- **Strategy-distribution balance check.** The realized distribution of `best_strategy` labels across the seven values is monitored against a target stratification (analogous to TIQS's per-`TaskType` quota, `DATASET_PLAN.md` §9); a severely imbalanced label distribution (e.g., one strategy dominating 90%+ of labels) would make a trained router's evaluation largely uninformative about the six other classes, and is grounds for targeted additional query collection, not silent acceptance.
- **Explanation faithfulness spot check.** A random sample of LLM-drafted explanations (target: 10% of LLM-drafted examples, revisited once labeling volume is known) is human-reviewed for whether the explanation actually justifies the assigned label and references real, query-relevant content rather than generic or templated language.
- **Repository-split integrity check.** Every labeling operation (oracle execution, human annotation, LLM prompting) for a given example is verified to operate only against that example's own repository at its TIQS-pinned commit and split — no oracle computation is permitted to reference a repository outside the query's declared split, mechanically enforced by the same manifest-driven approach already used for TIQS (`DATASET_PLAN.md` §14).
- **Ground-truth-existence precondition.** A query is eligible for oracle-based labeling only if it already has a verified relevant-context ground-truth set in TIQS (`DATASET_PLAN.md` §11); a query lacking this is either excluded from RTS or routed to human/LLM-only labeling with its lower provenance tier recorded accordingly.
- **Near-duplicate explanation detection**, specifically for LLM-drafted text, since a shared or lightly-varied prompt template can produce templated, low-diversity explanations across many examples — checked via simple text-similarity clustering, with over-similar clusters flagged for prompt-template revision rather than accepted as-is.

## 6. Dataset Split

RTS uses **exactly** TIQS's repository-level train/validation/test splits (`DATASET_PLAN.md` §6–§8) — no independent re-splitting. This is a design decision, stated once here rather than re-derived: any deviation would reopen the exact repository-level leakage risk `DATASET_PLAN.md` §9 was written to close.

**Validation and test splits: 1:1 with TIQS.** Every TIQS validation- and test-split query that has (or can obtain) a valid relevant-context ground truth is included in RTS's corresponding split, with no additional queries added beyond what TIQS already defines — keeping the evaluation splits directly comparable to every other metric already reported against TIQS elsewhere in this project's documentation, without introducing a second, RTS-specific query population that would need its own separate validity argument.

**Train split: scaled beyond TIQS's original query count.** Supervised model training generally benefits from more examples than an evaluation benchmark needs to provide, and — once oracle retrieval is available (§4) — labeling additional train-split queries no longer requires the expensive human-annotation step TIQS's original construction relied on for `TaskType` labels. RTS therefore proposes expanding the training-split query population beyond TIQS's original train-split count, using additional realistic queries authored against the same train-split repositories (following the same authoring protocol and circularity-avoidance constraints as `DATASET_PLAN.md` §10, but without requiring the full double-label-and-adjudicate cycle for every added query — only the human-annotated gold subset needs that). **Proposed target: 2,000–5,000 labeled training examples**, an initial estimate to be revised once a labeling pilot establishes realistic oracle-execution and LLM-labeling throughput and cost (`EXPERIMENT_PLAN.md` §8's cost-disclosure discipline applies directly here). This target, and the query-authoring effort required to reach it, is explicitly **not yet committed** — it is a planning input for the phase in which this dataset is actually constructed, not a promise made by this document alone.

## 7. Risks

- **Sequencing risk.** RTS's primary labeling method is blocked on Milestones 5–7 (and ideally 9) being implemented and reasonably correct first; if those milestones slip, RTS construction slips with them, and no amount of dataset-design work in advance changes that dependency.
- **Oracle-label noise inheritance.** Every risk already named for TIQS's relevant-context ground truth (`DATASET_PLAN.md` §17) propagates directly into RTS's `best_strategy` labels, since oracle retrieval is measured against exactly that ground truth.
- **LLM circularity risk**, as detailed in §4 — mitigated by prompt design, not eliminated; residual risk should be assumed, not assumed away.
- **Distribution-mismatch risk, sharper here than for TIQS.** TIQS's stratified, non-natural query distribution (`DATASET_PLAN.md` §14) is a known limitation for *evaluating* a system against it. For RTS, the same stratified distribution becomes the distribution a model is *trained to imitate* — a stronger risk, since a learned router could internalize the artificial per-`TaskType` balance as a prior about how often each task type occurs, which does not match real deployment traffic.
- **Reward-hacking / construct-validity risk.** If `best_strategy` is defined purely by an oracle metric (Recall@k or a generation-quality proxy), a router trained on it optimizes for *that specific metric*, which — per the same construct-validity reasoning already applied to retrieval metrics generally (`EXPERIMENT_PLAN.md` §14) — is a proxy for useful context, not identical to it.
- **Small-gold-subset statistical power.** The human-annotated calibration subset (§4) may be too small to detect a systematic miscalibration between oracle-derived and human-judged best strategies with adequate statistical power; this should be checked once the gold subset's realized size is known, not assumed adequate in advance.
- **Cost risk.** Running all seven strategies' retrieval (and, where used, generation) against thousands of training queries is a real, non-trivial compute and API cost, particularly for strategies invoking dense retrieval or an LLM-based generation oracle — subject to the same cost-disclosure commitment already made for the broader experimental program (`EXPERIMENT_PLAN.md` §8).

## 8. Limitations

- **Scale.** Even at the proposed expanded size (§6), RTS remains small by general machine-learning standards (thousands, not millions, of examples). This bounds the class of learned router this dataset can responsibly support to a lightweight, feature-based model (e.g., a small gradient-boosted-tree or logistic-regression classifier over the structured features in §2) — not a large neural model trained from scratch. Any future comparison should be scoped accordingly and this scope stated explicitly in whatever paper or report describes the result, not left implicit.
- **Taxonomy-bound labels.** `best_strategy` is defined, by construction, over TARA's own existing seven-member `RoutingStrategy` enumeration. RTS can support comparing a *learned selector over this taxonomy* against the *deterministic selector over the same taxonomy*; it cannot, by itself, evaluate whether a differently-shaped strategy taxonomy would route better — that is a separate, unaddressed question (`docs/methodology/Adaptive_Retrieval_Definition.md` §9, continuous multi-retriever blending, is one such alternative this dataset's schema does not accommodate).
- **Explanation reliability is weaker evidence than strategy-label reliability.** The `explanation` field, especially where LLM-drafted, is harder to validate at scale than the discrete `best_strategy` label, and any downstream use of RTS should weight it accordingly rather than treating both fields as equally trustworthy.
- **Scope relative to the project's central hypothesis.** RTS can only ever compare a *learned* routing mechanism against the *deterministic* one — it cannot, by construction, test whether task-aware routing is the right approach at all (that is TIQS's and `EXPERIMENT_PLAN.md`'s job, H1–H5). RTS assumes the general premise and interrogates only the routing *mechanism*, a narrower question than the project's central hypothesis.
- **Inherited corpus limitations.** Every repository-selection, language-coverage, and annotator-representativeness limitation already stated for TIQS (`DATASET_PLAN.md` §17) applies to RTS unchanged, since RTS shares TIQS's exact corpus and splits; restated here only as a pointer, not re-derived, per this document's stated relationship to `DATASET_PLAN.md`.
