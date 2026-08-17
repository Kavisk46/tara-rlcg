"""Configuration-driven baseline runner.

`BaselineRunner` executes one baseline's full retrieve -> fuse ->
generate pipeline for one query. It is constructed once, with the
collaborators every baseline (and, by the same construction, TARA-proper
run through the same harness) must share for a fair comparison:

- **repository corpus / query set**: not config fields on this class --
  fairness comes from calling the *same* `BaselineRunner` instance,
  against the *same* `RepositoryContext`, for *every* baseline and every
  query, rather than constructing a differently-configured runner per
  baseline.
- **generation model**: the single injected `CodeGenerator` instance is
  reused for every baseline -- there is no per-baseline model
  configuration to accidentally diverge.
- **token budget**: `settings.fusion_token_budget`, read from the single
  injected `TaraSettings` instance, reused for every baseline's
  `ContextFusion.fuse` call.
- **evaluation protocol**: every baseline flows through the identical
  `run()` method body (build a fixed plan -> retrieve -> fuse ->
  generate); only `baseline.strategy` differs between calls, and no
  `AdaptiveRouter`/`RoutingPolicy` is ever constructed or called (see
  `evaluation.baselines.plan_builder`).

No baseline is actually run against a real repository or real queries
by this module -- see `evaluation/baselines/tests/` for the synthetic
fixtures every test in this package uses instead.
"""
from __future__ import annotations

from dataclasses import dataclass

from evaluation.baselines.definitions import BaselineDefinition, BaselineId
from evaluation.baselines.plan_builder import build_fixed_plan
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.config import TaraSettings
from tara.fusion.fusion import ContextFusion
from tara.fusion.models import FusedContext
from tara.generation.models import GeneratedCode
from tara.generation.prompt import PromptBuilder, PromptTemplate
from tara.generation.service import CodeGenerationService
from tara.interfaces.code_generator import CodeGenerator
from tara.retrieval.orchestrator import RetrievalOrchestrator
from tara.routing.models import RetrievalPlan


@dataclass(frozen=True)
class BaselineRunResult:
    """Everything one `BaselineRunner.run()` call produced, for inspection or downstream metrics.

    Kept as a single result object (rather than returning only
    `GeneratedCode`) specifically so a future metrics stage can compute
    retrieval-quality metrics against `plan`/`fused_context` without
    needing `BaselineRunner` to re-run anything -- and so this
    milestone's own tests can assert on the intermediate `plan` and
    `fused_context` directly, per its explicit test requirements.
    """

    baseline_id: BaselineId
    plan: RetrievalPlan | None
    fused_context: FusedContext
    generated_code: GeneratedCode


class BaselineRunner:
    """Executes one baseline's retrieve -> fuse -> generate pipeline for one query.

    Every collaborator is injected (Dependency Inversion, matching every
    other multi-component TARA stage): swap `code_generator` for a real
    provider once one exists, swap `retrieval_orchestrator` for one
    registered against a real repository's retrievers, without changing
    this class.
    """

    def __init__(
        self,
        retrieval_orchestrator: RetrievalOrchestrator,
        code_generator: CodeGenerator,
        settings: TaraSettings | None = None,
        context_fusion: ContextFusion | None = None,
    ) -> None:
        """Construct the runner.

        Args:
            retrieval_orchestrator: Executes a baseline's `RetrievalPlan`
                against a `RepositoryContext`. Shared across every
                baseline run through this instance -- the same
                registered retrievers serve every baseline and TARA
                itself, so no baseline gets a retriever TARA doesn't
                also have access to, or vice versa.
            code_generator: The provider every baseline's final
                generation call uses, e.g.
                `tara.generation.fake_provider.FakeCodeGenerator` (no
                real network provider exists yet, see M8). This is the
                "same generation model" fairness requirement: one
                instance, reused for every baseline.
            settings: Supplies `fusion_token_budget`, the "same token
                budget" fairness requirement. Defaults to a plain
                `TaraSettings()` when omitted.
            context_fusion: Deduplicates/merges/budgets retrieved
                context. Defaults to a plain `ContextFusion()`.
        """
        self._orchestrator = retrieval_orchestrator
        self._settings = settings or TaraSettings()
        self._fusion = context_fusion or ContextFusion()
        # BASELINE, never WITH_TASK_CLASSIFICATION: a baseline's whole point is that
        # classification has no influence on it -- surfacing it in the prompt anyway would
        # reintroduce exactly the signal a baseline is meant to withhold.
        prompt_builder = PromptBuilder(template=PromptTemplate.BASELINE)
        self._service = CodeGenerationService(code_generator, prompt_builder)

    def build_plan(
        self,
        baseline: BaselineDefinition,
        classification: TaskClassification,
        context: RepositoryContext,
    ) -> RetrievalPlan | None:
        """Build `baseline`'s `RetrievalPlan` for `classification`, without running retrieval.

        Never constructs or calls `AdaptiveRouter`/`Router`/`RoutingPolicy`
        -- see `evaluation.baselines.plan_builder` for how a fixed plan is
        built instead.

        Args:
            baseline: Which baseline to build a plan for.
            classification: Passed through to `build_fixed_plan` for
                `RetrievalPlanner`'s own numeric/ordering logic
                (rerank-on-`reasoning_required`, metadata); never
                consulted to choose `baseline.strategy` -- that is fixed
                configuration data, not a decision.
            context: The repository context the plan would run against;
                consulted only for `RetrievalPlanner`'s own cheap
                capability downgrade checks (e.g. missing embeddings).

        Returns:
            The `RetrievalPlan`, or `None` for a baseline with no fixed
            `strategy` (B0: no retrieval at all).
        """
        if baseline.strategy is None:
            return None
        return build_fixed_plan(baseline.strategy, classification, context)

    def run(
        self,
        baseline: BaselineDefinition,
        query: str,
        classification: TaskClassification,
        context: RepositoryContext,
    ) -> BaselineRunResult:
        """Run `baseline` end to end for `query`.

        Args:
            baseline: Which baseline to run.
            query: The developer query text.
            classification: The query's `TaskClassification`. Computed
                once per query and reused across every baseline and
                TARA-proper being compared for that query, so
                classification cost/randomness is identical everywhere
                -- not recomputed per baseline. Baselines other than the
                B0 no-retrieval case still require one, purely to
                satisfy `RetrievalPlanner.plan`'s signature (see
                `evaluation.baselines.plan_builder.build_fixed_plan`);
                its content has no effect on which strategy a baseline
                uses.
            context: The repository context to retrieve against.

        Returns:
            A `BaselineRunResult` with the plan built (`None` for B0),
            the fused context, and the final `GeneratedCode`.
        """
        plan = self.build_plan(baseline, classification, context)

        if plan is None:
            fused_context = FusedContext(query=query, chunks=[], truncated=False, candidate_count=0)
        else:
            retrieved_contexts = self._orchestrator.execute(query, plan, context)
            fused_context = self._fusion.fuse(
                query, retrieved_contexts, plan, self._settings.fusion_token_budget
            )

        generated_code = self._service.generate(query, fused_context)
        return BaselineRunResult(
            baseline_id=baseline.baseline_id,
            plan=plan,
            fused_context=fused_context,
            generated_code=generated_code,
        )
