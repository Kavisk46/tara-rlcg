"""Data contracts for the evaluation harness: variants, ground truth, and result records.

Every result field that represents a metric is `Optional`, defaulting to
`None` when the metric could not be computed for that query (no ground
truth supplied, no reference output, an unsupported language, an
execution harness that doesn't exist) -- per this milestone's explicit
"do not fabricate missing metrics" instruction, `None` is the only
honest value in that situation, never a fabricated `0.0`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from evaluation.baselines.definitions import BaselineDefinition
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import Language, TaskType
from tara.routing.strategy import RoutingStrategy

TARA_VARIANT_ID = "TARA"
"""The variant id `ExperimentRunner`/aggregation reserve for TARA-proper (the real,
`AdaptiveRouter`-driven system), distinguishing it from every `evaluation.baselines.BaselineId`
value -- never a member of that enum, since TARA-proper is the system under test, not a baseline
compared against it."""


@dataclass(frozen=True)
class Variant:
    """One system configuration the harness can run a query through: TARA-proper or a baseline.

    Unifies `evaluation.baselines.definitions.BaselineDefinition` (whose
    `baseline_id` is the closed `BaselineId` enum, B0-B6, and which has
    no way to represent "the real adaptive router") with TARA-proper
    under one shape `ExperimentRunner` can iterate over uniformly,
    without `BaselineDefinition` itself needing to grow a case it isn't
    conceptually about.

    Three states, matching `evaluation.baselines.plan_builder`'s own
    Router-isolation design (see `BASELINE_DISCREPANCIES.md`, "Router
    isolation"): `is_adaptive=True` (TARA-proper: build the plan via a
    real, freshly-constructed `AdaptiveRouter().route()` call --
    `strategy` is ignored); `is_adaptive=False, strategy=<value>` (a
    baseline with a fixed strategy: build the plan via
    `evaluation.baselines.plan_builder.build_fixed_plan`, which never
    constructs or calls `AdaptiveRouter`/`RoutingPolicy`); `is_adaptive=False,
    strategy=None` (B0: no retrieval at all).
    """

    variant_id: str
    strategy: RoutingStrategy | None = None
    is_adaptive: bool = False


def variant_from_baseline(baseline: BaselineDefinition) -> Variant:
    """Adapt a `BaselineDefinition` into a `Variant`.

    `is_adaptive` is always `False`: no baseline ever uses the real
    adaptive router, by construction (`evaluation.baselines.plan_builder`'s
    own Router-isolation guarantee).
    """
    return Variant(variant_id=baseline.baseline_id.value, strategy=baseline.strategy)


def tara_variant() -> Variant:
    """The TARA-proper `Variant`: routes via a real, freshly-constructed `AdaptiveRouter()` call.

    `strategy` is left at its default (`None`) and ignored -- `is_adaptive=True`
    is what tells `ExperimentRunner` to call the real adaptive router
    instead of `build_fixed_plan`.
    """
    return Variant(variant_id=TARA_VARIANT_ID, is_adaptive=True)


class GroundTruth(BaseModel):
    """Everything about one query that a metric needs but the pipeline itself doesn't produce.

    Every field is optional except `query_id`: a query with no
    `relevant_node_ids` simply cannot have retrieval metrics computed
    for it (skipped, not fabricated); a query with no `reference_text`
    cannot have `exact_match`/`edit_similarity` computed; and so on.
    Mirrors `evaluation.tiqs.models.TIQSQueryRecord`'s ground-truth
    fields without depending on that module directly, since a caller
    may supply ground truth from a synthetic fixture (as every test in
    this package does) rather than a real TIQS record.
    """

    query_id: str = Field(..., min_length=1)
    relevant_node_ids: set[str] | None = Field(
        default=None, description="Ground-truth relevant node ids, for Precision@k/Recall@k/"
        "MRR/plan_coverage. None (not an empty set) means 'no ground truth available' -- an "
        "empty set is rejected by evaluation.metrics.retrieval as ill-defined, per its own "
        "validation."
    )
    relevance_grades: dict[str, float] | None = Field(
        default=None, description="Graded relevance, for NDCG@k. None means binary-only "
        "relevance was recorded (or no ground truth at all) -- ndcg_at_k already returns None "
        "in that case, per EXPERIMENT_PLAN.md §3."
    )
    reference_text: str | None = Field(
        default=None, description="A reference/acceptable-output string, for exact_match/"
        "edit_similarity."
    )
    language: Language | None = Field(
        default=None, description="The generated code's language, for syntactic_validity."
    )


class RetrievalMetricsResult(BaseModel):
    """Retrieval-stage metrics for one query, per `EXPERIMENT_PLAN.md` §3."""

    precision_at_k: dict[int, float] = Field(default_factory=dict)
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    reciprocal_rank: float | None = Field(default=None)
    ndcg_at_k: dict[int, float | None] = Field(default_factory=dict)
    plan_coverage: float | None = Field(default=None)


class GenerationMetricsResult(BaseModel):
    """Generation-stage metrics for one query, per `EXPERIMENT_PLAN.md` §3."""

    exact_match: bool | None = Field(default=None)
    edit_similarity: float | None = Field(default=None)
    syntactic_validity: bool | None = Field(default=None)


class EfficiencyResult(BaseModel):
    """Per-stage latency and cost-proxy measurements for one query, per `EXPERIMENT_PLAN.md` §3."""

    routing_latency_ms: float | None = Field(default=None)
    retrieval_latency_ms: float | None = Field(default=None)
    fusion_latency_ms: float | None = Field(default=None)
    generation_latency_ms: float = Field(...)
    total_latency_ms: float = Field(...)
    retriever_invocation_count: int = Field(..., ge=0)
    embedding_call_count: int = Field(..., ge=0)
    retrieved_token_count: int = Field(..., ge=0)
    generation_prompt_tokens: int | None = Field(default=None)
    generation_completion_tokens: int | None = Field(default=None)
    estimated_cost: float | None = Field(default=None)


class QueryRunResult(BaseModel):
    """The complete, machine-readable record of one `Variant` run against one query."""

    variant_id: str = Field(..., min_length=1)
    query_id: str = Field(..., min_length=1)
    repository_id: str = Field(..., min_length=1)
    task_type: TaskType | None = Field(default=None)
    plan_strategy: str | None = Field(default=None)
    plan_retrievers: list[str] = Field(default_factory=list)
    retrieval_metrics: RetrievalMetricsResult | None = Field(default=None)
    generation_metrics: GenerationMetricsResult | None = Field(default=None)
    efficiency: EfficiencyResult = Field(...)
    generated_text: str = Field(default="")
    error: str | None = Field(
        default=None, description="Set iff an exception was caught while running this "
        "query/variant; the rest of this record reflects whatever was computed before the "
        "failure, not a fully-formed successful run."
    )


class ExperimentConfig(BaseModel):
    """Every setting a reported result depends on -- stored alongside results, per this
    milestone's explicit instruction, never reconstructed after the fact."""

    experiment_id: str = Field(..., min_length=1)
    created_at: datetime = Field(...)
    variant_ids: list[str] = Field(..., min_length=1)
    generation_model: str = Field(..., min_length=1)
    token_budget: int = Field(..., gt=0)
    prompt_template: str = Field(...)
    k_values: list[int] = Field(
        ..., min_length=1, description="The k values Precision@k/Recall@k/NDCG@k are computed at."
    )
    repository_manifest_path: str | None = Field(default=None)
    queries_path: str | None = Field(default=None)
    tara_git_commit: str | None = Field(default=None)
    notes: str | None = Field(default=None)


@dataclass(frozen=True)
class QuerySpec:
    """One query to run every variant against -- the harness's per-query input unit."""

    query_id: str
    repository_id: str
    query_text: str
    task_type: TaskType | None
    classification: TaskClassification
    context: RepositoryContext
    ground_truth: GroundTruth | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
