# PILOT_EXECUTION_PLAN.md

## RTS Pilot: Step-by-Step Execution Plan

**Status.** Execution runbook, not a design document. Methodology (`docs/methodology/RANKER_DESIGN.md`), dataset design (`docs/DATASET_DESIGN.md`), and the build specification (`docs/DATASET_BUILDER_SPEC.md`) are treated as frozen inputs here — this document does not re-argue them, only operationalizes them at a small, deliberately cheap scale before any commitment to the full Retrieval Training Set (RTS) build.

**Hard blocking dependency, stated once, up front.** Steps under §6 (Retrieval Execution Workflow) require every one of the seven `RoutingStrategy` candidates to be executable, i.e. Milestones 5–7 (`ROADMAP.md`) complete. If Dense or Graph Retrieval is not yet implemented, this plan can be executed through §5 (Feature Extraction Workflow) and no further — do not attempt a partial pilot with fewer than seven strategies per query; a pilot dataset missing candidates would not exercise the ranking-generation logic (§8) it exists to validate.

**One gap this plan resolves that the source specifications left implicit:** Utility Computation (§7 below, and `DATASET_BUILDER_SPEC.md` §8) requires a verified relevant-context ground-truth set per query — it cannot run against a query that has only a text and a task label. §4 below therefore covers **both** task labeling and relevant-context annotation, even though it is titled per the task's naming convention ("Oracle task labeling"); a plan that annotated task labels only would silently block §7 later.

---

## 1. Pilot Objectives

1. Execute the full 12-stage pipeline (`DATASET_BUILDER_SPEC.md` §2) end to end, at a scale cheap enough to debug in days rather than weeks.
2. Surface pipeline and schema defects — missing features, broken assumptions, execution failures — before committing the full-scale labeling and compute budget to them.
3. Produce a first empirical read on the two calibration parameters left open in `DATASET_BUILDER_SPEC.md`: the utility trade-off coefficient $\lambda$ (§8, default 0.1) and the ranking tie threshold $\varepsilon$ (§9, default 0.02) — informing, not finalizing, the values eventually frozen for the full build.
4. Produce a small, versioned, manually-inspectable dataset artifact (tag `v0.1-pilot`, consistent with the tag already reserved for exactly this purpose in `DATASET_PLAN.md` §14) that a human reviewer can sanity-check before trusting the pipeline at scale.
5. If the pilot succeeds without requiring a schema or methodology change, its labeled rows are retained as the first real slice of the training split, not discarded — pilot repositories (§2) are therefore drawn from repositories already slated for the training split, never validation or test.

**Explicit non-objective:** this pilot is not sized to produce statistically meaningful or publication-reportable results. Any number it produces (accuracy, agreement, sensitivity trends) is a debugging signal, not a claim, and must not be cited in `EXPERIMENT_PLAN.md`-governed results.

## 2. Repository Selection Criteria

- Draw exclusively from repositories already eligible under `DATASET_PLAN.md` §2's full criteria (license, maintenance, no duplication) — the pilot does not use a relaxed standard.
- **Proposed pilot set: 4 repositories**, satisfying: at least 2 distinct languages; at least 2 size buckets (small and medium — large is excluded from the pilot specifically to keep preprocessing time low; large-repository behavior is a full-scale, not a pilot, concern).
- Draw only from repositories intended for the **training** split (`DATASET_PLAN.md` §6) — never validation or test, so nothing about pilot execution can contaminate a sealed split before the pipeline is even validated.
- **Proposed candidates**, drawn from the illustrative list already named in `DATASET_PLAN.md` §1: `psf/requests` (Python, small–medium), `expressjs/express` (JavaScript, small–medium), `spf13/cobra` (Go, small), `nlohmann/json` (C++, small–medium). Final selection is the research assistant's call within the criteria above; these four are a starting proposal, not a mandate.
- Record each selected repository in a pilot-scoped manifest (§14) before proceeding — do not select repositories informally and pin them only after the fact.

## 3. Query Generation Workflow

1. Target **10 queries per pilot repository** (40 total at 4 repositories) — enough to exercise the pipeline's handling of query diversity without approaching TIQS-scale annotation effort.
2. For each query, rotate through the three framing styles already established in `DATASET_PLAN.md` §10: issue-tracker-style, code-review-comment-style, onboarding-question-style.
3. Author each query **without** consulting `tara.classification.heuristics`'s keyword vocabulary — the same circularity-avoidance constraint that applies to full-scale TIQS/RTS authoring applies here unchanged.
4. Record every query in a pilot query log (`annotation_log.csv`, §12) with, at minimum: `query_id`, `repository_id`, `query_text`, `framing_style`, `author_id`, `timestamp`.
5. Aim for **loose, not strict, task-type diversity**: across the 40 pilot queries, try to touch at least 6–8 of the 13 `TaskType` categories. Do not attempt the full ~37-per-category stratification target `DATASET_PLAN.md` §9 sets for the full corpus — that target is statistically motivated and meaningless at pilot scale.

