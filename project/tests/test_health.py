"""
詳細ヘルスチェックエンドポイントのテスト
"""
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthDetail:
    def test_returns_200(self):
        """GET /health/detail が 200 を返すことを確認"""
        resp = client.get("/health/detail")
        assert resp.status_code == 200

    def test_response_keys(self):
        """必須フィールドが含まれることを確認"""
        resp = client.get("/health/detail")
        body = resp.json()
        assert "status" in body
        assert "uptime_sec" in body
        assert "checks" in body

    def test_checks_has_model(self):
        """checks.model フィールドが含まれることを確認"""
        resp = client.get("/health/detail")
        assert "model" in resp.json()["checks"]

    def test_checks_has_db(self):
        """checks.db フィールドが含まれることを確認（USE_DB=false なら disabled）"""
        resp = client.get("/health/detail")
        assert "db" in resp.json()["checks"]

    def test_checks_has_disk(self):
        """checks.disk フィールドが含まれることを確認"""
        resp = client.get("/health/detail")
        assert "disk" in resp.json()["checks"]

    def test_status_values(self):
        """status が ok/degraded/down のいずれかであることを確認"""
        resp = client.get("/health/detail")
        assert resp.json()["status"] in ("ok", "degraded", "down")

    def test_uptime_positive(self):
        """uptime_sec が正の整数であることを確認"""
        resp = client.get("/health/detail")
        assert resp.json()["uptime_sec"] >= 0

    def test_model_warn_when_missing(self, tmp_path, monkeypatch):
        """モデルファイルが存在しない場合 warn ステータスになることを確認"""
        import app.api.health as health_module
        monkeypatch.setattr(
            health_module, "_check_model",
            lambda: {"status": "warn", "message": "モデルファイルが見つかりません"}
        )
        resp = client.get("/health/detail")
        # degraded になっていることを確認
        assert resp.json()["status"] == "degraded"

    def test_use_db_true_path(self, monkeypatch):
        """USE_DB=true のとき _check_db が呼ばれ db キーに結果が入ること"""
        import app.api.health as health_module
        monkeypatch.setenv("USE_DB", "true")
        monkeypatch.setattr(
            health_module, "_check_db",
            AsyncMock(return_value={"status": "ok", "latency_ms": 5}),
        )
        resp = client.get("/health/detail")
        assert resp.status_code == 200
        assert resp.json()["checks"]["db"]["status"] == "ok"

    def test_use_db_true_db_error_causes_degraded(self, monkeypatch):
        """USE_DB=true で DB 接続エラーのとき status が degraded になること"""
        import app.api.health as health_module
        monkeypatch.setenv("USE_DB", "true")
        monkeypatch.setattr(
            health_module, "_check_db",
            AsyncMock(return_value={"status": "error", "message": "connection refused"}),
        )
        resp = client.get("/health/detail")
        assert resp.json()["status"] == "degraded"
        assert resp.json()["checks"]["db"]["status"] == "error"


class TestCheckModelHelper:
    def test_model_not_found_returns_warn(self, tmp_path, monkeypatch):
        """models/boat_race_model.pkl が存在しないとき warn を返すこと"""
        import app.api.health as health_module

        class _FakePath:
            def __init__(self, p):
                self._p = Path(tmp_path) / str(p)

            def __truediv__(self, other):
                result = _FakePath.__new__(_FakePath)
                result._p = self._p / other
                return result

            def exists(self):
                return False  # モデルは常に存在しない

            def stat(self):
                return self._p.stat()

        monkeypatch.setattr(health_module, "Path", _FakePath)
        result = health_module._check_model()
        assert result["status"] == "warn"

    def test_check_model_exception_returns_error(self, monkeypatch):
        """_check_model が例外を飲み込んで error を返すこと"""
        import app.api.health as health_module

        class _BrokenPath:
            def __init__(self, p): pass
            def __truediv__(self, other):
                result = _BrokenPath.__new__(_BrokenPath)
                return result
            def exists(self): return True
            def stat(self): raise OSError("disk error")

        monkeypatch.setattr(health_module, "Path", _BrokenPath)
        result = health_module._check_model()
        assert result["status"] == "error"


