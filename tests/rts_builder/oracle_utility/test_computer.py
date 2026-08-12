"""Unit and integration tests for `evaluation.rts_builder.oracle_utility.computer.OracleUtilityComputer`."""
from __future__ import annotations

import json

import pytest

from evaluation.rts_builder.oracle_utility.computer import OracleUtilityComputer
from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings
from evaluation.rts_builder.oracle_utility.exceptions import MismatchedInputsError
from evaluation.rts_builder.oracle_utility.models import OracleUtilityResult, RelevanceJudgment
from evaluation.rts_builder.retrieval_executor.models import RetrievalExecutionResult, RetrievalStrategyName
from tara.retrieval.utils import normalize_scores

from .conftest import make_execution_result, make_strategy_result


def _judgment_for(execution_result: RetrievalExecutionResult, relevance_grades: dict[str, float]) -> RelevanceJudgment:
    return RelevanceJudgment(
        repository_id=execution_result.repository_id,
        commit_sha=execution_result.commit_sha,
        query_text=execution_result.query_text,
        relevance_grades=relevance_grades,
    )


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_compute_returns_four_rows_sorted_by_rank_ascending(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0})
    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    assert isinstance(result, OracleUtilityResult)
    assert len(result.rows) == 4
    assert [row.rank for row in result.rows] == [1, 2, 3, 4]
    assert {row.strategy_name for row in result.rows} == set(RetrievalStrategyName)
    assert result.rows[0].is_best_strategy is True
    assert all(not row.is_best_strategy for row in result.rows[1:])


def test_quality_score_is_one_when_a_strategy_retrieves_exactly_the_relevant_set(
    oracle_settings: OracleUtilitySettings,
) -> None:
    execution_result = make_execution_result(
        lexical_files={"app.py": 5.0},
        dense_files={"other.py": 1.0},
        graph_files={"other.py": 1.0},
        hybrid_files={"other.py": 1.0},
    )
    judgment = _judgment_for(execution_result, {"app.py": 1.0})

    result = OracleUtilityComputer(settings=oracle_settings).compute(execution_result, judgment)

    lexical_row = next(row for row in result.rows if row.strategy_name is RetrievalStrategyName.LEXICAL)
    assert lexical_row.quality.recall_at_k == 1.0
    assert lexical_row.quality.mrr == 1.0
    assert lexical_row.quality.ndcg == 1.0
    assert lexical_row.quality.context_precision == 1.0
    assert lexical_row.quality.quality_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Utility formula and latency normalization
# ---------------------------------------------------------------------------


def test_utility_score_matches_the_alpha_quality_minus_beta_latency_formula(
    basic_execution_result: RetrievalExecutionResult,
) -> None:
    settings = OracleUtilitySettings(utility_quality_weight=2.0, utility_latency_weight=0.5)
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0, "pkg/base.py": 1.0})

    result = OracleUtilityComputer(settings=settings).compute(basic_execution_result, judgment)

    for row in result.rows:
        expected = settings.utility_quality_weight * row.quality.quality_score - settings.utility_latency_weight * row.latency_normalized
        assert row.utility_score == pytest.approx(expected)


def test_latency_normalized_matches_cross_strategy_min_max_normalization(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0})
    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    raw_latency = {row.strategy_name.value: row.latency_ms for row in result.rows}
    expected_normalized = normalize_scores(raw_latency)

    for row in result.rows:
        assert row.latency_normalized == pytest.approx(expected_normalized[row.strategy_name.value])


def test_disabling_the_latency_penalty_ranks_purely_by_quality(basic_execution_result: RetrievalExecutionResult) -> None:
    settings = OracleUtilitySettings(utility_latency_weight=0.0)
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0, "pkg/base.py": 1.0})

    result = OracleUtilityComputer(settings=settings).compute(basic_execution_result, judgment)

    for row in result.rows:
        assert row.utility_score == pytest.approx(row.quality.quality_score)


# ---------------------------------------------------------------------------
# Ranking, ties, confidence
# ---------------------------------------------------------------------------


