"""Unit tests for `evaluation.rts_builder.pilot.config.PilotSettings`."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.rts_builder.pilot.config import PilotSettings


def test_default_ratios_sum_to_one() -> None:
    settings = PilotSettings()
    assert settings.train_ratio + settings.validation_ratio + settings.test_ratio == pytest.approx(1.0)


def test_ratios_not_summing_to_one_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PilotSettings(train_ratio=0.5, validation_ratio=0.3, test_ratio=0.3)


def test_ratios_summing_to_one_within_tolerance_is_accepted() -> None:
    # 0.1 + 0.1 + 0.1 style float sums land a hair off 1.0 -- the tolerance must absorb that.
    settings = PilotSettings(train_ratio=0.34, validation_ratio=0.33, test_ratio=0.33)
    assert settings.train_ratio == 0.34
