"""Unit tests for `evaluation.baselines.registry`."""
from __future__ import annotations

from evaluation.baselines.definitions import BaselineId
from evaluation.baselines.registry import (
    build_reproducibility_report,
    render_reproducibility_report_markdown,
)


def test_report_covers_every_baseline_b0_through_b6_in_order() -> None:
    report = build_reproducibility_report()
    assert [row.baseline_id for row in report] == [
        BaselineId.B0,
        BaselineId.B1,
        BaselineId.B2,
        BaselineId.B3,
        BaselineId.B4,
        BaselineId.B5,
        BaselineId.B6,
    ]


def test_implemented_baselines_report_implemented_status() -> None:
    report = build_reproducibility_report()
    implemented_ids = (BaselineId.B0, BaselineId.B1, BaselineId.B2, BaselineId.B3, BaselineId.B4)
    for row in report:
        if row.baseline_id in implemented_ids:
            assert row.implementation_status == "implemented"


def test_unavailable_baselines_report_not_implemented_status_with_a_real_reason() -> None:
    report = build_reproducibility_report()
    for row in report:
        if row.baseline_id in (BaselineId.B5, BaselineId.B6):
            assert row.implementation_status == "not implemented"
            assert row.reproducibility_status.startswith("unavailable_reference:")


def test_b1_reports_dense_as_its_retrieval_mechanism() -> None:
    report = build_reproducibility_report()
    b1 = next(row for row in report if row.baseline_id is BaselineId.B1)
    assert b1.retrieval_mechanisms == ("dense",)


def test_b4_reports_all_three_retrieval_mechanisms() -> None:
    report = build_reproducibility_report()
    b4 = next(row for row in report if row.baseline_id is BaselineId.B4)
    assert set(b4.retrieval_mechanisms) == {"lexical", "dense", "graph"}


def test_b0_reports_no_retrieval_mechanisms() -> None:
    report = build_reproducibility_report()
    b0 = next(row for row in report if row.baseline_id is BaselineId.B0)
    assert b0.retrieval_mechanisms == ()
    assert b0.strategy == "none"


def test_no_baseline_reports_a_fabricated_reproducibility_claim() -> None:
    """Every implemented baseline's status must be honest: deterministic + no external
    dependency, never an unearned claim like 'validated' or 'benchmarked'."""
    report = build_reproducibility_report()
    for row in report:
        assert "validated" not in row.reproducibility_status.lower()
        assert "benchmarked" not in row.reproducibility_status.lower()


def test_markdown_report_contains_every_baseline_id() -> None:
    markdown = render_reproducibility_report_markdown()
    for baseline_id in BaselineId:
        assert baseline_id.value in markdown


def test_markdown_report_is_a_pipe_table() -> None:
    markdown = render_reproducibility_report_markdown()
    lines = markdown.splitlines()
    assert lines[0].startswith("|")
    assert lines[1].startswith("|---")
