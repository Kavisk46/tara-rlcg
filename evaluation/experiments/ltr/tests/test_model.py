"""Unit tests for `model.py`: `ModelConfig` validation and `LambdaRankModel`'s fit/predict/save/load/checkpoint contract.

Uses small, synthetic, seeded random feature matrices throughout --
this is testing *code correctness* (does fit/predict/save/load/resume
behave as documented), never reporting or implying a real ranking
-quality result. See `README.md`'s "Current dataset status" for why no
real experiment result exists yet.
"""
from __future__ import annotations

import numpy as np
import pytest

from evaluation.experiments.ltr.model import LambdaRankModel, ModelConfig


def _toy_data(seed: int = 0, n_groups: int = 4, group_size: int = 5, n_features: int = 6):
    rng = np.random.default_rng(seed)
    n_rows = n_groups * group_size
    X = rng.random((n_rows, n_features))
    y = rng.integers(0, 4, size=n_rows)
    group = np.full(n_groups, group_size)
    names = [f"f{i}" for i in range(n_features)]
    return X, y, group, names


class TestModelConfig:
    def test_defaults_are_valid(self) -> None:
        ModelConfig()  # should not raise

    def test_rejects_invalid_num_leaves(self) -> None:
        with pytest.raises(ValueError):
            ModelConfig(num_leaves=1)

    def test_rejects_invalid_learning_rate(self) -> None:
        with pytest.raises(ValueError):
            ModelConfig(learning_rate=0.0)
        with pytest.raises(ValueError):
            ModelConfig(learning_rate=1.5)

    def test_dict_roundtrip_preserves_tuples(self) -> None:
        cfg = ModelConfig(eval_at=(1, 2, 3), label_gain=(0.0, 1.0, 3.0, 7.0))
        restored = ModelConfig.from_dict(cfg.to_dict())
        assert restored.eval_at == (1, 2, 3)
        assert restored.label_gain == (0.0, 1.0, 3.0, 7.0)

    def test_to_lgbm_kwargs_excludes_early_stopping_rounds(self) -> None:
        kwargs = ModelConfig().to_lgbm_kwargs()
        assert "early_stopping_rounds" not in kwargs
        assert "n_estimators" in kwargs


class TestLambdaRankModelFitPredict:
    def test_not_fitted_raises_on_predict(self) -> None:
        model = LambdaRankModel()
        with pytest.raises(RuntimeError):
            model.predict(np.zeros((1, 3)))

    def test_fit_without_validation_set(self) -> None:
        X, y, group, names = _toy_data()
        model = LambdaRankModel(ModelConfig(n_estimators=5))
        model.fit(X, y, group, feature_names=names)
        assert model.is_fitted
        preds = model.predict(X)
        assert preds.shape == (X.shape[0],)
        assert np.all(np.isfinite(preds))

    def test_fit_with_validation_set_enables_early_stopping(self) -> None:
        X, y, group, names = _toy_data()
        model = LambdaRankModel(ModelConfig(n_estimators=50, early_stopping_rounds=3))
        model.fit(X, y, group, feature_names=names, X_val=X, y_val=y, group_val=group)
        assert model.best_iteration_ is not None

    def test_partial_validation_args_raise(self) -> None:
        X, y, group, names = _toy_data()
        model = LambdaRankModel(ModelConfig(n_estimators=5))
        with pytest.raises(ValueError):
            model.fit(X, y, group, feature_names=names, X_val=X)  # y_val/group_val missing

    def test_feature_name_length_mismatch_raises(self) -> None:
        X, y, group, _ = _toy_data()
        model = LambdaRankModel(ModelConfig(n_estimators=5))
        with pytest.raises(ValueError):
            model.fit(X, y, group, feature_names=["only_one_name"])


class TestLambdaRankModelSaveLoad:
    def test_save_before_fit_raises(self, tmp_path) -> None:
        model = LambdaRankModel()
        with pytest.raises(RuntimeError):
            model.save(tmp_path / "model.txt")

    def test_save_load_roundtrip_predictions_match_exactly(self, tmp_path) -> None:
        X, y, group, names = _toy_data()
        model = LambdaRankModel(ModelConfig(n_estimators=10))
        model.fit(X, y, group, feature_names=names)
        preds_before = model.predict(X)

        path = tmp_path / "model.txt"
        model.save(path)
        assert path.is_file()
        assert (tmp_path / "model.txt.meta.json").is_file()

        loaded = LambdaRankModel.load(path)
        preds_after = loaded.predict(X)
        np.testing.assert_allclose(preds_before, preds_after)
        assert loaded.feature_names == names

    def test_loaded_model_config_matches_original(self, tmp_path) -> None:
        original_config = ModelConfig(n_estimators=7, num_leaves=8, max_depth=3)
        X, y, group, names = _toy_data()
        model = LambdaRankModel(original_config)
        model.fit(X, y, group, feature_names=names)
        path = tmp_path / "model.txt"
        model.save(path)

        loaded = LambdaRankModel.load(path)
        assert loaded.config.num_leaves == 8
        assert loaded.config.max_depth == 3


class TestCheckpointing:
    def test_checkpoint_every_without_dir_raises(self) -> None:
        X, y, group, names = _toy_data()
        model = LambdaRankModel(ModelConfig(n_estimators=10))
        with pytest.raises(ValueError):
            model.fit(X, y, group, feature_names=names, checkpoint_every=2)

    def test_checkpoints_are_written_at_expected_iterations(self, tmp_path) -> None:
        X, y, group, names = _toy_data(n_groups=6, group_size=8)
        model = LambdaRankModel(ModelConfig(n_estimators=10, early_stopping_rounds=1000))
        ckpt_dir = tmp_path / "ckpts"
        model.fit(X, y, group, feature_names=names, checkpoint_dir=ckpt_dir, checkpoint_every=3)
        checkpoints = sorted(ckpt_dir.glob("checkpoint_iter_*.txt"))
        assert len(checkpoints) >= 3
        assert (ckpt_dir / "checkpoint_iter_3.txt").is_file()
        assert (ckpt_dir / "checkpoint_iter_6.txt").is_file()

    def test_resume_from_checkpoint_adds_trees(self, tmp_path) -> None:
        X, y, group, names = _toy_data(n_groups=6, group_size=8)
        ckpt_dir = tmp_path / "ckpts"
        model = LambdaRankModel(ModelConfig(n_estimators=9, early_stopping_rounds=1000))
        model.fit(X, y, group, feature_names=names, checkpoint_dir=ckpt_dir, checkpoint_every=3)
        checkpoint_at_3 = ckpt_dir / "checkpoint_iter_3.txt"
        assert checkpoint_at_3.is_file()

        resumed = LambdaRankModel(ModelConfig(n_estimators=4, early_stopping_rounds=1000))
        resumed.fit(X, y, group, feature_names=names, resume_from=checkpoint_at_3)
        # 3 trees from the checkpoint + 4 additional == 7 total.
        assert resumed._booster.num_trees() == 7  # noqa: SLF001 -- test is allowed to inspect internal state
