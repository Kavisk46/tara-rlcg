"""Descriptive statistics: mean, median, standard deviation, min/max over a sample.

Stdlib `statistics` only -- no new dependency for arithmetic this simple,
matching the project's established stance (`tara.retrieval.bm25_index`,
`tara.fusion.token_budget`, `evaluation.statistics.significance`'s own
hand-rolled McNemar).
"""
from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptiveStats:
    """Summary statistics for one sample of per-query metric values."""

    n: int
    mean: float
    median: float
    std: float
    minimum: float
    maximum: float


def compute_descriptive_stats(values: Sequence[float]) -> DescriptiveStats:
    """Compute `DescriptiveStats` for `values`.

    Args:
        values: A non-empty sample, e.g. one system's per-query metric
            values. Boolean metric values should already have been
            coerced to `0.0`/`1.0` by the caller (see
            `evaluation.statistics.metrics_registry`); this function
            treats every value as a plain float.

    Returns:
        `n`, `mean`, `median`, `std` (population-independent sample
        standard deviation; `0.0` when `n == 1`, since
        `statistics.stdev` is undefined for a single observation and
        `0.0` -- "no observed spread" -- is the honest value there, not
        an error), `minimum`, `maximum`.

    Raises:
        ValueError: If `values` is empty.
    """
    if not values:
        raise ValueError("values is empty -- cannot compute descriptive statistics of nothing.")

    sample = [float(v) for v in values]
    return DescriptiveStats(
        n=len(sample),
        mean=statistics.fmean(sample),
        median=statistics.median(sample),
        std=statistics.stdev(sample) if len(sample) > 1 else 0.0,
        minimum=min(sample),
        maximum=max(sample),
    )
