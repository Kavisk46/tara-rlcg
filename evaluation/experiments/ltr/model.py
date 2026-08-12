"""Phase 3 -- the Learning-to-Rank model: LightGBM's LambdaRank objective.

Thin, typed wrapper around `lightgbm.LGBMRanker` so `train.py`,
`evaluate.py`, `importance.py`, and `error_analysis.py` all construct,
save, and load the model the same way, with the same hyperparameter
surface (`ModelConfig`) driven by `config.yaml`.

See `MODEL_JUSTIFICATION.md` in this directory for the full
comparison against XGBoost's ranker and CatBoost's ranker; the summary
is reproduced in this module's docstring for anyone reading the code
without also opening that file.

Why LightGBM LambdaRank (short version):

1. **Native categorical-feature support without one-hot expansion.**
   This dataset's most informative categorical columns
   (`repository_id_code`, `category_code`) have low cardinality (8 and
   7 respectively) but LightGBM's histogram-based exact categorical
   split-finding (Fisher's method) still outperforms one-hot expansion
   or plain numeric treatment, and -- unlike XGBoost, where categorical
   support is newer and, as of the versions pinned in `config.yaml`,
   requires the (still maturing) `enable_categorical` path with its own
   caveats for ranking objectives -- LightGBM's categorical handling has
   been production-stable since `LightGBM>=2.x` and is fully compatible
   with `objective="lambdarank"`.
2. **Leaf-wise tree growth** finds lower training loss per split than
   XGBoost's/CatBoost's level-wise default for the same leaf budget,
   which matters more than usual here given this dataset's tiny group
   sizes (mean ~2.7 candidates/query -- see
   `merged_dataset/dataset_statistics.md` §5) and correspondingly low
   total row count (fewer than 500 candidate rows dataset-wide): a
   leaf-wise learner reaches useful splits with far less data per split
   than a level-wise one, at the cost of needing `max_depth`/
   `num_leaves` regularization to avoid overfitting such a small
   dataset, which `ModelConfig` exposes directly.
3. **First-class native NDCG-based LambdaRank/LambdaMART**, with
   `label_gain` and `eval_at` exposed directly as constructor
   parameters -- CatBoost's `YetiRank`/`YetiRankPairwise` are strong
   alternatives but are tuned for much larger per-group candidate
   counts than this dataset has, and CatBoost's own documentation
   recommends `PairLogit`/`PairLogitPairwise` (not a true listwise
   NDCG objective) below a certain group size.
4. **Training speed on CPU** on a dataset this small (hundreds of
   rows) is not a real differentiator between the three libraries, so
   it does not enter this decision -- called out explicitly so this
   justification is not overclaiming a benefit that would not actually
   be observed here.
5. **This project's existing dependency footprint** already includes
   `numpy`/`scikit-learn`-adjacent tooling used elsewhere in
   `evaluation.rts_builder`; LightGBM's pure-C++-plus-Python-binding
   package is a materially lighter addition (no GPU/CUDA toolchain
   assumptions, unlike some CatBoost distributions) for a CPU-only
   pilot-scale experiment.

None of these reasons are absolute -- see `MODEL_JUSTIFICATION.md` for
the caveats and the conditions under which XGBoost or CatBoost would
be the better choice.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np

from evaluation.experiments.ltr.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ModelConfig:
    """Every LightGBM `LGBMRanker` hyperparameter this project tunes, with defaults.

    Mirrors `config.yaml`'s `model:` section field-for-field --
    `ModelConfig.from_dict(yaml.safe_load(...)['model'])` round-trips
    exactly. Kept as an explicit dataclass (rather than passing a raw
    dict to `LGBMRanker`) so an invalid or misspelled hyperparameter
    name fails at config-load time with a clear `TypeError`, not deep
    inside a training run.
    """

    objective: str = "lambdarank"
    boosting_type: str = "gbdt"
    metric: str = "ndcg"
    eval_at: tuple[int, ...] = (1, 3, 5)
    n_estimators: int = 200
    learning_rate: float = 0.05
    num_leaves: int = 15
    max_depth: int = 4
    min_child_samples: int = 5
    min_split_gain: float = 0.0
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0
    subsample: float = 0.9
    subsample_freq: int = 1
    colsample_bytree: float = 0.9
    label_gain: tuple[float, ...] | None = None
    random_state: int = 42
    n_jobs: int = -1
    verbosity: int = -1
    early_stopping_rounds: int = 20

    def __post_init__(self) -> None:
        if self.num_leaves < 2:
            raise ValueError(f"num_leaves must be >= 2, got {self.num_leaves}")
        if self.max_depth < 1:
            raise ValueError(f"max_depth must be >= 1, got {self.max_depth}")
        if not (0.0 < self.learning_rate <= 1.0):
            raise ValueError(f"learning_rate must be in (0, 1], got {self.learning_rate}")
        if not (0.0 < self.subsample <= 1.0):
            raise ValueError(f"subsample must be in (0, 1], got {self.subsample}")
        if not (0.0 < self.colsample_bytree <= 1.0):
            raise ValueError(f"colsample_bytree must be in (0, 1], got {self.colsample_bytree}")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelConfig":
        d = dict(d)
        if "eval_at" in d:
            d["eval_at"] = tuple(d["eval_at"])
        if "label_gain" in d and d["label_gain"] is not None:
            d["label_gain"] = tuple(d["label_gain"])
        return cls(**d)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["eval_at"] = list(d["eval_at"])
        if d["label_gain"] is not None:
            d["label_gain"] = list(d["label_gain"])
        return d

    def to_lgbm_kwargs(self) -> dict[str, Any]:
        """The subset of fields that are literal `LGBMRanker` constructor kwargs.

        Excludes `early_stopping_rounds`, which this project passes to
        `LGBMRanker.fit(..., callbacks=[lgb.early_stopping(...)])`
        instead of the constructor, matching LightGBM's own
        recommended usage since `early_stopping_rounds` was deprecated
        as a bare constructor kwarg.
        """
        kwargs = asdict(self)
        kwargs.pop("early_stopping_rounds")
        kwargs["eval_at"] = list(kwargs["eval_at"])
        if kwargs["label_gain"] is not None:
            kwargs["label_gain"] = list(kwargs["label_gain"])
        else:
            kwargs.pop("label_gain")
        return kwargs


def _make_checkpoint_callback(checkpoint_dir: Path, every: int):
    """Build a LightGBM training callback that periodically saves the in-progress booster.

    Args:
        checkpoint_dir: Where to write `checkpoint_iter_<N>.txt` files
            (created if it does not exist).
        every: Save every this many completed boosting iterations.

    Returns:
        A callable usable in `LGBMRanker.fit(callbacks=[...])`, per
        LightGBM's callback-environment protocol (`env.iteration`,
        `env.model`).
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _callback(env: Any) -> None:
        iteration = env.iteration + 1  # env.iteration is 0-indexed; report/name checkpoints 1-indexed
        if iteration % every == 0:
            path = checkpoint_dir / f"checkpoint_iter_{iteration}.txt"
            env.model.save_model(str(path))
            logger.info("Saved training checkpoint at iteration %d: %s", iteration, path)

    _callback.order = 30  # runs after LightGBM's built-in callbacks (log_evaluation=10, early_stopping=30 by convention)
    return _callback


