# Anticipated Review: Oracle Utility Subsystem (RTS Builder, Milestone 6)

Following the discipline established for every prior RTS Builder
milestone, this document self-applies review scrutiny before an
external one happens.

---

## Item 1: `RelevanceJudgment` wasn't in the stated inputs — is this scope creep?

**Anticipated comment.** *"The task objective says 'Given the outputs
of every retrieval strategy, compute the supervision labels.' It
doesn't mention a `RelevanceJudgment` input. Where did this come from,
and is inventing a new required input a redesign the task didn't ask
for?"*

**Response.** Not invented — required by the mathematics the task
itself specifies. Recall@k, MRR, NDCG, and Context Precision are, by
definition, comparisons between a ranked retrieval result and a
ground-truth relevance set; none of the four is computable from
retrieval output alone. This exact gap — Oracle Utility Computation
needing relevant-context ground truth that no earlier automated stage
produces — was already identified during this project's research
-planning phase and resolved by treating ground-truth annotation as an
externally-supplied artifact, folded into query authoring rather than
computed by any pipeline stage (`docs/PILOT_EXECUTION_PLAN.md` §4).
`RelevanceJudgment` implements that already-established resolution; it
does not introduce a new one. The alternative — silently returning
`0.0` for every quality metric on every query, forever, with no way to
ever supply real judgments — would make "compute the supervision
labels" impossible to satisfy honestly.

---

## Item 2: Quality is a weighted composite of four metrics — why not report Recall@k alone, as `DATASET_BUILDER_SPEC.md`'s v1 default does?

**Anticipated comment.** *"`docs/DATASET_BUILDER_SPEC.md` §8's v1
default `Quality` is Recall@k alone, not a four-metric blend. Does
this implementation depart from that without saying so?"*

