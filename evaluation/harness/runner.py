"""`ExperimentRunner`: executes query -> routing -> retrieval -> fusion -> generation -> metrics.

For one `Variant` (TARA-proper or a baseline) and one `QuerySpec`,
`ExperimentRunner.run_query` performs the same four pipeline stages
`evaluation.baselines.runner.BaselineRunner` performs, but with
`time.perf_counter()` timing captured around each stage (this
milestone's own efficiency-metric requirement) and every metric family
in `evaluation.metrics` computed from the result, using whatever
`GroundTruth` was supplied -- skipping (not fabricating) any metric a
query's `GroundTruth` doesn't support.

Deliberately does not depend on `evaluation.baselines.runner.BaselineRunner`:
that class's tested M10 contract (no per-stage timing, no metrics) is
left unchanged; this runner composes the same underlying collaborators
directly instead -- `AdaptiveRouter` only for the TARA-proper `Variant`
(`Variant.is_adaptive`), `evaluation.baselines.plan_builder.build_fixed_plan`
for every baseline `Variant` (never `AdaptiveRouter`/`RoutingPolicy`, per
`evaluation.baselines`'s own Router-isolation guarantee -- see
`evaluation/baselines/BASELINE_DISCREPANCIES.md`, "Router isolation"),
and `RetrievalOrchestrator`/`ContextFusion`/`CodeGenerationService` for
every variant alike -- since the two runners' actual requirements
diverge enough (timing instrumentation, metrics, per-query error
isolation) that wrapping would be more contortion than reuse.
"""
from __future__ import annotations

import json
import time
import traceback
from collections.abc import Sequence
from pathlib import Path

from evaluation.baselines.plan_builder import build_fixed_plan
from evaluation.harness.models import (
    EfficiencyResult,
    ExperimentConfig,
    GenerationMetricsResult,
    GroundTruth,
    QueryRunResult,
    QuerySpec,
    RetrievalMetricsResult,
    Variant,
)
from evaluation.metrics import efficiency as efficiency_metrics
from evaluation.metrics import generation as generation_metrics
from evaluation.metrics import retrieval as retrieval_metrics
from tara.core.config import TaraSettings
from tara.fusion.fusion import ContextFusion
from tara.fusion.models import FusedContext
from tara.generation.prompt import PromptBuilder, PromptTemplate
from tara.generation.service import CodeGenerationService
from tara.interfaces.code_generator import CodeGenerator
from tara.retrieval.models import RetrievedContext
from tara.retrieval.orchestrator import RetrievalOrchestrator
from tara.routing.models import RetrievalPlan
from tara.routing.router import AdaptiveRouter


