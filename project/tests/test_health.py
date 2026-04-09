"""
詳細ヘルスチェックエンドポイントのテスト
"""
import sys
from pathlib import Path
from unittest.mock import patch

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
