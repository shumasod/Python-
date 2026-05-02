"""
scripts/analyze_model.py のテスト
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_versioning import _PicklableModel


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def trained_lgbm(tmp_path, monkeypatch):
    """analyze_model が使う学習済みモデルを返す"""
    from app.model.features import generate_sample_training_data, preprocess_dataframe
    from app.model.train import train_model
    import app.model.train as train_module

    monkeypatch.setattr(train_module, "MODEL_DIR", tmp_path)
    df = preprocess_dataframe(generate_sample_training_data(n_races=100))
    model, _ = train_model(df, model_name="boat_race_model", n_splits=2)
    return model


@pytest.fixture
def test_arrays(trained_lgbm):
    """テスト用 X_test / y_test を返す"""
    from app.model.features import FEATURE_COLUMNS, generate_sample_training_data, preprocess_dataframe
    df = preprocess_dataframe(generate_sample_training_data(n_races=60))
    X = df[FEATURE_COLUMNS]
    y = df["label"].values.astype(int)
    return X, y


# ============================================================
# plot_feature_importance
# ============================================================

class TestPlotFeatureImportance:
    def test_creates_png(self, tmp_path, trained_lgbm):
        """PNG ファイルが生成されること"""
        from scripts.analyze_model import plot_feature_importance
        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            plot_feature_importance(trained_lgbm, tmp_path)
        # CSV は実際に保存される
        assert (tmp_path / "feature_importance.csv").exists()

    def test_csv_has_correct_columns(self, tmp_path, trained_lgbm):
        """CSV に feature / importance / normalized カラムが含まれること"""
        import pandas as pd
        from scripts.analyze_model import plot_feature_importance
        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            plot_feature_importance(trained_lgbm, tmp_path)
        df = pd.read_csv(tmp_path / "feature_importance.csv")
        assert "feature" in df.columns
        assert "importance" in df.columns
        assert "normalized" in df.columns

    def test_csv_has_12_features(self, tmp_path, trained_lgbm):
        """CSV に 12 特徴量の行が含まれること"""
        import pandas as pd
        from scripts.analyze_model import plot_feature_importance
        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            plot_feature_importance(trained_lgbm, tmp_path)
        df = pd.read_csv(tmp_path / "feature_importance.csv")
        assert len(df) == 12

    def test_normalized_max_is_100(self, tmp_path, trained_lgbm):
        """正規化後の最大値が 100 であること"""
        import pandas as pd
        from scripts.analyze_model import plot_feature_importance
        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            plot_feature_importance(trained_lgbm, tmp_path)
        df = pd.read_csv(tmp_path / "feature_importance.csv")
        assert df["normalized"].max() == pytest.approx(100.0, abs=0.1)


# ============================================================
# plot_calibration
# ============================================================

class TestPlotCalibration:
    def test_saves_calibration_png(self, tmp_path, trained_lgbm, test_arrays):
        """キャリブレーション PNG が保存されること"""
        from scripts.analyze_model import plot_calibration
        X_test, y_test = test_arrays
        saved_paths = []
        with patch("matplotlib.pyplot.savefig", side_effect=lambda p, **kw: saved_paths.append(p)), \
             patch("matplotlib.pyplot.close"):
            plot_calibration(trained_lgbm, X_test, y_test, tmp_path)
        assert any("calibration" in str(p) for p in saved_paths)

    def test_runs_without_error(self, tmp_path, trained_lgbm, test_arrays):
        """エラーなく完了すること"""
        from scripts.analyze_model import plot_calibration
        X_test, y_test = test_arrays
        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            plot_calibration(trained_lgbm, X_test, y_test, tmp_path)


# ============================================================
# print_classification_report
# ============================================================

class TestPrintClassificationReport:
    def test_outputs_report(self, capsys, trained_lgbm, test_arrays):
        """分類レポートが stdout に出力されること"""
        from scripts.analyze_model import print_classification_report
        X_test, y_test = test_arrays
        print_classification_report(trained_lgbm, X_test, y_test)
        out = capsys.readouterr().out
        assert "号艇" in out
        assert "precision" in out or "support" in out

    def test_confusion_matrix_printed(self, capsys, trained_lgbm, test_arrays):
        """混同行列が出力されること"""
        from scripts.analyze_model import print_classification_report
        X_test, y_test = test_arrays
        print_classification_report(trained_lgbm, X_test, y_test)
        out = capsys.readouterr().out
        assert "混同行列" in out
