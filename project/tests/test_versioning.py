"""
モデルバージョン管理のユニットテスト
実際のファイルI/Oを伴うため、tmp_path フィクスチャで隔離する
"""
import json
import pickle
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """テスト用 ModelRegistry（一時ディレクトリを使用）"""
    # MODEL_DIR を tmp_path に差し替える
    import app.model.versioning as ver_module
    monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

    from app.model.versioning import ModelRegistry
    return ModelRegistry()


class _PicklableModel:
    """pickle 可能なダミーモデル（MagicMock は pickle 不可）"""
    feature_importances_ = [1.0] * 12

    def predict_proba(self, X):
        import numpy as np
        return np.ones((len(X), 6)) / 6


@pytest.fixture
def mock_model():
    """pickle 可能なダミーモデル"""
    return _PicklableModel()


@pytest.fixture
def sample_metrics():
    return {
        "cv_logloss_mean": 1.234,
        "cv_logloss_std": 0.05,
        "cv_accuracy_mean": 0.28,
        "cv_accuracy_std": 0.02,
        "n_samples": 12000,
        "feature_columns": ["win_rate"] * 12,
    }


class TestModelRegistry:
    def test_register_creates_files(self, registry, mock_model, sample_metrics, tmp_path):
        """register() がPKLとJSONを生成することを確認"""
        version = registry.register(mock_model, sample_metrics, notes="テスト学習")
        versions_dir = tmp_path / "versions"
        assert (versions_dir / f"{version}.pkl").exists()
        assert (versions_dir / f"{version}_metrics.json").exists()

    def test_register_increments_sequence(self, registry, mock_model, sample_metrics):
        """同日に2回登録すると連番になることを確認"""
        v1 = registry.register(mock_model, sample_metrics)
        v2 = registry.register(mock_model, sample_metrics)
        assert v1 != v2
        assert v1.endswith("_1")
        assert v2.endswith("_2")

    def test_promote_copies_to_production(self, registry, mock_model, sample_metrics, tmp_path):
        """promote() が本番ファイルを更新することを確認"""
        import app.model.versioning as ver_module

        # PKLをダミーデータで作成（pickle.dump が通るオブジェクト）
        version = registry.register(mock_model, sample_metrics)

        # versions/xxx.pkl に実際のpickleファイルを作成
        versions_dir = tmp_path / "versions"
        pkl_path = versions_dir / f"{version}.pkl"
        with open(pkl_path, "wb") as f:
            pickle.dump({"dummy": True}, f)

        with patch.object(ver_module, "MODEL_DIR", tmp_path):
            registry.promote(version)

        prod_path = tmp_path / "boat_race_model.pkl"
        assert prod_path.exists()
        assert registry.get_production_version() == version

    def test_list_versions(self, registry, mock_model, sample_metrics):
        """登録数分のバージョン一覧が返ることを確認"""
        registry.register(mock_model, sample_metrics)
        registry.register(mock_model, sample_metrics)
        versions = registry.list_versions()
        assert len(versions) == 2

    def test_notes_persisted(self, registry, mock_model, sample_metrics):
        """備考が保存されることを確認"""
        registry.register(mock_model, sample_metrics, notes="特別なデータ")
        versions = registry.list_versions()
        assert versions[0]["notes"] == "特別なデータ"

    def test_registry_json_created(self, registry, mock_model, sample_metrics, tmp_path):
        """registry.json が生成されることを確認"""
        registry.register(mock_model, sample_metrics)
        assert (tmp_path / "registry.json").exists()

    def test_cleanup_removes_old_versions(self, registry, mock_model, sample_metrics, tmp_path):
        """cleanup_old_versions() が古いバージョンを削除することを確認"""
        versions_dir = tmp_path / "versions"

        for _ in range(5):
            version = registry.register(mock_model, sample_metrics)
            pkl_path = versions_dir / f"{version}.pkl"
            with open(pkl_path, "wb") as f:
                pickle.dump({}, f)

        deleted = registry.cleanup_old_versions(keep=3)
        assert len(registry.list_versions()) <= 3

    def test_promote_cache_reset_exception_swallowed(self, registry, mock_model, sample_metrics):
        """promote() で _cached_model リセット時に例外が出ても無視されること"""
        import sys
        version = registry.register(mock_model, sample_metrics)

        with patch.dict(sys.modules, {"app.model.predict": None}):
            registry.promote(version)  # 例外にならないこと

    def test_load_version_not_found_raises(self, registry):
        """load_version() でファイルがないとき FileNotFoundError を投げること"""
        with pytest.raises(FileNotFoundError):
            registry.load_version("nonexistent_version_xyz")

    def test_load_production_calls_load_model(self, registry, mock_model, sample_metrics, tmp_path, monkeypatch):
        """load_production() が本番モデルを読み込むこと"""
        import app.model.train as train_module
        monkeypatch.setattr(train_module, "MODEL_DIR", tmp_path)

        version = registry.register(mock_model, sample_metrics)
        registry.promote(version)

        model = registry.load_production()
        assert model is not None
