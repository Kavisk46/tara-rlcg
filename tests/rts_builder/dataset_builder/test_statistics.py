"""Unit tests for `evaluation.rts_builder.dataset_builder.statistics.StatisticsAccumulator`."""
from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.rts_builder.dataset_builder.statistics import StatisticsAccumulator
from evaluation.rts_builder.feature_extraction.models import (
    FeatureVector,
    GraphFeatures,
    QueryFeatures,
    RepositoryFeatures,
    ResourceFeatures,
    RepositorySizeCategory,
    StructuralFeatures,
)
from evaluation.rts_builder.oracle_utility.models import OracleUtilityResult, QualityMetrics, StrategyOracleRow
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName
from tara.core.types import Language


def _make_feature_vector(repository_id: str, query_text: str, query_length: int = 10) -> FeatureVector:
    return FeatureVector(
        repository_id=repository_id,
        commit_sha="a" * 40,
        query_text=query_text,
        query=QueryFeatures(
            length=query_length, identifier_count=0, api_token_count=0, has_question_keyword=False,
            has_bug_keyword=False, has_test_keyword=False, has_refactor_keyword=False, complexity=0.1,
        ),
        repository=RepositoryFeatures(
            file_count=1, function_count=1, class_count=0, module_count=1, avg_file_size_bytes=100.0,
            dominant_language=Language.PYTHON,
        ),
        graph=GraphFeatures(import_density=0.0, call_density=0.0, inheritance_density=0.0, connected_components=1, avg_degree=0.0),
        structural=StructuralFeatures(avg_functions_per_file=1.0, avg_classes_per_file=0.0, docstring_coverage_ratio=0.0, comment_coverage_ratio=0.0),
        resource=ResourceFeatures(estimated_repository_tokens=25, repository_size_category=RepositorySizeCategory.SMALL),
    )


def _make_oracle_result(repository_id: str, query_text: str, utilities: dict[RetrievalStrategyName, float]) -> OracleUtilityResult:
    ordered = sorted(utilities.items(), key=lambda pair: -pair[1])
    rows = [
        StrategyOracleRow(
            repository_id=repository_id, commit_sha="a" * 40, query_text=query_text, strategy_name=name,
            quality=QualityMetrics(recall_at_k=0.5, mrr=0.5, ndcg=0.5, context_precision=0.5, quality_score=0.5),
            latency_ms=1.0, latency_normalized=0.5, context_token_count=10,
            utility_score=utility, rank=rank, is_best_strategy=(rank == 1), label_confidence=0.5, tied_with=[],
        )
        for rank, (name, utility) in enumerate(ordered, start=1)
    ]
    return OracleUtilityResult(repository_id=repository_id, commit_sha="a" * 40, query_text=query_text, rows=rows)


_EQUAL_UTILITIES = {
    RetrievalStrategyName.LEXICAL: 0.9,
    RetrievalStrategyName.DENSE: 0.1,
    RetrievalStrategyName.GRAPH: 0.2,
    RetrievalStrategyName.HYBRID: 0.3,
}


def test_empty_accumulator_produces_zeroed_statistics() -> None:
    statistics = StatisticsAccumulator().build_statistics()
    assert statistics.repository_count == 0
    assert statistics.query_count == 0
    assert statistics.row_count == 0
    assert statistics.average_utility_overall == 0.0


def test_update_increments_counts_correctly() -> None:
    accumulator = StatisticsAccumulator()
    accumulator.update(_make_feature_vector("r1", "q1"), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))
    accumulator.update(_make_feature_vector("r1", "q2"), _make_oracle_result("r1", "q2", _EQUAL_UTILITIES))

    statistics = accumulator.build_statistics()
    assert statistics.repository_count == 1
    assert statistics.repository_ids == ["r1"]
    assert statistics.query_count == 2
    assert statistics.row_count == 8


def test_best_strategy_distribution_counts_rank_one_only() -> None:
    accumulator = StatisticsAccumulator()
    accumulator.update(_make_feature_vector("r1", "q1"), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))

    statistics = accumulator.build_statistics()
    assert statistics.best_strategy_distribution == {"lexical": 1}