class LambdaRankModel:
    """A trained-or-trainable `lightgbm.LGBMRanker`, with this project's save/load convention.

    Args:
        config: Hyperparameters. Defaults to `ModelConfig()`.
        categorical_feature_indices: Column indices (into the feature
            matrix passed to `fit`/`predict`) that are categorical.
            Passed through to LightGBM's own `categorical_feature`
            support -- see this module's docstring, reason 1.
    """

    def __init__(self, config: ModelConfig | None = None, categorical_feature_indices: list[int] | None = None) -> None:
        self.config = config or ModelConfig()
        self.categorical_feature_indices = categorical_feature_indices or []
        # `_booster` is always a raw `lgb.Booster` once fitted/loaded -- the
        # sklearn `LGBMRanker` wrapper is used only transiently inside `fit()`
        # for its `eval_set`/early-stopping convenience API, then immediately
        # unwrapped via `.booster_`. Predicting and saving/loading only ever
        # touch the raw `Booster`, which has a version-stable, format-stable
        # native serialization (`save_model`/`Booster(model_file=...)`) and no
        # sklearn-estimator "is this fitted, with how many features" state to
        # get out of sync when reconstructed in a fresh process -- an earlier
        # version of this class tried to rebuild the sklearn wrapper's
        # internal state by hand after `load()` and broke `predict()` with a
        # LightGBM-internal-version-dependent `ValueError`; storing only the
        # raw `Booster` sidesteps that fragility entirely.
        self._booster: lgb.Booster | None = None
        self.feature_names: list[str] | None = None
        self.best_iteration_: int | None = None
        self.evals_result_: dict[str, Any] = {}

    @property
    def is_fitted(self) -> bool:
        return self._booster is not None

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        group_train: np.ndarray,
        *,
        feature_names: list[str],
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        group_val: np.ndarray | None = None,
        checkpoint_dir: Path | None = None,
        checkpoint_every: int = 0,
        resume_from: Path | None = None,
    ) -> "LambdaRankModel":
        """Fit the ranker, with early stopping on `(X_val, y_val, group_val)` if given.

        Checkpointing: if `checkpoint_dir` and `checkpoint_every > 0` are
        both given, the in-progress `Booster` is written to
        `checkpoint_dir/checkpoint_iter_<N>.txt` every `checkpoint_every`
        boosting iterations (LightGBM's native model format, the same
        one `save`/`load` use). If training is interrupted, pass the
        latest such file as `resume_from` to continue from it rather
        than restarting -- LightGBM's `init_model` mechanism appends
        new trees on top of the loaded ones, so `n_estimators` in
        `self.config` is interpreted as "how many *additional* trees to
        grow" when resuming, matching LightGBM's own `init_model`
        semantics.

        Args:
            X_train: `(n_rows, n_features)` training feature matrix.
            y_train: `(n_rows,)` integer relevance grades.
            group_train: `(n_groups,)` group sizes summing to `n_rows`
                (LightGBM's ranking-group format -- see
                `feature_pipeline.FeatureMatrix.group_sizes`).
            feature_names: Column names, same order as `X_train`'s columns.
            X_val: Optional validation feature matrix, for early stopping.
            y_val: Optional validation labels.
            group_val: Optional validation group sizes.
            checkpoint_dir: Directory to periodically save the
                in-progress model to. Created if it does not exist.
                No checkpointing occurs if omitted.
            checkpoint_every: Save a checkpoint every this many
                boosting iterations. No checkpointing occurs if `<= 0`.
            resume_from: Path to a previously-saved checkpoint (or a
                model saved via `save()`) to resume training from.

        Returns:
            `self`, for chaining.

        Raises:
            ValueError: If exactly one of `X_val`/`y_val`/`group_val`
                is given (all three or none are required), if
                `feature_names` length does not match `X_train`'s
                column count, or if `checkpoint_every > 0` without a
                `checkpoint_dir`.
        """
        val_args = (X_val, y_val, group_val)
        if any(a is not None for a in val_args) and not all(a is not None for a in val_args):
            raise ValueError("X_val, y_val, and group_val must be given together or not at all.")
        if len(feature_names) != X_train.shape[1]:
            raise ValueError(f"feature_names has {len(feature_names)} entries but X_train has {X_train.shape[1]} columns.")
        if checkpoint_every > 0 and checkpoint_dir is None:
            raise ValueError("checkpoint_every > 0 requires checkpoint_dir to be given.")

        self.feature_names = list(feature_names)
        ranker = lgb.LGBMRanker(**self.config.to_lgbm_kwargs())

        fit_kwargs: dict[str, Any] = dict(
            X=X_train,
            y=y_train,
            group=group_train,
            feature_name=feature_names,
            categorical_feature=self.categorical_feature_indices or "auto",
        )
        if resume_from is not None:
            logger.info("Resuming training from checkpoint: %s", resume_from)
            fit_kwargs["init_model"] = str(resume_from)

        callbacks = [lgb.log_evaluation(period=0)]
        if X_val is not None:
            fit_kwargs["eval_set"] = [(X_val, y_val)]
            fit_kwargs["eval_group"] = [group_val]
            fit_kwargs["eval_at"] = list(self.config.eval_at)
            callbacks.append(lgb.early_stopping(stopping_rounds=self.config.early_stopping_rounds, verbose=False))
        if checkpoint_every > 0:
            assert checkpoint_dir is not None  # guaranteed by the ValueError check above
            callbacks.append(_make_checkpoint_callback(checkpoint_dir, checkpoint_every))
        fit_kwargs["callbacks"] = callbacks

        logger.info(
            "Fitting LGBMRanker: %d train rows / %d groups%s, %d features (%d categorical), n_estimators=%d",
            X_train.shape[0], len(group_train),
            f", {X_val.shape[0]} val rows / {len(group_val)} groups" if X_val is not None else " (no validation set)",
            X_train.shape[1], len(self.categorical_feature_indices), self.config.n_estimators,
        )
        ranker.fit(**fit_kwargs)
        self.best_iteration_ = getattr(ranker, "best_iteration_", None)
        self.evals_result_ = getattr(ranker, "evals_result_", {})
        self._booster = ranker.booster_
        logger.info("Fit complete. best_iteration_=%s", self.best_iteration_)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Score every row of `X`. Higher score == predicted more relevant.

        Args:
            X: `(n_rows, n_features)` feature matrix, same column
                order as the matrix `fit` was called with.

        Returns:
            `(n_rows,)` float scores.

        Raises:
            RuntimeError: If called before `fit` (or `load`).
        """
        if self._booster is None:
            raise RuntimeError("LambdaRankModel.predict() called before fit()/load(). Nothing to predict with.")
        # Deliberately omit `num_iteration`: a raw `Booster` that was fit with
        # an early-stopping callback already has its own internal
        # `best_iteration` recorded, and `Booster.predict`'s default
        # (`num_iteration=None`) already uses it automatically. Passing
        # `self.best_iteration_` explicitly here would be wrong whenever it
        # is legitimately `0` (the first iteration was the best one --
        # observed in this module's own smoke test on a toy fit): LightGBM
        # treats an explicit `num_iteration=0` as "predict with zero trees",
        # not "use the best iteration", which are different things only when
        # the best iteration happens to be the literal integer 0.
        return self._booster.predict(X)

    def save(self, path: Path) -> None:
        """Save the fitted booster (LightGBM's native text format) plus this project's own metadata.

        Args:
            path: Destination `.txt` model file. A sibling
                `<path>.meta.json` is written alongside it with the
                config, feature names, categorical indices, and
                best_iteration_, so `load` can fully reconstruct this
                object rather than just the raw booster.

        Raises:
            RuntimeError: If called before `fit`.
        """
        if self._booster is None:
            raise RuntimeError("LambdaRankModel.save() called before fit(). Nothing to save.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(path))
        meta = {
            "config": self.config.to_dict(),
            "categorical_feature_indices": self.categorical_feature_indices,
            "feature_names": self.feature_names,
            "best_iteration_": self.best_iteration_,
        }
        Path(f"{path}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("Saved model to %s (+ %s.meta.json)", path, path)

    @classmethod
    def load(cls, path: Path) -> "LambdaRankModel":
        """Load a model previously written by `save`.

        Args:
            path: The `.txt` model file passed to `save`.

        Returns:
            A `LambdaRankModel` with `is_fitted == True`, ready for `predict`.
        """
        meta = json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))
        config = ModelConfig.from_dict(meta["config"])
        instance = cls(config=config, categorical_feature_indices=meta["categorical_feature_indices"])
        instance._booster = lgb.Booster(model_file=str(path))
        instance.feature_names = meta["feature_names"]
        instance.best_iteration_ = meta["best_iteration_"]
        logger.info("Loaded model from %s (%d features)", path, instance._booster.num_feature())
        return instance
