"""Unit tests for `evaluation.statistics.metrics_registry`."""
from __future__ import annotations

import pytest

from evaluation.statistics.metrics_registry import (
    EDIT_SIMILARITY,
    EXACT_MATCH,
    PLAN_COVERAGE,
    RECIPROCAL_RANK,
    RETRIEVED_TOKEN_COUNT,
    SYNTACTIC_VALIDITY,
    TOTAL_LATENCY_MS,
    ndcg_at_k_spec,
    precision_at_k_spec,
    recall_at_k_spec,
    select_paired_test_name,
)
from evaluation.statistics.tests.conftest import make_result

# ============================================================================
# select_paired_test_name: the "don't cherry-pick a test" guarantee
# ============================================================================


def test_select_paired_test_name_continuous_is_wilcoxon() -> None:
    assert select_paired_test_name("continuous") == "wilcoxon_signed_rank"


def test_select_paired_test_name_binary_is_mcnemar() -> None:
    assert select_paired_test_name("binary") == "mcnemar"


def test_select_paired_test_name_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown metric kind"):
        select_paired_test_name("ordinal")  # type: ignore[arg-type]


def test_every_standard_metric_kind_maps_to_a_valid_test_name() -> None:
    for metric in (
        precision_at_k_spec(5),
        recall_at_k_spec(5),
        ndcg_at_k_spec(5),
        RECIPROCAL_RANK,
        PLAN_COVERAGE,
        EXACT_MATCH,
        EDIT_SIMILARITY,
        SYNTACTIC_VALIDITY,
        TOTAL_LATENCY_MS,
        RETRIEVED_TOKEN_COUNT,
    ):
        assert select_paired_test_name(metric.kind) in ("wilcoxon_signed_rank", "mcnemar")


def test_binary_metrics_are_exactly_exact_match_and_syntactic_validity() -> None:
    assert EXACT_MATCH.kind == "binary"
    assert SYNTACTIC_VALIDITY.kind == "binary"
    for metric in (
        precision_at_k_spec(5),
        recall_at_k_spec(5),
        ndcg_at_k_spec(5),
        RECIPROCAL_RANK,
        PLAN_COVERAGE,
        EDIT_SIMILARITY,
        TOTAL_LATENCY_MS,
        RETRIEVED_TOKEN_COUNT,
    ):
        assert metric.kind == "continuous"


# ============================================================================
# Extractors
# ============================================================================


def test_precision_at_k_extractor_reads_the_right_k() -> None:
    result = make_result(precision_at_5=0.8)
    assert precision_at_k_spec(5).extractor(result) == 0.8
    assert precision_at_k_spec(10).extractor(result) is None


def test_recall_at_k_extractor() -> None:
    result = make_result(recall_at_5=0.6)
    assert recall_at_k_spec(5).extractor(result) == 0.6


def test_reciprocal_rank_extractor() -> None:
    result = make_result(reciprocal_rank=0.5)
    assert RECIPROCAL_RANK.extractor(result) == 0.5


def test_plan_coverage_extractor() -> None:
    result = make_result(plan_coverage=1.0)
    assert PLAN_COVERAGE.extractor(result) == 1.0


def test_exact_match_extractor() -> None:
    result = make_result(exact_match=True)
    assert EXACT_MATCH.extractor(result) is True


def test_edit_similarity_extractor() -> None:
    result = make_result(edit_similarity=0.75)
    assert EDIT_SIMILARITY.extractor(result) == 0.75


def test_syntactic_validity_extractor() -> None:
    result = make_result(syntactic_validity=False)
    assert SYNTACTIC_VALIDITY.extractor(result) is False


def test_total_latency_ms_extractor() -> None:
    result = make_result(total_latency_ms=123.0)
    assert TOTAL_LATENCY_MS.extractor(result) == 123.0


def test_retrieved_token_count_extractor() -> None:
    result = make_result()
    assert RETRIEVED_TOKEN_COUNT.extractor(result) == 100.0


def test_extractors_return_none_when_retrieval_metrics_missing() -> None:
    result = make_result()  # no retrieval metrics supplied
    assert precision_at_k_spec(5).extractor(result) is None
    assert RECIPROCAL_RANK.extractor(result) is None
    assert PLAN_COVERAGE.extractor(result) is None


def test_extractors_return_none_when_generation_metrics_missing() -> None:
    result = make_result()  # no generation metrics supplied
    assert EXACT_MATCH.extractor(result) is None
    assert EDIT_SIMILARITY.extractor(result) is None
    assert SYNTACTIC_VALIDITY.extractor(result) is None


def test_all_extractors_return_none_for_an_errored_result() -> None:
    result = make_result(
        precision_at_5=0.8,
        reciprocal_rank=0.5,
        exact_match=True,
        edit_similarity=1.0,
        error="boom",
    )
    assert precision_at_k_spec(5).extractor(result) is None
    assert RECIPROCAL_RANK.extractor(result) is None
    assert EXACT_MATCH.extractor(result) is None
    assert EDIT_SIMILARITY.extractor(result) is None
    assert TOTAL_LATENCY_MS.extractor(result) is None
