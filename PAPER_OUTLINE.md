# PAPER_OUTLINE.md

## TARA: Publication Outline

**Purpose.** This document specifies the section structure of the eventual TARA paper and, for each section, what content belongs there, what it must establish, what it must avoid, and which existing project document(s) it should be drafted from. **It contains no paper prose.** Every entry below is meta-level drafting guidance (what to write, not the writing itself). This outline should be used as the drafting checklist during Phase 10 of `EXPERIMENT_PLAN.md` §15, and is expected to be filled in incrementally as earlier phases complete — several sections below can be drafted today (Introduction, Related Work, Methodology, Architecture, Implementation); several cannot be honestly drafted until results exist (Results, most of Discussion) and should remain outlined-but-empty until then.

**Governing constraint, carried from every prior document in this suite:** no claim in any section may exceed what `CONTRIBUTIONS.md` states the project can support. Where a section's natural content would overclaim, this outline says so explicitly.

**Source-document map**, so a drafter always knows where to pull from:

| Paper section | Primary source(s) |
|---|---|
| Abstract | All documents, written last |
| Introduction | `PROJECT_SPEC.md` §1–§5, `CONTRIBUTIONS.md` §1 |
| Related Work | `PROJECT_SPEC.md` §4 |
| Methodology | `PROJECT_SPEC.md` §3, §5, §6, §17 (design rationale); `docs/task_taxonomy.md` |
| Architecture | `PROJECT_SPEC.md` §9–§11, §18 |
| Implementation | `PROJECT_SPEC.md` §12–§14, §19–§21; `CONTRIBUTIONS.md` §3 |
| Experimental Setup | `EXPERIMENT_PLAN.md` §1–§9 |
| Results | `EXPERIMENT_PLAN.md` §10–§11 (once populated with real numbers) |
| Discussion | `EXPERIMENT_PLAN.md` §12–§13 |
| Limitations | `CONTRIBUTIONS.md` §6, `EXPERIMENT_PLAN.md` §14 |
| Future Work | `CONTRIBUTIONS.md` §7 |
| Conclusion | `CONTRIBUTIONS.md` §1–§2, Results (compressed) |
| References | See §13 below |

---

## 1. Abstract

**What belongs here:** a single paragraph (venue length limit TBD, typically 150–250 words) stating, in order: (a) the problem — repository-level code generation systems typically select a retrieval strategy independent of what the developer is actually trying to do; (b) the approach — TARA's explicit, deterministic task-classification-and-routing layer inserted before retrieval; (c) what was built — the specific pipeline stages and their engineering properties worth a one-clause mention (deterministic, sub-millisecond classification/routing, no LLM in the routing path); (d) what was evaluated and how — one clause naming the benchmark (TIQS) and the comparison performed; (e) the headline finding, stated at the precision the actual result supports (a clear win, a mixed/task-type-dependent result, or a null result are all legitimate things to state here — see `CONTRIBUTIONS.md` §4's commitment to reporting null results); (f) availability — that code and, where applicable, the dataset are released.

**What must NOT go here:** any claim of state-of-the-art generation quality, any claim of superiority over AIRCoder/RepoFormer/AllianceCoder/RepoGraph/STALL+ that is not backed by Table 6 of `EXPERIMENT_PLAN.md` (reproduction-status-qualified), and no forward-looking claim about future work.

**Drafting note:** write this section **last**, after Results and Discussion are finalized. Every sentence in the abstract must be traceable to a specific table, figure, or explicitly-stated finding elsewhere in the paper — this is a checkable property a drafter should verify sentence-by-sentence before submission, not a stylistic aspiration.

## 2. Introduction

**What belongs here**, in the following order:

