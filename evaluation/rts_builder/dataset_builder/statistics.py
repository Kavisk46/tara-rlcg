"""Streaming, cumulative computation of `DatasetStatistics` -- O(1) memory in the number of rows processed.

`StatisticsAccumulator.update` is called once per query (not once per
row), immediately after that query's `OracleUtilityResult` is computed,
so the full dataset never needs to be held in memory or re-read from
disk to produce statistics for *this run* -- consistent with
"Streaming writes" applied to statistics as well as export.

Critically, this accumulator can also be *seeded* from a previously
-written `DatasetStatistics` (`from_existing`), so a resumed,
multi-session dataset build's final statistics are cumulative across
every session that has ever contributed to the same output directory,
not just whatever queries happened to be newly processed in the most
recent run -- exactly the case checkpoint/resume support exists for.
Reseeding is exact, not approximate: every mean this module tracks is
reconstructible losslessly from `(mean, count)` via `sum = mean * count`,
so folding old and new data together never drifts from what a single
-pass computation over the complete, cumulative dataset would produce.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from evaluation.rts_builder.dataset_builder.models import DatasetStatistics, FeatureStatistic
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.oracle_utility.models import OracleUtilityResult


class _RunningMean:
    """A running sum/count pair, optionally seeded from a previously-known mean and count."""

    def __init__(self, seed_mean: float = 0.0, seed_count: int = 0) -> None:
        self._sum = seed_mean * seed_count
        self._count = seed_count

    def add(self, value: float) -> None:
        self._sum += value
        self._count += 1

    @property
    def mean(self) -> float:
        return self._sum / self._count if self._count else 0.0

    @property
    def count(self) -> int:
        return self._count


class _RunningStatistic(_RunningMean):
    """A running mean plus running min/max, optionally seeded from a previous `FeatureStatistic`."""

    def __init__(self, seed: FeatureStatistic | None = None) -> None:
        super().__init__(seed.mean, seed.count) if seed else super().__init__()
        self._minimum: float | None = seed.minimum if seed else None
        self._maximum: float | None = seed.maximum if seed else None

    def add(self, value: float) -> None:
        super().add(value)
        self._minimum = value if self._minimum is None else min(self._minimum, value)
        self._maximum = value if self._maximum is None else max(self._maximum, value)

    def to_feature_statistic(self) -> FeatureStatistic:
        return FeatureStatistic(mean=self.mean, minimum=self._minimum or 0.0, maximum=self._maximum or 0.0, count=self.count)


class StatisticsAccumulator:
    """Accumulates `DatasetStatistics` incrementally, one query at a time, optionally starting from prior data."""

    def __init__(self, seed: DatasetStatistics | None = None) -> None:
        """Construct an accumulator, optionally pre-populated from a prior run's `DatasetStatistics`.

        Args:
            seed: A previously-written `DatasetStatistics` to fold new
                data on top of (see `from_existing`), or `None` to
                start empty.
        """
        self._repository_ids: set[str] = set(seed.repository_ids) if seed else set()
        self._query_count = seed.query_count if seed else 0
        self._row_count = seed.row_count if seed else 0
        self._best_strategy_counts: dict[str, int] = defaultdict(int, seed.best_strategy_distribution if seed else {})

        # Every strategy contributes exactly one row per query, unconditionally (Retrieval Executor
        # always runs all four strategies) -- so each strategy's prior row count is exactly the
        # prior query_count, not an approximation.
        prior_query_count = seed.query_count if seed else 0

        self._utility_overall = _RunningMean(seed.average_utility_overall, seed.row_count) if seed else _RunningMean()
        self._utility_by_strategy: dict[str, _RunningMean] = defaultdict(
            _RunningMean,
            {s: _RunningMean(v, prior_query_count) for s, v in (seed.average_utility_by_strategy.items() if seed else [])},
        )
        self._latency_overall = _RunningMean(seed.average_latency_ms_overall, seed.row_count) if seed else _RunningMean()
        self._latency_by_strategy: dict[str, _RunningMean] = defaultdict(
            _RunningMean,
            {s: _RunningMean(v, prior_query_count) for s, v in (seed.average_latency_ms_by_strategy.items() if seed else [])},
        )
        self._quality_overall = _RunningMean(seed.average_quality_overall, seed.row_count) if seed else _RunningMean()
        self._quality_by_strategy: dict[str, _RunningMean] = defaultdict(
            _RunningMean,
            {s: _RunningMean(v, prior_query_count) for s, v in (seed.average_quality_by_strategy.items() if seed else [])},
        )

        self._feature_statistics: dict[str, _RunningStatistic] = defaultdict(
            _RunningStatistic,
            {key: _RunningStatistic(stat) for key, stat in (seed.feature_statistics.items() if seed else [])},
        )

    def update(self, feature_vector: FeatureVector, oracle_result: OracleUtilityResult) -> None:
        """Fold one query's results into the running statistics.

        Args:
            feature_vector: The query's features -- folded in once
                (not once per strategy row), since it is identical
                across all four of a query's rows.
            oracle_result: The query's four `StrategyOracleRow`s.
        """
        self._repository_ids.add(oracle_result.repository_id)
        self._query_count += 1

        for row in oracle_result.rows:
            self._row_count += 1
            strategy = row.strategy_name.value

            self._utility_overall.add(row.utility_score)
            self._utility_by_strategy[strategy].add(row.utility_score)
            self._latency_overall.add(row.latency_ms)
            self._latency_by_strategy[strategy].add(row.latency_ms)
            self._quality_overall.add(row.quality.quality_score)
            self._quality_by_strategy[strategy].add(row.quality.quality_score)

            if row.is_best_strategy:
                self._best_strategy_counts[strategy] += 1

        for key, value in feature_vector.to_flat_dict().items():
            if isinstance(value, (bool, int, float)):
                self._feature_statistics[key].add(float(value))
            # str (e.g. repo_dominant_language, resource_repository_size_category) is categorical,
            # not summarizable by mean/min/max -- intentionally skipped, not an oversight.

    def build_statistics(self) -> DatasetStatistics:
        """Return the final, cumulative `DatasetStatistics` for everything folded in so far (seed + updates)."""
        return DatasetStatistics(
            repository_count=len(self._repository_ids),
            repository_ids=sorted(self._repository_ids),
            query_count=self._query_count,
            row_count=self._row_count,
            best_strategy_distribution=dict(self._best_strategy_counts),
            average_utility_overall=self._utility_overall.mean,
            average_utility_by_strategy={strategy: running.mean for strategy, running in self._utility_by_strategy.items()},
            average_latency_ms_overall=self._latency_overall.mean,
            average_latency_ms_by_strategy={strategy: running.mean for strategy, running in self._latency_by_strategy.items()},
            average_quality_overall=self._quality_overall.mean,
            average_quality_by_strategy={strategy: running.mean for strategy, running in self._quality_by_strategy.items()},
            feature_statistics={key: running.to_feature_statistic() for key, running in self._feature_statistics.items()},
        )

    @staticmethod
    def from_existing(statistics_path: Path) -> DatasetStatistics | None:
        """Load a previously-written `dataset_statistics.json`, or `None` if it doesn't exist.

        Args:
            statistics_path: Where a prior run may have written
                `DatasetStatistics` as JSON.

        Returns:
            The parsed `DatasetStatistics`, or `None` if the file
            doesn't exist. A corrupt/unreadable existing file is *not*
            silently treated as "no prior data" -- unlike a checkpoint
            line or a cache entry, silently discarding real prior
            statistics would make a resumed run's cumulative numbers
            quietly wrong rather than cleanly absent; callers should
            see the underlying error.
        """
        if not statistics_path.exists():
            return None
        return DatasetStatistics.model_validate_json(statistics_path.read_text(encoding="utf-8"))
