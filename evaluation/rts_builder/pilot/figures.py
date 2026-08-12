"""Renders the six required quality-report figures as static PNGs (matplotlib, Agg backend).

Color choices follow the project's data-visualization method (fixed
categorical hue order for the four strategies, single-hue sequential
ramps for magnitude distributions, a blue<->red diverging ramp with a
neutral gray midpoint for the correlation matrix, hue+marker-shape
composite encoding for the one all-pairs scatter form -- see
`references/color-formula.md`/`choosing-a-form.md` in the `dataviz`
skill). These are static, light-mode-only PNG exports for a written
report (not a theme-aware interactive artifact), so only the light
-surface chrome is used, deliberately -- there is no dark-mode toggle
for a saved image file.
"""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from evaluation.rts_builder.pilot.exceptions import PilotError  # noqa: E402

# Fixed categorical order, matching RetrievalStrategyName's own declaration order
# (lexical, dense, graph, hybrid) -- never re-sorted alphabetically or by frequency, so a
# strategy's color/marker identity is stable across every figure and every pilot run.
_STRATEGY_ORDER = ("lexical", "dense", "graph", "hybrid")
_STRATEGY_COLORS = {"lexical": "#2a78d6", "dense": "#eb6834", "graph": "#1baf7a", "hybrid": "#eda100"}
_STRATEGY_MARKERS = {"lexical": "o", "dense": "s", "graph": "^", "hybrid": "D"}

_SEQUENTIAL_HUE = "#2a78d6"
_DIVERGING_NEGATIVE = "#e34948"
_DIVERGING_NEUTRAL = "#f0efec"
_DIVERGING_POSITIVE = "#2a78d6"

_INK_PRIMARY = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_INK_MUTED = "#898781"
_GRIDLINE = "#e1e0d9"
_SURFACE = "#fcfcfb"


def _new_axes() -> tuple["plt.Figure", "plt.Axes"]:
    figure, axes = plt.subplots(figsize=(8, 5), facecolor=_SURFACE)
    axes.set_facecolor(_SURFACE)
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.spines["left"].set_color(_GRIDLINE)
    axes.spines["bottom"].set_color(_GRIDLINE)
    axes.tick_params(colors=_INK_MUTED, labelsize=9)
    axes.yaxis.grid(True, color=_GRIDLINE, linewidth=0.8, zorder=0)
    axes.set_axisbelow(True)
    return figure, axes


def _save(figure: "plt.Figure", path: Path, dpi: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(str(path), dpi=dpi, facecolor=figure.get_facecolor(), bbox_inches="tight")
    except OSError as exc:
        raise PilotError(f"Could not write figure to {path}: {exc}") from exc
    finally:
        plt.close(figure)


def render_utility_histogram(rows: list[dict[str, object]], path: Path, dpi: int) -> None:
    """One hue, more-is-darker not needed here (single series) -- sequential blue over utility_score bins."""
    values = [float(row["utility_score"]) for row in rows]
    figure, axes = _new_axes()
    axes.hist(values, bins=20, color=_SEQUENTIAL_HUE, edgecolor=_SURFACE, linewidth=0.5, zorder=3)
    axes.set_title("Utility score distribution", color=_INK_PRIMARY, fontsize=12, loc="left")
    axes.set_xlabel("utility_score", color=_INK_SECONDARY)
    axes.set_ylabel("row count", color=_INK_SECONDARY)
    _save(figure, path, dpi)


def render_latency_histogram(rows: list[dict[str, object]], path: Path, dpi: int) -> None:
    """Single-series magnitude distribution -- sequential blue, same convention as the utility histogram."""
    values = [float(row["latency_ms"]) for row in rows]
    figure, axes = _new_axes()
    axes.hist(values, bins=20, color=_SEQUENTIAL_HUE, edgecolor=_SURFACE, linewidth=0.5, zorder=3)
    axes.set_title("Latency (ms) distribution", color=_INK_PRIMARY, fontsize=12, loc="left")
    axes.set_xlabel("latency_ms", color=_INK_SECONDARY)
    axes.set_ylabel("row count", color=_INK_SECONDARY)
    _save(figure, path, dpi)


def render_strategy_frequency(rows: list[dict[str, object]], path: Path, dpi: int) -> None:
    """Categorical bar chart: the x-axis itself names each strategy, so hue reinforces rather than alone carries identity."""
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["strategy_name"])] += 1

    figure, axes = _new_axes()
    strategies = [name for name in _STRATEGY_ORDER if name in counts]
    values = [counts[name] for name in strategies]
    colors = [_STRATEGY_COLORS[name] for name in strategies]
    bars = axes.bar(strategies, values, color=colors, width=0.6, zorder=3)
    axes.bar_label(bars, padding=3, color=_INK_SECONDARY, fontsize=9)
    axes.set_title("Strategy row frequency", color=_INK_PRIMARY, fontsize=12, loc="left")
    axes.set_ylabel("row count", color=_INK_SECONDARY)
    _save(figure, path, dpi)


def render_repository_contribution(rows: list[dict[str, object]], path: Path, dpi: int) -> None:
    """Magnitude by repository -- sequential single hue, sorted descending (a ranking, not an identity comparison)."""
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["repository_id"])] += 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)

    figure, axes = _new_axes()
    axes.barh([name for name, _ in ordered], [count for _, count in ordered], color=_SEQUENTIAL_HUE, zorder=3)
    axes.invert_yaxis()
    axes.set_title("Rows contributed per repository", color=_INK_PRIMARY, fontsize=12, loc="left")
    axes.set_xlabel("row count", color=_INK_SECONDARY)
    axes.xaxis.grid(True, color=_GRIDLINE, linewidth=0.8, zorder=0)
    axes.yaxis.grid(False)
    _save(figure, path, dpi)


