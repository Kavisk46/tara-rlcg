"""Phase 6 -- feature importance: Gain, Split, and SHAP, with publication-quality plots.

Three complementary views of "which features drive the model's
ranking decisions":

- **Gain**: total reduction in the training loss attributable to each
  feature across every split that used it -- LightGBM's default,
  usually the most decision-relevant view.
- **Split**: how many times each feature was chosen as a split
  point, regardless of the gain each split produced -- flags features
  the model consults *often* even if each individual split's
  contribution is small (useful for spotting a feature the model
  leans on for fine-grained tie-breaking).
- **SHAP** (SHapley Additive exPlanations, via `shap.TreeExplainer`):
  a per-prediction, theoretically-grounded attribution that (unlike
  Gain/Split, which are training-time, global statistics) can also
  explain *individual* rows -- used here for a global summary (mean
  |SHAP value| per feature) and a beeswarm plot showing both magnitude
  and direction of each feature's effect.

All three are computed from a *trained* model plus a feature matrix
(conventionally the training or test matrix `feature_pipeline.py`
already wrote) -- this module trains nothing itself.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: this module only ever writes figures to disk, never shows an interactive window
import matplotlib.pyplot as plt
import numpy as np
import shap

if __package__ in (None, ""):  # pragma: no cover - direct-execution convenience
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evaluation.experiments.ltr.model import LambdaRankModel
from evaluation.experiments.ltr.utils import FIGURES_DIR, REPORTS_DIR, get_logger

logger = get_logger(__name__)


@dataclass
class ImportanceResult:
    """Every importance view this module computes, for one `(model, X)` pair."""

    feature_names: list[str]
    gain: np.ndarray
    split: np.ndarray
    mean_abs_shap: np.ndarray
    shap_values: np.ndarray  # (n_rows, n_features) -- kept for the beeswarm plot

    def to_dict(self) -> dict[str, list]:
        order = np.argsort(-self.gain)
        return {
            "ranked_by_gain": [
                {
                    "feature": self.feature_names[i],
                    "gain": float(self.gain[i]),
                    "split_count": int(self.split[i]),
                    "mean_abs_shap": float(self.mean_abs_shap[i]),
                }
                for i in order
            ]
        }


def compute_importance(model: LambdaRankModel, X: np.ndarray) -> ImportanceResult:
    """Compute Gain, Split, and SHAP importance for `model` against `X`.

    Args:
        model: A fitted (or loaded) `LambdaRankModel`.
        X: `(n_rows, n_features)` feature matrix to explain -- SHAP
            values are computed per-row against this matrix, so this
            should generally be a real evaluation split (train or
            test), not synthetic data, once real labels exist.

    Returns:
        An `ImportanceResult`.

    Raises:
        RuntimeError: If `model` is not fitted.
    """
    if not model.is_fitted:
        raise RuntimeError("compute_importance() requires a fitted model.")
    assert model.feature_names is not None

    booster = model._booster  # noqa: SLF001 -- this module is allowed to read the raw booster for importance introspection
    gain = booster.feature_importance(importance_type="gain")
    split = booster.feature_importance(importance_type="split")

    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):  # some SHAP/LightGBM version combinations return a list of arrays
        shap_values = shap_values[0]
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

    return ImportanceResult(
        feature_names=model.feature_names,
        gain=gain,
        split=split,
        mean_abs_shap=mean_abs_shap,
        shap_values=shap_values,
    )


def _plot_bar(names: list[str], values: np.ndarray, title: str, xlabel: str, path: Path, top_n: int = 25) -> None:
    """Save a horizontal bar chart of the top `top_n` features by `values`, largest at the top."""
    order = np.argsort(values)[::-1][:top_n]
    sorted_names = [names[i] for i in order][::-1]
    sorted_values = values[order][::-1]

    fig, ax = plt.subplots(figsize=(8, max(4, 0.28 * len(sorted_names))))
    ax.barh(sorted_names, sorted_values, color="#3B6FA0")
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    logger.info("Wrote figure: %s", path)


def plot_gain_importance(result: ImportanceResult, path: Path, top_n: int = 25) -> None:
    _plot_bar(result.feature_names, result.gain, "Feature Importance -- Gain", "Total gain", path, top_n)


def plot_split_importance(result: ImportanceResult, path: Path, top_n: int = 25) -> None:
    _plot_bar(result.feature_names, result.split.astype(float), "Feature Importance -- Split Count", "Number of splits", path, top_n)


def plot_shap_summary(result: ImportanceResult, X: np.ndarray, path: Path, top_n: int = 25) -> None:
    """Save a SHAP beeswarm summary plot (magnitude + direction of each feature's effect)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, max(4, 0.3 * min(top_n, len(result.feature_names)))))
    shap.summary_plot(
        result.shap_values, X, feature_names=result.feature_names, max_display=top_n, show=False, plot_size=None
    )
    fig = plt.gcf()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    logger.info("Wrote figure: %s", path)


def format_report(result: ImportanceResult, top_n: int = 20) -> str:
    ranked = result.to_dict()["ranked_by_gain"][:top_n]
    lines = [
        "# Phase 6 -- Feature Importance Report",
        "",
        f"Top {top_n} features by Gain (with their Split count and mean |SHAP value| for comparison):",
        "",
        "| Rank | Feature | Gain | Split count | Mean |SHAP| |",
        "|---|---|---|---|---|",
    ]
    for i, row in enumerate(ranked, start=1):
        lines.append(f"| {i} | `{row['feature']}` | {row['gain']:.2f} | {row['split_count']} | {row['mean_abs_shap']:.4f} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: load a model + a `.npz` feature matrix (from `feature_pipeline.py`), compute and save everything."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--features-npz", type=Path, required=True, help="A features_<split>.npz written by feature_pipeline.py.")
    parser.add_argument("--output-dir", type=Path, default=FIGURES_DIR)
    parser.add_argument("--report-path", type=Path, default=REPORTS_DIR / "phase6_feature_importance.md")
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args(argv)

    model = LambdaRankModel.load(args.model_path)
    data = np.load(args.features_npz)
    X = data["X"]

    result = compute_importance(model, X)

    plot_gain_importance(result, args.output_dir / "importance_gain.png", args.top_n)
    plot_split_importance(result, args.output_dir / "importance_split.png", args.top_n)
    plot_shap_summary(result, X, args.output_dir / "importance_shap_summary.png", args.top_n)

    report = format_report(result, args.top_n)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(report, encoding="utf-8")
    (args.report_path.with_suffix(".json")).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(report)
    logger.info("Wrote %s", args.report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
