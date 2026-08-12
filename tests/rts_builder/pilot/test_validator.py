"""Unit tests for `evaluation.rts_builder.pilot.validator.PilotValidator`."""
from __future__ import annotations

import copy

from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.validator import PilotValidator


def _validator() -> PilotValidator:
    return PilotValidator(PilotSettings())


def test_clean_dataset_passes_every_blocking_check(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)

    assert report.passed is True
    assert report.missing_value_row_count == 0
    assert report.duplicate_row_count == 0
    assert report.duplicate_query_strategy_pair_count == 0
    assert report.queries_with_unexpected_strategy_count == 0
    assert all(check.passed for check in report.checks if check.blocking)


def test_row_count_and_query_count_are_correct(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    assert report.row_count == 24
    assert report.query_count == 6  # 2 repos x 3 queries


def test_missing_value_detection(sample_rows: list[dict[str, object]]) -> None:
    rows = copy.deepcopy(sample_rows)
    rows[0]["utility_score"] = None

    report = _validator().validate(rows)

    assert report.missing_value_row_count == 1
    check = next(c for c in report.checks if c.name == "no_missing_values")
    assert check.passed is False
    assert report.passed is False


def test_nan_value_is_also_treated_as_missing(sample_rows: list[dict[str, object]]) -> None:
    rows = copy.deepcopy(sample_rows)
    rows[0]["latency_ms"] = float("nan")

    report = _validator().validate(rows)

    assert report.missing_value_row_count == 1
    assert report.passed is False


def test_duplicate_row_detection(sample_rows: list[dict[str, object]]) -> None:
    rows = copy.deepcopy(sample_rows)
    rows.append(copy.deepcopy(rows[0]))

    report = _validator().validate(rows)

    assert report.duplicate_row_count == 1
    check = next(c for c in report.checks if c.name == "no_duplicate_rows")
    assert check.passed is False
    assert report.passed is False


def test_duplicate_query_strategy_pair_detection(sample_rows: list[dict[str, object]]) -> None:
    rows = copy.deepcopy(sample_rows)
    duplicate = copy.deepcopy(rows[0])
    duplicate["latency_ms"] = 999.0  # differs, so this is NOT an exact-duplicate-row case
    rows.append(duplicate)

    report = _validator().validate(rows)

    assert report.duplicate_row_count == 0
    assert report.duplicate_query_strategy_pair_count == 1
    check = next(c for c in report.checks if c.name == "no_duplicate_query_strategy_pairs")
    assert check.passed is False
    assert report.passed is False


def test_wrong_strategy_count_detection(sample_rows: list[dict[str, object]]) -> None:
    rows = copy.deepcopy(sample_rows)
    # Drop one strategy row from the first query -- 3 rows instead of 4.
    first_key = (rows[0]["repository_id"], rows[0]["commit_sha"], rows[0]["query_text"])
    removed = False
    filtered = []
    for row in rows:
        key = (row["repository_id"], row["commit_sha"], row["query_text"])
        if key == first_key and not removed:
            removed = True
            continue
        filtered.append(row)

    report = _validator().validate(filtered)

    assert report.queries_with_unexpected_strategy_count == 1
    check = next(c for c in report.checks if c.name == "every_query_has_expected_strategy_rows")
    assert check.passed is False
    assert report.passed is False


def test_strategy_distribution_counts_every_strategy(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    assert set(report.strategy_distribution) == {"lexical", "dense", "graph", "hybrid"}
    assert sum(report.strategy_distribution.values()) == 24
    assert all(count == 6 for count in report.strategy_distribution.values())  # 6 queries x 1 row each


def test_repository_distribution_counts_both_repositories(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    assert set(report.repository_distribution) == {"pilot-repo-0", "pilot-repo-1"}
    assert sum(report.repository_distribution.values()) == 24


def test_rank_distribution_covers_ranks_one_through_four(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    assert set(report.rank_distribution) == {"1", "2", "3", "4"}
    assert sum(report.rank_distribution.values()) == 24


def test_feature_distributions_exclude_label_and_provenance_columns(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    for excluded in ("utility_score", "latency_ms", "rank", "repository_id", "query_id", "pipeline_digest", "split"):
        assert excluded not in report.feature_distributions


def test_feature_distributions_include_known_feature_columns(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    assert "query_length" in report.feature_distributions
    assert "repo_file_count" in report.feature_distributions
    stat = report.feature_distributions["query_length"]
    assert stat.count == 24


def test_histograms_have_matching_bin_edges_and_counts(sample_rows: list[dict[str, object]]) -> None:
    report = _validator().validate(sample_rows)
    for histogram in (report.utility_histogram, report.latency_histogram, report.quality_histogram):
        assert len(histogram.bin_edges) == len(histogram.counts) + 1
        assert sum(histogram.counts) == 24


def test_empty_rows_produce_a_report_without_crashing() -> None:
    report = _validator().validate([])
    assert report.row_count == 0
    assert report.query_count == 0
    assert report.passed is True  # vacuously -- no rows to violate any check
