"""
app/data/loader.py のテスト
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.features import FEATURE_COLUMNS


# ============================================================
# テスト用 CSV ヘルパー
# ============================================================

def _write_valid_csv(path: Path, n_rows: int = 24) -> None:
    """必須カラムをすべて持つ最小 CSV を作成する"""
    data = {col: [0.0] * n_rows for col in FEATURE_COLUMNS}
    data["label"] = list(range(1, 7)) * (n_rows // 6)
    pd.DataFrame(data).to_csv(path, index=False, encoding="utf-8")


def _write_missing_col_csv(path: Path) -> None:
    """必須カラムが欠けた不正 CSV を作成する"""
    df = pd.DataFrame({"dummy": [1, 2, 3]})
    df.to_csv(path, index=False, encoding="utf-8")


# ============================================================
# load_training_data
# ============================================================

class TestLoadTrainingData:
    def test_use_sample_returns_dataframe(self):
        """use_sample=True でサンプルデータが返ること"""
        from app.data.loader import load_training_data
        df = load_training_data(use_sample=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_use_sample_has_feature_columns(self):
        """サンプルデータに FEATURE_COLUMNS が含まれること"""
        from app.data.loader import load_training_data
        df = load_training_data(use_sample=True)
        for col in FEATURE_COLUMNS:
            assert col in df.columns

    def test_use_sample_has_label(self):
        """サンプルデータに label カラムが含まれること"""
        from app.data.loader import load_training_data
        df = load_training_data(use_sample=True)
        assert "label" in df.columns

    def test_load_from_csv(self, tmp_path):
        """既存 CSV ファイルを正常に読み込めること"""
        csv_path = tmp_path / "training.csv"
        _write_valid_csv(csv_path)

        from app.data.loader import load_training_data
        df = load_training_data(file_path=str(csv_path))
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 24

    def test_nonexistent_file_raises(self, tmp_path):
        """存在しないファイルで FileNotFoundError が発生すること"""
        from app.data.loader import load_training_data
        with pytest.raises(FileNotFoundError, match="見つかりません"):
            load_training_data(file_path=str(tmp_path / "nope.csv"))

    def test_missing_columns_raises(self, tmp_path):
        """必須カラム不足で ValueError が発生すること"""
        csv_path = tmp_path / "bad.csv"
        _write_missing_col_csv(csv_path)

        from app.data.loader import load_training_data
        with pytest.raises(ValueError, match="必須カラム"):
            load_training_data(file_path=str(csv_path))

    def test_default_path_raises_when_missing(self, monkeypatch, tmp_path):
        """file_path 未指定かつデフォルトパスが存在しない場合に FileNotFoundError"""
        import app.data.loader as loader_mod
        monkeypatch.setattr(loader_mod, "DATA_DIR", tmp_path / "nodir")

        from app.data.loader import load_training_data
        with pytest.raises(FileNotFoundError):
            load_training_data()

    def test_returned_df_preprocessed(self, tmp_path):
        """返される DataFrame が preprocess_dataframe 済みであること（欠損なし）"""
        csv_path = tmp_path / "training.csv"
        _write_valid_csv(csv_path, n_rows=12)

        from app.data.loader import load_training_data
        df = load_training_data(file_path=str(csv_path))
        assert df.isnull().sum().sum() == 0


# ============================================================
# save_training_data
# ============================================================

class TestSaveTrainingData:
    def test_creates_csv(self, tmp_path):
        """CSV ファイルが作成されること"""
        from app.data.loader import save_training_data
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        out = tmp_path / "out.csv"
        save_training_data(df, file_path=str(out))
        assert out.exists()

    def test_roundtrip(self, tmp_path):
        """保存 → 読み込みで同じ行数が復元されること"""
        from app.data.loader import save_training_data
        df = pd.DataFrame({"x": range(10)})
        out = tmp_path / "rt.csv"
        save_training_data(df, file_path=str(out))
        loaded = pd.read_csv(out)
        assert len(loaded) == 10

    def test_default_path_used(self, monkeypatch, tmp_path):
        """file_path 未指定のとき DATA_DIR/training.csv に保存されること"""
        import app.data.loader as loader_mod
        monkeypatch.setattr(loader_mod, "DATA_DIR", tmp_path)

        from app.data.loader import save_training_data
        df = pd.DataFrame({"z": [99]})
        save_training_data(df)
        assert (tmp_path / "training.csv").exists()