class TestCheckDbHelper:
    def test_check_db_success(self):
        """_check_db がコネクション成功のとき ok を返すこと"""
        import asyncio
        import app.api.health as health_module

        conn_mock = AsyncMock()
        conn_mock.fetchval = AsyncMock(return_value=1)

        class _FakeCtx:
            async def __aenter__(self): return conn_mock
            async def __aexit__(self, *_): pass

        with patch("app.db.get_connection", return_value=_FakeCtx()):
            result = asyncio.run(health_module._check_db())

        assert result["status"] == "ok"
        assert "latency_ms" in result

    def test_check_db_error(self):
        """_check_db が接続失敗のとき error を返すこと"""
        import asyncio
        import app.api.health as health_module

        with patch(
            "app.db.get_connection",
            side_effect=ConnectionRefusedError("refused"),
        ):
            result = asyncio.run(health_module._check_db())

        assert result["status"] == "error"
        assert "message" in result


class TestCheckDiskHelper:
    def test_check_disk_missing_dirs(self, tmp_path, monkeypatch):
        """ディレクトリが存在しないとき 'directory not found' が入ること"""
        import app.api.health as health_module

        # Path を tmp_path 以下の存在しないパスに差し替え
        orig_path = health_module.Path

        class _P:
            def __init__(self, p):
                self._p = orig_path(p)
                self._exists = False

            def exists(self):
                return self._exists

            def rglob(self, pat):
                return []

        monkeypatch.setattr(health_module, "Path", _P)
        result = health_module._check_disk()
        assert result.get("models") == "directory not found"
        assert result.get("data") == "directory not found"

    def test_check_disk_has_root_free_gb(self):
        """_check_disk に root_free_gb キーが含まれること"""
        import app.api.health as health_module
        result = health_module._check_disk()
        assert "root_free_gb" in result


class TestHealthDetail:
    def test_returns_200(self):
        """GET /health/detail が 200 を返すことを確認"""
        resp = client.get("/health/detail")
        assert resp.status_code == 200

    def test_response_keys(self):
        """必須フィールドが含まれることを確認"""
        resp = client.get("/health/detail")
        body = resp.json()
        assert "status" in body
        assert "uptime_sec" in body
        assert "checks" in body

    def test_checks_has_model(self):
        """checks.model フィールドが含まれることを確認"""
        resp = client.get("/health/detail")
        assert "model" in resp.json()["checks"]

    def test_checks_has_db(self):
        """checks.db フィールドが含まれることを確認（USE_DB=false なら disabled）"""
        resp = client.get("/health/detail")
        assert "db" in resp.json()["checks"]

    def test_checks_has_disk(self):
        """checks.disk フィールドが含まれることを確認"""
        resp = client.get("/health/detail")
        assert "disk" in resp.json()["checks"]

    def test_status_values(self):
        """status が ok/degraded/down のいずれかであることを確認"""
        resp = client.get("/health/detail")
        assert resp.json()["status"] in ("ok", "degraded", "down")

    def test_uptime_positive(self):
        """uptime_sec が正の整数であることを確認"""
        resp = client.get("/health/detail")
        assert resp.json()["uptime_sec"] >= 0

    def test_model_warn_when_missing(self, tmp_path, monkeypatch):
        """モデルファイルが存在しない場合 warn ステータスになることを確認"""
        import app.api.health as health_module
        monkeypatch.setattr(
            health_module, "_check_model",
            lambda: {"status": "warn", "message": "モデルファイルが見つかりません"}
        )
        resp = client.get("/health/detail")
        # degraded になっていることを確認
        assert resp.json()["status"] == "degraded"
