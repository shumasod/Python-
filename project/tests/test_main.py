"""
app/main.py の lifespan（起動・終了）パスのテスト
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# lifespan startup / shutdown
# ============================================================

class TestLifespan:
    def test_startup_with_model_warm(self):
        """モデルウォームアップ成功パスが lifespan 内で実行されること"""
        from fastapi.testclient import TestClient
        from app.main import app

        mock_model = MagicMock()
        with patch("app.model.predict.get_model", return_value=mock_model), \
             patch("app.utils.notification.notify", new=AsyncMock()):
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200

    def test_startup_model_not_found_warning(self):
        """モデルファイルなし（FileNotFoundError）でもサーバーが起動すること"""
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.model.predict.get_model",
                   side_effect=FileNotFoundError("no model")), \
             patch("app.utils.notification.notify", new=AsyncMock()):
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200

    def test_startup_with_use_db_true(self, monkeypatch):
        """USE_DB=true のとき DB 接続プール初期化パスが通ること"""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "_USE_DB", True)
        mock_pool = AsyncMock()

        with patch("app.db.get_pool", new=AsyncMock(return_value=mock_pool)), \
             patch("app.db.close_pool", new=AsyncMock()), \
             patch("app.model.predict.get_model", side_effect=FileNotFoundError), \
             patch("app.utils.notification.notify", new=AsyncMock()):
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200

    def test_startup_db_connection_failure_ignored(self, monkeypatch):
        """USE_DB=true でDB接続失敗してもサーバーが起動すること"""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "_USE_DB", True)

        with patch("app.db.get_pool",
                   new=AsyncMock(side_effect=ConnectionRefusedError("db down"))), \
             patch("app.model.predict.get_model", side_effect=FileNotFoundError), \
             patch("app.utils.notification.notify", new=AsyncMock()):
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200

    def test_startup_notification_failure_ignored(self):
        """Slack 通知失敗でもサーバーが起動すること"""
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.model.predict.get_model", side_effect=FileNotFoundError), \
             patch("app.utils.notification.notify",
                   new=AsyncMock(side_effect=Exception("slack down"))):
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200

    def test_shutdown_with_use_db_true(self, monkeypatch):
        """USE_DB=true のとき shutdown で close_pool が呼ばれること"""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "_USE_DB", True)
        close_mock = AsyncMock()

        with patch("app.db.get_pool", new=AsyncMock()), \
             patch("app.db.close_pool", close_mock), \
             patch("app.model.predict.get_model", side_effect=FileNotFoundError), \
             patch("app.utils.notification.notify", new=AsyncMock()):
            with TestClient(app):
                pass  # context manager exit triggers shutdown

        close_mock.assert_called_once()
