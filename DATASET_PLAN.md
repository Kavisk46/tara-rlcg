# DATASET_PLAN.md

## TARA: Dataset Strategy

**Status.** This document is the authoritative, detailed specification of TARA's dataset strategy. It extends `PROJECT_SPEC.md` §22 and `EXPERIMENT_PLAN.md` §1–§2 with full procedural detail, and it makes one methodological refinement to those documents that should be read as superseding, not contradicting, them: **repository-level train/validation/test splitting**, introduced in §6–§8 below, replacing the flat, repository-agnostic 70/15/15 query split originally described in `EXPERIMENT_PLAN.md` §2. That document should be read as referring to the split defined here. No dataset construction described in this document has occurred yet; every number below is a target, not a report.

---

## 1. Objectives

This document exists to ensure TARA's evaluation data is constructed once, deliberately, and correctly — before any experiment consumes it — rather than assembled ad hoc as experiments are run. Its specific objectives:

1. Assemble a repository corpus diverse enough across language, size, and domain to support a defensible external-validity claim, while small enough to remain tractable for a modest research team (`PROJECT_SPEC.md` §7 scope constraints).
2. Construct the Task-Intent Query Set (TIQS), a benchmark resource that — as far as a literature-verification pass (`PROJECT_SPEC.md` §4) can currently confirm — does not have a direct existing analog: a query set labeled against an explicit, closed task-intent taxonomy with ground-truth relevant-context annotations.
3. Enforce a genuine train/validation/test separation **at the repository level**, not only the query level, so that no design decision (rule tuning, threshold selection, prompt iteration) made against data used to produce a paper's confirmatory results could have been informed, even indirectly, by that same data.
4. Make the complete dataset — repository selections, TIQS, and every annotation and quality-control artifact — versioned, reproducible, and, where licensing permits, releasable as a standalone resource independent of whether TARA's own central hypothesis is confirmed (`CONTRIBUTIONS.md` §5).

**Explicit non-goal:** this dataset is not sized or constructed to fine-tune an LLM or train a large classifier from scratch (`PROJECT_SPEC.md` §8). It is sized for evaluation and for informing, but not training, a future learned classifier (`CONTRIBUTIONS.md` §7).

## 2. Repository Selection Criteria

A candidate repository is eligible for the corpus only if it satisfies all of the following:

- **License:** MIT, Apache-2.0, or BSD (2- or 3-clause) — permits redistribution of derived artifacts (extracted context snippets, ground-truth annotations referencing its content) alongside the dataset release.
- **Active maintenance:** at least one commit within the 12 months preceding selection, to reduce the chance of the corpus over-representing abandoned or unidiomatic practice.
- **Language coverage:** contributes to the per-language quota defined in §3.
- **No duplication within the corpus:** not a fork, vendored copy, or git submodule of another corpus member, and not itself containing another corpus member as a submodule — avoiding near-duplicate content that would silently inflate apparent diversity or create cross-split leakage risk (see §17).
- **Durable public availability:** hosted at a stable, publicly browsable URL expected to remain accessible for the project's duration, so that a pinned commit remains fetchable by anyone attempting reproduction.
- **No active legal or licensing controversy** at the time of selection (e.g., a pending relicensing dispute), assessed at selection time only — this is a practical exclusion criterion, not an ongoing monitoring commitment.
- **Test-suite presence** is preferred but not mandatory for corpus eligibility; it instead gates that specific repository's queries for pass@k eligibility only (`EXPERIMENT_PLAN.md` §3).

## 3. Programming Languages

The corpus must cover all eight languages the Repository Parser supports (`tara.parsing.language_registry`): **Python, JavaScript, TypeScript, Java, Go, Rust, C, C++**.

