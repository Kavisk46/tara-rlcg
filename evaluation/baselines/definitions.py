"""Baseline definitions: which fixed strategy (if any) each baseline uses.

**Naming deviates from `PROJECT_SPEC.md` §24 / `EXPERIMENT_PLAN.md` §4.**
Both documents number baselines differently from this milestone's task
instructions (e.g. their B2 is "fixed full-pipeline," not "fixed
lexical-only"; their B3 is "random routing," not "fixed graph-only").
This module implements the baseline set exactly as specified in this
milestone's own instructions, since that is the authoritative task
definition for this piece of work. See `BASELINE_DISCREPANCIES.md` in
this directory for the full three-way comparison (`PROJECT_SPEC.md` §24
vs. `EXPERIMENT_PLAN.md` §4 vs. this module) and the reasoning behind
every mapping decision, including the B4 "hybrid / unified retrieval"
ambiguity resolution.

**No `Router`/`AdaptiveRouter` involved.** Each `BaselineDefinition`
names a fixed `RoutingStrategy` (or `None`, for B0's "no retrieval at
all") as plain data; `evaluation.baselines.plan_builder.build_fixed_plan`
turns that into a `RetrievalPlan` without constructing or calling
`AdaptiveRouter`, `RoutingPolicy`, or `TaskClassifier` -- see that
module's docstring and `BASELINE_DISCREPANCIES.md` for why an earlier
version of this file used a `router_factory: Callable[[], Router]` field
instead, and why that was replaced.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tara.routing.strategy import RoutingStrategy


class BaselineId(str, Enum):
    """Identifiers for every baseline this milestone defines or discloses."""

    B0 = "B0"
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    B4 = "B4"
    B5 = "B5"
    B6 = "B6"


@dataclass(frozen=True)
class BaselineDefinition:
    """One implementable baseline: a name, a description, and its fixed strategy (if any).

    This *is* the baseline's entire "retrieval plan" as fixed
    configuration data -- nothing about `strategy` is decided at
    runtime, and nothing here depends on a query's content.
    """

    baseline_id: BaselineId
    name: str
    description: str
    strategy: RoutingStrategy | None
    """`None` for B0 specifically: "no retrieval" has no strategy to fix at all -- see
    `evaluation.baselines.runner.BaselineRunner.build_plan`, which treats `strategy is None`
    as "skip routing, retrieval, and fusion; generate directly from the query with no context,"
    matching this baseline's own definition."""


BASELINE_DEFINITIONS: tuple[BaselineDefinition, ...] = (
    BaselineDefinition(
        baseline_id=BaselineId.B0,
        name="No retrieval",
        description="The LLM generates directly from the query with no repository context at "
        "all. Establishes the floor.",
        strategy=None,
    ),
    BaselineDefinition(
        baseline_id=BaselineId.B1,
        name="Fixed semantic-only",
        description="Every query is routed to SEMANTIC_ONLY (dense retrieval), regardless of "
        "classification. Represents the dominant existing-practice retrieval strategy this "
        "project's motivation argues against.",
        strategy=RoutingStrategy.SEMANTIC_ONLY,
    ),
    BaselineDefinition(
        baseline_id=BaselineId.B2,
        name="Fixed lexical-only",
        description="Every query is routed to LEXICAL_ONLY (BM25 keyword search), regardless of "
        "classification. Isolates how much of TARA's advantage, if any, a single non-adaptive "
        "lexical strategy alone would already capture.",
        strategy=RoutingStrategy.LEXICAL_ONLY,
    ),
    BaselineDefinition(
        baseline_id=BaselineId.B3,
        name="Fixed graph-only",
        description="Every query is routed to GRAPH_ONLY (repository graph traversal), "
        "regardless of classification. Isolates how much of TARA's advantage, if any, a single "
        "non-adaptive graph strategy alone would already capture.",
        strategy=RoutingStrategy.GRAPH_ONLY,
    ),
    BaselineDefinition(
        baseline_id=BaselineId.B4,
        name="Always full-pipeline (unified retrieval)",
        description="Every query is routed to FULL_PIPELINE (lexical + semantic + graph, "
        "together), regardless of classification -- 'always combine every retrieval modality "
        "available,' the most literal reading of this milestone's 'always hybrid / unified "
        "retrieval' instruction. Isolates 'more retrieval, always' from 'adaptive selection of "
        "retrieval': TARA-proper should not need to beat this baseline on retrieval breadth, "
        "only on not paying full-pipeline's cost when a narrower strategy would do as well. "
        "NOTE: this is a deliberate disambiguation of 'hybrid' -- TARA's own "
        "RoutingStrategy.HYBRID enum member is narrower (lexical + semantic only, no graph); see "
        "BASELINE_DISCREPANCIES.md for the reasoning and how to swap this to HYBRID instead if "
        "that was the intended reading.",
        strategy=RoutingStrategy.FULL_PIPELINE,
    ),
)


@dataclass(frozen=True)
class UnavailableBaseline:
    """A baseline named in this milestone's instructions or in the project's specification
    documents that is not implemented here, and why."""

    baseline_id: BaselineId
    name: str
    reason: str


UNAVAILABLE_BASELINES: tuple[UnavailableBaseline, ...] = (
    UnavailableBaseline(
        baseline_id=BaselineId.B5,
        name="AIRCoder (reproduction or re-implementation)",
        reason="PROJECT_SPEC.md §24 / EXPERIMENT_PLAN.md §4 both mark this 'Status: TBD, "
        "contingent on public code/artifact availability.' No literature-verification pass "
        "confirming a reproducible public artifact exists has been performed (PROJECT_SPEC.md "
        "§4 names this as a separate, not-yet-done task), and this milestone's own instructions "
        "require justification before implementing B5/B6 at all. A best-effort re-implementation "
        "without verified grounding in AIRCoder's actual published methodology would itself be "
        "fabrication, which this milestone's instructions explicitly prohibit. Not implemented.",
    ),
    UnavailableBaseline(
        baseline_id=BaselineId.B6,
        name="RepoFormer-style dense retrieval / AllianceCoder-style ensemble retrieval",
        reason="Same status and same reasoning as B5 (PROJECT_SPEC.md §24 marks both "
        "'Status: TBD, same reproducibility caveat as B4/AIRCoder'). EXPERIMENT_PLAN.md §4 notes "
        "AllianceCoder's ensemble strategy is 'likely near-equivalent to' a fixed full-pipeline "
        "baseline if its ensemble strategy is non-adaptive -- if that equivalence is confirmed by "
        "a future literature-verification pass, this milestone's B4 (fixed full-pipeline) may "
        "substitute for it, with the equivalence stated explicitly, rather than requiring a "
        "separate implementation. Not implemented.",
    ),
)