**Response.** Stated explicitly, not silently: `Architecture.md`'s
Design Decisions calls this out directly. The task's own Objective
section lists all four metrics as first-class deliverables ("1.
Retrieval Quality metrics: Recall@k, MRR, NDCG, Context precision"),
which only makes sense as a *composite* Quality signal, matching the
"name several signals, blend by configurable weights" pattern already
established at every combination point in this codebase (Lexical
Retrieval's three signals, Hybrid Retrieval's three strategy scores).
A caller that wants `DATASET_BUILDER_SPEC.md` §8's exact v1 behavior
can reproduce it by setting `quality_recall_weight=1.0` and the other
three quality weights to `0.0` — the composite design is a strict
superset of the single-metric default, not incompatible with it.

---

## Item 3: The utility tie-break deviates from `DATASET_BUILDER_SPEC.md`'s specified mechanism

**Anticipated comment.** *"§9 says ties are broken by
`RETRIEVER_EXECUTION_PRIORITY`, a specific, already-existing table.
This implementation uses raw measured latency instead. Isn't that
supposed to be frozen, established behavior this milestone should
reuse, not replace?"*

**Response.** `RETRIEVER_EXECUTION_PRIORITY` (from
`tara.routing.strategy`) is a static priority ordering over
`RoutingStrategy`'s 7 candidates — a taxonomy Retrieval Executor
(accepted, frozen, three milestones ago) never implements. It has no
defined entries for `lexical`/`dense`/`graph`/`hybrid`. Reusing it
would require either (a) inventing a new, unvalidated mapping from 4
strategies onto a 7-strategy priority table, or (b) modifying
`tara.routing.strategy` itself — both worse than the alternative
chosen: use each strategy's own already-measured, already-frozen
-protocol `retrieval_latency_ms` for the exact query being ranked. This
is not a different rule from §9's — "the cheaper strategy ranks
higher" — it is the same rule, evaluated with real per-query cost data
instead of a context-independent a-priori table that doesn't cover
this milestone's actual strategy set. Both `Architecture.md` and
`Oracle_Math.md` state this adaptation and its reasoning explicitly.

---

## Item 4: `label_confidence` being query-level (not per-strategy) — is that a weaker signal than it could be?

**Anticipated comment.** *"Every row for a query carries the identical
`label_confidence` value. A Learning-to-Rank model sees no
per-strategy distinction in confidence at all — isn't a rank-2
strategy's confidence in being 'clearly not rank 1' different from a
rank-3-vs-rank-4 distinction buried in noise?"*

**Response.** This is `docs/DATASET_BUILDER_SPEC.md` §9's specified
design, reproduced exactly, not a simplification introduced here: "A
single scalar per query (repeated across that query's seven rows)."
The formula measures confidence in *the labeling itself* — specifically,
confidence that the identified best strategy really is best — not
confidence in each row's individual rank. A per-strategy confidence
variant (e.g., each row's margin to its nearest neighbor) was
considered during design and rejected in favor of matching the
established, already-specified formula precisely rather than
introducing an unreconciled second definition of "confidence" into a
project that already has one on record. If a future milestone
determines the per-rank variant is worth having *in addition*, it is
a straightforward additive change (a new field, not a replacement).

---

## Item 5: All-tied latency maps every strategy to `latency_normalized = 1.0` (the worst value) — is that a bug?

**Anticipated comment.** *"When all four strategies happen to have
identical latency, `normalize_scores`'s all-equal convention maps every
one of them to `1.0` — the *maximum* penalty, not zero. That seems
backwards: identical latency should arguably be 'neutral,' not
'maximally bad.'"*

**Response.** Correct that `1.0` (not `0.5` or `0.0`) is what
`normalize_scores` returns for an all-tied input — that convention
belongs to `tara.retrieval.utils.normalize_scores`, reused unmodified
per the task's explicit instruction not to redesign frozen behavior,
and is unrelated to Oracle Utility's own logic. What matters for this
milestone's correctness is the *consequence*: since every strategy
receives the identical `1.0` penalty in this scenario, `utility_score`
for every strategy shifts down by the same constant `beta`, and the
*relative* ranking among strategies (determined by `Quality` alone in
this case) is completely unaffected. Only the absolute `utility_score`
values are shifted, which is inherent to any min-max-normalized
penalty term and not specific to the all-tied case. Documented in
`Oracle_Math.md` and `Architecture.md`'s Failure Modes rather than
left for a reader to discover by inspecting `normalize_scores`'s source.

---

## Item 6: No test verifies NDCG's IDCG-recomputation-per-strategy is actually wasteful, or that it matters

**Anticipated comment.** *"`Oracle_Math.md` notes IDCG@k is identical
across all 4 strategies for a given query but is recomputed once per
strategy anyway. Is that a real performance concern, and is it
tested?"*

**Response.** Not a correctness concern — recomputing an
identical value 4 times produces the identical result each time, so no
test was written to prove correctness that redundant computation
cannot violate. As a performance matter: `IDCG@k` costs
`O(|relevance_grades| log |relevance_grades|)` (a sort) plus `O(k)`,
trivial at realistic RTS query-annotation scale (a handful to a few
dozen judged files per query), so the 4x redundancy was accepted for
simplicity (one self-contained `ndcg_at_k` call per strategy, no shared
-state threading between strategies) rather than optimized preemptively.
Listed as a Future Extension Point, not fixed, since profiling has not
shown it to matter at this milestone's actual scale.

---

## Summary

| # | Concern | Status |
|---|---|---|
| 1 | `RelevanceJudgment` as a required input beyond the stated objective | Required by the metrics' own mathematics; implements an already-established project resolution, not new scope |
| 2 | Quality as a 4-metric composite vs. `DATASET_BUILDER_SPEC.md`'s Recall@k-only v1 default | Explicit, documented generalization; v1 behavior reproducible via weight configuration |
| 3 | Tie-break uses measured latency, not `RETRIEVER_EXECUTION_PRIORITY` | Deliberate, documented adaptation — same principle, real per-query data, no strategy-taxonomy mismatch |
| 4 | `label_confidence` is query-level, not per-strategy | Matches `DATASET_BUILDER_SPEC.md` §9's specified formula exactly, not a simplification |
| 5 | All-tied latency normalizes to `1.0` (max penalty) for every strategy | Inherited from reused `normalize_scores`; relative ranking is provably unaffected |
| 6 | Redundant per-strategy IDCG computation | Accepted for simplicity; not shown to matter at RTS scale; tracked as a Future Extension Point |

No code outside `evaluation/rts_builder/oracle_utility/` was modified.
Repository Loader, Parser, Feature Extraction, and Retrieval Executor
were not touched. `tests/rts_builder/oracle_utility/` has 46 tests, all
passing alongside the full existing project suite.