## 4. Oracle Task Labeling Workflow

This step has two parts, both required before §7 can run: task-type labeling, and relevant-context ground-truth annotation.

**Part A — Task-type labeling** (`DATASET_BUILDER_SPEC.md` §5):

1. Run `HeuristicTaskClassifier` on every pilot query. This is free and fast; run it on all 40 before doing anything else.
2. Record `task_type` and `task_confidence` for each query.
3. For queries with `task_confidence ≥ 0.7` (the proposed default threshold), accept the heuristic label as-is; record `label_source = heuristic`.
4. For queries below threshold, the research assistant reviews the query directly and assigns the correct `task_type` by hand; record `label_source = manual`. **At pilot scale, do not build out the LLM-assisted labeling path** (`DATASET_BUILDER_SPEC.md` §5) even if some queries fall below threshold — the number of such queries at this scale should be small enough for direct manual review to be faster than standing up the LLM-assisted infrastructure. If the below-threshold count exceeds roughly a third of the pilot set, stop and treat that ratio itself as a pilot finding (§10) rather than manually pushing through it.
5. Compute and record the **heuristic acceptance rate** (fraction of the 40 queries with confidence ≥ 0.7) — this number is itself one of the pilot's deliverables (§12), informing whether 0.7 is a reasonable threshold at full scale.

**Part B — Relevant-context ground truth** (`DATASET_PLAN.md` §11, reused unchanged):

1. For every pilot query, inspect the actual pinned repository (never from memory) and record the minimal file/symbol set a competent developer would need to address it.
2. Use the same node-id scheme as `tara.context.models.build_symbol_node_id` / `build_file_node_id` for symbol-level entries, so this ground truth is directly usable by the Recall@k computation in §7 without a translation step.
3. Mechanically verify every recorded file path / symbol id resolves against the pinned repository at the pinned commit before accepting the annotation — reject and re-annotate anything that doesn't resolve.
4. A query without a verified relevant-context set by the end of this step **must not proceed to §7** — flag it and either complete its annotation or exclude it from the pilot's utility-computation stage, but do not silently skip Quality computation for it.

## 5. Feature Extraction Workflow

