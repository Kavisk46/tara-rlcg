"""Unit tests for `evaluation.statistics.tables`.

Structural/content checks (the rendered numbers appear, correctly
formatted) rather than pixel-perfect Markdown matching -- reporting
code is held to a lighter bar than the statistics it renders, per
`ROADMAP.md` M10's own established convention, since the numbers
themselves are already independently verified in
`test_paired_comparison.py`.
"""
from __future__ import annotations

import pytest

from evaluation.statistics.metrics_registry import RECIPROCAL_RANK
from evaluation.statistics.paired_comparison import (
    ComparisonFamily,
    compare_variants,
    correct_family,
)
from evaluation.statistics.protocol import StatisticalProtocol
from evaluation.statistics.tables import render_comparison_family_table
from evaluation.statistics.tests.conftest import (
    RECIPROCAL_RANK_A_VALUES,
    RECIPROCAL_RANK_B_VALUES,
    make_reciprocal_rank_results,
    make_result,
)

_PROTOCOL = StatisticalProtocol(ci_n_resamples=200, ci_seed=42)


def _family() -> ComparisonFamily:
    comparison = compare_variants(
        make_reciprocal_rank_results("TARA", RECIPROCAL_RANK_A_VALUES),
        make_reciprocal_rank_results("B1", RECIPROCAL_RANK_B_VALUES),
        RECIPROCAL_RANK,
        _PROTOCOL,
    )
    return correct_family("TARA vs. B1, reciprocal_rank", [comparison], _PROTOCOL)


def test_render_comparison_family_table_includes_family_name() -> None:
    table = render_comparison_family_table(_family())
    assert "TARA vs. B1, reciprocal_rank" in table


def test_render_comparison_family_table_includes_system_ids() -> None:
    table = render_comparison_family_table(_family())
    assert "`TARA`" in table
    assert "`B1`" in table


def test_render_comparison_family_table_includes_n() -> None:
    table = render_comparison_family_table(_family())
    assert "| reciprocal_rank | 5 |" in table


def test_render_comparison_family_table_includes_test_name_and_p_value() -> None:
    table = render_comparison_family_table(_family())
    assert "wilcoxon_signed_rank" in table
    assert "1.0000" in table  # the hand-verified p-value, formatted to 4 decimals


def test_render_comparison_family_table_includes_effect_size() -> None:
    table = render_comparison_family_table(_family())
    assert "-0.100" in table
    assert "rank_biserial_correlation" in table


def test_render_comparison_family_table_uses_custom_row_label_and_names() -> None:
    table = render_comparison_family_table(_family(), row_label="TaskType", row_names=["search"])
    assert "| TaskType |" in table
    assert "| search |" in table


def test_render_comparison_family_table_rejects_mismatched_row_names() -> None:
    with pytest.raises(ValueError, match="row_names"):
        render_comparison_family_table(_family(), row_names=["a", "b"])


def test_render_comparison_family_table_marks_significance_from_corrected_result() -> None:
    table = render_comparison_family_table(_family())
    # A single-comparison family with p=1.0 is never significant at any reasonable alpha.
    lines = [line for line in table.splitlines() if line.startswith("| reciprocal_rank")]
    assert len(lines) == 1
    assert "| no |" in lines[0]


def test_render_comparison_family_table_never_contains_a_narrative_verdict() -> None:
    table = render_comparison_family_table(_family())
    for forbidden in ("superior", "outperforms", "better", "worse", "wins", "beats"):
        assert forbidden not in table.lower()


def test_render_comparison_family_table_binary_metric_has_no_effect_size() -> None:
    from evaluation.statistics.metrics_registry import EXACT_MATCH

    results_a = [make_result(query_id=f"q-{i}", exact_match=True) for i in range(10)] + [
        make_result(query_id=f"q-{i}", exact_match=False) for i in range(10, 12)
    ]
    results_b = [make_result(query_id=f"q-{i}", exact_match=False) for i in range(10)] + [
        make_result(query_id=f"q-{i}", exact_match=True) for i in range(10, 12)
    ]
    comparison = compare_variants(results_a, results_b, EXACT_MATCH, _PROTOCOL)
    family = correct_family("exact_match family", [comparison], _PROTOCOL)

    table = render_comparison_family_table(family)

    assert "n/a" in table
    assert "mcnemar" in table