1. **A concrete motivating contrast**, establishing intuitively why a single fixed retrieval strategy is insufficient — drawing on the kind of example already used throughout the project's own documents (e.g., an exact-symbol-lookup query vs. a graph-traversal query vs. a conceptual-explanation query, each plausibly best served by a different retrieval mechanism). This should be concrete and specific, not abstract throat-clearing.
2. **The general problem statement**, compressed from `PROJECT_SPEC.md` §3 — one or two sentences, not the full formalization (that belongs in Methodology).
3. **The stated gap relative to prior work**, compressed from `PROJECT_SPEC.md` §4 — naming the closest system (AIRCoder) and stating precisely, in one to two sentences, what distinguishes TARA's approach, with the explicit caveat (stated in the paper, not only in this outline) that a literature-verification pass confirming this distinction against AIRCoder's actual published mechanism is a prerequisite for this claim to stand as written (`PROJECT_SPEC.md` §4 already flags this as an open verification item).
4. **The research question and central contribution**, stated as one crisp sentence matching `CONTRIBUTIONS.md` §1's framing: this is a system-design-and-evaluation contribution, not a new retrieval algorithm or model.
5. **A compressed contributions list** (3–5 bullet points, drawn from `CONTRIBUTIONS.md` §1–§3, selecting only what the finished experiments actually support — do not list a prospective/untested contribution here as if delivered).
6. **A one-paragraph roadmap** of the rest of the paper's structure.

**What must NOT go here:** the full research-question list (RQ1–RQ6) or hypothesis list (H1–H5) verbatim — those belong in Methodology; any experimental number (Introduction is written before or independent of specific result values being quoted, aside from the abstract-level headline finding if the venue convention calls for restating it).

**Length guidance:** roughly one to one-and-a-half printed pages in a typical two-column venue format.

## 3. Related Work

**Structure:** organize by cluster, not strictly by citation order, so the section reads as a synthesis rather than a list. Suggested clusters, each ending in a short "how TARA differs" sentence specific to that cluster:

1. **Retrieval-augmented code generation, generally** — brief grounding of the broader RAG-for-code space the paper sits in.
2. **Repository-level context construction** — RepoGraph (graph-based repository representation) as the primary citation; TARA's Context Extractor graph is narrower in scope (containment/definition/import edges only at present, per `PROJECT_SPEC.md` §10) and this narrower scope should be stated plainly, not glossed over, when differentiating from RepoGraph.
3. **Repository-level retrieval for completion** — RepoFormer, characterized (pending verification) as dense-retrieval-centric; used as grounding for the "semantic-only" baseline family (B1/B6 in `EXPERIMENT_PLAN.md` §4).
4. **Adaptive/iterative retrieval** — AIRCoder, the closest work (`PROJECT_SPEC.md` §4). This paragraph requires the most careful, precise differentiation in the entire section: state exactly what is and is not currently known/verified about AIRCoder's routing-signal source, and phrase the distinction from TARA (explicit pre-retrieval task classification vs. retrieval-internal adaptive signals) as the paper's central related-work contrast.
5. **Ensemble/multi-retriever approaches** — AllianceCoder; used to motivate the `FULL_PIPELINE` / always-hybrid baseline (B2/B7).
6. **Retrieval-augmentation strategy studies for code LLMs** — STALL+; positioned as a methodological/analytical reference point, exact relationship to TARA's design **TBD pending literature review** (per `PROJECT_SPEC.md` §4).
7. **Benchmarks and evaluation methodology for retrieval-augmented code generation** — CodeRAG-Bench, cited both as related work and as a methodological influence on `EXPERIMENT_PLAN.md`'s metric and dataset design (§2–§3); this dual role should be made explicit rather than citing it only once and losing that connection.
8. **(Optional, if space and relevance permit) Query-intent classification outside code** — general information-retrieval query-intent taxonomies, cited briefly to situate TARA's task-taxonomy design (`docs/task_taxonomy.md`) within a broader, pre-existing tradition of explicit intent classification for retrieval, rather than presenting the *idea* of intent-conditioned retrieval as novel to this paper (it is not; what is under test is its application and evaluation in this specific setting — see §1 of `CONTRIBUTIONS.md`).

