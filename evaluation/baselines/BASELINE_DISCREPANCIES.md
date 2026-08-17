# Baseline naming: three-way discrepancy, and how this package resolves it

This project has, at this point, three different baseline numbering
schemes across three sources. This document exists so the divergence is
disclosed explicitly rather than silently absorbed into the code.

## The three schemes

| ID | `PROJECT_SPEC.md` §24 | `EXPERIMENT_PLAN.md` §4 (restates §24 "with execution-level precision") | This milestone's task instructions (implemented here) |
|---|---|---|---|
| B0 | No retrieval | No retrieval | No retrieval |
| B1 | Fixed semantic-only | Fixed semantic-only | Fixed semantic-only |
| B2 | Fixed full-pipeline | Fixed full-pipeline | **Fixed lexical-only** |
| B3 | Random routing | Random routing | **Fixed graph-only** |
| B4 | AIRCoder (reproduction, TBD) | Oracle retrieval (upper-bound reference; *new in `EXPERIMENT_PLAN.md`, not in §24*) | **Always full-pipeline ("hybrid / unified retrieval")** |
| B5 | RepoFormer-style dense retrieval (TBD) | AIRCoder (reproduction, TBD) | Not implemented (external reproduction, unavailable) |
| B6 | AllianceCoder-style ensemble retrieval (TBD) | RepoFormer-style dense retrieval (TBD) | Not implemented (external reproduction, unavailable) |
| B7 | -- | AllianceCoder-style ensemble retrieval (TBD) | -- (this milestone's instructions only go to B4, plus a B5/B6 "only if justified" slot) |

B0/B1 agree across all three sources. Everything from B2 onward diverges.

## Resolution

**This module (`evaluation/baselines/`) implements exactly what this
milestone's task instructions specify**, since that is the authoritative
definition of the work requested in this turn. It does not silently
adopt `PROJECT_SPEC.md` §24's or `EXPERIMENT_PLAN.md` §4's numbering,
and it does not silently edit those documents to match -- both are left
untouched. Whoever runs an actual experiment against this code should
be aware that "B2" here means "fixed lexical-only," not "fixed
full-pipeline" as `PROJECT_SPEC.md` §24 defines it.

Note that the baseline set implemented here (semantic-only, lexical-only,
graph-only, always-full-pipeline) is arguably a *more* orthogonal
ablation design than `PROJECT_SPEC.md` §24's original B0-B3 (which has
only one single-retriever baseline -- semantic -- plus one
always-everything baseline and one random-routing control): testing
each of TARA's three retrievers individually in isolation, plus one
always-everything upper-effort baseline, more directly answers "which
single retriever, if any, already captures most of TARA's value" --
which is presumably why this milestone's instructions specify it this
way. This is offered as a plausible rationale for the divergence, not a
confirmed one; it has not been discussed with, or confirmed by, anyone
who could speak to the original intent behind `PROJECT_SPEC.md` §24's
numbering.

## B4's specific ambiguity: "hybrid" vs. "unified retrieval"

The task instruction reads: *"B4 — Always hybrid / unified retrieval if
supported by the finalized design."* TARA's own `RoutingStrategy` enum
(`tara.routing.strategy`) has two members this could plausibly mean:

- `HYBRID` — lexical + semantic (dense) only, **no graph**.
- `FULL_PIPELINE` — lexical + semantic + graph, all three retrievers.

**This implementation uses `FULL_PIPELINE`**, reasoning that "unified
retrieval" most literally means "combine every available retrieval
modality," and that `PROJECT_SPEC.md` §24's original B2 ("fixed
full-pipeline... retrieve everything, always") describes exactly this
concept under a different number -- i.e., this milestone's B4 is very
plausibly meant to preserve that specific, already-specified baseline
concept, just renumbered to make room for the two new single-retriever
baselines at B2/B3. "Hybrid" is read here as colloquial/loose phrasing
for "combine multiple retrievers," not as a precise reference to the
narrower `RoutingStrategy.HYBRID` enum member.

**If `HYBRID` (lexical + semantic, no graph) was actually intended**,
the fix is a one-line change:
`evaluation/baselines/definitions.py`'s `BaselineId.B4` entry,
`router_factory=_fixed_router(RoutingStrategy.FULL_PIPELINE)` ->
`router_factory=_fixed_router(RoutingStrategy.HYBRID)`. Every other part
of this milestone's implementation (the runner, the tests, the fairness
guarantees) is unaffected by this choice.