def test_average_utility_by_strategy_matches_input() -> None:
    accumulator = StatisticsAccumulator()
    accumulator.update(_make_feature_vector("r1", "q1"), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))

    statistics = accumulator.build_statistics()
    assert statistics.average_utility_by_strategy["lexical"] == pytest.approx(0.9)
    assert statistics.average_utility_by_strategy["dense"] == pytest.approx(0.1)


def test_feature_statistics_track_mean_min_max() -> None:
    accumulator = StatisticsAccumulator()
    accumulator.update(_make_feature_vector("r1", "q1", query_length=10), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))
    accumulator.update(_make_feature_vector("r1", "q2", query_length=20), _make_oracle_result("r1", "q2", _EQUAL_UTILITIES))

    statistics = accumulator.build_statistics()
    length_stat = statistics.feature_statistics["query_length"]
    assert length_stat.mean == pytest.approx(15.0)
    assert length_stat.minimum == 10.0
    assert length_stat.maximum == 20.0
    assert length_stat.count == 2


def test_categorical_features_are_excluded_from_feature_statistics() -> None:
    accumulator = StatisticsAccumulator()
    accumulator.update(_make_feature_vector("r1", "q1"), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))

    statistics = accumulator.build_statistics()
    assert "repo_dominant_language" not in statistics.feature_statistics
    assert "resource_repository_size_category" not in statistics.feature_statistics


# ---------------------------------------------------------------------------
# Cumulative reseeding (the multi-session resume case)
# ---------------------------------------------------------------------------


def test_reseeding_from_prior_statistics_produces_exact_cumulative_results() -> None:
    # Ground truth: process everything in one pass.
    single_pass = StatisticsAccumulator()
    single_pass.update(_make_feature_vector("r1", "q1", query_length=10), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))
    single_pass.update(_make_feature_vector("r1", "q2", query_length=30), _make_oracle_result("r1", "q2", _EQUAL_UTILITIES))
    expected = single_pass.build_statistics()

    # Split across two sessions, the second reseeded from the first's output.
    session_one = StatisticsAccumulator()
    session_one.update(_make_feature_vector("r1", "q1", query_length=10), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))
    intermediate = session_one.build_statistics()

    session_two = StatisticsAccumulator(seed=intermediate)
    session_two.update(_make_feature_vector("r1", "q2", query_length=30), _make_oracle_result("r1", "q2", _EQUAL_UTILITIES))
    actual = session_two.build_statistics()

    assert actual.query_count == expected.query_count
    assert actual.row_count == expected.row_count
    assert actual.repository_count == expected.repository_count
    assert actual.average_utility_overall == pytest.approx(expected.average_utility_overall)
    assert actual.average_utility_by_strategy == pytest.approx(expected.average_utility_by_strategy)
    assert actual.feature_statistics["query_length"].mean == pytest.approx(expected.feature_statistics["query_length"].mean)
    assert actual.feature_statistics["query_length"].minimum == expected.feature_statistics["query_length"].minimum
    assert actual.feature_statistics["query_length"].maximum == expected.feature_statistics["query_length"].maximum


def test_reseeding_does_not_double_count_a_repository_seen_in_both_sessions() -> None:
    session_one = StatisticsAccumulator()
    session_one.update(_make_feature_vector("r1", "q1"), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))
    intermediate = session_one.build_statistics()

    session_two = StatisticsAccumulator(seed=intermediate)
    session_two.update(_make_feature_vector("r1", "q2"), _make_oracle_result("r1", "q2", _EQUAL_UTILITIES))  # same repository r1 again
    statistics = session_two.build_statistics()

    assert statistics.repository_count == 1
    assert statistics.repository_ids == ["r1"]


def test_from_existing_returns_none_when_no_file_exists(tmp_path: Path) -> None:
    assert StatisticsAccumulator.from_existing(tmp_path / "does_not_exist.json") is None


def test_from_existing_round_trips_a_written_statistics_file(tmp_path: Path) -> None:
    accumulator = StatisticsAccumulator()
    accumulator.update(_make_feature_vector("r1", "q1"), _make_oracle_result("r1", "q1", _EQUAL_UTILITIES))
    statistics = accumulator.build_statistics()

    path = tmp_path / "dataset_statistics.json"
    path.write_text(statistics.model_dump_json(), encoding="utf-8")

    reloaded = StatisticsAccumulator.from_existing(path)
    assert reloaded == statistics
