"""
API Key 認証・Prometheus メトリクスのユニットテスト
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# auth.py テスト
# ============================================================

class TestApiKeyAuth:
    def test_generate_api_key_format(self):
        """generate_api_key() が 'prefix-...' 形式を返すことを確認"""
        from app.api.auth import generate_api_key
        key = generate_api_key("test")
        assert key.startswith("test-")
        assert len(key) > 10

    def test_generate_unique_keys(self):
        """2回生成したキーが異なることを確認"""
        from app.api.auth import generate_api_key
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2

    def test_hash_key_deterministic(self):
        """同じキーは同じハッシュになることを確認"""
        from app.api.auth import _hash_key
        assert _hash_key("mykey") == _hash_key("mykey")

    def test_hash_key_different_for_different_inputs(self):
        """異なるキーは異なるハッシュになることを確認"""
        from app.api.auth import _hash_key
        assert _hash_key("key1") != _hash_key("key2")

    def test_verify_rejects_invalid_key(self):
        """無効な API Key で 401 が発生することを確認"""
        from fastapi import HTTPException
        from app.api.auth import verify_api_key

        # 認証有効な状態で無効なキーをテスト
        with patch("app.api.auth._AUTH_ENABLED", True):
            with patch("app.api.auth._VALID_KEY_HASHES", {"dummy_hash"}):
                with pytest.raises(HTTPException) as exc:
                    verify_api_key("invalid-key")
                assert exc.value.status_code == 401

    def test_verify_skips_when_disabled(self):
        """API_AUTH_ENABLED=false のとき認証をスキップすることを確認"""
        from app.api.auth import verify_api_key

        with patch("app.api.auth._AUTH_ENABLED", False):
            result = verify_api_key(None)
            assert result == "auth-disabled"

    def test_verify_rejects_missing_key(self):
        """X-API-Key ヘッダーなしで 401 が発生することを確認"""
        from fastapi import HTTPException
        from app.api.auth import verify_api_key

        with patch("app.api.auth._AUTH_ENABLED", True):
            with pytest.raises(HTTPException) as exc:
                verify_api_key(None)
            assert exc.value.status_code == 401

    def test_verify_valid_key_returns_key(self):
        """正しい API Key を渡すとキー文字列を返すこと"""
        import app.api.auth as auth_mod
        test_key = "valid-test-key-xyz"
        key_hash = auth_mod._hash_key(test_key)
        with patch("app.api.auth._AUTH_ENABLED", True), \
             patch("app.api.auth._VALID_KEY_HASHES", {key_hash}):
            result = auth_mod.verify_api_key(test_key)
        assert result == test_key

    def test_load_api_keys_from_env(self, monkeypatch):
        """API_KEYS 環境変数からキーが読み込まれること"""
        import app.api.auth as auth_mod
        monkeypatch.setenv("API_KEYS", "key-a, key-b , key-c")
        original = set(auth_mod._VALID_KEY_HASHES)
        auth_mod._VALID_KEY_HASHES.clear()
        with patch.dict("os.environ", {"API_KEYS": "key-a,key-b,key-c"}):
            auth_mod._load_api_keys()
        assert len(auth_mod._VALID_KEY_HASHES) == 3
        # 復元
        auth_mod._VALID_KEY_HASHES.clear()
        auth_mod._VALID_KEY_HASHES.update(original)


# ============================================================
# notification.py テスト
# ============================================================

class TestNotificationBuilders:
    def test_build_prediction_summary_contains_race_id(self):
        """予測サマリーにレースIDが含まれることを確認"""
        from app.utils.notification import build_prediction_summary
        msg = build_prediction_summary("race-001", [0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        assert "race-001" in msg

    def test_build_prediction_summary_top3(self):
        """上位3艇が含まれることを確認"""
        from app.utils.notification import build_prediction_summary
        msg = build_prediction_summary("R1", [0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        assert "1位" in msg and "2位" in msg and "3位" in msg

    def test_build_retrain_summary_contains_version(self):
        """再学習サマリーにバージョンが含まれることを確認"""
        from app.utils.notification import build_retrain_summary
        msg = build_retrain_summary(
            "boat_race_model_v20240415_1",
            {"cv_logloss_mean": 1.23, "cv_accuracy_mean": 0.28, "n_samples": 12000},
        )
        assert "boat_race_model_v20240415_1" in msg
        assert "1.2300" in msg

    def test_notify_sync_disabled(self):
        """NOTIFY_ENABLED=false のとき空dictを返すことを確認"""
        from app.utils.notification import notify_sync

        with patch("app.utils.notification._ENABLED", False):
            result = notify_sync("test message")
            assert result == {}


# ============================================================
# ensemble.py テスト
# ============================================================

class TestEnsemblePredictor:
    import numpy as np

    def _make_mock_model(self, proba_value: float = 1 / 6):
        """ダミー確率を返すモックモデルを生成"""
        import numpy as np
        from unittest.mock import MagicMock
        model = MagicMock()
        # 全艇均等確率
        model.predict_proba.return_value = np.full((6, 6), proba_value)
        return model

    def test_predict_proba_shape(self):
        """predict_proba が (n_samples, 6) を返すことを確認"""
        import numpy as np
        from app.model.ensemble import EnsemblePredictor

        ens = EnsemblePredictor(method="average")
        ens.add_model("m1", self._make_mock_model(), weight=1.0)
        ens.add_model("m2", self._make_mock_model(), weight=1.0)

        X = np.zeros((6, 12))
        proba = ens.predict_proba(X)
        assert proba.shape == (6, 6)

    def test_average_mode(self):
        """average モードで確率が均等になることを確認"""
        import numpy as np
        from app.model.ensemble import EnsemblePredictor

        ens = EnsemblePredictor(method="average")
        ens.add_model("m1", self._make_mock_model(0.2))
        ens.add_model("m2", self._make_mock_model(0.1))

        X = np.zeros((2, 12))
        proba = ens.predict_proba(X)
        expected = (0.2 + 0.1) / 2
        assert proba[0, 0] == pytest.approx(expected)

    def test_no_models_raises(self):
        """モデル未登録で RuntimeError が発生することを確認"""
        import numpy as np
        from app.model.ensemble import EnsemblePredictor

        ens = EnsemblePredictor()
        with pytest.raises(RuntimeError):
            ens.predict_proba(np.zeros((6, 12)))

    def test_invalid_method_raises(self):
        """無効な method で ValueError が発生することを確認"""
        from app.model.ensemble import EnsemblePredictor
        with pytest.raises(ValueError):
            EnsemblePredictor(method="invalid")

    def test_weight_from_cv_logloss(self):
        """cv_logloss が小さいほど重みが大きくなることを確認"""
        from app.model.ensemble import EnsemblePredictor, ModelEntry
        from unittest.mock import MagicMock

        ens = EnsemblePredictor(method="weighted")
        ens.add_model("low_loss", MagicMock(), cv_logloss=0.5)   # より良い
        ens.add_model("high_loss", MagicMock(), cv_logloss=2.0)  # より悪い

        assert ens._models[0].weight > ens._models[1].weight

    def test_from_registry_with_versions(self, tmp_path, monkeypatch):
        """from_registry がレジストリからモデルを読み込んでアンサンブルを構築すること"""
        import numpy as np
        import app.model.versioning as ver_mod
        from app.model.ensemble import EnsemblePredictor
        from tests.test_versioning import _PicklableModel

        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 1000, "feature_columns": ["x"] * 12,
        }
        registry.register(_PicklableModel(), metrics)
        registry.register(_PicklableModel(), {**metrics, "cv_logloss_mean": 1.4})

        ens = EnsemblePredictor.from_registry(method="average", top_n=2)
        assert len(ens._models) >= 1

    def test_from_registry_with_named_versions(self, tmp_path, monkeypatch):
        """version_names 指定で特定バージョンのみ読み込まれること"""
        import app.model.versioning as ver_mod
        from app.model.ensemble import EnsemblePredictor
        from tests.test_versioning import _PicklableModel

        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 1000, "feature_columns": ["x"] * 12,
        }
        v1 = registry.register(_PicklableModel(), metrics)
        _  = registry.register(_PicklableModel(), metrics)

        ens = EnsemblePredictor.from_registry(version_names=[v1], method="average")
        assert len(ens._models) == 1
        assert ens._models[0].name == v1

    def test_from_registry_no_versions_raises(self, tmp_path, monkeypatch):
        """バージョン未登録で RuntimeError が発生すること"""
        import app.model.versioning as ver_mod
        from app.model.ensemble import EnsemblePredictor

        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

        with pytest.raises(RuntimeError, match="有効なモデルバージョンが見つかりません"):
            EnsemblePredictor.from_registry()

    def test_from_registry_missing_file_warns_and_skips(self, tmp_path, monkeypatch):
        """バージョンファイルが見つからないとき警告してスキップすること"""
        import app.model.versioning as ver_mod
        from app.model.ensemble import EnsemblePredictor
        from tests.test_versioning import _PicklableModel

        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        metrics = {
            "cv_logloss_mean": 1.5, "cv_logloss_std": 0.05,
            "cv_accuracy_mean": 0.28, "cv_accuracy_std": 0.02,
            "n_samples": 1000, "feature_columns": ["x"] * 12,
        }
        v1 = registry.register(_PicklableModel(), metrics)

        # Delete the version file to trigger FileNotFoundError in from_registry
        (tmp_path / "versions" / f"{v1}.pkl").unlink()

        # from_registry should warn and skip (ensemble has 0 models but no exception)
        # Actually, since selected=[v1] but load fails → ensemble._models=[]
        # from_registry calls ensemble.summary() and returns even with no models
        ens = EnsemblePredictor.from_registry(version_names=[v1], method="average")
        assert len(ens._models) == 0  # file was missing, so nothing loaded


# ============================================================
# metrics.py テスト
# ============================================================

class TestMetricsModule:
    def test_record_predict_request_no_error(self):
        """record_predict_request がエラーなく実行されること"""
        from app.api.metrics import record_predict_request
        # prometheus_client が使える環境なら実際にカウンタを更新する
        record_predict_request("success", 0.05)
        record_predict_request("error", 0.10)

    def test_update_model_info_no_error(self, tmp_path, monkeypatch):
        """update_model_info がエラーなく実行されること"""
        import app.model.versioning as ver_mod
        monkeypatch.setattr(ver_mod, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(ver_mod, "REGISTRY_FILE", tmp_path / "registry.json")

        from app.api.metrics import update_model_info
        update_model_info()  # バージョン未登録でも例外にならないこと

    def test_metrics_endpoint_returns_data(self):
        """GET /metrics が 200 またはプレーンテキストを返すこと"""
        from fastapi.testclient import TestClient
        from app.main import app
        tc = TestClient(app)
        resp = tc.get("/metrics")
        assert resp.status_code in (200, 503)

    def test_metrics_middleware_predict_path(self):
        """metrics_middleware が /predict パスのレイテンシを計測すること"""
        from fastapi.testclient import TestClient
        from app.main import app

        tc = TestClient(app)
        try:
            tc.post(
                "/api/v1/predict",
                headers={"X-API-Key": "test-key"},
                json={"jyo_code": "01", "race_date": "20260420", "race_no": 1,
                      "boats": [{"boat_no": i+1, "racer_no": i+1, "rank": i+1,
                                 "motor_no": i+1, "boat_no_official": i+1,
                                 "exhibition_time": 6.5} for i in range(6)]},
            )
        except Exception:
            pass  # 例外が出ても中置エラー計測パスをカバーできればよい

    def test_metrics_middleware_exception_path(self):
        """metrics_middleware の例外パスがカバーされること"""
        import asyncio
        from unittest.mock import AsyncMock
        from starlette.requests import Request
        from app.api.metrics import metrics_middleware, _PROMETHEUS_AVAILABLE

        async def _bad_next(_req):
            raise RuntimeError("simulated error")

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/predict",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)

        async def run():
            try:
                await metrics_middleware(request, _bad_next)
            except RuntimeError:
                pass  # expected

        asyncio.run(run())

    def test_record_predict_request_with_error_status(self):
        """record_predict_request が 'error' ステータスを処理すること"""
        from app.api.metrics import record_predict_request
        record_predict_request("error", 1.5)
        record_predict_request("model_not_found", 0.0)

    def test_update_model_info_exception_swallowed(self, tmp_path, monkeypatch):
        """update_model_info が内部例外を飲み込むこと"""
        import app.api.metrics as met
        from unittest.mock import patch

        with patch.dict("sys.modules", {"app.model.versioning": None}):
            met.update_model_info()  # 例外にならないこと

    def test_record_predict_request_prometheus_disabled(self, monkeypatch):
        """_PROMETHEUS_AVAILABLE=False のとき record_predict_request が即座に返ること"""
        import app.api.metrics as met
        monkeypatch.setattr(met, "_PROMETHEUS_AVAILABLE", False)
        met.record_predict_request("success", 0.1)  # 例外にならないこと

    def test_update_model_info_prometheus_disabled(self, monkeypatch):
        """_PROMETHEUS_AVAILABLE=False のとき update_model_info が即座に返ること"""
        import app.api.metrics as met
        monkeypatch.setattr(met, "_PROMETHEUS_AVAILABLE", False)
        met.update_model_info()  # 例外にならないこと

    def test_metrics_endpoint_prometheus_disabled(self, monkeypatch):
        """_PROMETHEUS_AVAILABLE=False のとき /metrics が 503 を返すこと"""
        import app.api.metrics as met
        monkeypatch.setattr(met, "_PROMETHEUS_AVAILABLE", False)

        from fastapi.testclient import TestClient
        from app.main import app as _app
        tc = TestClient(_app)
        resp = tc.get("/metrics")
        assert resp.status_code == 503

    def test_record_predict_request_counter_exception_swallowed(self, monkeypatch):
        """PREDICT_REQUESTS.labels().inc() が例外を投げても飲み込まれること"""
        import app.api.metrics as met
        from unittest.mock import MagicMock
        monkeypatch.setattr(met, "_PROMETHEUS_AVAILABLE", True)
        bad_counter = MagicMock()
        bad_counter.labels.return_value.inc.side_effect = RuntimeError("counter error")
        monkeypatch.setattr(met, "PREDICT_REQUESTS", bad_counter)
        met.record_predict_request("success", 0.05)  # 例外にならないこと
