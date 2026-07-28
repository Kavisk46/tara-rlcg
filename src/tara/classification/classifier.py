"""Task Classifier: the third stage of the TARA pipeline.

`HeuristicTaskClassifier` is the reference implementation of
`tara.interfaces.task_classifier.TaskClassifier`. It orchestrates two
injected collaborators -- a `FeatureExtractor` and a `RuleEngine` -- and
is the only place their outputs are combined into one
`TaskClassification`. Classification is fully deterministic (no
randomness, no ML model, no network call) and cheap: every pattern is
compiled once at import time (see `heuristics.py`), and a query is
tokenized exactly once per `classify()` call.
"""
from __future__ import annotations

import time
from collections import defaultdict

from tara.classification.features import FeatureExtractor
from tara.classification.models import TaskClassification
from tara.classification.rules import RuleEngine, RuleVote
from tara.core.exceptions import TaskClassificationError
from tara.core.logging import get_logger
from tara.core.types import RetrievalStrategy, TaskType
from tara.interfaces.task_classifier import TaskClassifier

logger = get_logger(__name__)

_FALLBACK_SYMBOL_CONFIDENCE = 0.3

# Tie-break order when two or more task types accumulate exactly equal
# vote weight, most specific/actionable first. This only ever matters
# when rules disagree with equal strength; it never overrides a rule
# set that already has a clear winner.
_TASK_TYPE_PRIORITY: tuple[TaskType, ...] = (
    TaskType.BUG_FIX,
    TaskType.DEBUG,
    TaskType.SECURITY,
    TaskType.PERFORMANCE,
    TaskType.TEST,
    TaskType.REFACTOR,
    TaskType.DOCUMENTATION,
    TaskType.DEPENDENCY_ANALYSIS,
    TaskType.ARCHITECTURE,
    TaskType.GENERATE,
    TaskType.EXPLAIN,
    TaskType.SEARCH,
    TaskType.UNKNOWN,
)


class HeuristicTaskClassifier(TaskClassifier):
    """Deterministic, rule-based `TaskClassifier`.

    Every collaborator is injected through the constructor rather than
    instantiated internally, so a caller can supply a customized
    `RuleEngine` (e.g. with domain-specific rules appended or swapped
    in) or a `FeatureExtractor` subclass without changing this class.
    This class itself contains no feature-extraction or rule logic --
    it only calls its collaborators and combines their outputs.
    """

    def __init__(
        self,
        feature_extractor: FeatureExtractor | None = None,
        rule_engine: RuleEngine | None = None,
    ) -> None:
        """Construct the classifier.

        Args:
            feature_extractor: Turns a raw query into `QueryFeatures`.
                Defaults to a plain `FeatureExtractor()`.
            rule_engine: Evaluates rules against `QueryFeatures`.
                Defaults to a `RuleEngine()` built on `DEFAULT_RULES`.
        """
        self._feature_extractor = feature_extractor or FeatureExtractor()
        self._rule_engine = rule_engine or RuleEngine()

    def classify(self, query: str) -> TaskClassification:
        """See `TaskClassifier.classify`."""
        start = time.perf_counter()
        try:
            features = self._feature_extractor.extract(query)
            votes = self._rule_engine.evaluate(features)
        except TaskClassificationError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize unexpected failures at the orchestration boundary
            raise TaskClassificationError(f"Failed to classify query: {exc}") from exc

        logger.debug(
            "Extracted features for %r: tokens=%d symbols=%s file_paths=%s language_hint=%s",
            query, len(features.tokens), features.detected_symbols, features.detected_file_paths,
            features.language_hint,
        )

        task_type, confidence = self._combine_task_type(votes)
        graph_required = any(vote.graph_required for vote in votes)
        semantic_required = any(vote.semantic_required for vote in votes)
        lexical_required = any(vote.lexical_required for vote in votes)
        reasoning_required = any(vote.reasoning_required for vote in votes)

        if not votes and features.detected_symbols:
            task_type = TaskType.SEARCH
            lexical_required = True
            confidence = max(confidence, _FALLBACK_SYMBOL_CONFIDENCE)

        retriever_kind = self._select_retriever(graph_required, semantic_required, lexical_required)
        fired_rule_names = [vote.rule_name for vote in votes]

        classification = TaskClassification(
            task_type=task_type,
            retriever_kind=retriever_kind,
            confidence=confidence,
            graph_required=graph_required,
            semantic_required=semantic_required,
            lexical_required=lexical_required,
            reasoning_required=reasoning_required,
            extracted_keywords=list(features.extracted_keywords),
            detected_symbols=list(features.detected_symbols),
            detected_file_paths=list(features.detected_file_paths),
            language_hint=features.language_hint,
            metadata={"fired_rules": fired_rule_names, "token_count": len(features.tokens)},
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Classified query %r -> task_type=%s retriever_kind=%s confidence=%.2f "
            "(fired_rules=%s, %.3fms)",
            query, task_type.value, retriever_kind.value, confidence, fired_rule_names, elapsed_ms,
        )
        return classification

    @staticmethod
    def _combine_task_type(votes: list[RuleVote]) -> tuple[TaskType, float]:
        """Aggregate every rule's `task_type` vote into a single type and a confidence score.

        Confidence is the winning type's share of total vote weight
        across every task type that received a vote: full agreement
        (every voting rule picks the same type) yields 1.0, while a
        query pulling in several different directions yields a lower
        score reflecting that disagreement. A query with no task_type
        votes at all classifies as `TaskType.UNKNOWN` with confidence 0.0.
        """
        weights: dict[TaskType, float] = defaultdict(float)
        for vote in votes:
            if vote.task_type is not None:
                weights[vote.task_type] += vote.weight

        if not weights:
            return TaskType.UNKNOWN, 0.0

        total = sum(weights.values())
        best_weight = max(weights.values())
        tied_candidates = [task_type for task_type, weight in weights.items() if weight == best_weight]
        winner = min(tied_candidates, key=_TASK_TYPE_PRIORITY.index)
        confidence = min(1.0, max(0.0, weights[winner] / total))
        return winner, confidence

    @staticmethod
    def _select_retriever(graph_required: bool, semantic_required: bool, lexical_required: bool) -> RetrievalStrategy:
        """Derive the recommended `RetrievalStrategy` from the three requirement flags.

        HYBRID whenever two or more of graph/semantic/lexical are
        required; otherwise the single required strategy; SEMANTIC is
        the fallback default for underspecified queries where no rule
        asserted a specific requirement, since embedding-based search is
        the most broadly useful default retrieval mode.
        """
        active = [
            strategy
            for strategy, required in (
                (RetrievalStrategy.GRAPH, graph_required),
                (RetrievalStrategy.SEMANTIC, semantic_required),
                (RetrievalStrategy.LEXICAL, lexical_required),
            )
            if required
        ]
        if len(active) >= 2:
            return RetrievalStrategy.HYBRID
        if len(active) == 1:
            return active[0]
        return RetrievalStrategy.SEMANTIC
