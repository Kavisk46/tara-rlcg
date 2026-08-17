# Evaluation Baselines (M10)

**No experiments have been run in M10.** This package implements
baseline *infrastructure* only: fixed, non-adaptive retrieval
configurations that can be fairly compared against TARA's adaptive
router, once a real experiment run is deliberately started (see
[§13](#13-future-experiment-procedure)). No query set was executed, no
generation model was called against real data, and no result numbers
exist anywhere in this package.

## 1. Purpose of baselines

TARA's central research claim is that task-aware adaptive routing
produces better retrieval/generation outcomes than retrieval held to a
single, fixed strategy. That claim is only testable if the *only*
variable between TARA and each comparison point is the retrieval/routing
mechanism itself -- everything else (corpus, queries, generation model,
prompt, token budget, evaluation protocol) must be held identical. This
package exists to make that isolation structural, not just a documented
intention: `evaluation.baselines.runner.BaselineRunner` is constructed
once, with one set of shared collaborators, and every baseline flows
through the identical `run()` method body.

## 2. B0 -- No retrieval

The LLM generates directly from the query, with no repository context at
all. `BaselineDefinition.strategy is None`; `BaselineRunner.run()`
detects this and skips routing, retrieval, and fusion entirely,
constructing an explicitly empty `FusedContext` instead. Establishes the
floor every other baseline (and TARA itself) must beat to justify
retrieval's cost at all.

## 3. B1 -- Fixed semantic-only

Every query is fixed to `RoutingStrategy.SEMANTIC_ONLY` (dense/embedding
retrieval via `tara.retrieval.dense_retriever.DenseRetriever`),
regardless of query content. Represents the retrieval strategy this
project's own motivation (`PROJECT_SPEC.md` §2) argues most existing
retrieval-augmented systems default to.

## 4. B2 -- Fixed lexical-only

Every query is fixed to `RoutingStrategy.LEXICAL_ONLY` (BM25 keyword
search via `tara.retrieval.lexical_retriever.LexicalRetriever`). Isolates
how much of TARA's advantage, if any, a single non-adaptive lexical
strategy alone already captures.

## 5. B3 -- Fixed graph-only

Every query is fixed to `RoutingStrategy.GRAPH_ONLY` (repository-graph
traversal via `tara.retrieval.graph_retriever.GraphRetriever`). Isolates
how much of TARA's advantage, if any, a single non-adaptive graph
strategy alone already captures. TARA's graph retrieval is itself
structurally limited today (containment/definition/import edges only, no
call graph -- see `tara.context.graph_builder`'s own documented
limitation), so this baseline's ceiling is bounded by that same
limitation, not by anything specific to this package.

## 6. B4 -- Always full-pipeline (unified retrieval)

Every query is fixed to `RoutingStrategy.FULL_PIPELINE` -- lexical +
semantic + graph, all three retrievers, every time. This is a deliberate
disambiguation of this milestone's "hybrid / unified retrieval" wording:
TARA's own `RoutingStrategy.HYBRID` enum member is narrower (lexical +
semantic only, no graph). See `BASELINE_DISCREPANCIES.md`, "B4's specific
ambiguity," for the full reasoning and the one-line change needed if
`HYBRID` was the intended reading instead. Combination of the three
retrievers' output uses TARA's own existing, already-specified fixed
mechanism (`tara.fusion.fusion.ContextFusion` -- deduplicate, then
score-merge, then optionally rerank, then token-budget) -- no new
weighting scheme was invented for this baseline.

## 7. Why B5/B6 are not implemented

Both `PROJECT_SPEC.md` §24 and `EXPERIMENT_PLAN.md` §4 mark every
external-system baseline (AIRCoder, RepoFormer, AllianceCoder) `Status:
TBD, contingent on public code/artifact availability` -- no
literature-verification pass confirming a reproducible public artifact
exists has been performed. Building a "best-effort re-implementation"
without that verification would mean attributing an invented retrieval
strategy to a published system without having confirmed its actual
methodology -- indistinguishable from fabrication, which this
milestone's instructions explicitly prohibit.
`evaluation.baselines.definitions.UNAVAILABLE_BASELINES` records this
status machine-readably; `evaluation.baselines.registry` turns it into
the same reproducibility report every implemented baseline appears in
(see [§12](#12-reproducibility-status)), so B5/B6's absence is disclosed
in the same place their presence would otherwise be, not silently
omitted.

## 8. Fairness constraints

Every baseline must share, unconditionally: the repository corpus (the
same `RepositoryContext` instance), the query set (the same query
text/IDs), the generation model (the same injected `CodeGenerator`
instance), the generation prompt (`PromptTemplate.BASELINE`, never
`WITH_TASK_CLASSIFICATION`), the token budget (`TaraSettings.fusion_token_budget`),
and the evaluation protocol. Only the retrieval/routing mechanism may
differ.

Two independent layers enforce this:

- **Structural (by construction).** `BaselineDefinition` is
  `(baseline_id, name, description, strategy)` only -- there is no field
  on it that could override any shared setting, even accidentally.
  `BaselineRunner` is constructed once, with one set of collaborators,
  reused for every `.run()` call.
- **Explicit runtime validation.** `evaluation.baselines.fairness`
  provides `reject_generation_overrides` / `reject_evaluation_overrides`
  / `reject_corpus_override` / `reject_query_set_override` (and
  `validate_no_overrides`, which runs all four), each raising
  `FairnessInvariantError` (a `TaraError` subclass) if a per-baseline
  configuration source ever attempts to set a field that must stay
  common. See `evaluation/baselines/tests/test_fairness.py`.

## 9. Common generation configuration

`evaluation.baselines.models.GenerationConfig` -- `model`, `temperature`,
`max_tokens`, `prompt_template` (always `PromptTemplate.BASELINE`,
enforced by `__post_init__`) -- is immutable (`@dataclass(frozen=True)`),
so it cannot diverge across baselines once constructed. It is a
disclosure/reporting type: `BaselineRunner` still receives its actual
`CodeGenerator`/`PromptBuilder` collaborators via constructor injection
(TARA's own established DI pattern), never via this config object.

## 10. Common evaluation protocol

`evaluation.baselines.models.EvaluationConfig` -- `evaluator`, `metrics`,
`scoring_protocol`, `output_schema`, `query_set_id`, `corpus_id` -- is
likewise immutable and constructed once. `evaluation.baselines.models.RetrievalResultRecord`
is the shared output schema every baseline's retrieval produces
(`baseline_id`, `query_id`, `retrieved_document_ids`, `retrieval_mode`,
`scores`, `ranks`, `metadata`) -- deliberately excluding any generated
answer, per this milestone's explicit instruction not to mix retrieval
results with generation output.

## 11. TARA adaptive-router isolation

No file in this package imports `tara.routing.router.AdaptiveRouter`,
`tara.routing.policies.RoutingPolicy` (or any concrete policy), or
`tara.classification.classifier.HeuristicTaskClassifier`/
`tara.interfaces.task_classifier.TaskClassifier`.
`evaluation.baselines.plan_builder.build_fixed_plan` constructs a
`RetrievalPlan` from a hand-built `RoutingDecision` (inert data) fed
through `tara.routing.planner.RetrievalPlanner` (which makes no strategy
decision of its own). `evaluation/baselines/tests/test_router_isolation.py`
proves this with a literal call-count spy on `AdaptiveRouter.route` and
`HeuristicTaskClassifier.classify`, for every baseline B0-B4, both
individually and swept together -- asserting `call_count == 0` in every
case. See `BASELINE_DISCREPANCIES.md`, "Router isolation," for why an
earlier version of this package (built on `AdaptiveRouter` with a
one-policy tuple) was replaced.

## 12. Reproducibility status

| ID | Name | Strategy | Status | Mechanisms | Reproducibility |
|---|---|---|---|---|---|
| B0 | No retrieval | none | implemented | - | reproducible (deterministic; no external dependency) |
| B1 | Fixed semantic-only | semantic_only | implemented | dense | reproducible (deterministic; no external dependency) |
| B2 | Fixed lexical-only | lexical_only | implemented | lexical | reproducible (deterministic; no external dependency) |
| B3 | Fixed graph-only | graph_only | implemented | graph | reproducible (deterministic; no external dependency) |
| B4 | Always full-pipeline | full_pipeline | implemented | lexical, dense, graph | reproducible (deterministic; no external dependency) |
| B5 | AIRCoder (reproduction/re-implementation) | n/a | not implemented | - | unavailable_reference -- see `UNAVAILABLE_BASELINES` |
| B6 | RepoFormer/AllianceCoder-style | n/a | not implemented | - | unavailable_reference -- see `UNAVAILABLE_BASELINES` |

Generated programmatically by `evaluation.baselines.registry.render_reproducibility_report_markdown()`
from `evaluation.baselines.definitions` -- this table is a snapshot for
convenience, not a second source of truth; run the function directly for
the current, authoritative report.

"Reproducible" means exactly what it says here: deterministic, no
external system, no unverified reference. It is **not** a claim that any
baseline has been run, benchmarked, or validated against real outcomes
-- see `evaluation/baselines/tests/test_registry.py`,
`test_no_baseline_reports_a_fabricated_reproducibility_claim`.

## 13. Future experiment procedure

Not started in M10. Once TIQS (`PROJECT_SPEC.md` §22) and a real
repository corpus (`EXPERIMENT_PLAN.md` §1) are frozen, and a real
`CodeGenerator` provider exists (`ROADMAP.md` M9, currently only
`tara.generation.fake_provider.FakeCodeGenerator`), an experiment runner
would: construct one `BaselineRunner` per experimental condition (one for
TARA-proper via the real `AdaptiveRouter`, one reused across every
baseline in `BASELINE_DEFINITIONS`), iterate every TIQS query against the
frozen corpus's `RepositoryContext`, call `.run()` for TARA and for every
baseline, and record each `BaselineRunResult`/`RetrievalResultRecord`
for the (not-yet-implemented) metrics stage (`ROADMAP.md` M11) to score.
No such runner exists yet, and none should be built or executed as part
of this milestone.
