"""Phase 4 -- the training entry point: config-driven, seeded, checkpointed, early-stopped, logged.

Orchestrates Phases 1-3 (`dataset_inspection` is not called directly
here -- it is a separate diagnostic step a user runs first, per
`README.md`'s reproduction instructions) into one command:

    python -m evaluation.experiments.ltr.train --config config.yaml

1. Loads `config.yaml` (`ExperimentConfig`).
2. Seeds every RNG this package touches (`utils.set_global_seed`).
3. Loads `train.jsonl`/`validation.jsonl`, and -- the single most
   important gate in this entire pipeline -- calls
   `feature_pipeline.validate_labels_are_numeric` on both *before*
   doing anything else. RTS Dataset v1.0 ships fully unlabeled (every
   grade is the placeholder `"TO_BE_ASSIGNED"`); this call raises
   `UnlabeledDatasetError` in that case, and `main` lets that
   exception propagate as a non-zero exit code with a clear message,
   rather than training against a fabricated or silently-coerced
   label. **This is expected, correct behavior against the dataset as
   currently shipped, not a bug** -- see `README.md`'s "Current
   dataset status" section.
4. Builds feature matrices for both splits (fitting `Encoders` on
   `train` only).
5. Fits a `model.LambdaRankModel`, with early stopping against the
   validation split and periodic checkpointing, both config-driven.
6. Saves the model, the fitted encoders, and a run manifest (config
   used, dataset digest, timestamps, git commit if available) to
   `outputs/models/<run_id>/`, so every artifact needed to reproduce
   or audit the run lives in one place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if __package__ in (None, ""):  # pragma: no cover - direct-execution convenience
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evaluation.experiments.ltr.feature_pipeline import (
    Encoders, RetrievalFeatureProvider, build_feature_matrix, validate_labels_are_numeric,
)
from evaluation.experiments.ltr.model import LambdaRankModel, ModelConfig
from evaluation.experiments.ltr.utils import (
    MERGED_DATASET_DIR, MODELS_DIR, REPO_ROOT, get_logger, read_jsonl, set_global_seed,
)

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@dataclass
class ExperimentConfig:
    """The full contents of `config.yaml`, typed."""

    seed: int
    merged_dataset_dir: str
    use_retrieval_features: bool
    model: ModelConfig
    checkpoint_every: int
    output_dir: str

    @classmethod
    def from_yaml(cls, path: Path) -> "ExperimentConfig":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            seed=raw["seed"],
            merged_dataset_dir=raw.get("merged_dataset_dir", str(MERGED_DATASET_DIR)),
            use_retrieval_features=raw.get("use_retrieval_features", True),
            model=ModelConfig.from_dict(raw["model"]),
            checkpoint_every=raw.get("checkpoint_every", 0),
            output_dir=raw.get("output_dir", str(MODELS_DIR)),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["model"] = self.model.to_dict()
        return d


def _git_commit_sha(repo_root: Path) -> str | None:
    """Best-effort `git rev-parse HEAD` for `repo_root`, or `None` if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, timeout=10, check=True
        )
        return result.stdout.strip()
    except Exception as exc:  # noqa: BLE001 - this is diagnostic metadata, never fatal
        logger.warning("Could not determine git commit for run manifest: %s", exc)
        return None


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_run_id(seed: int) -> str:
    """A sortable, collision-resistant run identifier: `<UTC timestamp>_seed<seed>`."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_seed{seed}"


def train(config: ExperimentConfig, *, resume_from: Path | None = None) -> Path:
    """Run the full training pipeline described in this module's docstring.

    Args:
        config: The experiment configuration.
        resume_from: Optional checkpoint to resume training from (see
            `model.LambdaRankModel.fit`'s `resume_from`).

    Returns:
        Path to the run's output directory (`outputs/models/<run_id>/`),
        containing `model.txt`, `model.txt.meta.json`, `encoders.json`,
        and `run_manifest.json`.

    Raises:
        feature_pipeline.UnlabeledDatasetError: If `train.jsonl` or
            `validation.jsonl` has no real numeric relevance grades --
            see module docstring, step 3. This is the expected outcome
            against RTS Dataset v1.0 as currently shipped.
    """
    set_global_seed(config.seed)
    merged_dataset_dir = Path(config.merged_dataset_dir)

    train_rows = read_jsonl(merged_dataset_dir / "train.jsonl")
    val_rows = read_jsonl(merged_dataset_dir / "validation.jsonl")

    logger.info("Validating that train/validation splits have real (non-placeholder) relevance grades...")
    validate_labels_are_numeric(train_rows, split_name="train")
    validate_labels_are_numeric(val_rows, split_name="validation")
    logger.info("Label validation passed -- proceeding to feature construction and training.")

    encoders = Encoders.fit(train_rows)
    provider = RetrievalFeatureProvider() if config.use_retrieval_features else None

    logger.info("Building training feature matrix...")
    train_matrix = build_feature_matrix(train_rows, encoders=encoders, retrieval_provider=provider, require_numeric_labels=True)
    logger.info("Building validation feature matrix...")
    val_matrix = build_feature_matrix(val_rows, encoders=encoders, retrieval_provider=provider, require_numeric_labels=True)

    categorical_indices = [train_matrix.feature_names.index(c) for c in train_matrix.categorical_feature_names]

    run_id = make_run_id(config.seed)
    run_dir = Path(config.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = run_dir / "checkpoints"

    model = LambdaRankModel(config=config.model, categorical_feature_indices=categorical_indices)
    model.fit(
        train_matrix.X, train_matrix.y, train_matrix.group_sizes,
        feature_names=train_matrix.feature_names,
        X_val=val_matrix.X, y_val=val_matrix.y, group_val=val_matrix.group_sizes,
        checkpoint_dir=checkpoint_dir if config.checkpoint_every > 0 else None,
        checkpoint_every=config.checkpoint_every,
        resume_from=resume_from,
    )

    model.save(run_dir / "model.txt")
    encoders.save(run_dir / "encoders.json")

    manifest = {
        "run_id": run_id,
        "config": config.to_dict(),
        "seed": config.seed,
        "git_commit": _git_commit_sha(REPO_ROOT),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_split_digest": _file_digest(merged_dataset_dir / "train.jsonl"),
        "validation_split_digest": _file_digest(merged_dataset_dir / "validation.jsonl"),
        "n_train_rows": int(train_matrix.X.shape[0]),
        "n_train_groups": int(len(train_matrix.group_sizes)),
        "n_validation_rows": int(val_matrix.X.shape[0]),
        "n_validation_groups": int(len(val_matrix.group_sizes)),
        "n_features": int(train_matrix.X.shape[1]),
        "feature_names": train_matrix.feature_names,
        "best_iteration": model.best_iteration_,
        "resumed_from": str(resume_from) if resume_from else None,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("Training complete. Run artifacts written to %s", run_dir)
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--resume-from", type=Path, default=None, help="Path to a checkpoint or saved model to resume training from.")
    args = parser.parse_args(argv)

    config = ExperimentConfig.from_yaml(args.config)
    logger.info("Loaded config from %s: %s", args.config, config.to_dict())

    train(config, resume_from=args.resume_from)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