def render_quality_vs_latency_scatter(rows: list[dict[str, object]], path: Path, dpi: int) -> None:
    """Quality vs. latency, one point per row -- an all-pairs scatter, so identity uses hue x marker-shape,
    not hue alone (4 strategies would otherwise sit past the all-pairs-safe cap of 3)."""
    figure, axes = _new_axes()
    for name in _STRATEGY_ORDER:
        strategy_rows = [row for row in rows if str(row["strategy_name"]) == name]
        if not strategy_rows:
            continue
        axes.scatter(
            [float(row["latency_ms"]) for row in strategy_rows],
            [float(row["quality_quality_score"]) for row in strategy_rows],
            c=_STRATEGY_COLORS[name], marker=_STRATEGY_MARKERS[name],
            s=28, alpha=0.75, edgecolors=_SURFACE, linewidths=0.4, zorder=3, label=name,
        )
    axes.set_title("Retrieval quality vs. latency", color=_INK_PRIMARY, fontsize=12, loc="left")
    axes.set_xlabel("latency_ms", color=_INK_SECONDARY)
    axes.set_ylabel("quality_score", color=_INK_SECONDARY)
    legend = axes.legend(frameon=False, labelcolor=_INK_SECONDARY, fontsize=9, loc="best")
    for handle in legend.legend_handles or []:
        handle.set_alpha(1.0)
    _save(figure, path, dpi)


def render_feature_correlation_matrix(rows: list[dict[str, object]], feature_columns: list[str], path: Path, dpi: int) -> None:
    """Diverging blue<->red with a neutral gray midpoint at zero correlation -- polarity, not magnitude."""
    columns = sorted(feature_columns)
    matrix = _correlation_matrix(rows, columns)

    colormap = LinearSegmentedColormap.from_list(
        "diverging", [_DIVERGING_NEGATIVE, _DIVERGING_NEUTRAL, _DIVERGING_POSITIVE]
    )
    figure, axes = plt.subplots(figsize=(max(6, 0.4 * len(columns)), max(6, 0.4 * len(columns))), facecolor=_SURFACE)
    axes.set_facecolor(_SURFACE)
    image = axes.imshow(matrix, cmap=colormap, vmin=-1.0, vmax=1.0)
    axes.set_xticks(range(len(columns)))
    axes.set_yticks(range(len(columns)))
    axes.set_xticklabels(columns, rotation=90, fontsize=6, color=_INK_MUTED)
    axes.set_yticklabels(columns, fontsize=6, color=_INK_MUTED)
    axes.set_title("Feature correlation matrix", color=_INK_PRIMARY, fontsize=12, loc="left")
    colorbar = figure.colorbar(image, ax=axes, fraction=0.046, pad=0.04)
    colorbar.ax.tick_params(colors=_INK_MUTED, labelsize=8)
    _save(figure, path, dpi)


def _correlation_matrix(rows: list[dict[str, object]], columns: list[str]) -> list[list[float]]:
    series = {column: [float(row[column]) for row in rows] for column in columns}
    matrix: list[list[float]] = []
    for row_column in columns:
        matrix_row: list[float] = []
        for col_column in columns:
            matrix_row.append(_pearson_correlation(series[row_column], series[col_column]))
        matrix.append(matrix_row)
    return matrix


def _pearson_correlation(values_a: list[float], values_b: list[float]) -> float:
    n = len(values_a)
    if n == 0:
        return 0.0
    mean_a, mean_b = sum(values_a) / n, sum(values_b) / n
    covariance = sum((a - mean_a) * (b - mean_b) for a, b in zip(values_a, values_b, strict=True))
    variance_a = sum((a - mean_a) ** 2 for a in values_a)
    variance_b = sum((b - mean_b) ** 2 for b in values_b)
    denominator = math.sqrt(variance_a * variance_b)
    return covariance / denominator if denominator else 0.0


def generate_all(
    rows: list[dict[str, object]], feature_columns: list[str], output_dir: Path, dpi: int
) -> dict[str, str]:
    """Render every required figure into `output_dir`, returning `{figure_name: absolute_path}`."""
    figure_paths = {
        "utility_histogram": output_dir / "utility_histogram.png",
        "latency_histogram": output_dir / "latency_histogram.png",
        "strategy_frequency": output_dir / "strategy_frequency.png",
        "repository_contribution": output_dir / "repository_contribution.png",
        "quality_vs_latency_scatter": output_dir / "quality_vs_latency_scatter.png",
        "feature_correlation_matrix": output_dir / "feature_correlation_matrix.png",
    }
    render_utility_histogram(rows, figure_paths["utility_histogram"], dpi)
    render_latency_histogram(rows, figure_paths["latency_histogram"], dpi)
    render_strategy_frequency(rows, figure_paths["strategy_frequency"], dpi)
    render_repository_contribution(rows, figure_paths["repository_contribution"], dpi)
    render_quality_vs_latency_scatter(rows, figure_paths["quality_vs_latency_scatter"], dpi)
    render_feature_correlation_matrix(rows, feature_columns, figure_paths["feature_correlation_matrix"], dpi)
    return {name: str(path) for name, path in figure_paths.items()}