1. For each of the 4 pilot repositories, run Repository Preprocessing (`DATASET_BUILDER_SPEC.md` Stage 1): `TreeSitterRepositoryParser` → `GraphBuilder` → `SymbolIndexBuilder`, producing one `RepositoryContext` per repository.
2. **Compute embeddings for every pilot repository** (`SentenceTransformerEmbedder`, default `BAAI/bge-small-en-v1.5`) — this is required, not optional, at pilot scale: without embeddings, `DenseRetriever`-involving strategies degrade to a trivial capability downgrade for every pilot repository (`DESIGN_DECISIONS.md` §2), which would make those strategies' oracle utility uninformative and defeat the purpose of testing all seven candidates distinctly.
3. With the embedding model already loaded from step 2, also compute the optional per-query dense embedding feature (`query_embedding`, `DATASET_BUILDER_SPEC.md` §6) for every pilot query — the marginal cost is low once the model is warm, and including it now means the pilot dataset can support the query-embedding-feature ablation later without a second extraction pass.
4. Extract the shared feature groups (Query, Task, Repository, Graph, Structural — `DATASET_BUILDER_SPEC.md` §6's table) once per query, identical across that query's seven strategy rows.
5. Extract the Resource Features group (candidate-conditioned) per strategy row, via direct lookup against `STRATEGY_RETRIEVERS` and `RETRIEVER_EXECUTION_PRIORITY` (`tara.routing.strategy`) — no computation beyond table lookup and boolean combination.
6. Manually spot-check 5 fully-extracted rows against their source `RepositoryContext` and `TaskClassification` objects directly (not against the pipeline's own output) — confirm every feature value traces to a real, correct source field. Record findings in the manual verification checklist (§15).

## 6. Retrieval Execution Workflow

**Do not begin this section until the blocking dependency stated at the top of this document is confirmed resolved.**

1. For each pilot query and each of the seven `RoutingStrategy` candidates, construct a fixed single-policy `AdaptiveRouter` pinning that candidate — the identical mechanism already used to build baselines B1/B2 (`EXPERIMENT_PLAN.md` §4) — and pass its output through the unmodified `RetrievalPlanner`.
2. Execute retrieval for that (query, strategy) pair. Record the resulting `RetrievedContext`.
3. Measure wall-clock latency for the retrieval call **three times per (query, strategy) pair**; retain the median as `latency_ms`. Run all three repetitions on the same machine, in the same session, without other heavy processes competing for resources, so the three measurements are comparable to each other.
4. Confirm every query produced exactly seven `RetrievedContext` records (one per strategy) before proceeding — a query with fewer than seven is incomplete and must be re-run, not padded or excluded silently.
5. Manually inspect the retrieved chunks for **3 queries, across all 7 strategies each** (21 inspections total) — do the chunks returned by, say, `GRAPH_ONLY` look structurally different from `LEXICAL_ONLY`'s, and does each look like a plausible response to the query's actual content? This is a qualitative sanity check, not a metric; record findings in §15.

## 7. Utility Computation

1. Confirm every pilot query has a verified relevant-context ground truth (§4, Part B) before computing anything in this section — this is a hard precondition, not a formality.
2. Compute `quality_score` per row as Recall@k against that ground truth (`EXPERIMENT_PLAN.md` §3's definition, reused unchanged).
3. Compute `latency_normalized` per row via `tara.retrieval.utils.normalize_scores`, applied to each query's own 7-element `latency_ms` vector (never normalized across queries).
4. Compute the **primary** `utility_score` using $\lambda = 0.1$ (`DATASET_BUILDER_SPEC.md` §8's proposed default) — this becomes the pilot dataset's canonical utility column.
5. **Run the full sensitivity sweep**: recompute `utility_score` for every row under each of $\lambda \in \{0.0, 0.05, 0.1, 0.2, 0.5\}$, retaining all five variants (not only the primary one) in a separate sweep-results table, not merged into the canonical dataset file.
6. For each $\lambda$ value, record how many queries' `best_strategy` (rank-1 candidate) differs from the $\lambda = 0.1$ result — this comparison is the pilot's direct empirical input to §10's sensitivity-stability success criterion.

## 8. Ranking Generation

1. For the primary $\lambda = 0.1$ utility values, sort each query's 7 rows by descending `utility_score` to assign `rank ∈ {1,...,7}`.
2. Apply tie-breaking where two candidates' utilities differ by less than $\varepsilon = 0.02$ (proposed default): break the tie toward the lower `strategy_cost_rank` (cheaper strategy ranks higher).
3. Compute `label_confidence` per query using the relative-margin formula in `DATASET_BUILDER_SPEC.md` §9, based on the top-1/top-2 utility gap.
4. Repeat steps 1–3 for each of the four additional $\lambda$ values from §7's sweep, producing five parallel ranking sets for later sensitivity comparison — only the $\lambda=0.1$ set is the pilot dataset's canonical ranking.
5. **Face-validity review**, the single highest-value cheap check this pilot performs: for 10 queries chosen to span different apparent intents (e.g., an exact-symbol-lookup-looking query, a conceptual-explanation-looking query, a structural-tracing-looking query), read the query text and the rank-1 strategy side by side, and judge — independent of any metric — whether the top choice looks intuitively reasonable. Record each judgment (plausible / not plausible / unclear) and a one-line reason. This check can catch a sign error in the utility formula or a strategy-mapping bug that would otherwise pass every mechanical validation check in §9 while being substantively wrong.

## 9. Dataset Validation

Run every check specified in `DATASET_BUILDER_SPEC.md` §11 against the pilot dataset, exactly as they will run at full scale — the goal here is as much to confirm **the checks themselves work correctly** as to confirm the pilot data passes them:

1. Duplicate check: no duplicate `query_id`; no duplicate `query_text` within the same `repository_id`.
2. Missing-value check: every column populated except the explicitly-nullable ones (`embedding_dimension`, `annotator_id` for non-manual rows); any other null blocks the pilot from proceeding to §10.
3. Outlier check: flag any `latency_ms` more than 5× its query group's median; flag any `utility_score` outside $[-\lambda, 1]$.
4. Repository-leakage check: confirm every pilot repository's declared split is `train` and appears nowhere else — expected to trivially pass at pilot scale, but run the check mechanically anyway, since it is the same script that must work correctly at full scale.
5. Group-completeness check: every `group_id` has exactly 7 rows.

Record the full validation output as `validation_report_pilot.md` (§12) regardless of outcome — a report showing every check passed is still a required deliverable, not an optional one skipped because nothing was found.

## 10. Pilot Success Criteria

| # | Criterion | Threshold |
|---|---|---|
| 1 | Query/group completeness | 100% of pilot queries produce a complete, schema-conformant 7-row group |
| 2 | Validation checks | All §9 checks pass, or every failure is explained and resolved (not silently ignored) |
| 3 | Heuristic acceptance rate | Above roughly 50% (§4); a lower rate is a pilot finding requiring review, not an automatic failure, but must be reported explicitly |
| 4 | Face-validity review | At least 8 of 10 reviewed queries (§8) judged "plausible" |
| 5 | $\lambda$-sensitivity stability | The rank-1 strategy is unchanged across $\lambda \in \{0.05, 0.1, 0.2\}$ for the majority of pilot queries |
| 6 | Pipeline robustness | No pipeline stage requires more than minor, documented manual intervention to complete |
| 7 | Wall-clock time | Full pipeline (excluding human annotation time) completes within the timeframe extrapolated in §13, run once, without needing to be restarted from scratch |

**Failing one or more criteria is not a project failure.** It is exactly the outcome a pilot exists to surface cheaply. A failed criterion triggers a design review of the relevant source document (`DATASET_DESIGN.md`, `RANKER_DESIGN.md`, or `DATASET_BUILDER_SPEC.md`) before any full-scale execution begins — it does not trigger a second, larger pilot attempt without first understanding why the first one failed.

## 11. Risks

- **Pilot scale may not surface scale-dependent issues.** A defect that only manifests with a large corpus (memory pressure, index-build time, latency-measurement noise under load) will not necessarily appear in a 4-repository pilot. A passing pilot reduces, but does not eliminate, full-scale execution risk.
- **Pilot repository choice bias.** If the four selected repositories happen to share unusual characteristics, pilot findings (heuristic acceptance rate, $\lambda$-sensitivity pattern) may not generalize to the full corpus's intended diversity (`DATASET_PLAN.md` §17).
- **Blocking dependency risk.** Retrieval Execution (§6) cannot run without Milestones 5–7 complete; if any of those milestones is delayed, this plan's schedule (§13) slips with it, and there is no partial workaround that preserves the pilot's purpose.
- **Human-effort underestimation.** Relevant-context annotation, manual task-label review, and the face-validity review may take longer per query than the schedule in §13 assumes, even at this small scale — track actual time spent per step and adjust the full-scale timeline estimate accordingly rather than silently absorbing the overrun.
- **Embedding-model operational risk.** Downloading and running `SentenceTransformerEmbedder` introduces a real, if modest, dependency on model availability and local compute — have a fallback plan (e.g., retry, or proceed without the optional query-embedding feature) rather than letting this block the entire pilot.
- **False confidence risk.** A pilot that meets every criterion in §10 demonstrates the pipeline works at pilot scale, under pilot conditions, on these four repositories — it does not guarantee identical success at full scale, and should not be reported or treated as such.

## 12. Deliverables

| File | Contents |
|---|---|
| `evaluation/datasets/rts/pilot/repository_manifest_pilot.json` | The 4 selected pilot repositories, per §2 |
| `evaluation/datasets/rts/pilot/rts_pilot_v0.1.jsonl` | The canonical ($\lambda=0.1$) pilot dataset, in the schema defined by `DATASET_BUILDER_SPEC.md` §10 |
| `evaluation/datasets/rts/pilot/config_pilot.yaml` | The exact configuration used (thresholds, $\lambda$, $\varepsilon$) |
| `evaluation/datasets/rts/pilot/lambda_sensitivity_analysis.md` | The five-value $\lambda$ sweep (§7 step 5–6) and its stability findings |
| `evaluation/datasets/rts/pilot/face_validity_review.md` | The 10-query manual review (§8 step 5) |
| `evaluation/datasets/rts/pilot/validation_report_pilot.md` | Full output of every §9 check |
| `evaluation/datasets/rts/pilot/annotation_log.csv` | Query authoring, task labeling, and relevant-context annotation records (§3–§4) |
| `evaluation/datasets/rts/pilot/PILOT_REPORT.md` | The summary report: which §10 criteria were met, what was learned, whether `DATASET_DESIGN.md`/`RANKER_DESIGN.md`/`DATASET_BUILDER_SPEC.md` need revision before full-scale execution, and recommended final $\lambda$/$\varepsilon$/threshold values |
| `evaluation/datasets/rts/pilot/logs/{run_timestamp}/` | Structured per-stage execution logs (`DATASET_BUILDER_SPEC.md` §13) |

`PILOT_REPORT.md` is the deliverable that actually matters to the project — every other file is evidence supporting it.

## 13. Timeline

Assumes Milestones 5–7 are already complete when this plan begins; the schedule below covers pilot execution only, not any wait time for blocked dependencies.

| Day | Activity |
|---|---|
| 1 | Repository selection and preprocessing (§2, §5 steps 1–3) |
| 1–2 | Query generation and oracle labeling — task type and relevant context (§3, §4) |
| 2 | Feature extraction completion and spot-check (§5 steps 4–6) |
| 2–3 | Retrieval execution across all 7 strategies (§6) |
| 3 | Utility computation and $\lambda$ sweep (§7) |
| 3–4 | Ranking generation and face-validity review (§8) |
| 4 | Dataset validation (§9) |
| 4–5 | Success-criteria assessment, deliverable assembly, `PILOT_REPORT.md` writeup (§10, §12) |

**Total: approximately 5 working days.** This is a planning estimate, not a commitment — actual time should be tracked per step and used to correct the full-scale timeline in `EXPERIMENT_PLAN.md` §15, not silently reconciled after the fact.

## 14. Repository Structure

```
evaluation/
└── datasets/
    ├── repository_manifest.json          # full-scale manifest (future, not this pilot)
    └── rts/
        ├── pilot/
        │   ├── repository_manifest_pilot.json
        │   ├── rts_pilot_v0.1.jsonl
        │   ├── config_pilot.yaml
        │   ├── validation_report_pilot.md
        │   ├── lambda_sensitivity_analysis.md
        │   ├── face_validity_review.md
        │   ├── annotation_log.csv
        │   ├── PILOT_REPORT.md
        │   └── logs/
        │       └── {run_timestamp}/
        ├── config.yaml                    # full-scale config (future, not this pilot)
        ├── CHANGELOG.md
        └── README.md
```

Pilot artifacts live entirely under `rts/pilot/`, kept structurally separate from the eventual full-scale `rts/` release files, so pilot data can never be accidentally merged into or mistaken for the real dataset.

## 15. Manual Verification Checklist

To be completed alongside execution, not reconstructed afterward from memory.

**Repository and preprocessing**
- [ ] All 4 pilot repositories satisfy `DATASET_PLAN.md` §2's eligibility criteria
- [ ] All 4 are assigned to the `train` split only
- [ ] Commit SHAs are pinned and recorded in `repository_manifest_pilot.json` before any annotation begins
- [ ] `RepositoryContext` built successfully for all 4 (parser, graph, symbol index)
- [ ] Embeddings computed successfully for all 4

**Query generation and annotation**
- [ ] 40 queries authored, framing styles rotated across the three established styles
- [ ] No query authored with reference to `tara.classification.heuristics`'s vocabulary
- [ ] Every query has a `task_type` label with recorded `label_source`
- [ ] Heuristic acceptance rate computed and recorded
- [ ] Every query has a verified relevant-context ground-truth set, mechanically checked to resolve against the pinned repository

**Feature extraction**
- [ ] All 6 feature groups populated for every row
- [ ] 5 rows manually spot-checked against source `RepositoryContext`/`TaskClassification` objects directly
- [ ] No unexpected null values outside the two explicitly-nullable columns

**Retrieval execution**
- [ ] Every query has exactly 7 `RetrievedContext` records
- [ ] Latency measured 3× per (query, strategy) pair; median recorded
- [ ] 21 chunk inspections (3 queries × 7 strategies) completed and recorded

**Utility and ranking**
- [ ] `quality_score` computed for every row against verified ground truth
- [ ] `latency_normalized` computed per query group, not globally
- [ ] Primary ($\lambda=0.1$) `utility_score` computed for every row
- [ ] Full 5-value $\lambda$ sweep computed and retained separately from the canonical dataset
- [ ] Rank, tie-breaking, and confidence computed for the primary $\lambda$ setting
- [ ] 10-query face-validity review completed with recorded judgments

**Validation and reporting**
- [ ] All 5 validation checks (§9) run and their output recorded, regardless of outcome
- [ ] Every §10 success criterion assessed explicitly (met / not met, with evidence)
- [ ] `PILOT_REPORT.md` drafted, including an explicit recommendation on whether to proceed to full-scale execution as-is, with modifications, or not yet
