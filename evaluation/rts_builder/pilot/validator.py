"""Automated validation of an assembled pilot dataset: the Success Criteria, plus descriptive statistics.

Computed directly from the flat rows the pilot itself assembled
(`assembler.load_current_rows`), independently of
`StatisticsAccumulator`/`DatasetStatistics` (the frozen Dataset
Builder's own cumulative statistics) -- both read from the same
underlying data, but recomputing here rather than reusing the
accumulator means a bug in one is unlikely to be silently masked by the
other, and lets this report additionally check things Dataset Builder
was never asked to check (missing values, duplicates, exactly-four
-rows-per-query).
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict

from evaluation.rts_builder.dataset_builder.models import FeatureStatistic
from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.models import Histogram, ValidationCheck, ValidationReport

# Every non-feature column the frozen upstream schemas (or the pilot layer itself) can put on a
# flat row. Anything numeric NOT in this set is treated as a feature column for
# `feature_distributions` -- explicit exclusion, rather than prefix-guessing, so a rename or
# addition upstream fails loudly (KeyError-free but visibly wrong bucketing) rather than silently.
_NON_FEATURE_COLUMNS = frozenset(
    {
        "repository_id", "commit_sha", "query_text", "query_id", "strategy_name",
        "latency_ms", "latency_normalized", "context_token_count",
        "utility_score", "rank", "is_best_strategy", "label_confidence", "tied_with",
        "quality_recall_at_k", "quality_mrr", "quality_ndcg", "quality_context_precision", "quality_quality_score",
        "pipeline_digest", "input_digest", "metadata", "split",
    }
)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _coerce_float(value: object) -> float | None:
    """`float(value)`, or `None` if `value` is missing -- never raises.

    A missing utility_score/latency_ms/quality_quality_score is already
    surfaced by the `no_missing_values` check; averages and histograms
    silently exclude it rather than crashing the whole report over one
    bad value the caller will already see flagged elsewhere.
    """
    if _is_missing(value):
        return None
    return float(value)  # type: ignore[arg-type]


def _histogram(values: list[float], bin_count: int) -> Histogram:
    if not values:
        return Histogram(bin_edges=[0.0, 0.0], counts=[0])

    minimum, maximum = min(values), max(values)
    if math.isclose(minimum, maximum):
        return Histogram(bin_edges=[minimum, maximum], counts=[len(values)])

    width = (maximum - minimum) / bin_count
    bin_edges = [minimum + i * width for i in range(bin_count + 1)]
    counts = [0] * bin_count
    for value in values:
        index = min(int((value - minimum) / width), bin_count - 1)
        counts[index] += 1
    return Histogram(bin_edges=bin_edges, counts=counts)


def _row_key(row: dict[str, object]) -> str:
    return json.dumps(row, sort_keys=True, default=str)


class PilotValidator:
    """Runs every automated validation check over an assembled pilot dataset."""

    def __init__(self, settings: PilotSettings) -> None:
        self._settings = settings

    def validate(self, rows: list[dict[str, object]]) -> ValidationReport:
        """Compute the full `ValidationReport` for `rows` (every current, de-duplicated flat row)."""
        query_groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            query_groups[(str(row["repository_id"]), str(row["commit_sha"]), str(row["query_text"]))].append(row)

        missing_value_row_count = sum(1 for row in rows if any(_is_missing(value) for value in row.values()))

        row_keys = [_row_key(row) for row in rows]
        duplicate_row_count = sum(count - 1 for count in Counter(row_keys).values() if count > 1)

        strategy_pair_counter: Counter[tuple[str, str, str, str]] = Counter(
            (str(row["repository_id"]), str(row["commit_sha"]), str(row["query_text"]), str(row["strategy_name"]))
            for row in rows
        )
        duplicate_query_strategy_pair_count = sum(count - 1 for count in strategy_pair_counter.values() if count > 1)

        queries_with_unexpected_strategy_count = sum(
            1 for group_rows in query_groups.values() if len(group_rows) != self._settings.expected_strategy_count
        )

        strategy_distribution: Counter[str] = Counter(str(row["strategy_name"]) for row in rows)
        repository_distribution: Counter[str] = Counter(str(row["repository_id"]) for row in rows)
        rank_distribution: Counter[str] = Counter(str(row["rank"]) for row in rows)
        split_distribution: Counter[str] = Counter(str(group_rows[0]["split"]) for group_rows in query_groups.values())

        utility_values = [v for row in rows if (v := _coerce_float(row["utility_score"])) is not None]
        latency_values = [v for row in rows if (v := _coerce_float(row["latency_ms"])) is not None]
        quality_values = [v for row in rows if (v := _coerce_float(row["quality_quality_score"])) is not None]

        average_utility_overall = sum(utility_values) / len(utility_values) if utility_values else 0.0
        average_latency_overall = sum(latency_values) / len(latency_values) if latency_values else 0.0
        average_quality_overall = sum(quality_values) / len(quality_values) if quality_values else 0.0

        average_utility_by_strategy = self._mean_by_strategy(rows, "utility_score")
        average_latency_by_strategy = self._mean_by_strategy(rows, "latency_ms")
        average_quality_by_strategy = self._mean_by_strategy(rows, "quality_quality_score")

        feature_distributions = self._feature_distributions(rows)

        checks = [
            ValidationCheck(
                name="no_missing_values", blocking=True, passed=missing_value_row_count == 0,
                detail=f"{missing_value_row_count} row(s) contain a None/NaN value." if missing_value_row_count
                else "No missing values found in any column.",
            ),
            ValidationCheck(
                name="no_duplicate_rows", blocking=True, passed=duplicate_row_count == 0,
                detail=f"{duplicate_row_count} exact-duplicate row(s) found." if duplicate_row_count
                else "No exact-duplicate rows found.",
            ),
            ValidationCheck(
                name="no_duplicate_query_strategy_pairs", blocking=True, passed=duplicate_query_strategy_pair_count == 0,
                detail=f"{duplicate_query_strategy_pair_count} duplicate (repository, commit, query, strategy) pair(s) found."
                if duplicate_query_strategy_pair_count else "Every (repository, commit, query, strategy) pair is unique.",
            ),
            ValidationCheck(
                name="every_query_has_expected_strategy_rows", blocking=True,
                passed=queries_with_unexpected_strategy_count == 0,
                detail=f"{queries_with_unexpected_strategy_count} quer(ies) do not have exactly "
                f"{self._settings.expected_strategy_count} strategy rows." if queries_with_unexpected_strategy_count
                else f"Every query has exactly {self._settings.expected_strategy_count} strategy rows.",
            ),
        ]
        passed = all(check.passed for check in checks if check.blocking)

        return ValidationReport(
            row_count=len(rows),
            query_count=len(query_groups),
            checks=checks,
            passed=passed,
            missing_value_row_count=missing_value_row_count,
            duplicate_row_count=duplicate_row_count,
            duplicate_query_strategy_pair_count=duplicate_query_strategy_pair_count,
            queries_with_unexpected_strategy_count=queries_with_unexpected_strategy_count,
            strategy_distribution=dict(strategy_distribution),
            repository_distribution=dict(repository_distribution),
            rank_distribution=dict(rank_distribution),
            split_distribution=dict(split_distribution),
            average_utility_overall=average_utility_overall,
            average_utility_by_strategy=average_utility_by_strategy,
            average_latency_ms_overall=average_latency_overall,
            average_latency_ms_by_strategy=average_latency_by_strategy,
            average_quality_overall=average_quality_overall,
            average_quality_by_strategy=average_quality_by_strategy,
            utility_histogram=_histogram(utility_values, self._settings.histogram_bin_count),
            latency_histogram=_histogram(latency_values, self._settings.histogram_bin_count),
            quality_histogram=_histogram(quality_values, self._settings.histogram_bin_count),
            feature_distributions=feature_distributions,
        )

    @staticmethod
    def _mean_by_strategy(rows: list[dict[str, object]], column: str) -> dict[str, float]:
        sums: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            value = _coerce_float(row[column])
            if value is None:
                continue
            strategy = str(row["strategy_name"])
            sums[strategy] += value
            counts[strategy] += 1
        return {strategy: sums[strategy] / counts[strategy] for strategy in sums}

    @staticmethod
    def _feature_distributions(rows: list[dict[str, object]]) -> dict[str, FeatureStatistic]:
        values_by_column: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            for column, value in row.items():
                if column in _NON_FEATURE_COLUMNS:
                    continue
                if isinstance(value, (bool, int, float)) and not _is_missing(value):
                    values_by_column[column].append(float(value))
                # str-valued feature columns (e.g. repo_dominant_language) are categorical, not
                # summarizable by mean/min/max -- intentionally skipped, matching
                # StatisticsAccumulator.update's own established convention.

        return {
            column: FeatureStatistic(mean=sum(values) / len(values), minimum=min(values), maximum=max(values), count=len(values))
            for column, values in values_by_column.items()
        }