## B5/B6: reported as unavailable, not implemented

Per this milestone's own instruction ("B5/B6 — only if the existing
project specification and literature verification justify them" and
"Report any baseline whose implementation cannot be reproduced because
the necessary external system/reference implementation is
unavailable"):

Both `PROJECT_SPEC.md` §24 and `EXPERIMENT_PLAN.md` §4 mark every
external-system baseline (AIRCoder, RepoFormer, AllianceCoder) as
`Status: TBD, contingent on public code/artifact availability`. No
literature-verification pass confirming a reproducible public artifact
for any of the three has been performed in this project (`PROJECT_SPEC.md`
§4 names that pass as a separate, not-yet-done task). Building a
"best-effort re-implementation" without that verification would mean
inventing a retrieval strategy attributed to a published system without
having actually read and confirmed its methodology -- indistinguishable
from fabrication, which this milestone's instructions explicitly
prohibit. `evaluation.baselines.definitions.UNAVAILABLE_BASELINES`
records this status machine-readably (`baseline_id`, `name`, `reason`)
rather than only in this document, so any future experiment-runner
script can enumerate and report it without needing to re-derive the
justification.

`EXPERIMENT_PLAN.md` §4 also names one baseline this milestone's
instructions do not mention at all: **B4 (Oracle retrieval)** --
context assembled directly from TIQS's ground-truth relevant-context
labels, bypassing retrieval entirely, to establish an upper-bound
reference. This is a genuinely useful, already-specified baseline this
package does not implement, since it was not part of this milestone's
task instructions; noted here as a known gap for whoever scopes a
future milestone, not implemented speculatively.

## Router isolation: why this package no longer touches `AdaptiveRouter`

**An earlier version of this package built every baseline on top of
`AdaptiveRouter`**, via a `FixedStrategyPolicy(RoutingPolicy)` and
`AdaptiveRouter(policies=(FixedStrategyPolicy(strategy),))`. This
followed `DESIGN_DECISIONS.md` #2's own stated methodology almost
verbatim: *"a fixed-strategy baseline is just an `AdaptiveRouter`
constructed with a one-policy tuple."* It was correctness-tested (a
baseline's plan provably did not vary across wildly different
classifications) and passed every test this package had at the time.

That approach was replaced because this milestone's task instructions
are explicit, in multiple independent places, that it is not a valid
implementation of a "fixed" baseline, regardless of whether it behaves
correctly:

- *"The baseline code must NOT import or call: TARA adaptive router,
  adaptive routing policy, TARA routing decision function..."*
- *"Even if the router happens to select semantic retrieval, that is
  NOT a valid fixed semantic baseline."*
- The explicit **ROUTER SPY TEST** requirement: inject a spy for
  `AdaptiveRouter` and assert its call count is `0` for every baseline.

A router-call-count spy makes the distinction observable, not just
philosophical: under the earlier `FixedStrategyPolicy` design,
`AdaptiveRouter.route()` was called exactly once per baseline run (with
a policy tuple that happened to have only one, non-adaptive member).
Under `evaluation.baselines.plan_builder.build_fixed_plan` (the current
design), `AdaptiveRouter.route()` is called **zero** times, because
nothing in this package ever constructs an `AdaptiveRouter` or a
`RoutingPolicy` at all -- see `evaluation/baselines/tests/test_router_isolation.py`
for the spy tests that now enforce this directly, for every baseline
B0-B4, both individually and across a full sweep.

**What is still reused, deliberately, and why it's not the same
concern:** `tara.routing.planner.RetrievalPlanner` (turning a
`RoutingDecision` into a fully-formed `RetrievalPlan` -- top-k,
execution order, rerank, context-capability downgrades) and
`tara.routing.policies.RoutingDecision` (a plain, frozen dataclass --
inert data). Neither of these *decides* a strategy; `RetrievalPlanner`'s
own docstring says exactly this: *"owns every numeric and ordering
decision the router itself does not."* A hand-built `RoutingDecision`
naming a fixed strategy, fed through `RetrievalPlanner`, produces the
exact same plan shape TARA's real router would have produced for that
strategy, without asking anything to choose it -- reuse of "how a chosen
strategy becomes an executable plan," never reuse of "what strategy gets
chosen."
