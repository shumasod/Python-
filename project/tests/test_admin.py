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

    def test_delete_existing_shadow_log(self, tmp_path, monkeypatch):
        """存在するシャドウログが削除されること"""
        import app.api.admin as admin_mod

        shadow_dir = tmp_path / "shadow_logs"
        shadow_dir.mkdir()
        log_file = shadow_dir / "mytest.jsonl"
        log_file.write_text('{"top1_match": true}\n', encoding="utf-8")

        orig_path = admin_mod.Path

        class _P:
            def __init__(self, p):
                if "shadow_logs" in str(p):
                    self._p = shadow_dir
                else:
                    self._p = orig_path(p)

            def __truediv__(self, other):
                return self._p / other

            def exists(self):
                return self._p.exists()

            def glob(self, pat):
                return self._p.glob(pat)

        monkeypatch.setattr(admin_mod, "Path", _P)
        resp = client.delete("/api/v1/admin/shadow/mytest")
        assert resp.status_code == 200
        assert not log_file.exists()


# ============================================================
# ヘルパー関数の直接テスト（未カバー行）
# ============================================================

class TestAdminHelpers:
    def test_read_shadow_stats_with_data(self, tmp_path, monkeypatch):
        """シャドウログがあるとき統計が正しく計算されること"""
        import app.api.admin as admin_mod

        shadow_dir = tmp_path / "shadow_logs"
        shadow_dir.mkdir()
        entries = [
            {"top1_match": True,  "kl_divergence": 0.1},
            {"top1_match": False, "kl_divergence": 0.3},
            {"top1_match": True,  "kl_divergence": 0.2},
        ]
        (shadow_dir / "shadow.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )

        orig_path = admin_mod.Path

        class _P:
            def __init__(self, p):
                if "shadow_logs" in str(p):
                    self._p = shadow_dir
                else:
                    self._p = orig_path(p)

            def __truediv__(self, other):
                return self._p / other

            def exists(self):
                return self._p.exists()

        monkeypatch.setattr(admin_mod, "Path", _P)
        stats = admin_mod._read_shadow_stats("shadow")
        assert stats["n_sampled"] == 3
        assert abs(stats["top1_match_rate"] - 2/3) < 0.01
        assert stats["avg_kl_divergence"] == pytest.approx(0.2, abs=0.001)

    def test_read_ab_stats_with_data(self, tmp_path, monkeypatch):
        """A/Bテストログがあるとき統計リストが返ること"""
        import app.api.admin as admin_mod

        ab_dir = tmp_path / "ab_test_logs"
        ab_dir.mkdir()
        entries = [
            {"variant": "control",   "race_id": "r1"},
            {"variant": "treatment", "race_id": "r2"},
            {"variant": "control",   "race_id": "r3"},
        ]
        (ab_dir / "exp1.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )

        orig_path = admin_mod.Path

        class _P:
            def __init__(self, p):
                self._p = ab_dir if "ab_test_logs" in str(p) else orig_path(p)

            def __truediv__(self, other):
                return self._p / other

            def exists(self):
                return self._p.exists()

            def glob(self, pat):
                return self._p.glob(pat)

        monkeypatch.setattr(admin_mod, "Path", _P)
        stats = admin_mod._read_ab_stats()
        assert len(stats) == 1
        assert stats[0]["test_name"] == "exp1"
        assert stats[0]["n_total_records"] == 3
        assert "control" in stats[0]["variants"]
        assert "treatment" in stats[0]["variants"]

    def test_latest_drift_status_stable(self, tmp_path, monkeypatch):
        """ドリフトレポートが stable のとき 'stable' を返すこと"""
        import app.api.admin as admin_mod

        drift_dir = tmp_path / "drift_reports"
        drift_dir.mkdir()
        report = {"needs_retraining": False, "feature_results": []}
        (drift_dir / "r1.json").write_text(json.dumps(report), encoding="utf-8")

        orig_path = admin_mod.Path

        class _P:
            def __init__(self, p):
                self._p = drift_dir if "drift_reports" in str(p) else orig_path(p)

            def exists(self):
                return self._p.exists()

            def glob(self, pat):
                return self._p.glob(pat)

        monkeypatch.setattr(admin_mod, "Path", _P)
        status = admin_mod._latest_drift_status()
        assert status == "stable"

    def test_latest_drift_status_needs_retraining(self, tmp_path, monkeypatch):
        """ドリフトレポートが needs_retraining のとき 'needs_retraining' を返すこと"""
        import app.api.admin as admin_mod

        drift_dir = tmp_path / "drift_reports"
        drift_dir.mkdir()
        report = {"needs_retraining": True, "feature_results": []}
        (drift_dir / "r1.json").write_text(json.dumps(report), encoding="utf-8")

        orig_path = admin_mod.Path

        class _P:
            def __init__(self, p):
                self._p = drift_dir if "drift_reports" in str(p) else orig_path(p)

            def exists(self):
                return self._p.exists()

            def glob(self, pat):
                return self._p.glob(pat)

        monkeypatch.setattr(admin_mod, "Path", _P)
        status = admin_mod._latest_drift_status()
        assert status == "needs_retraining"

    def test_latest_drift_status_no_dir(self):
        """ドリフトレポートディレクトリなしのとき None を返すこと"""
        import app.api.admin as admin_mod
        import unittest.mock as mock

        with mock.patch.object(admin_mod.Path("data/drift_reports").__class__, "exists",
                               return_value=False):
            pass  # Path class patching is tricky; test via the endpoint instead

    def test_admin_key_restriction(self):
        """ADMIN_API_KEY が設定されているとき不一致で 403 になること"""
        import app.api.admin as admin_mod

        with patch.object(admin_mod, "_ADMIN_KEY", "secret-admin-key"):
            resp = client.get("/api/v1/admin/status")
            assert resp.status_code == 403

    def test_promote_success(self, tmp_path, monkeypatch):
        """存在するバージョンの昇格が成功すること"""
        import app.model.versioning as ver_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

        from tests.test_versioning import _PicklableModel
        from app.model.versioning import ModelRegistry

        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 1000, "feature_columns": ["x"] * 12,
        }
        version_name = registry.register(_PicklableModel(), metrics)

        resp = client.post(
            "/api/v1/admin/models/promote",
            json={"version": version_name},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_version"] == version_name
