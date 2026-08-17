"""Shared, immutable configuration and result contracts every baseline
(and TARA-proper, when compared against them) must use identically.

Per this milestone's COMMON GENERATION CONFIG / COMMON EVALUATION CONFIG
/ RETRIEVAL RESULT CONTRACT requirements. Neither config type is ever
constructed per-baseline: exactly one instance of each is built once, by
the caller orchestrating a comparison, and threaded through every
baseline run. See `evaluation.baselines.fairness` for the explicit
rejection of any attempt to override a field here on a per-baseline
basis.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from evaluation.baselines.definitions import BaselineId
from tara.generation.prompt import PromptTemplate
from tara.retrieval.models import RetrievedContext
from tara.routing.models import RetrievalPlan


@dataclass(frozen=True)
class GenerationConfig:
    """The generation-stage settings every baseline (and TARA-proper) must share.

    Deliberately data-only, with no live `CodeGenerator`/`PromptBuilder`
    instance: `evaluation.baselines.runner.BaselineRunner` still takes
    those as constructor-injected collaborators (matching every other
    TARA component's dependency-injection pattern). This type exists so
    the *values* those collaborators were built with are recorded once,
    explicitly, and can be asserted equal across a full baseline sweep
    -- not to replace constructor injection with a config object.
    """

    model: str
    temperature: float
    max_tokens: int
    prompt_template: PromptTemplate = PromptTemplate.BASELINE
    """Always `BASELINE` for a fair baseline comparison -- surfacing
    `TaskClassification` in the prompt (`WITH_TASK_CLASSIFICATION`) is
    ablation A9 (`EXPERIMENT_PLAN.md` §5), not part of the baseline
    fairness matrix. `BaselineRunner` independently, structurally
    enforces this by always constructing its own
    `PromptBuilder(template=PromptTemplate.BASELINE)` regardless of what
    this field says; it is recorded here for disclosure/reporting, not
    because `BaselineRunner` reads it.
    """

    def __post_init__(self) -> None:
        if self.temperature < 0:
            raise ValueError(f"temperature must be non-negative; got {self.temperature!r}.")
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive; got {self.max_tokens!r}.")
        if self.prompt_template is not PromptTemplate.BASELINE:
            raise ValueError(
                "GenerationConfig.prompt_template must be PromptTemplate.BASELINE for a fair "
                "baseline comparison; WITH_TASK_CLASSIFICATION is ablation A9, not a baseline "
                "configuration value."
            )


@dataclass(frozen=True)
class EvaluationConfig:
    """The evaluation-protocol settings every baseline (and TARA-proper) must share."""

    evaluator: str
    metrics: tuple[str, ...]
    scoring_protocol: str
    output_schema: str
    query_set_id: str
    corpus_id: str

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValueError("EvaluationConfig.metrics must name at least one metric.")
        if not self.evaluator:
            raise ValueError("EvaluationConfig.evaluator must be non-empty.")
        if not self.query_set_id:
            raise ValueError("EvaluationConfig.query_set_id must be non-empty.")
        if not self.corpus_id:
            raise ValueError("EvaluationConfig.corpus_id must be non-empty.")


@dataclass(frozen=True)
class RetrievalResultRecord:
    """A flat, evaluator-facing view of one baseline's retrieval output for one query.

    Per this milestone's RETRIEVAL RESULT CONTRACT requirement.
    Deliberately excludes the generated answer -- "Do not put generated
    answers into the retrieval result" is explicit in this milestone's
    instructions. `evaluation.baselines.runner.BaselineRunResult` is
    where a generated answer belongs, alongside (not instead of) this
    record.
    """

    baseline_id: BaselineId
    query_id: str
    retrieved_document_ids: tuple[str, ...]
    retrieval_mode: str | None
    """`RetrievalPlan.strategy.value`, or `None` for B0 (no retrieval mode at all)."""
    scores: tuple[float, ...]
    """Parallel to `retrieved_document_ids`: each chunk's normalized_score, same order."""
    ranks: tuple[int, ...]
    """Parallel to `retrieved_document_ids`: each chunk's 0-indexed rank (its position in the
    already-ranked `retrieved_document_ids` list)."""
    metadata: dict[str, object]

    def __post_init__(self) -> None:
        lengths = {len(self.retrieved_document_ids), len(self.scores), len(self.ranks)}
        if len(lengths) > 1:
            raise ValueError(
                "retrieved_document_ids, scores, and ranks must be the same length; got "
                f"{sorted(lengths)}."
            )


def build_retrieval_result_record(
    baseline_id: BaselineId,
    query_id: str,
    plan: RetrievalPlan | None,
    retrieved_contexts: Sequence[RetrievedContext],
) -> RetrievalResultRecord:
    """Flatten one baseline's raw retrieval output into a `RetrievalResultRecord`.

    Args:
        baseline_id: Which baseline produced `retrieved_contexts`.
        query_id: The query identifier this retrieval was for.
        plan: The `RetrievalPlan` that was executed, or `None` for B0.
        retrieved_contexts: One `RetrievedContext` per retriever that
            ran (`RetrievalOrchestrator.execute`'s own output), or an
            empty sequence for B0.

    Returns:
        A flat record with document ids, scores, and ranks in the same
        order every contributing `RetrievedContext.chunks` list was
        already ranked in.
    """
    document_ids: list[str] = []
    scores: list[float] = []
    for context in retrieved_contexts:
        for chunk in context.chunks:
            document_ids.append(chunk.chunk_id)
            scores.append(chunk.score.normalized_score)

    return RetrievalResultRecord(
        baseline_id=baseline_id,
        query_id=query_id,
        retrieved_document_ids=tuple(document_ids),
        retrieval_mode=plan.strategy.value if plan is not None else None,
        scores=tuple(scores),
        ranks=tuple(range(len(document_ids))),
        metadata={"retriever_count": len(retrieved_contexts)},
    )
