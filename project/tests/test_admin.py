"""
Admin API エンドポイントのテスト
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import verify_api_key

app.dependency_overrides[verify_api_key] = lambda: "test-key"
client = TestClient(app)


# ============================================================
# GET /admin/status
# ============================================================

class TestAdminStatus:
    def test_status_ok(self):
        """/admin/status が 200 を返すこと"""
        resp = client.get("/api/v1/admin/status")
        assert resp.status_code == 200

    def test_status_structure(self):
        """必要フィールドが含まれること"""
        resp = client.get("/api/v1/admin/status")
        body = resp.json()
        assert "status" in body
        assert "n_registered_versions" in body
        assert "ab_test_active" in body
        assert "shadow_active" in body
        assert "prediction_store" in body


# ============================================================
# GET /admin/models
# ============================================================

class TestAdminModels:
    def test_models_returns_list(self):
        """/admin/models がリストを返すこと"""
        resp = client.get("/api/v1/admin/models")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_models_with_registered_version(self, tmp_path, monkeypatch):
        """モデル登録後に一覧に含まれること"""
        import app.model.versioning as ver_module
        monkeypatch.setattr(ver_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_module, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.model.versioning import ModelRegistry
        # test_versioning.py と同じ _PicklableModel を再利用
        from tests.test_versioning import _PicklableModel

        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 1200, "feature_columns": ["x"] * 12,
        }
        registry.register(_PicklableModel(), metrics, notes="テスト")

        resp = client.get("/api/v1/admin/models")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1


# ============================================================
# POST /admin/models/promote
# ============================================================

class TestAdminPromote:
    def test_promote_nonexistent_version_returns_404(self):
        """存在しないバージョンの昇格で 404 が返ること"""
        resp = client.post(
            "/api/v1/admin/models/promote",
            json={"version": "boat_race_model_v99999999_1"},
        )
        assert resp.status_code == 404

    def test_promote_missing_body_returns_422(self):
        """ボディなしで 422 が返ること"""
        resp = client.post("/api/v1/admin/models/promote", json={})
        assert resp.status_code == 422


# ============================================================
# GET /admin/drift
# ============================================================

class TestAdminDrift:
    def test_drift_no_reports(self, tmp_path, monkeypatch):
        """ドリフトレポートがない場合もエラーにならないこと"""
        import app.api.admin as admin_module
        from pathlib import Path as P

        resp = client.get("/api/v1/admin/drift")
        # 200 または空 dict を返す
        assert resp.status_code == 200

    def test_drift_with_report(self, tmp_path, monkeypatch):
        """ドリフトレポートがある場合に内容が返ること"""
        import app.api.admin as admin_module

        # ダミーレポートファイルを作成
        report_dir = tmp_path / "drift_reports"
        report_dir.mkdir()
        report = {
            "checked_at": "2026-04-12T00:00:00+00:00",
            "n_current": 100,
            "needs_retraining": False,
            "feature_results": [],
        }
        (report_dir / "report_20260412.json").write_text(
            json.dumps(report), encoding="utf-8"
        )

        # モンキーパッチで Path を差し替え
        original_path = admin_module.Path

        class MockPath:
            def __init__(self, p):
                if str(p) == "data/drift_reports":
                    self._path = report_dir
                else:
                    self._path = original_path(p)

            def __truediv__(self, other):
                return self._path / other

            def exists(self):
                return self._path.exists()

            def glob(self, pattern):
                return self._path.glob(pattern)

        monkeypatch.setattr(admin_module, "Path", MockPath)
        resp = client.get("/api/v1/admin/drift")
        assert resp.status_code == 200


# ============================================================
# GET /admin/ab-test
# ============================================================

class TestAdminAbTest:
    def test_ab_test_returns_list(self):
        """/admin/ab-test がリストを返すこと"""
        resp = client.get("/api/v1/admin/ab-test")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ============================================================
# GET /admin/shadow
# ============================================================

class TestAdminShadow:
    def test_shadow_stats_no_log(self, tmp_path, monkeypatch):
        """シャドウログなしでも 200 が返ること"""
        import app.api.admin as admin_module

        class _MockPath:
            def __init__(self, p):
                if "shadow_logs" in str(p):
                    self._path = tmp_path / "shadow_logs"
                else:
                    from pathlib import Path as P
                    self._path = P(p)

            def __truediv__(self, other):
                return self._path / other

            def exists(self):
                return self._path.exists()

        monkeypatch.setattr(admin_module, "Path", _MockPath)
        resp = client.get("/api/v1/admin/shadow")
        assert resp.status_code == 200
        assert resp.json()["n_sampled"] == 0


# ============================================================
# DELETE /admin/shadow/{name}
# ============================================================

class TestAdminShadowDelete:
    def test_delete_nonexistent_shadow_log_returns_404(self):
        """存在しないシャドウログ削除で 404 が返ること"""
        resp = client.delete("/api/v1/admin/shadow/nonexistent_log_xyz")
        assert resp.status_code == 404
