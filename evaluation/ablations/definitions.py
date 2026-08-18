"""The ablation catalog: A1-A9, per this milestone's instructions.

`ABLATION_DEFINITIONS` is the single source of truth for which ablations
are actually implemented (`AblationStatus.SUPPORTED`, with one or more
concrete `AblationVariant`s) versus explicitly unsupported/TBD
(`AblationStatus.UNSUPPORTED_TBD`, with a `prerequisite_notes` string
explaining exactly what is missing and why it was not built
speculatively). Every `AblationVariant.parameters` value is concrete and
runnable; nothing here is a placeholder pretending to be configured.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AblationId(str, Enum):
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    A7 = "A7"
    A8 = "A8"
    A9 = "A9"


class AblationStatus(str, Enum):
    SUPPORTED = "supported"
    """Implemented in this package; a caller can construct and run this variant today."""
    UNSUPPORTED_TBD = "unsupported_tbd"
    """Not implemented -- see the owning `AblationDefinition.prerequisite_notes` for why."""


class AblationVariant(BaseModel):
    """One concrete, runnable configuration within an ablation.

    `mechanism` names the exact class/function in this package (or, for
    A1/A9, the exact already-existing construct elsewhere) that
    implements this variant -- a caller (or a future experiment-runner
    script) resolves it by that name rather than this model trying to
    embed a live, non-serializable Python callable.
    """

    variant_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    mechanism: str = Field(
        ..., min_length=1, description="The importable name that implements this variant."
    )
    parameters: dict[str, Any] = Field(default_factory=dict)


class AblationDefinition(BaseModel):
    """One ablation (A1-A9): its research question, status, and (if supported) its variants."""

    ablation_id: AblationId
    name: str = Field(..., min_length=1)
    tests: str = Field(
        ..., min_length=1, description="What this ablation isolates, per `EXPERIMENT_PLAN.md` §5."
    )
    status: AblationStatus
    controlled_variable_exceptions: list[str] = Field(
        default_factory=list,
        description="ExperimentConfig field names this ablation is explicitly allowed to vary "
        "(passed as allowed_to_vary to "
        "evaluation.ablations.validation.validate_controlled_variables). "
        "Empty for every ablation whose mechanism lives entirely outside ExperimentConfig "
        "(A2-A7): those change a Router/context/policy, never a repository, query set, LLM, "
        "token budget, or embedding model.",
    )
    variants: list[AblationVariant] = Field(default_factory=list)
    prerequisite_notes: str | None = Field(
        default=None,
        description="Required, non-empty, when status is UNSUPPORTED_TBD: exactly what is "
        "missing and why it was not built speculatively for this milestone.",
    )


ABLATION_DEFINITIONS: tuple[AblationDefinition, ...] = (
    AblationDefinition(
        ablation_id=AblationId.A1,
        name="No Task Classifier / no Router",
        tests="The entire routing layer's contribution, in one step.",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id="A1-no-router",
                description="Equivalent to baseline B1 (fixed semantic-only): every query "
                "routed to SEMANTIC_ONLY regardless of classification, per "
                "EXPERIMENT_PLAN.md §5's own framing ('Equivalent to B1... isolates the "
                "entire routing layer's contribution in one step'). No new mechanism -- "
                "reuses the already-implemented baseline directly rather than duplicating it.",
                mechanism="evaluation.baselines.definitions.BASELINE_DEFINITIONS "
                "(the entry with baseline_id == BaselineId.B1)",
            )
        ],
    ),
    AblationDefinition(
        ablation_id=AblationId.A2,
        name="No REFACTOR override",
        tests="The specific hand-authored FullPipelinePolicy REFACTOR exception "
        "(CONTRIBUTIONS.md §2).",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id="A2-no-refactor-override",
                description="AdaptiveRouter constructed with ablated_policies(): "
                "FullPipelinePolicyWithoutRefactorOverride in place of FullPipelinePolicy, "
                "every other DEFAULT_POLICIES member unchanged.",
                mechanism="evaluation.ablations.policies.ablated_policies",
            )
        ],
    ),
    AblationDefinition(
        ablation_id=AblationId.A3,
        name="Graph retrieval disabled",
        tests="The marginal value of graph retrieval specifically.",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id="A3-no-graph",
                description="RepositoryContext transformed so RetrievalPlanner's own "
                "context-capability-downgrade path drops GRAPH from every plan; register no "
                "GraphRetriever in the RetrievalOrchestrator as a second safeguard.",
                mechanism="evaluation.ablations.context_transforms.disable_graph_retrieval",
            )
        ],
    ),
    AblationDefinition(
        ablation_id=AblationId.A4,
        name="Fixed top-k",
        tests="Whether strategy-specific result-count tuning matters independent of strategy "
        "selection.",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id="A4-fixed-top-k-10",
                description="Every plan's top_k forced to 10 (the current SEMANTIC_ONLY "
                "default, chosen as a neutral fixed value already inside the existing "
                "per-strategy range of 8-20), candidate_limit recomputed to match.",
                mechanism="evaluation.ablations.router_wrappers.FixedTopKRouter",
                parameters={"fixed_top_k": 10},
            )
        ],
    ),
    AblationDefinition(
        ablation_id=AblationId.A5,
        name="No reranking",
        tests="Reranking's own contribution within Context Fusion.",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id="A5-no-rerank",
                description="Every plan's rerank forced False, candidate_limit recomputed down "
                "to top_k.",
                mechanism="evaluation.ablations.router_wrappers.NoRerankRouter",
            )
        ],
    ),
    AblationDefinition(
        ablation_id=AblationId.A6,
        name="Reranker variant (cross-encoder vs. score-merge)",
        tests="Which reranking approach is worth its cost.",
        status=AblationStatus.UNSUPPORTED_TBD,
        prerequisite_notes="Requires a CrossEncoderReranker implementation in "
        "tara.fusion.reranker; none exists. M7 (Context Fusion) explicitly scoped "
        "cross-encoder reranking out ('Do NOT implement cross-encoder reranking yet') and it "
        "has not been built since. Only the score-merge baseline "
        "(tara.fusion.reranker.BaselineReranker) exists today, so this ablation cannot yet "
        "compare two variants -- building a cross-encoder reranker is a real ML-component "
        "decision (model choice, latency profiling) out of scope for this milestone.",
    ),
    AblationDefinition(
        ablation_id=AblationId.A7,
        name="Confidence-threshold fallback sweep",
        tests="Quality/coverage trade-off from confidence-gated fallback.",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id=f"A7-threshold-{threshold}",
                description=f"Router wrapped so classifications with confidence < {threshold} "
                f"are forced to SEMANTIC_ONLY instead of the real routing decision.",
                mechanism="evaluation.ablations.router_wrappers.ConfidenceThresholdFallbackRouter",
                parameters={"confidence_threshold": threshold},
            )
            for threshold in (0.3, 0.4, 0.5, 0.6, 0.7)
        ],
    ),
    AblationDefinition(
        ablation_id=AblationId.A8,
        name="Embedding model swap",
        tests="Sensitivity of results to embedding model choice.",
        status=AblationStatus.SUPPORTED,
        controlled_variable_exceptions=["embedding_model_name"],
        variants=[
            AblationVariant(
                variant_id="A8-bge-small",
                description="TARA's current default embedding model.",
                mechanism="tara.core.config.TaraSettings.embedding_model_name",
                parameters={"embedding_model_name": "BAAI/bge-small-en-v1.5"},
            ),
            AblationVariant(
                variant_id="A8-minilm-l6",
                description="A smaller, widely-used general-purpose sentence-embedding model.",
                mechanism="tara.core.config.TaraSettings.embedding_model_name",
                parameters={"embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2"},
            ),
        ],
        prerequisite_notes="A third, code-domain-specific variant (candidate: "
        "jinaai/jina-embeddings-v2-base-code) is named in EXPERIMENT_PLAN.md §5 but marked "
        "'final choice TBD' there -- not included as a variant here since no final model has "
        "actually been chosen; adding one speculatively would not be a real, reproducible "
        "configuration. The two variants above ARE fully supported: "
        "TaraSettings.embedding_model_name and SentenceTransformerEmbedder already accept any "
        "sentence-transformers model name "
        "with no new code required.",
    ),
    AblationDefinition(
        ablation_id=AblationId.A9,
        name="TaskClassification surfaced to LLM vs. not",
        tests="Whether the classification is useful beyond its use in retrieval selection.",
        status=AblationStatus.SUPPORTED,
        variants=[
            AblationVariant(
                variant_id="A9-baseline",
                description="TaskClassification omitted from the generation prompt (current "
                "default).",
                mechanism="tara.generation.prompt.PromptTemplate.BASELINE",
            ),
            AblationVariant(
                variant_id="A9-with-classification",
                description="TaskClassification (task type + routing reason) included in the "
                "generation prompt.",
                mechanism="tara.generation.prompt.PromptTemplate.WITH_TASK_CLASSIFICATION",
            ),
        ],
    ),
)
