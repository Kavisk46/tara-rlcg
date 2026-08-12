"""`OracleUtilityComputer`: the Oracle Utility subsystem's single public entry point.

Turns a `RetrievalExecutionResult` (Retrieval Executor's output --
accepted, frozen) plus a `RelevanceJudgment` (externally supplied
ground truth) into an `OracleUtilityResult`: one Learning-to-Rank-ready
row per strategy, with quality metrics, normalized latency, utility
score, rank, and label confidence. See `Oracle_Math.md` for the full
formal derivation of every computation below.
"""
from __future__ import annotations

from evaluation.rts_builder.oracle_utility import metrics
from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings
from evaluation.rts_builder.oracle_utility.exceptions import MismatchedInputsError
from evaluation.rts_builder.oracle_utility.models import (
    OracleUtilityResult,
    QualityMetrics,
    RelevanceJudgment,
    StrategyOracleRow,
)
from evaluation.rts_builder.retrieval_executor.models import (
    RetrievalExecutionResult,
    RetrievalStrategyName,
    StrategyResult,
)
from tara.core.logging import get_logger
from tara.retrieval.utils import normalize_scores

logger = get_logger(__name__)


class OracleUtilityComputer:
    """Computes Learning-to-Rank supervision labels from retrieval results and ground truth."""

    def __init__(self, settings: OracleUtilitySettings | None = None) -> None:
        """Construct the computer.

        Args:
            settings: Configuration for every quality-metric weight,
                the utility trade-off coefficients, and ranking
                tie/confidence constants. Defaults to
                `OracleUtilitySettings()` (environment defaults).
        """
        self._settings = settings or OracleUtilitySettings()

    def compute(
        self, execution_result: RetrievalExecutionResult, relevance_judgment: RelevanceJudgment
    ) -> OracleUtilityResult:
        """Compute Oracle Utility rows for every strategy in `execution_result`.

        Args:
            execution_result: `RetrievalExecutor.execute_all`'s output
                for one `(repository, commit, query)` combination.
            relevance_judgment: Ground-truth relevance grades for the
                same combination.

        Returns:
            An `OracleUtilityResult` with exactly 4 rows, sorted by
            rank ascending (best strategy first).

        Raises:
            MismatchedInputsError: If `relevance_judgment` was not
                authored for the same `(repository_id, commit_sha,
                query_text)` as `execution_result`.
        """
        self._validate_inputs_match(execution_result, relevance_judgment)

        strategy_results = execution_result.all_results()
        quality_by_strategy = {
            strategy_result.strategy_name: self._compute_quality(strategy_result, relevance_judgment)
            for strategy_result in strategy_results
        }

        raw_latency = {
            strategy_result.strategy_name.value: strategy_result.retrieval_latency_ms
            for strategy_result in strategy_results
        }
        normalized_latency = normalize_scores(raw_latency)

        utility_by_strategy: dict[RetrievalStrategyName, float] = {}
        for strategy_result in strategy_results:
            name = strategy_result.strategy_name
            quality_score = quality_by_strategy[name].quality_score
            latency_norm = normalized_latency.get(name.value, 0.0)
            utility_by_strategy[name] = (
                self._settings.utility_quality_weight * quality_score
                - self._settings.utility_latency_weight * latency_norm
            )

        ordered_results, label_confidence = self._rank_strategies(strategy_results, utility_by_strategy)

        rows = [
            self._build_row(
                execution_result, strategy_result, quality_by_strategy[strategy_result.strategy_name],
                normalized_latency, utility_by_strategy, rank, label_confidence,
            )
            for rank, strategy_result in enumerate(ordered_results, start=1)
        ]

        logger.info(
            "Computed Oracle Utility for %s@%s: best_strategy=%s utility=%.4f confidence=%.4f",
            execution_result.repository_id, execution_result.commit_sha[:8],
            rows[0].strategy_name.value, rows[0].utility_score, label_confidence,
        )
        return OracleUtilityResult(
            repository_id=execution_result.repository_id,
            commit_sha=execution_result.commit_sha,
            query_text=execution_result.query_text,
            rows=rows,
        )

    def _compute_quality(self, strategy_result: StrategyResult, judgment: RelevanceJudgment) -> QualityMetrics:
        retrieved_paths = [retrieved.file_path for retrieved in strategy_result.retrieved_files]
        relevant_paths = {path for path, grade in judgment.relevance_grades.items() if grade > 0.0}
        k = self._settings.quality_metrics_k

        recall = metrics.recall_at_k(retrieved_paths, relevant_paths, k)
        mrr = metrics.reciprocal_rank(retrieved_paths, relevant_paths)
        ndcg = metrics.ndcg_at_k(retrieved_paths, judgment.relevance_grades, k)
        precision = metrics.context_precision(retrieved_paths, relevant_paths)

        quality_score = (
            self._settings.quality_recall_weight * recall
            + self._settings.quality_mrr_weight * mrr
            + self._settings.quality_ndcg_weight * ndcg
            + self._settings.quality_context_precision_weight * precision
        )

        return QualityMetrics(
            recall_at_k=recall, mrr=mrr, ndcg=ndcg, context_precision=precision, quality_score=quality_score
        )

    def _rank_strategies(
        self, strategy_results: list[StrategyResult], utility_by_strategy: dict[RetrievalStrategyName, float]
    ) -> tuple[list[StrategyResult], float]:
        """Sort by descending utility; ties broken by ascending measured latency, then strategy name.

        Tie-break rationale: `docs/DATASET_BUILDER_SPEC.md` §9 breaks
        ties "by ascending strategy_cost_rank (the cheaper strategy
        ranks higher)," via a static priority table
        (`RETRIEVER_EXECUTION_PRIORITY`) designed for
        `tara.routing.strategy`'s 7-candidate taxonomy. Retrieval
        Executor implements 4 strategies, not 7, with no corresponding
        static table. This uses each strategy's own *measured*
        `retrieval_latency_ms` for this exact query as the cost
        signal instead -- the same underlying principle ("the cheaper
        strategy ranks higher"), realized with real, per-query cost
        data rather than a context-independent a-priori ranking. See
        `Architecture.md`'s "Design Decisions."
        """
        ordered = sorted(
            strategy_results,
            key=lambda result: (
                -utility_by_strategy[result.strategy_name],
                result.retrieval_latency_ms,
                result.strategy_name.value,
            ),
        )

        utility_1 = utility_by_strategy[ordered[0].strategy_name]
        utility_2 = utility_by_strategy[ordered[1].strategy_name] if len(ordered) > 1 else 0.0
        label_confidence = min(
            max((utility_1 - utility_2) / max(utility_1, self._settings.confidence_epsilon), 0.0), 1.0
        )
        return ordered, label_confidence

    def _build_row(
        self,
        execution_result: RetrievalExecutionResult,
        strategy_result: StrategyResult,
        quality: QualityMetrics,
        normalized_latency: dict[str, float],
        utility_by_strategy: dict[RetrievalStrategyName, float],
        rank: int,
        label_confidence: float,
    ) -> StrategyOracleRow:
        name = strategy_result.strategy_name
        utility_score = utility_by_strategy[name]
        tied_with = [
            other_name
            for other_name, other_utility in utility_by_strategy.items()
            if other_name != name and abs(other_utility - utility_score) < self._settings.tie_epsilon
        ]
        return StrategyOracleRow(
            repository_id=execution_result.repository_id,
            commit_sha=execution_result.commit_sha,
            query_text=execution_result.query_text,
            strategy_name=name,
            quality=quality,
            latency_ms=strategy_result.retrieval_latency_ms,
            latency_normalized=normalized_latency.get(name.value, 0.0),
            context_token_count=strategy_result.context_token_count,
            utility_score=utility_score,
            rank=rank,
            is_best_strategy=(rank == 1),
            label_confidence=label_confidence,
            tied_with=tied_with,
        )

    @staticmethod
    def _validate_inputs_match(
        execution_result: RetrievalExecutionResult, relevance_judgment: RelevanceJudgment
    ) -> None:
        if (
            execution_result.repository_id != relevance_judgment.repository_id
            or execution_result.commit_sha != relevance_judgment.commit_sha
            or execution_result.query_text != relevance_judgment.query_text
        ):
            raise MismatchedInputsError(
                f"relevance_judgment ({relevance_judgment.repository_id!r}@"
                f"{relevance_judgment.commit_sha!r}, query={relevance_judgment.query_text!r}) was not "
                f"authored for execution_result ({execution_result.repository_id!r}@"
                f"{execution_result.commit_sha!r}, query={execution_result.query_text!r})."
            )
