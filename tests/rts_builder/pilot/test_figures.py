"""Unit tests for `evaluation.rts_builder.pilot.figures`.

Only checks that each figure renders without raising and produces a
non-trivial PNG file -- pixel-level assertions about a chart's visual
content are out of scope for a unit test; `dataviz` skill guidance
governs the actual design choices (see `figures.py`'s module docstring).
"""
from __future__ import annotations

from pathlib import Path

from evaluation.rts_builder.pilot import figures

_MINIMUM_PNG_BYTES = 500


def test_generate_all_writes_all_six_figures(sample_rows: list[dict[str, object]], tmp_path: Path) -> None:
    feature_columns = ["query_length", "repo_file_count"]
    output_dir = tmp_path / "figures"

    figure_paths = figures.generate_all(sample_rows, feature_columns, output_dir, dpi=100)

    assert set(figure_paths) == {
        "utility_histogram", "latency_histogram", "strategy_frequency",
        "repository_contribution", "quality_vs_latency_scatter", "feature_correlation_matrix",
    }
    for path_str in figure_paths.values():
        path = Path(path_str)
        assert path.is_file()
        assert path.stat().st_size > _MINIMUM_PNG_BYTES


def test_individual_renderers_do_not_raise_on_a_single_repository(sample_rows: list[dict[str, object]], tmp_path: Path) -> None:
    single_repo_rows = [row for row in sample_rows if row["repository_id"] == sample_rows[0]["repository_id"]]

    figures.render_utility_histogram(single_repo_rows, tmp_path / "u.png", dpi=100)
    figures.render_latency_histogram(single_repo_rows, tmp_path / "l.png", dpi=100)
    figures.render_strategy_frequency(single_repo_rows, tmp_path / "s.png", dpi=100)
    figures.render_repository_contribution(single_repo_rows, tmp_path / "r.png", dpi=100)
    figures.render_quality_vs_latency_scatter(single_repo_rows, tmp_path / "q.png", dpi=100)
    figures.render_feature_correlation_matrix(single_repo_rows, ["query_length", "repo_file_count"], tmp_path / "c.png", dpi=100)

    for name in ("u", "l", "s", "r", "q", "c"):
        assert (tmp_path / f"{name}.png").is_file()


def test_correlation_matrix_handles_a_constant_valued_feature(sample_rows: list[dict[str, object]], tmp_path: Path) -> None:
    # A feature with zero variance makes Pearson correlation's denominator zero -- must not
    # raise (ZeroDivisionError) or produce NaN pixels that crash imshow.
    rows = [dict(row, constant_feature=1.0) for row in sample_rows]
    path = tmp_path / "constant.png"

    figures.render_feature_correlation_matrix(rows, ["query_length", "constant_feature"], path, dpi=100)

    assert path.is_file()
    assert path.stat().st_size > _MINIMUM_PNG_BYTES
