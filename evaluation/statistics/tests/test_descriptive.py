"""Unit tests for `evaluation.statistics.descriptive`."""
from __future__ import annotations

import pytest

from evaluation.statistics.descriptive import compute_descriptive_stats


def test_compute_descriptive_stats_hand_computed() -> None:
    # Textbook example (Wikipedia's "Standard deviation" worked example): mean=5, median=4.5,
    # sample stdev=2.138089935299395.
    stats = compute_descriptive_stats([2, 4, 4, 4, 5, 5, 7, 9])
    assert stats.n == 8
    assert stats.mean == pytest.approx(5.0)
    assert stats.median == pytest.approx(4.5)
    assert stats.std == pytest.approx(2.138089935299395)
    assert stats.minimum == 2.0
    assert stats.maximum == 9.0


def test_compute_descriptive_stats_single_value_has_zero_std() -> None:
    stats = compute_descriptive_stats([42.0])
    assert stats.n == 1
    assert stats.mean == 42.0
    assert stats.median == 42.0
    assert stats.std == 0.0
    assert stats.minimum == stats.maximum == 42.0


def test_compute_descriptive_stats_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        compute_descriptive_stats([])


def test_compute_descriptive_stats_even_count_median_is_average_of_middle_two() -> None:
    stats = compute_descriptive_stats([1.0, 2.0, 3.0, 4.0])
    assert stats.median == pytest.approx(2.5)