def test_rank_strategies_breaks_an_exact_utility_tie_by_ascending_latency() -> None:
    # Under cross-strategy min-max normalization, two strategies can only reach an *exact*
    # utility tie with *differing* raw latencies through a coincidental (quality, latency)
    # offset -- not something worth reverse-engineering through the public formula. Exercising
    # `_rank_strategies` directly with a hand-constructed tie isolates the tie-break rule itself
    # (docs/DATASET_BUILDER_SPEC.md §9: "the cheaper strategy ranks higher") from the arithmetic
    # that produces `utility_by_strategy` in the first place.
    strategy_results = [
        make_strategy_result(RetrievalStrategyName.LEXICAL, {}, latency_ms=5.0),
        make_strategy_result(RetrievalStrategyName.GRAPH, {}, latency_ms=1.0),
        make_strategy_result(RetrievalStrategyName.DENSE, {}, latency_ms=9.0),
        make_strategy_result(RetrievalStrategyName.HYBRID, {}, latency_ms=9.0),
    ]
    utility_by_strategy = {
        RetrievalStrategyName.LEXICAL: 0.5,
        RetrievalStrategyName.GRAPH: 0.5,  # exact tie with LEXICAL, despite latency_ms=1.0 vs 5.0
        RetrievalStrategyName.DENSE: 0.1,
        RetrievalStrategyName.HYBRID: 0.1,  # exact tie with DENSE, at equal latency too
    }

    ordered, _ = OracleUtilityComputer()._rank_strategies(strategy_results, utility_by_strategy)  # noqa: SLF001

    assert ordered[0].strategy_name is RetrievalStrategyName.GRAPH  # cheaper of the two 0.5-utility strategies
    assert ordered[1].strategy_name is RetrievalStrategyName.LEXICAL
    # DENSE and HYBRID are tied on both utility (0.1) and latency (9.0) -- final tie-break is strategy name.
    assert ordered[2].strategy_name is RetrievalStrategyName.DENSE
    assert ordered[3].strategy_name is RetrievalStrategyName.HYBRID


def test_tied_with_detects_near_ties_within_epsilon(basic_execution_result: RetrievalExecutionResult) -> None:
    settings = OracleUtilitySettings(tie_epsilon=1.0)  # very generous -- everything should tie
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0})

    result = OracleUtilityComputer(settings=settings).compute(basic_execution_result, judgment)

    for row in result.rows:
        other_names = {other.strategy_name for other in result.rows if other.strategy_name != row.strategy_name}
        assert set(row.tied_with) == other_names


def test_tied_with_is_empty_when_epsilon_is_zero_and_scores_differ(basic_execution_result: RetrievalExecutionResult) -> None:
    settings = OracleUtilitySettings(tie_epsilon=0.0)
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0, "pkg/base.py": 1.0})

    result = OracleUtilityComputer(settings=settings).compute(basic_execution_result, judgment)

    # With tie_epsilon=0.0, only exactly-equal utility scores would tie; this scenario's four
    # strategies retrieve different file sets with different latencies, so no exact ties are expected.
    assert all(row.tied_with == [] for row in result.rows)


def test_label_confidence_matches_the_top1_top2_margin_formula(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0, "pkg/base.py": 1.0})
    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    utility_1 = result.rows[0].utility_score
    utility_2 = result.rows[1].utility_score
    expected = min(max((utility_1 - utility_2) / max(utility_1, oracle_settings.confidence_epsilon), 0.0), 1.0)

    assert result.rows[0].label_confidence == pytest.approx(expected)


def test_label_confidence_is_identical_across_all_four_rows(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0})
    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    confidences = {row.label_confidence for row in result.rows}
    assert len(confidences) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_relevance_judgment_degrades_all_quality_to_zero_and_ranks_by_latency(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {})

    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    assert all(row.quality.quality_score == 0.0 for row in result.rows)
    # With no quality signal, the fastest strategy (lowest latency_normalized) wins.
    assert result.rows[0].strategy_name is RetrievalStrategyName.HYBRID  # latency=0.1, the fastest in basic_execution_result