**Per-split coverage requirement (new, beyond `EXPERIMENT_PLAN.md` §1's flat "coverage of all eight languages"):** each of the eight languages must be represented by at least one repository in **each** of the train, validation, and test splits (§6–§8) — a minimum of 3 repositories per language, 24 repositories total at minimum. This is required specifically so that language-specific behavior (naming-convention heuristics, per-language import-resolution patterns) can be iterated on using training/validation data and still independently verified on held-out test data, for every language, not only in aggregate.

**Stated scope boundary, restated from `PROJECT_SPEC.md` §27/§35:** this corpus, and therefore TIQS, does not attempt coverage of non-English query phrasing or non-Latin-script identifier conventions in v1. This is a deliberate scope limitation, not an oversight, and is listed again here because it directly shapes repository selection (no repository is excluded *for* using non-English comments, but no special effort is made to seek such repositories out either, since the classifier's heuristics are not yet designed to be evaluated fairly on them).

## 4. Repository Sizes

Three size buckets, by lines of code (LOC), restated from `EXPERIMENT_PLAN.md` §1: **small** (< 5,000 LOC), **medium** (5,000–50,000 LOC), **large** (50,000–200,000 LOC). Repositories above 200,000 LOC remain excluded from v1.

**Distribution across splits (new, refining `EXPERIMENT_PLAN.md` §1):**
- **Train and validation** splits draw primarily from **small and medium** repositories — these are the sizes the team will most directly inspect while iterating on classifier heuristics, threshold sweeps (A7), and prompt design, and keeping iteration cycles fast matters more there than size diversity.
- **Large repositories are deliberately concentrated in the test split.** This is a specific, reasoned choice: large repositories are the size tier most likely to reveal scaling issues (graph/index construction cost, symbol-index collision risk, retrieval precision degradation) that smaller development-time repositories would not surface — reserving them for test means the project cannot inadvertently tune its way around a large-repository-specific weakness before that weakness is ever measured, which is precisely the failure mode repository-level splitting (§6–§8) exists to prevent.
- Every split must still contain at least one small and one medium repository, so no split is entirely composed of one size bucket.

## 5. Repository Domains

**Domain** here means the general purpose/subject area of the repository, since task-type vocabulary and identifier conventions plausibly differ by domain (e.g., a CLI tool's vocabulary clusters around "flag"/"command"; a web backend's around "endpoint"/"route"; a data-processing library's around "transform"/"pipeline") — the classifier's per-category keyword sets (`tara.classification.heuristics`) were authored with general software-engineering vocabulary in mind, not validated against any specific domain, and an accidentally domain-homogeneous corpus would silently understate this risk.

**Target domain categories** (a working taxonomy for corpus selection purposes only, not a claim of completeness): web frameworks / backend services; CLI tools; data processing / scientific computing; systems / infrastructure tooling; general-purpose libraries and SDKs; and research tooling (TARA's own repository, `tara-rlcg`, sits here — see the dogfooding caveat in §6).

**Distribution requirement:** at least 3 distinct domains represented across the full corpus, with no single domain comprising more than half of all corpus repositories, so that no single domain's vocabulary can dominate rule design or evaluation without that dominance being a visible, checkable property of the corpus manifest (§14).

## 6. Training Repositories

**Purpose:** the set of repositories against which the team may freely iterate — reading code, refining classifier keyword sets, validating naming-convention assumptions, drafting and piloting TIQS annotation guidelines, and iterating on prompt templates (M9) — without any risk of contaminating a confirmatory result.

**Hard rule, stated once here and binding throughout the rest of this document:** nothing computed on training-repository data may be reported as, or contribute numerically to, a confirmatory result (`EXPERIMENT_PLAN.md` Tables 3–4). Training-repository TIQS queries exist for development and debugging only.

**Target allocation:** approximately **40%** of the corpus by repository count, satisfying the per-language (§3) and per-domain (§5) minimums, drawn primarily from the small/medium size buckets (§4).

**Dogfooding caveat (restated and tightened from `EXPERIMENT_PLAN.md` §1):** if TARA's own repository is included in the corpus at all, it belongs in the **training** split only, never in validation or test — the team's intimate familiarity with its own codebase makes it unsuitable as anything but a development-time convenience repository, and including it in a split used for confirmatory or even threshold-selection results would be a direct, easily-avoidable validity threat.

## 7. Validation Repositories

**Purpose:** the set of repositories against which any decision that must be finalized *before* the test split is touched is made — specifically, the A7 confidence-threshold sweep's chosen value, and any other tunable parameter with hyperparameter-like character (e.g., a BM25 parameter, a candidate-limit reranking multiplier, a token-budget cutoff for Context Fusion, once M5–M8 exist). The chosen configuration is frozen after this selection and applied unchanged to the test split.

**Target allocation:** approximately **25%** of the corpus, satisfying the per-language and per-domain minimums, drawn from a size-bucket mix similar to training (§4).

**Reporting rule:** validation-repository results may appear in the paper as supporting evidence for a specific design choice (e.g., a threshold-sweep curve justifying the chosen confidence cutoff) but must be **explicitly labeled as validation-split results** in every table/figure caption they appear in, and must never be merged into or presented alongside the confirmatory test-split main-results table (`EXPERIMENT_PLAN.md` Table 3).

## 8. Test Repositories

**Purpose:** the sealed, held-out set used exclusively to produce the paper's final, confirmatory H1–H5 results. Touched exactly once, after every design decision elsewhere in the pipeline has already been frozen.

**Target allocation:** approximately **35%** of the corpus, satisfying the per-language and per-domain minimums, and containing the large-size-bucket repositories concentrated here per §4.

**Sealing protocol (binding procedure, not aspiration):**
1. Commit SHAs for every test-split repository are pinned and recorded in the corpus manifest (§14) **before** any TIQS annotation on those repositories begins.
2. Annotators authoring or labeling test-split queries must not have participated in classifier rule-engine development, threshold selection, or prompt-template iteration against those specific repositories — this is a per-repository constraint, not a blanket exclusion of any team member from all annotation work.
3. No rule, threshold, or prompt change is permitted after the first look at any test-split result. Test-split evaluation is run by a single, dated, archived script execution; any subsequent change to the pipeline requires a **new, separately dated** run, and if both a pre- and post-change run exist, both are disclosed in the paper, not only the more favorable one.

## 9. Task Intent Query Set (TIQS)

TIQS queries are authored **against a specific pinned repository** and **inherit that repository's split** (train/validation/test, §6–§8) — this is the refinement to `EXPERIMENT_PLAN.md` §2 flagged at the top of this document. Splitting queries independently of their source repository (the original, flat 70/15/15 description) would permit a subtler leakage channel than it first appears: a team member could develop intuition from a *training-split* query authored against Repository X, and unconsciously bring that intuition to bear on a *test-split* query authored against that same Repository X, if X's queries were not required to sit entirely within one split. Repository-level splitting closes this channel by construction.

**Target size and stratification:** 480 queries total (proposed, per `EXPERIMENT_PLAN.md` §2), stratified two ways simultaneously:

| Dimension | Target |
|---|---|
| Per `TaskType` (13 categories) | ≈37 queries each |
| Per split | Train ≈192 (40%), Validation ≈120 (25%), Test ≈168 (35%) |

Exact per-cell counts (`TaskType` × split) will not be perfectly uniform, since they are constrained jointly by which repositories fall in which split and by which task types are naturally well-represented in a given repository — the 480/13/40-25-35 figures are targets to steer toward, not hard per-cell quotas; any resulting imbalance must be disclosed in the dataset statistics table (`EXPERIMENT_PLAN.md` Table 2), not silently smoothed over.

## 10. Annotation Protocol

**Annotator qualification:** annotators should have general software-engineering background sufficient to author and evaluate realistic developer queries; they need not be TARA contributors, and — per the sealing protocol in §8 — must not have contributed to classifier/threshold/prompt design against any repository whose queries they author or label.

**Calibration round, before full-scale annotation begins:** a pilot batch of approximately 20 queries, drawn from training-split repositories only, authored and independently double-labeled by all annotators, followed by a group discussion of disagreements — used to align interpretation of the taxonomy and the guidelines before they are applied at scale. The guideline document itself is versioned (§14); any revision made after the pilot round is recorded as a new guideline version, and the pilot batch's own labels are discarded from the reported dataset (they were for calibration, not for inclusion).

**Full annotation workflow**, per query:

1. **Authoring (Annotator A):** given a pinned repository and one of three prompt framings (an issue-tracker-style request, a code-review-comment-style request, or an onboarding-question-style request — rotated to encourage phrasing diversity), Annotator A writes a realistic query **without consulting the classifier's rule vocabulary** (`tara.classification.heuristics`), to avoid the circularity risk stated in `PROJECT_SPEC.md` §22 and `CONTRIBUTIONS.md` §6.
2. **Independent labeling (Annotator B, blind):** a different annotator, without seeing Annotator A's identity or any existing label, assigns a `TaskType` label and constructs a ground-truth relevant-context set (§11) by inspecting the actual pinned repository.
3. **Independent labeling (Annotator A, blind, after a delay):** the original author independently re-labels their own query — blind to their own original intent framing, having moved on to other queries in the interim — providing the second label needed for the agreement computation in §13.
4. **Adjudication:** where the two `TaskType` labels or the two relevant-context sets disagree materially, a third annotator reviews both and either selects one, merges them, or escalates to a guideline revision if the disagreement reveals a genuine taxonomy gap.

**Tooling:** a structured annotation form or lightweight internal tool (exact tooling **TBD**) capturing, at minimum: query text, repository identifier and pinned commit, `TaskType` label, relevant-context set, optional reference output, annotator identifier, and timestamp — sufficient for every quality-control check in §12 to be run mechanically rather than manually re-derived.

## 11. Ground Truth Creation

**Relevant-context ground truth:** the annotator inspects the actual pinned repository at its pinned commit (never from memory or general familiarity) and records the minimal set of files and/or symbols a competent developer would need to address the query. Symbol-level entries use the same node-id scheme already implemented by `tara.context.models.build_symbol_node_id`, so that retrieval-quality metrics (`EXPERIMENT_PLAN.md` §3) can compare a retriever's output against ground truth directly, without a translation layer between annotation format and system output format.

**Graded vs. binary relevance:** whether an annotator additionally records a graded relevance tier (e.g., primary/essential vs. secondary/helpful) — needed for NDCG@k — is **TBD**, consistent with the conditional NDCG status already stated in `EXPERIMENT_PLAN.md` §3; if adopted, the tiering scheme must be fixed in the annotation guideline before the calibration round (§10), not introduced partway through annotation.

**Reference-output construction, for queries where a generation-quality reference is feasible:** code-generation tasks frequently admit more than one valid solution, so exact-match ground truth is often ill-posed. The default reference format is an **acceptance-criteria rubric** (a short, checkable list of properties a correct output must satisfy), not a single canonical code string. A single canonical reference string is used only where the query genuinely has one clear correct answer (e.g., a specific, unambiguous bug fix with one evident correct patch) — this distinction is itself recorded per query, so downstream exact-match scoring is only ever applied where it is a valid metric, per `EXPERIMENT_PLAN.md` §3's exact-match definition.

**Verification:** every relevant-context entry is spot-checked by a second annotator on a random 20% sample per split (§12), and every file path / symbol id is mechanically verified to exist in the pinned repository at the pinned commit before the query is accepted into the dataset.

## 12. Quality Control

Quality control operates in layers, each catching a different failure mode:

1. **Pre-annotation calibration** (§10) — aligns interpretation before scale annotation begins.
2. **Double-labeling and adjudication for `TaskType`** (§10) — the primary defense against individual annotator error or drift.
3. **Spot-check of relevant-context ground truth** — a second annotator independently re-derives the relevant-context set for a random 20% sample per split, compared against the original via the agreement measure in §13.
4. **Automated existence checks** — a mechanical script verifies every referenced file path and symbol id resolves against the pinned repository at the pinned commit; any query failing this check is rejected and returned to the authoring annotator, not silently corrected.
5. **Periodic batch review** — every 50 annotated queries, a random subsample is reviewed by the full annotation team together, specifically to catch slow interpretive drift that pairwise adjudication alone might not surface.
6. **Final full-dataset consistency pass**, before any version is frozen (§14): checks for duplicate or near-duplicate queries, checks the realized `TaskType` and split distributions against the targets in §9 (with any material deviation disclosed, not corrected after the fact by discarding inconvenient queries), and checks that no query's repository reference crosses its declared split.

## 13. Inter-Annotator Agreement

**Primary measure — `TaskType` labels:** Cohen's κ, computed on the double-labeled pairs, with the same acceptability threshold as `PROJECT_SPEC.md` §22 and `EXPERIMENT_PLAN.md` §6: **κ ≥ 0.6**. Computed **overall and separately per split** (train/validation/test), since annotation difficulty could plausibly differ by repository size or domain composition, and an aggregate κ above threshold could mask a below-threshold split.

**Secondary measure — relevant-context ground truth (new, not previously specified in `PROJECT_SPEC.md`/`EXPERIMENT_PLAN.md`):** since retrieval-quality metrics (Precision@k, Recall@k, MRR) are only as trustworthy as the relevant-context labels they are computed against, the relevant-context spot-check (§11, §12) is scored with a **set-overlap agreement measure (Jaccard similarity, with mean and distribution reported; F1 reported as a secondary form of the same comparison)** between the original annotator's set and the spot-checking annotator's independently-derived set. There is no pre-existing convention to borrow a threshold from as directly as Cohen's κ's; a **target mean Jaccard similarity ≥ 0.5** is proposed as this project's own acceptability threshold, to be revisited once pilot-round data exists to judge whether it is realistic.

**Escalation protocol:** if either agreement measure falls below its threshold on any split, annotation for that split pauses; guidelines are revised, a fresh pilot batch from that split's repositories is double-labeled and reviewed, and full-scale annotation for that split does not resume until the threshold is met on the revised pilot batch.

## 14. Versioning

**TIQS versioning:** semantic-version-style tags (e.g., `v0.1-pilot` for the calibration batch, never included in a released dataset version; `v1.0` for the first frozen version used to produce paper results). Every tagged version is **immutable** — a later-discovered error is corrected by publishing a new version with a changelog entry describing the fix, never by silently editing a previously tagged version, since a paper's reported numbers must map to one exact, unchanging dataset version indefinitely.

**Repository corpus versioning:** every corpus repository's identity (source URL, pinned commit SHA, license, language, size bucket, domain category, assigned split) is recorded in a single version-controlled manifest file (proposed location: `evaluation/datasets/repository_manifest.json`, consistent with the `evaluation/` layout already proposed in `PROJECT_SPEC.md` §12 / `ROADMAP.md` M10). Any re-pin of a repository (e.g., because a previously selected repository becomes unavailable) is itself a dataset-version bump, with the reason recorded in the manifest's changelog, never a silent substitution.

**Storage format:** TIQS itself is stored as plain-text/structured data (e.g., JSON Lines or CSV, exact format **TBD**), chosen specifically for diffability under version control — no binary or proprietary format, so that any change between dataset versions is human-reviewable in a standard diff.

## 15. Dataset Release Plan

**What is released:** the TIQS query/label/ground-truth data, the annotation guideline document (all versions, not only the final one, for methodological transparency), the repository manifest (source URLs and pinned commit SHAs), and the quality-control summary statistics (agreement scores, per §13).

**What is not vendored:** repository *contents* are not redistributed as part of the TARA/TIQS release. Users reconstruct the exact corpus by cloning each manifest-listed repository at its pinned commit. This decision is deliberate, not an oversight: it avoids repository-size bloat in the TARA release, avoids any ambiguity about redistribution terms for another project's full source tree even under a permissive license, and is consistent with the project's general preference (already applied to the embedding-model and LLM decisions, `DESIGN_DECISIONS.md` §5/§9) for reproducibility via pinning rather than via vendoring.

**Release format:** a dataset card documenting purpose, construction methodology, the taxonomy TIQS is labeled against, known limitations (cross-referencing §16–§17 below), a license (a permissive, open data license — candidate CC-BY-4.0, **TBD pending a legal/licensing review** specific to redistributing annotations that reference third-party source code), and citation information once the associated paper is published or a preprint exists.

**Release timing:** train and validation splits, and the guideline documents, are released together once TIQS reaches its first frozen version (`v1.0`). The test split's **queries** are released at the same time; its **ground-truth labels** are released alongside the paper's submission or acceptance (whichever the venue's norms make appropriate), not earlier — this is a modest, non-leaderboard academic dataset, and a full formal holdback/leaderboard infrastructure was considered and judged disproportionate to its scale, but releasing ground truth simultaneously with a not-yet-public paper's queries was avoided as an easy, low-cost precaution against inadvertent early use. The release should explicitly recommend that TIQS not be included in future LLM pretraining corpora, for the same contamination reasons discussed in `EXPERIMENT_PLAN.md` §14 — a recommendation, not an enforceable restriction, and stated as such.

**Hosting:** a public code-hosting platform (e.g., GitHub, alongside the TARA codebase) at minimum; a dedicated dataset-hosting platform for discoverability is under consideration but **TBD**.

## 16. Ethical Considerations

- **License and attribution:** repository selection is restricted to permissively-licensed projects specifically so that redistribution rights are unambiguous (§2); the release (§15) credits each source repository and its original authors explicitly, rather than treating extracted excerpts as anonymous input data.
- **Annotator labor:** annotators contributing substantive intellectual work (query authoring, labeling, guideline co-design) should receive appropriate credit — co-authorship or formal acknowledgment, per the eventual venue's norms — and, if compensated, compensated fairly for the time annotation genuinely requires (informed by the pilot round's measured per-query time, not assumed in advance).
- **Incidental sensitive content:** although source repositories are public open-source code, an annotator excerpting real repository content (a file, a code comment, a commit message) for a ground-truth or reference-output entry must flag and exclude any inadvertently-included sensitive material (e.g., a credential accidentally committed upstream, a personal email address in a comment) from the released dataset, rather than assuming public-repository status alone guarantees this cannot occur.
- **Representativeness, stated plainly:** neither the repository corpus nor the annotator pool is claimed to be demographically or globally representative of the developer population at large — open-source GitHub repositories and a small, non-randomly-sampled annotator group both carry selection bias, and TIQS should be described and cited as a specific, bounded resource, not generalized beyond that.
- **Dual-use acknowledgment:** a system and dataset aimed at improving repository-level retrieval for code generation is, like any such tool, agnostic between assisting a correct change and assisting an incorrect or malicious one — retrieval quality does not distinguish intent. This is noted here in the same spirit as `CONTRIBUTIONS.md`'s explicit non-claim regarding the `SECURITY` task type: the project does not claim to improve code security or safety outcomes, only retrieval relevance, and this distinction should not be blurred in how the dataset or system is described publicly.
- **Disclosure of any LLM assistance in dataset construction:** if an LLM is used at any point to help annotators brainstorm query phrasing or draft guideline text, this must be disclosed in the dataset card (§15), and any LLM-assisted query drafting must still satisfy the "not derived from the classifier's own rule vocabulary" constraint (§10) — LLM assistance is a process detail to disclose, not an exemption from the circularity-avoidance requirement.

## 17. Threats

Threats specific to dataset construction; broader experimental threats to validity are covered in `EXPERIMENT_PLAN.md` §14 and are not repeated here except where directly relevant.

- **Selection bias toward "well-known, well-maintained" repositories.** The eligibility criteria in §2 (active maintenance, durable availability, no license controversy) systematically favor mature, popular projects over messier, more typical real-world codebases — plausibly the majority of real code developers actually work in daily. Findings should be understood as applying to this specific kind of repository, not to codebases generally.
- **Small corpus size limits per-language and per-domain conclusions.** With a minimum of 3 repositories per language, any single repository's idiosyncrasies could disproportionately shape that language's apparent results; this compounds the already-noted statistical-power limitation for `TaskType` subgroups (`EXPERIMENT_PLAN.md` §6, §14).
- **Repository-level split leakage risk, specific to this document's own new design.** The repository-level train/validation/test separation (§6–§8) is only as strong as its procedural enforcement — an annotator who has read a training-split repository's code and later authors a test-split query for a *different* repository could still, in principle, bring generalized pattern-matching intuition across the boundary in a way pure repository-level splitting cannot fully prevent. This is a real, acknowledged residual risk of any human-annotation process, not fully closed by the split design, only substantially reduced by it.
- **Ground-truth relevant-context subjectivity.** Two competent developers can reasonably disagree about whether a borderline file belongs in a query's relevant-context set — this is precisely what the Jaccard-agreement measurement (§13) is designed to quantify, but a Jaccard score below 1.0 (which should be expected, not treated as a defect) means every retrieval-quality metric computed against this ground truth inherits some irreducible measurement noise, which should be stated alongside any precision/recall result, not only in this document.
- **Domain and language imbalance despite quotas.** Meeting the minimum per-language and per-domain repository counts (§3, §5) does not guarantee genuinely equal *richness* or *difficulty* of task-relevant content across them — a language represented by exactly the quota minimum could still be thinly covered in practice even while nominally satisfying the target.
- **Data contamination in candidate generation LLMs.** Directly relevant to repository *selection*, not only to downstream evaluation: where feasible, repository/commit selection should prefer content created or substantially modified after a candidate generation model's disclosed training cutoff (`EXPERIMENT_PLAN.md` §14), though this preference must be balanced against the maintenance/popularity criteria in §2, which can pull toward older, more established projects.
- **Manifest-based reproducibility is contingent on repository persistence.** Despite the durable-availability criterion (§2), a selected repository could still be taken down, relicensed, or have its history rewritten after pinning; the versioned-manifest re-pin process (§14) is a mitigation, not a guarantee, and any such event during the project's timeline should be disclosed in the dataset's changelog, not quietly worked around.