class ExperimentRunner:
    """Runs `Variant`s against `QuerySpec`s, producing `QueryRunResult`s.

    Every collaborator is injected, matching every other multi-component
    TARA/evaluation stage. `k_values` fixes which cutoffs Precision@k/
    Recall@k/NDCG@k are computed at for every query in a run -- held
    constant across the whole run, per `EXPERIMENT_PLAN.md` §3's matched-k
    requirement.
    """

    def __init__(
        self,
        retrieval_orchestrator: RetrievalOrchestrator,
        code_generator: CodeGenerator,
        k_values: Sequence[int] = (5, 10),
        settings: TaraSettings | None = None,
        context_fusion: ContextFusion | None = None,
        prompt_template: PromptTemplate = PromptTemplate.BASELINE,
    ) -> None:
        """Construct the runner.

        Args:
            retrieval_orchestrator: Executes a variant's `RetrievalPlan`.
            code_generator: Shared across every variant run through this
                instance -- the "same generation model" fairness
                requirement, identical in spirit to
                `evaluation.baselines.runner.BaselineRunner`.
            k_values: Which cutoffs to compute Precision@k/Recall@k/
                NDCG@k at. Defaults to `(5, 10)`.
            settings: Supplies `fusion_token_budget`. Defaults to a
                plain `TaraSettings()`.
            context_fusion: Defaults to a plain `ContextFusion()`.
            prompt_template: Defaults to `PromptTemplate.BASELINE` --
                pass `WITH_TASK_CLASSIFICATION` explicitly for the A9
                ablation (`EXPERIMENT_PLAN.md` §5), never silently.
        """
        self._orchestrator = retrieval_orchestrator
        self._code_generator = code_generator
        self._k_values = tuple(k_values)
        self._settings = settings or TaraSettings()
        self._fusion = context_fusion or ContextFusion()
        self._prompt_builder = PromptBuilder(template=prompt_template)
        self._service = CodeGenerationService(code_generator, self._prompt_builder)

    def run_query(self, variant: Variant, query: QuerySpec) -> QueryRunResult:
        """Run `variant` against `query`, end to end, with metrics.

        Never raises for a pipeline-stage failure: any exception raised
        by routing, retrieval, fusion, or generation is caught and
        recorded on the returned `QueryRunResult.error`, so one query's
        failure cannot abort a batch run
        (`evaluation.harness.aggregation` skips errored records rather
        than crashing on them). A `pydantic.ValidationError` while
        constructing the result itself is not caught -- that would be a
        bug in this runner, not a query-specific failure, and should
        surface loudly.

        Args:
            variant: Which system configuration to run.
            query: The query, its repository context, and (optionally)
                its ground truth.

        Returns:
            A `QueryRunResult`. `error` is set, and every metric field
            is `None`/default, iff a pipeline stage raised.
        """
        run_start = time.perf_counter()
        try:
            return self._run_query_unguarded(variant, query, run_start)
        except Exception as exc:  # noqa: BLE001 - isolate one query's failure from the batch
            total_latency_ms = (time.perf_counter() - run_start) * 1000
            return QueryRunResult(
                variant_id=variant.variant_id,
                query_id=query.query_id,
                repository_id=query.repository_id,
                task_type=query.task_type,
                efficiency=EfficiencyResult(
                    generation_latency_ms=0.0,
                    total_latency_ms=total_latency_ms,
                    retriever_invocation_count=0,
                    embedding_call_count=0,
                    retrieved_token_count=0,
                ),
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )

    def _run_query_unguarded(
        self, variant: Variant, query: QuerySpec, run_start: float
    ) -> QueryRunResult:
        routing_latency_ms: float | None = None
        retrieval_latency_ms: float | None = None
        fusion_latency_ms: float | None = None
        plan: RetrievalPlan | None = None
        retrieved_contexts: list[RetrievedContext] = []

        if variant.is_adaptive:
            t0 = time.perf_counter()
            router = AdaptiveRouter()
            plan = router.route(query.classification, query.context)
            routing_latency_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            retrieved_contexts = self._orchestrator.execute(query.query_text, plan, query.context)
            retrieval_latency_ms = (time.perf_counter() - t1) * 1000

            t2 = time.perf_counter()
            fused_context = self._fusion.fuse(
                query.query_text, retrieved_contexts, plan, self._settings.fusion_token_budget
            )
            fusion_latency_ms = (time.perf_counter() - t2) * 1000
        elif variant.strategy is not None:
            # A baseline with a fixed strategy: build_fixed_plan never constructs or calls
            # AdaptiveRouter/RoutingPolicy/TaskClassifier -- see evaluation.baselines.plan_builder.
            t0 = time.perf_counter()
            plan = build_fixed_plan(variant.strategy, query.classification, query.context)
            routing_latency_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            retrieved_contexts = self._orchestrator.execute(query.query_text, plan, query.context)
            retrieval_latency_ms = (time.perf_counter() - t1) * 1000

            t2 = time.perf_counter()
            fused_context = self._fusion.fuse(
                query.query_text, retrieved_contexts, plan, self._settings.fusion_token_budget
            )
            fusion_latency_ms = (time.perf_counter() - t2) * 1000
        else:
            fused_context = FusedContext(
                query=query.query_text, chunks=[], truncated=False, candidate_count=0
            )

        t3 = time.perf_counter()
        generated = self._service.generate(query.query_text, fused_context)
        generation_latency_ms = (time.perf_counter() - t3) * 1000

        total_latency_ms = (time.perf_counter() - run_start) * 1000

        candidate_pool = {
            chunk.chunk_id for context in retrieved_contexts for chunk in context.chunks
        }
        retrieved_ids = [chunk.chunk_id for chunk in fused_context.chunks]

        efficiency = EfficiencyResult(
            routing_latency_ms=routing_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            fusion_latency_ms=fusion_latency_ms,
            generation_latency_ms=generation_latency_ms,
            total_latency_ms=total_latency_ms,
            retriever_invocation_count=efficiency_metrics.retriever_invocation_count(plan),
            embedding_call_count=efficiency_metrics.embedding_call_count(plan),
            retrieved_token_count=fused_context.total_tokens,
            generation_prompt_tokens=generated.prompt_tokens,
            generation_completion_tokens=generated.completion_tokens,
        )

        return QueryRunResult(
            variant_id=variant.variant_id,
            query_id=query.query_id,
            repository_id=query.repository_id,
            task_type=query.task_type,
            plan_strategy=plan.strategy.value if plan is not None else None,
            plan_retrievers=[r.value for r in plan.retrievers] if plan is not None else [],
            retrieval_metrics=self._compute_retrieval_metrics(
                retrieved_ids, candidate_pool, query.ground_truth
            ),
            generation_metrics=self._compute_generation_metrics(generated.text, query.ground_truth),
            efficiency=efficiency,
            generated_text=generated.text,
        )

    def _compute_retrieval_metrics(
        self, retrieved_ids: list[str], candidate_pool: set[str], ground_truth: GroundTruth | None
    ) -> RetrievalMetricsResult | None:
        if ground_truth is None or not ground_truth.relevant_node_ids:
            return None

        relevant = ground_truth.relevant_node_ids
        return RetrievalMetricsResult(
            precision_at_k={
                k: retrieval_metrics.precision_at_k(retrieved_ids, relevant, k)
                for k in self._k_values
            },
            recall_at_k={
                k: retrieval_metrics.recall_at_k(retrieved_ids, relevant, k)
                for k in self._k_values
            },
            reciprocal_rank=retrieval_metrics.reciprocal_rank(retrieved_ids, relevant),
            ndcg_at_k={
                k: retrieval_metrics.ndcg_at_k(retrieved_ids, ground_truth.relevance_grades, k)
                for k in self._k_values
            },
            plan_coverage=retrieval_metrics.plan_coverage(candidate_pool, relevant),
        )

    def _compute_generation_metrics(
        self, generated_text: str, ground_truth: GroundTruth | None
    ) -> GenerationMetricsResult | None:
        if ground_truth is None:
            return None

        exact_match = None
        edit_similarity = None
        if ground_truth.reference_text is not None:
            reference = ground_truth.reference_text
            exact_match = generation_metrics.exact_match(generated_text, reference)
            edit_similarity = generation_metrics.edit_similarity(generated_text, reference)

        syntactic_validity = None
        if ground_truth.language is not None:
            syntactic_validity = generation_metrics.syntactic_validity(
                generated_text, ground_truth.language
            )

        if exact_match is None and syntactic_validity is None:
            return None
        return GenerationMetricsResult(
            exact_match=exact_match,
            edit_similarity=edit_similarity,
            syntactic_validity=syntactic_validity,
        )

    def run_batch(
        self, variants: Sequence[Variant], queries: Sequence[QuerySpec]
    ) -> list[QueryRunResult]:
        """Run every `variant` against every `query`. Order: outer `queries`, inner `variants`.

        Matches `evaluation.baselines.runner.BaselineRunner`'s and this
        milestone's own fairness framing: for a given query, every
        variant runs back to back, against the identical
        `RepositoryContext`/`GroundTruth`.
        """
        results: list[QueryRunResult] = []
        for query in queries:
            for variant in variants:
                results.append(self.run_query(variant, query))
        return results


