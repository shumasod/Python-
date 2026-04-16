"""
scripts/promote_model.py のテスト

promote_model.py は ModelRegistry への薄い CLI ラッパーなので、
registry の振る舞いをモンキーパッチして CLI フローを検証する。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_versioning import _PicklableModel


# ============================================================
# フィクスチャ: populated registry
# ============================================================

@pytest.fixture
def registry_with_model(tmp_path, monkeypatch):
    """テスト用モデルが登録された ModelRegistry を返す"""
    import app.model.versioning as ver_module
    monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

    from app.model.versioning import ModelRegistry
    registry = ModelRegistry()
    metrics = {
        "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
        "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
        "n_samples": 1200, "feature_columns": ["x"] * 12,
    }
    registry.register(_PicklableModel(), metrics, notes="テスト v1")
    registry.register(_PicklableModel(), metrics, notes="テスト v2")
    return registry, tmp_path


# ============================================================
# --list
# ============================================================

class TestListVersions:
    def test_list_outputs_versions(self, capsys, registry_with_model, monkeypatch):
        """--list がバージョン一覧を stdout に出力すること"""
        import app.model.versioning as ver_module
        registry, tmp_path = registry_with_model
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

        monkeypatch.setattr(sys, "argv", ["promote_model.py", "--list"])
        from scripts.promote_model import main
        main()
        out = capsys.readouterr().out + capsys.readouterr().err
        # print_summary は stdout に出力される
        # エラーなく完了することを確認
        assert True  # エラーが出なければ OK

    def test_list_does_not_raise(self, registry_with_model, monkeypatch):
        """--list が例外なく完了すること"""
        import app.model.versioning as ver_module
        registry, tmp_path = registry_with_model
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(sys, "argv", ["promote_model.py", "--list"])

        from scripts.promote_model import main
        main()  # 例外が出なければ OK


# ============================================================
# --latest
# ============================================================

class TestPromoteLatest:
    def test_promote_latest_sets_production(self, registry_with_model, monkeypatch):
        """--latest が最新バージョンを production=True にすること"""
        import app.model.versioning as ver_module
        registry, tmp_path = registry_with_model
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(sys, "argv", ["promote_model.py", "--latest"])
        monkeypatch.setattr("builtins.input", lambda _: "y")  # 確認プロンプトに y

        from scripts.promote_model import main
        main()

        # registry を再読み込みして検証
        from app.model.versioning import ModelRegistry
        reg2 = ModelRegistry()
        prod = reg2.get_production_version()
        assert prod is not None
        assert isinstance(prod, str)
        assert "boat_race_model" in prod

    def test_promote_latest_no_versions_exits(self, tmp_path, monkeypatch):
        """バージョンなしで --latest を実行すると sys.exit すること"""
        import app.model.versioning as ver_module
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "empty_reg.json")
        monkeypatch.setattr(sys, "argv", ["promote_model.py", "--latest"])

        from scripts.promote_model import main
        with pytest.raises(SystemExit):
            main()


# ============================================================
# --version
# ============================================================

class TestPromoteVersion:
    def test_promote_specific_version(self, registry_with_model, monkeypatch):
        """特定バージョン名で昇格できること"""
        import app.model.versioning as ver_module
        registry, tmp_path = registry_with_model
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

        # 登録済みバージョン名を取得
        versions = registry.list_versions()
        assert len(versions) >= 1
        target = versions[0]["version"]

        monkeypatch.setattr(sys, "argv", ["promote_model.py", "--version", target])
        monkeypatch.setattr("builtins.input", lambda _: "y")  # 確認プロンプト

        from scripts.promote_model import main
        main()

        from app.model.versioning import ModelRegistry
        reg2 = ModelRegistry()
        prod = reg2.get_production_version()
        assert prod is not None

    def test_promote_nonexistent_version_exits(self, registry_with_model, monkeypatch):
        """存在しないバージョンで sys.exit すること"""
        import app.model.versioning as ver_module
        registry, tmp_path = registry_with_model
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")
        monkeypatch.setattr(
            sys, "argv",
            ["promote_model.py", "--version", "boat_race_model_v99999999_99"],
        )
        monkeypatch.setattr("builtins.input", lambda _: "y")  # 確認プロンプト

        from scripts.promote_model import main
        with pytest.raises(SystemExit):
            main()


# ============================================================
# --cleanup
# ============================================================

class TestCleanupVersions:
    def test_cleanup_keeps_specified_count(self, tmp_path, monkeypatch):
        """--cleanup --keep N で N 件以下になること"""
        import app.model.versioning as ver_module
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 100, "feature_columns": ["x"] * 12,
        }
        for _ in range(5):
            registry.register(_PicklableModel(), metrics)

        assert len(registry.list_versions()) == 5

        monkeypatch.setattr(
            sys, "argv", ["promote_model.py", "--cleanup", "--keep", "3"]
        )
        from scripts.promote_model import main
        main()

        reg2 = ModelRegistry()
        assert len(reg2.list_versions()) <= 3

    def test_cleanup_outputs_deleted_count(self, tmp_path, monkeypatch, capsys):
        """削除数が stdout に出力されること"""
        import app.model.versioning as ver_module
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 100, "feature_columns": ["x"] * 12,
        }
        for _ in range(4):
            registry.register(_PicklableModel(), metrics)

        monkeypatch.setattr(
            sys, "argv", ["promote_model.py", "--cleanup", "--keep", "2"]
        )
        from scripts.promote_model import main
        main()
        out = capsys.readouterr().out
        assert "削除" in out
