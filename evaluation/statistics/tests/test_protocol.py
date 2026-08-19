"""Unit tests for `evaluation.statistics.protocol`."""
from __future__ import annotations

import pytest

from evaluation.statistics.protocol import DEFAULT_PROTOCOL, StatisticalProtocol


def test_default_protocol_matches_experiment_plan_section_6() -> None:
    assert DEFAULT_PROTOCOL.alpha == 0.05
    assert DEFAULT_PROTOCOL.ci_confidence_level == 0.95
    assert DEFAULT_PROTOCOL.ci_n_resamples == 10_000
    assert DEFAULT_PROTOCOL.ci_seed is None


def test_protocol_rejects_out_of_range_alpha() -> None:
    with pytest.raises(ValueError, match="alpha"):
        StatisticalProtocol(alpha=0.0)
    with pytest.raises(ValueError, match="alpha"):
        StatisticalProtocol(alpha=1.0)


def test_protocol_rejects_out_of_range_confidence_level() -> None:
    with pytest.raises(ValueError, match="ci_confidence_level"):
        StatisticalProtocol(ci_confidence_level=1.5)


def test_protocol_rejects_non_positive_n_resamples() -> None:
    with pytest.raises(ValueError, match="ci_n_resamples"):
        StatisticalProtocol(ci_n_resamples=0)


def test_protocol_accepts_a_fixed_seed_for_reproducibility() -> None:
    protocol = StatisticalProtocol(ci_seed=42)
    assert protocol.ci_seed == 42


def test_protocol_is_frozen() -> None:
    protocol = StatisticalProtocol()
    with pytest.raises(AttributeError):
        protocol.alpha = 0.1  # type: ignore[misc]