**Closing paragraph:** a single synthesizing paragraph stating the gap precisely (`PROJECT_SPEC.md` §4's "stated gap" paragraph is the direct source), setting up Methodology.

**What must NOT go here:** any claim that no prior work has considered task-aware or intent-aware retrieval in general (§3.8 above exists specifically to prevent this overclaim) — the precise, defensible claim is narrower: no *verified* prior system in this specific literature cluster performs *this* combination (explicit closed taxonomy, deterministic pre-retrieval classification, enumerable strategy space, per-decision natural-language justification) for *this* problem (repository-level code generation).

## 4. Methodology

**What belongs here** — the conceptual research design, independent of any specific implementation technology:

1. **Formal problem statement**, drawn directly from `PROJECT_SPEC.md` §3: given a repository and a query, select a context subset maximizing downstream generation quality subject to latency/token constraints.
2. **The two-stage decision reframing**: classify task intent, then select a retrieval strategy as a function of that classification and repository state — stated as the paper's core methodological move, distinguished from the "retrieve directly by similarity" formulation used elsewhere in related work.
3. **Task taxonomy design rationale.** This subsection should explain *why* a small, closed, human-interpretable taxonomy was chosen over an open-ended or learned representation of task intent, and should explicitly acknowledge the existence of **two related but distinct taxonomies** in this project (`CONTRIBUTIONS.md` §2, item 1): the 13-category routing taxonomy and the 6-category semantic taxonomy (`docs/task_taxonomy.md`), stating clearly which one the paper's classifier and experiments actually use, and describing the other as a complementary conceptual artifact rather than silently conflating the two.
4. **Research questions and hypotheses**, stated in full here (RQ1–RQ6, H1–H5, from `PROJECT_SPEC.md` §5–§6) — this is the correct location for the complete list, not the Introduction.
5. **Evaluation methodology at the conceptual level**: within-subjects design against a fixed benchmark, the role of baselines vs. ablations as answering different questions (baselines answer "is this better than alternatives," ablations answer "which part of this contributes"), and the pre-registration discipline itself (stating that hypotheses, metrics, and statistical tests were fixed before results were observed) — worth stating explicitly as a methodological strength, not merely practiced silently.

**What must NOT go here:** specific dataset names/sizes, specific model names, specific hardware, specific statistical test parameters (α levels, correction method) — all of that is Experimental Setup. Methodology answers "what is the logic of the evaluation," Experimental Setup answers "exactly what was run."

## 5. Architecture

**What belongs here** — the system's structural design, at the level of a paper figure and accompanying prose, not implementation detail:

1. **The five-stage pipeline diagram** (Figure 1 per `EXPERIMENT_PLAN.md` §10), with one paragraph per stage stating its responsibility and its input/output data contract at a conceptual level (`PROJECT_SPEC.md` §9–§10).
2. **The interface-first, Dependency-Inversion design principle**, explained specifically for *why it matters to this paper's methodology*: because every stage is independently substitutable, the ablation program (`EXPERIMENT_PLAN.md` §5) is implementable as configuration rather than as source forks, which is a direct methodological enabler worth stating in the architecture section rather than only in an implementation appendix.
3. **The routing algorithm's conceptual structure**: the priority-ordered policy chain and the separate planning step (`PROJECT_SPEC.md` §18), presented as a decision diagram or a short structured description — the *logic* of first-match-wins policy dispatch and of separating "what to retrieve with" from "how to execute it," not the concrete Python class names.
4. **The task-type-conditioned override** (the `REFACTOR` exception), presented here as a documented architectural decision with its stated rationale, cross-referenced forward to where it is empirically tested (Results §8, ablation A2).

**What must NOT go here:** package/module names, function signatures, dependency library names (`networkx`, `pydantic`, etc.) — those belong in Implementation. Architecture is about structure and decision logic; Implementation is about what it is built out of.

## 6. Implementation

**What belongs here:**

1. **Current implementation status, stated plainly and specifically**, including exactly which pipeline stages exist and are tested at time of submission (`CONTRIBUTIONS.md`'s status framing) — a paper claiming an evaluated system must not obscure which parts were built for that evaluation versus described only at the design level; if retrieval/fusion/generation are implemented by submission time, state so; if any remain design-only, state that too, explicitly, in this section rather than leaving a reader to infer it from the Experimental Setup.
2. **Technology stack**, compressed from `PROJECT_SPEC.md` §13, naming the concrete tools/libraries actually used (Tree-sitter for parsing, NetworkX for the graph, the specific embedding library, the specific LLM interface pattern) — this is where such names belong, in contrast to Architecture above.
3. **Notable implementation details worth a paper-level mention**, selected for genuine relevance to correctness or reproducibility rather than exhaustively listing engineering minutiae: the shared node-id scheme guaranteeing consistency across the graph, symbol index, and embedding store; the context-capability downgrade mechanism (routing decisions adapting to what a given repository's extracted context actually supports); the deterministic, rule-based classifier design and its stated rationale for being LLM-free.
4. **Engineering rigor as evidence supporting the paper's reproducibility claims**: test coverage figures (e.g., total passing tests, per-stage), and the measured (not merely budgeted) latency figures for the deterministic stages, since these are already-demonstrated, verifiable properties as of `CONTRIBUTIONS.md` §3 and can be stated with confidence independent of the main experimental results.
5. **A reproducibility statement**: pinned dependency versions, open-source release location, licensing — cross-referenced to `CONTRIBUTIONS.md` §5.

**What must NOT go here:** any experimental result (retrieval quality, generation quality) — Implementation describes what was built, not how well it performed.

## 7. Experimental Setup

**What belongs here** — a compact, reader-facing summary of `EXPERIMENT_PLAN.md` §1–§9, structured as short subsections with a table reference for anything enumerable:

1. **Repository corpus** — one short paragraph plus a reference to the corpus statistics table (`EXPERIMENT_PLAN.md` Table 1): languages covered, size range, licensing, freezing protocol (pinned commits).
2. **Benchmark (TIQS)** — construction summary (annotator count, agreement protocol and achieved κ, size, per-category stratification), referencing Table 2; brief mention of any external benchmark subset reused for pass@k, with the exact executable-subset size disclosed.
3. **Baselines** — the baseline table (`EXPERIMENT_PLAN.md` §4) reproduced or summarized, with each baseline's purpose stated in one clause.
4. **Ablations** — the ablation table (§5) summarized similarly.
5. **Metrics** — the metric list (§3), with formulas included only for non-standard or easily-ambiguous cases (e.g., the exact pass@k estimator used) — well-known metrics (Precision@k, F1) need not have their formula re-derived in the paper if space is constrained, only cited.
6. **Statistical procedure** — the test, correction method, and significance threshold (§6), stated once here so Results and Discussion can refer back to "significant" without redefining it each time.
7. **Hardware, LLMs, embedding models** — compressed from §7–§9, exact model identifiers/versions and exact hardware, since these must be reproducible-grade precise per the reproducibility commitment (`PROJECT_SPEC.md` §29).

**What must NOT go here:** the rationale/justification for *why* a given statistical test or metric was chosen over alternatives — that belongs in Methodology (or a footnote at most); Experimental Setup states what was done, Methodology (and this outline's §4) states why.

## 8. Results

**Current status: this section cannot be honestly drafted yet.** No experiment described in `EXPERIMENT_PLAN.md` has been run. What follows is the section's intended *shape*, to be populated once Phase 7–9 (`EXPERIMENT_PLAN.md` §15) complete.

**What belongs here**, structured as one subsection per research question, each ending in a reference to its corresponding table/figure (`EXPERIMENT_PLAN.md` §10–§11):

1. **Classification results (RQ1)** — Table 7, Figure 3 (confusion matrix), Figure 4 (calibration).
2. **Retrieval quality results (RQ2)** — Table 3 (main results), Table 4 (per-task-type breakdown), Figure 5.
3. **Generation quality results (RQ3)** — Table 3 continued, Figure 7, with the executable-subset size for pass@k stated inline wherever pass@k is reported, never presented without that qualifier.
4. **Efficiency results (RQ4)** — Figure 6, plus the specific descriptive statistic motivating any efficiency claim (e.g., the fraction of queries routed to single-retriever strategies).
5. **Explainability results (RQ5, exploratory)** — reported descriptively, explicitly labeled exploratory, not folded into the confirmatory results above.
6. **Confidence-calibration results (RQ6)** — Figure 9.
7. **Ablation results** — Table 5, Figure 8, one short paragraph per ablation stating the observed effect (or absence of one) without yet interpreting *why* (interpretation is Discussion's job).

**Discipline to state explicitly in the drafted section:** Results reports what was observed, with statistical qualifiers (significance, effect size, CI) attached to every comparison; it does not yet explain *why* a pattern occurred or relate it back to the taxonomy design (`docs/task_taxonomy.md`) — that synthesis is deliberately deferred to Discussion, per standard practice, so that Results remains a clean, checkable record of the numbers.

**What must NOT go here:** interpretation, comparison to intuition, or any claim about *why* a result occurred — reserve all of that for §9.

## 9. Discussion

**What belongs here**, using the pre-registered "Expected Analysis" reasoning in `EXPERIMENT_PLAN.md` §12 as the direct template for what each subsection's argument structure should look like once real numbers are available:

1. **Per-hypothesis interpretation (H1–H5)**, following exactly the support/refute logic pre-specified in `EXPERIMENT_PLAN.md` §12 — including the diagnostic decomposition for a negative result (e.g., distinguishing "classification failed" from "classification succeeded but didn't propagate to retrieval gains") rather than reporting a flat "no effect."
2. **Synthesis with the task taxonomy.** This is where the paper connects quantitative results back to the qualitative, per-task-type reasoning already documented in `docs/task_taxonomy.md` — e.g., if TARA's advantage concentrates in Refactoring/Bug-Fix-type queries and is flat or negative for Documentation-type queries, this should be discussed in light of `docs/task_taxonomy.md`'s stated expectation that different task types have structurally different retrieval needs (recall-dominant vs. precision-dominant vs. rationale-dominant), turning a numeric pattern into an explained one.
3. **Ablation synthesis** — which architectural decisions (the `REFACTOR` override, graph retrieval, reranking, confidence thresholding) turned out to matter and which did not, discussed together as a coherent narrative about where the system's complexity is and is not earning its cost, referencing Figure 8 as a single entry point into this discussion.
4. **Qualitative failure analysis discussion**, drawing on `EXPERIMENT_PLAN.md` §13's failure taxonomy (Table 8) and the case study (Figure 10) — used to illustrate and ground the quantitative findings, not to introduce new unquantified claims.
5. **Relation back to Related Work**, explicitly revisiting the AIRCoder differentiation claim from §3 above in light of actual results (or, if AIRCoder reproduction was not achievable per Table 6, explicitly stating that this comparison remains architectural/qualitative only, not empirical).
6. **Direct engagement with the falsifiability framing from `CONTRIBUTIONS.md` §1**: a paragraph stating plainly whether the central contribution's claim was supported, partially supported, or not supported, and why — this paragraph should be the single most quotable, unhedged paragraph in the paper, precisely because everything around it is appropriately hedged.

**What must NOT go here:** restating the numbers already given in Results without adding interpretation (a common weakness reviewers flag); any new quantitative claim not already presented in a Results table/figure — Discussion interprets, it does not introduce.

## 10. Limitations

**What belongs here** — a direct synthesis of `CONTRIBUTIONS.md` §6 and `EXPERIMENT_PLAN.md` §14, organized so the reader sees both the *research-design* limitations and the *validity-threat* limitations without redundant restatement:

1. **Scope limitations** — the fixed, small repository corpus and language set (eight languages, English/Latin-identifier-centric heuristics); the fixed, modest-sized benchmark (TIQS); explicit statement that generalization beyond this scope is unverified, not merely "left to future work" (that framing belongs in §11 below, not here — here, the limitation itself is stated).
2. **Taxonomy limitations** — both taxonomies are hand-authored and have not been validated against a large corpus of naturalistic queries or against prior taxonomic literature at scale; the potential circularity between the classifier's authors and TIQS's annotators (mitigated, not eliminated, by the independent-annotation protocol).
3. **Design-choice limitations** — the classifier is deliberately non-learned, so this work does not by itself establish that explicit rule-based classification outperforms a learned or LLM-based alternative, only that it is implementable, testable, and (per whatever Results show) competitive or not on this benchmark.
4. **Reproduction limitations** — the uncertain status of external baseline reproduction (Table 6), stated with the same precision as in the Results/Discussion sections, not softened here.
5. **Data-contamination threat** (`EXPERIMENT_PLAN.md` §14) — stated explicitly regardless of whether concrete contamination was detected during the study.
6. **Statistical power limitations** — the per-task-type subgroup analyses are exploratory, not confirmatory, given TIQS's size; stated here as a limitation of what can be concluded, not only as a methods-section caveat.

**Drafting note:** this section should be direct and unhedged in tone even though its content is about hedging everything else — a Limitations section that itself reads as defensive or minimizing undermines the paper's credibility more than the limitations themselves do.

## 11. Future Work

**What belongs here** — a curated, prioritized subset of `CONTRIBUTIONS.md` §7 (not the full list verbatim; a paper's Future Work section should be shorter and more selective than a living project roadmap document), with each item explicitly connected to the specific limitation (§10 above) it would address, so the section reads as a response to the paper's own limitations rather than a generic wish list:

1. **Learned/LLM-based classifier comparison** — directly addresses the design-choice limitation (§10.3); the single most important item to lead with, since it is the most direct empirical follow-up to this paper's central design choice.
2. **Call-graph and inheritance-edge resolution**, enabling genuinely multi-hop graph retrieval — addresses a scope limitation in what the current graph retrieval can express, independent of the classification/routing question.
3. **Taxonomy reconciliation and/or naturalistic-corpus validation** — directly addresses the taxonomy limitation (§10.2).
4. **Extension to additional languages and non-English queries** — directly addresses the scope limitation (§10.1).
5. Remaining items from `CONTRIBUTIONS.md` §7 (multi-hop/agentic retrieval, cross-repository retrieval, cost-aware routing, active-learning feedback loop, production service layer) may be included briefly, but should be visibly deprioritized relative to items 1–4 above, which follow most directly from this paper's own stated limitations.

**What must NOT go here:** any future-work item framed as if it were already partially demonstrated by this paper's results — future work is explicitly *not yet done*, and should read as clearly distinct from the Results/Discussion sections' claims.

## 12. Conclusion

**What belongs here** — short (typically under half a page):

1. One-paragraph restatement of the problem and approach, compressed further than the Introduction's version.
2. A compressed restatement of the contributions actually delivered (per `CONTRIBUTIONS.md` §1–§2), filtered to what Results/Discussion actually support — a Conclusion must not introduce, restate more strongly, or generalize beyond any claim already established earlier in the paper.
3. A one-sentence restatement of the headline finding, at the same precision level used in the Abstract (§1) — Abstract and Conclusion should be near-mirror-images in what they claim, which is a useful self-check during drafting: if they diverge, one of them is wrong.
4. A closing statement on availability (open-source release) and, if applicable, on the significance of a null or partial result as a legitimate contribution to the field's understanding of this design space (per `CONTRIBUTIONS.md` §4's stated commitment) — this closing framing matters specifically because it is the reader's last impression of how the authors themselves characterize their own findings.

**What must NOT go here:** any new citation, any new figure/table, any claim not traceable to an earlier section.

## 13. References

**What belongs here** — not paper prose, but a checklist of the citation categories that must be assembled and correctly resolved before submission:

1. **The five/six named related systems** — AIRCoder, RepoGraph, RepoFormer, AllianceCoder, STALL+, CodeRAG-Bench — full bibliographic entries, contingent on the literature-verification pass flagged as outstanding in `PROJECT_SPEC.md` §4; this verification must be completed **before** the Related Work section (§3 above) is finalized, since the differentiation claims in that section depend on it.
2. **Foundational retrieval-augmented generation literature** (the general RAG paradigm, cited briefly to ground the approach for readers outside the code-specific subfield).
3. **Foundational code-LLM literature** relevant to the generation stage and to the pass@k metric specifically (the unbiased pass@k estimator's original source).
4. **Model/tool citations required for reproducibility**: the specific embedding model(s) used (§9 of `EXPERIMENT_PLAN.md`, model card citation), the specific LLM(s) used (§8, model card or technical report citation), Tree-sitter, NetworkX, FAISS, and any other load-bearing dependency a venue's citation norms expect to be credited rather than only listed in a reproducibility appendix.
5. **Statistical methodology citations**: the Wilcoxon signed-rank test, BCa bootstrap, Holm–Bonferroni correction, Cohen's κ, and (if used) Krippendorff's α — standard methodological citations, included because `EXPERIMENT_PLAN.md` §6 commits to using these specific, named procedures.
6. **Software-engineering task-taxonomy / query-intent literature**, if a related-work subsection on this (§3, item 8) is included.
7. **A self-citation placeholder for the TIQS dataset**, once released as a standalone artifact (`CONTRIBUTIONS.md` §5), if the venue's norms call for citing one's own released dataset distinctly from the paper itself.

**Drafting note:** maintain a single, version-controlled bibliography file for the whole project rather than assembling references only at submission time, so that every other document in this suite (`PROJECT_SPEC.md`, `CONTRIBUTIONS.md`, `EXPERIMENT_PLAN.md`) can eventually point to the same resolved citations rather than each accumulating its own inconsistent shorthand for "AIRCoder" or "CodeRAG-Bench." Citation style is venue-dependent and **TBD** until a target venue is chosen.
