"""
EnsemblePredictor のテスト
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.ensemble import EnsemblePredictor, ModelEntry
from tests.test_versioning import _PicklableModel


# ============================================================
# 初期化・バリデーション
# ============================================================

class TestEnsemblePredictorInit:
    def test_default_method_is_weighted(self):
        """デフォルトのアンサンブル手法は 'weighted' であること"""
        ens = EnsemblePredictor()
        assert ens.method == "weighted"

    def test_average_method_accepted(self):
        """'average' メソッドが受け入れられること"""
        ens = EnsemblePredictor(method="average")
        assert ens.method == "average"

    def test_invalid_method_raises(self):
        """無効な手法指定で ValueError が発生すること"""
        with pytest.raises(ValueError, match="average.*weighted"):
            EnsemblePredictor(method="stacking")

    def test_empty_models_list(self):
        """初期状態でモデルリストが空であること"""
        ens = EnsemblePredictor()
        assert ens._models == []


# ============================================================
# add_model
# ============================================================

class TestAddModel:
    def test_add_single_model(self):
        """モデルを1件追加できること"""
        ens = EnsemblePredictor()
        ens.add_model("m1", _PicklableModel(), weight=1.0)
        assert len(ens._models) == 1
        assert ens._models[0].name == "m1"

    def test_add_multiple_models(self):
        """複数モデルを追加できること"""
        ens = EnsemblePredictor()
        for i in range(3):
            ens.add_model(f"model_{i}", _PicklableModel(), weight=1.0)
        assert len(ens._models) == 3

    def test_cv_logloss_overrides_weight(self):
        """cv_logloss 指定時に weight が 1/logloss に設定されること"""
        ens = EnsemblePredictor()
        ens.add_model("m1", _PicklableModel(), cv_logloss=2.0)
        expected_weight = 1.0 / 2.0
        assert ens._models[0].weight == pytest.approx(expected_weight)

    def test_lower_logloss_gets_higher_weight(self):
        """Log Loss が小さいモデルに高い重みが付くこと"""
        ens = EnsemblePredictor()
        ens.add_model("good", _PicklableModel(), cv_logloss=1.0)
        ens.add_model("bad",  _PicklableModel(), cv_logloss=2.0)
        assert ens._models[0].weight > ens._models[1].weight


# ============================================================
# predict_proba
# ============================================================

class TestPredictProba:
    def _make_X(self, n_samples: int = 6) -> np.ndarray:
        return np.zeros((n_samples, 12))

    def test_no_models_raises(self):
        """モデルなしで RuntimeError が発生すること"""
        ens = EnsemblePredictor()
        with pytest.raises(RuntimeError, match="モデルが1つも"):
            ens.predict_proba(self._make_X())

    def test_output_shape(self):
        """出力の形状が (n_samples, 6) であること"""
        ens = EnsemblePredictor()
        ens.add_model("m1", _PicklableModel(), weight=1.0)
        proba = ens.predict_proba(self._make_X(6))
        assert proba.shape == (6, 6)

    def test_probabilities_sum_to_one(self):
        """各サンプルの確率の和が 1 であること"""
        ens = EnsemblePredictor()
        ens.add_model("m1", _PicklableModel(), weight=1.0)
        proba = ens.predict_proba(self._make_X(6))
        np.testing.assert_allclose(proba.sum(axis=1), np.ones(6), atol=1e-6)

    def test_average_method_equals_mean(self):
        """average メソッドの結果が各モデル出力の平均に等しいこと"""
        ens = EnsemblePredictor(method="average")
        ens.add_model("m1", _PicklableModel(), weight=1.0)
        ens.add_model("m2", _PicklableModel(), weight=1.0)
        X = self._make_X(4)
        proba = ens.predict_proba(X)
        # _PicklableModel は常に均一確率 → 平均しても同じ
        np.testing.assert_allclose(proba.sum(axis=1), np.ones(4), atol=1e-6)

    def test_single_model_same_as_direct_predict(self):
        """モデル1件の場合、直接呼び出し結果と一致すること"""
        model = _PicklableModel()
        ens = EnsemblePredictor()
        ens.add_model("only", model, weight=1.0)
        X = self._make_X(3)
        assert np.allclose(ens.predict_proba(X), model.predict_proba(X))

    def test_weighted_sum_is_normalized(self):
        """weighted モードで重みが正規化されること（確率の和=1）"""
        ens = EnsemblePredictor(method="weighted")
        ens.add_model("a", _PicklableModel(), weight=3.0)
        ens.add_model("b", _PicklableModel(), weight=7.0)
        proba = ens.predict_proba(self._make_X(6))
        np.testing.assert_allclose(proba.sum(axis=1), np.ones(6), atol=1e-6)


# ============================================================
# predict（ラベル出力）
# ============================================================

class TestPredict:
    def test_predict_returns_integer_labels(self):
        """predict が整数ラベル配列を返すこと"""
        ens = EnsemblePredictor()
        ens.add_model("m1", _PicklableModel(), weight=1.0)
        X = np.zeros((6, 12))
        labels = ens.predict(X)
        assert labels.dtype in (np.int32, np.int64, int) or np.issubdtype(labels.dtype, np.integer)
        assert labels.shape == (6,)

    def test_predict_values_in_range(self):
        """予測ラベルが 0〜5 の範囲であること"""
        ens = EnsemblePredictor()
        ens.add_model("m1", _PicklableModel(), weight=1.0)
        labels = ens.predict(np.zeros((12, 12)))
        assert all(0 <= lbl <= 5 for lbl in labels)


# ============================================================
# summary（smoke test）
# ============================================================

class TestSummary:
    def test_summary_runs_without_error(self, capsys):
        """summary() がエラーなく動作すること"""
        ens = EnsemblePredictor()
        ens.add_model("model_a", _PicklableModel(), weight=0.6, cv_logloss=None)
        ens.add_model("model_b", _PicklableModel(), cv_logloss=1.5)
        ens.summary()
        out = capsys.readouterr().out
        assert "model_a" in out
        assert "model_b" in out

    def test_summary_shows_method(self, capsys):
        """summary にアンサンブル手法が表示されること"""
        ens = EnsemblePredictor(method="average")
        ens.add_model("m", _PicklableModel(), weight=1.0)
        ens.summary()
        assert "average" in capsys.readouterr().out


# ============================================================
# ModelEntry dataclass
# ============================================================

class TestModelEntry:
    def test_model_entry_defaults(self):
        """ModelEntry のデフォルト値が正しいこと"""
        entry = ModelEntry(name="test", model=_PicklableModel())
        assert entry.weight == 1.0
        assert entry.cv_logloss is None
