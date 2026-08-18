"""A2 -- Router without the REFACTOR override.

`tara.routing.policies.FullPipelinePolicy.applies()` fires either when
every retrieval flag is set, or -- regardless of the raw flags --
whenever `task_type is TaskType.REFACTOR`; this second, hand-authored
exception is exactly what `EXPERIMENT_PLAN.md` §5 A2 exists to isolate
("The specific hand-authored exception flagged in `CONTRIBUTIONS.md` §2").
`FullPipelinePolicyWithoutRefactorOverride` is the same policy with only
that `or task_type is REFACTOR` clause removed -- every other policy in
`tara.routing.policies.DEFAULT_POLICIES` (`GraphPolicy`, `HybridPolicy`,
`LexicalPolicy`, `SemanticPolicy`) is reused unchanged, per
`ablated_policies` below, so this ablation changes exactly one decision
rule and nothing else about routing.
"""
from __future__ import annotations

from tara.classification.models import TaskClassification
from tara.routing.policies import DEFAULT_POLICIES, RoutingDecision, RoutingPolicy
from tara.routing.strategy import STRATEGY_RETRIEVERS, RoutingStrategy


class FullPipelinePolicyWithoutRefactorOverride(RoutingPolicy):
    """`FullPipelinePolicy`, minus its REFACTOR task-type exception.

    Fires only when every retrieval flag (graph/semantic/lexical) is
    independently set by the classifier -- never merely because
    `task_type is TaskType.REFACTOR`. A REFACTOR query under this
    ablation is routed purely by whichever of `GraphPolicy`/`HybridPolicy`/
    `LexicalPolicy`/`SemanticPolicy` its raw flags actually satisfy,
    exactly as `EXPERIMENT_PLAN.md` §5 A2 specifies ("REFACTOR queries
    routed purely by raw classification flags").
    """

    name = "full_pipeline_no_refactor_override"

    def applies(self, classification: TaskClassification) -> bool:
        return (
            classification.graph_required
            and classification.semantic_required
            and classification.lexical_required
        )

    def decide(self, classification: TaskClassification) -> RoutingDecision:
        return RoutingDecision(
            policy_name=self.name,
            strategy=RoutingStrategy.FULL_PIPELINE,
            retrievers=STRATEGY_RETRIEVERS[RoutingStrategy.FULL_PIPELINE],
            reason="The classifier flagged graph, semantic, and lexical retrieval as all "
            "required (REFACTOR task-type override disabled for this ablation).",
        )


def ablated_policies() -> tuple[RoutingPolicy, ...]:
    """The A2 policy tuple: `DEFAULT_POLICIES` with only its first entry swapped.

    Returns:
        `(FullPipelinePolicyWithoutRefactorOverride(), GraphPolicy(), HybridPolicy(),
        LexicalPolicy(), SemanticPolicy())` -- identical order and identical remaining
        policies to `tara.routing.policies.DEFAULT_POLICIES`, whose own composition this
        function reads from directly (via `DEFAULT_POLICIES[1:]`) rather than
        re-listing the four unchanged policy classes by hand, so this ablation can never
        silently drift out of sync if `DEFAULT_POLICIES`'s non-REFACTOR members ever change.
    """
    return (FullPipelinePolicyWithoutRefactorOverride(), *DEFAULT_POLICIES[1:])