def test_strategy_with_empty_retrieved_files_gets_zero_quality(oracle_settings: OracleUtilitySettings) -> None:
    execution_result = make_execution_result(lexical_files={}, dense_files={"app.py": 1.0}, graph_files={}, hybrid_files={})
    judgment = _judgment_for(execution_result, {"app.py": 1.0})

    result = OracleUtilityComputer(settings=oracle_settings).compute(execution_result, judgment)

    lexical_row = next(row for row in result.rows if row.strategy_name is RetrievalStrategyName.LEXICAL)
    assert lexical_row.quality.recall_at_k == 0.0
    assert lexical_row.quality.mrr == 0.0
    assert lexical_row.quality.context_precision == 0.0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_mismatched_repository_id_raises(basic_execution_result: RetrievalExecutionResult) -> None:
    judgment = RelevanceJudgment(
        repository_id="a-different-repo",
        commit_sha=basic_execution_result.commit_sha,
        query_text=basic_execution_result.query_text,
        relevance_grades={"app.py": 1.0},
    )
    with pytest.raises(MismatchedInputsError):
        OracleUtilityComputer().compute(basic_execution_result, judgment)


def test_mismatched_commit_sha_raises(basic_execution_result: RetrievalExecutionResult) -> None:
    judgment = RelevanceJudgment(
        repository_id=basic_execution_result.repository_id,
        commit_sha="b" * 40,
        query_text=basic_execution_result.query_text,
        relevance_grades={"app.py": 1.0},
    )
    with pytest.raises(MismatchedInputsError):
        OracleUtilityComputer().compute(basic_execution_result, judgment)


def test_mismatched_query_text_raises(basic_execution_result: RetrievalExecutionResult) -> None:
    judgment = RelevanceJudgment(
        repository_id=basic_execution_result.repository_id,
        commit_sha=basic_execution_result.commit_sha,
        query_text="a completely different query",
        relevance_grades={"app.py": 1.0},
    )
    with pytest.raises(MismatchedInputsError):
        OracleUtilityComputer().compute(basic_execution_result, judgment)


# ---------------------------------------------------------------------------
# Determinism, serialization, LTR output
# ---------------------------------------------------------------------------


def test_compute_is_deterministic_across_repeated_calls(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0, "pkg/base.py": 1.0})
    computer = OracleUtilityComputer(settings=oracle_settings)

    first = computer.compute(basic_execution_result, judgment)
    second = computer.compute(basic_execution_result, judgment)

    assert [row.model_dump(exclude={"computed_at"}) for row in first.rows] == [
        row.model_dump(exclude={"computed_at"}) for row in second.rows
    ]


def test_result_json_round_trip(oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0})
    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    payload = result.model_dump_json()
    reloaded = OracleUtilityResult.model_validate(json.loads(payload))

    assert reloaded.rows == result.rows


def test_to_long_format_rows_produces_flat_scalar_only_dicts(
    oracle_settings: OracleUtilitySettings, basic_execution_result: RetrievalExecutionResult
) -> None:
    judgment = _judgment_for(basic_execution_result, {"app.py": 1.0})
    result = OracleUtilityComputer(settings=oracle_settings).compute(basic_execution_result, judgment)

    flat_rows = result.to_long_format_rows()

    assert len(flat_rows) == 4
    expected_keys = {
        "repository_id", "commit_sha", "query_text", "strategy_name", "latency_ms", "latency_normalized",
        "context_token_count", "utility_score", "rank", "is_best_strategy", "label_confidence", "tied_with",
        "quality_recall_at_k", "quality_mrr", "quality_ndcg", "quality_context_precision", "quality_quality_score",
    }
    for row in flat_rows:
        assert set(row.keys()) == expected_keys
        assert all(isinstance(value, (int, float, bool, str)) for value in row.values())


# ---------------------------------------------------------------------------
# Real pipeline integration
# ---------------------------------------------------------------------------


def test_real_pipeline_end_to_end(oracle_settings: OracleUtilitySettings, real_execution_result: RetrievalExecutionResult) -> None:
    judgment = RelevanceJudgment(
        repository_id=real_execution_result.repository_id,
        commit_sha=real_execution_result.commit_sha,
        query_text=real_execution_result.query_text,
        relevance_grades={"app.py": 2.0, "pkg/base.py": 1.0},
    )

    result = OracleUtilityComputer(settings=oracle_settings).compute(real_execution_result, judgment)

    assert len(result.rows) == 4
    assert result.rows[0].rank == 1
    assert all(0.0 <= row.utility_score or row.utility_score < 0.0 for row in result.rows)  # utility is defined, not NaN
    assert all(row.label_confidence == result.rows[0].label_confidence for row in result.rows)
