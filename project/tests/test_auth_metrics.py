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