def write_results_jsonl(results: Sequence[QueryRunResult], path: Path) -> None:
    """Write `results` as JSON Lines, one `QueryRunResult` per line.

    The sole intended way a results file is produced -- per this
    milestone's "do not hand-edit result files" instruction, no other
    code path in this package writes to a results file.

    Args:
        results: The records to write, in the order given (typically
            `ExperimentRunner.run_batch`'s own output order).
        path: Destination file. Overwritten if it already exists.
    """
    with path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(result.model_dump_json())
            handle.write("\n")


def read_results_jsonl(path: Path) -> list[QueryRunResult]:
    """Read a `write_results_jsonl`-produced file back into `QueryRunResult` objects."""
    results = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                results.append(QueryRunResult.model_validate(json.loads(line)))
    return results


def write_config_json(config: ExperimentConfig, path: Path) -> None:
    """Write `config` as a single JSON object.

    Per this milestone's instruction to "store every experiment
    configuration alongside results": call this once per experiment run,
    writing to a path a human can trivially associate with the matching
    `write_results_jsonl` output (e.g. `<experiment_id>_config.json`
    next to `<experiment_id>_results.jsonl`) -- this function does not
    enforce or assume any particular naming convention itself.
    """
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def read_config_json(path: Path) -> ExperimentConfig:
    """Read a `write_config_json`-produced file back into an `ExperimentConfig`."""
    return ExperimentConfig.model_validate_json(path.read_text(encoding="utf-8"))
