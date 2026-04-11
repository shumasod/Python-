"""
エンドツーエンド統合テスト
実際にモデルを学習してAPIエンドポイントを叩く
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

pytestmark = pytest.mark.slow  # make test-fast で除外可能


# ============================================================
# モデル学習 → predict_race() パイプライン
# ============================================================

class TestTrainThenPredict:
    def test_train_produces_model(self, tmp_path, monkeypatch):
        """train_model() が LGBMClassifier を返すことを確認"""
        import app.model.train as train_module
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        from app.model.train import train_model
        import lightgbm as lgb

        monkeypatch.setattr(train_module, "MODEL_DIR", tmp_path)
        df = preprocess_dataframe(generate_sample_training_data(n_races=100))
        model, metrics = train_model(df, model_name="int_test", n_splits=2)

        assert isinstance(model, lgb.LGBMClassifier)
        assert "cv_logloss_mean" in metrics
        assert metrics["cv_logloss_mean"] > 0

    def test_train_then_load_and_predict(self, tmp_path, monkeypatch):
        """学習 → 保存 → ロード → predict_race() の完全パイプライン"""
        import app.model.train as train_module
        import app.model.predict as predict_module
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        from app.model.train import train_model
        from app.model.predict import predict_race

        monkeypatch.setattr(train_module, "MODEL_DIR", tmp_path)
        # predict.py は load_model() → train.MODEL_DIR を参照するため同じ tmp_path を使う
        monkeypatch.setattr(train_module, "MODEL_DIR", tmp_path)
        # キャッシュをリセット
        monkeypatch.setattr(predict_module, "_cached_model", None)

        # 学習・保存（load_model() のデフォルト名 "boat_race_model" で保存）
        df = preprocess_dataframe(generate_sample_training_data(n_races=100))
        train_model(df, model_name="boat_race_model", n_splits=2)

        # predict_race は race_data dict を受け取る
        race_data = {
            "race_id": "test_001",
            "boats": [
                {
                    "boat_number": i,
                    "racer_rank": "A1",
                    "win_rate": 20.0 + i,
                    "motor_score": 55.0,
                    "course_win_rate": 30.0,
                    "start_timing": 0.18,
                    "motor_2rate": 40.0,
                    "boat_2rate": 38.0,
                    "recent_3_avg": 3.0,
                }
                for i in range(1, 7)
            ],
            "weather": {"condition": "晴", "wind_speed": 2.0, "water_temp": 22.0},
        }

        result = predict_race(race_data)

        # 結果構造の検証
        assert "win_probabilities" in result
        assert len(result["win_probabilities"]) == 6
        assert "trifecta" in result
        assert "recommendations" in result

        # 確率の合計が ≈1.0
        total = sum(result["win_probabilities"])
        assert abs(total - 1.0) < 0.01

    def test_win_probabilities_sum_to_one(self, tmp_path, monkeypatch):
        """win_probabilities が正規化されていることを確認"""
        import app.model.train as train_module
        import app.model.predict as predict_module
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        from app.model.train import train_model
        from app.model.predict import predict_race

        monkeypatch.setattr(train_module, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(predict_module, "_cached_model", None)

        df = preprocess_dataframe(generate_sample_training_data(n_races=100))
        train_model(df, model_name="boat_race_model", n_splits=2)

        race_data = {
            "boats": [
                {"boat_number": i, "racer_rank": "B1", "win_rate": 15.0,
                 "motor_score": 50.0, "course_win_rate": 25.0, "start_timing": 0.20,
                 "motor_2rate": 35.0, "boat_2rate": 33.0, "recent_3_avg": 3.5}
                for i in range(1, 7)
            ],
            "weather": {"condition": "曇", "wind_speed": 4.0, "water_temp": 20.0},
        }

        result = predict_race(race_data)
        proba_sum = sum(result["win_probabilities"])
        assert abs(proba_sum - 1.0) < 0.01


# ============================================================
# HTTPエンドポイント統合テスト（TestClient）
# ============================================================

class TestAPIEndpointIntegration:
    """
    FastAPIエンドポイントのHTTPレベル統合テスト
    実モデルを使用しないためモック差し替え
    """

    VALID_REQUEST = {
        "race_id": "integration_001",
        "race": {
            "boats": [
                {
                    "boat_number": i,
                    "racer_rank": "A1",
                    "win_rate": 20.0,
                    "motor_score": 55.0,
                    "course_win_rate": 30.0,
                    "start_timing": 0.18,
                    "motor_2rate": 40.0,
                    "boat_2rate": 38.0,
                    "recent_3_avg": 3.0,
                }
                for i in range(1, 7)
            ],
            "weather": {"condition": "晴", "wind_speed": 2.0, "water_temp": 22.0},
        },
    }

    def test_health_then_predict_flow(self):
        """ヘルスチェック → 予測の順でAPIを呼ぶ"""
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from app.main import app
        from app.api.auth import verify_api_key

        app.dependency_overrides[verify_api_key] = lambda: "test-key"
        client = TestClient(app)

        # ヘルスチェック
        health = client.get("/health")
        assert health.status_code == 200

        # 予測（モックあり）
        mock_result = {
            "win_probabilities": [0.35, 0.22, 0.15, 0.12, 0.09, 0.07],
            "trifecta": [{"combination": [1, 2, 3], "probability": 0.042, "rank": 1}],
            "recommendations": [],
        }
        with patch("app.api.predict.predict_race", return_value=mock_result):
            predict = client.post("/api/v1/predict", json=self.VALID_REQUEST)
        assert predict.status_code == 200
        assert predict.json()["race_id"] == "integration_001"

    def test_metrics_endpoint_accessible(self):
        """Prometheus メトリクスエンドポイントが 200 または 503 を返すことを確認
        (prometheus-client 未インストール環境では 503)
        """
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code in (200, 503)


# ============================================================
# ドリフト検知 + A/Bテスト連携
# ============================================================

class TestDriftAndABIntegration:
    def test_drift_then_ab_test_pipeline(self, tmp_path, monkeypatch):
        """
        DriftDetector でデータをチェックし、
        問題がなければ ABTestRouter でモデルを比較する
        """
        import app.model.drift as drift_module
        import app.model.ab_test as ab_module
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        from app.model.drift import DriftDetector
        from app.model.ab_test import ABTestRouter
        from unittest.mock import MagicMock

        monkeypatch.setattr(drift_module, "REFERENCE_FILE", tmp_path / "ref.json")
        monkeypatch.setattr(drift_module, "DRIFT_REPORT_DIR", tmp_path / "reports")
        monkeypatch.setattr(ab_module, "AB_LOG_DIR", tmp_path / "ab_logs")

        # ドリフト検知
        detector = DriftDetector(n_bins=5)
        df = preprocess_dataframe(generate_sample_training_data(n_races=100))
        detector.set_reference(df)
        report = detector.check(df)
        assert report.needs_retraining is False  # 同データなのでドリフトなし

        # A/Bテスト
        mock_v1 = MagicMock()
        mock_v1.predict_proba.return_value = np.full((6, 6), 1 / 6)
        mock_v2 = MagicMock()
        mock_v2.predict_proba.return_value = np.full((6, 6), 1 / 6)

        router = ABTestRouter(name="drift_ab_test")
        router.add_variant("v1", mock_v1, traffic_weight=0.5)
        router.add_variant("v2", mock_v2, traffic_weight=0.5)

        X = np.zeros((6, 12))
        for i in range(10):
            variant, proba = router.predict(X, race_id=f"race_{i:03d}")
            router.record_result(race_id=f"race_{i:03d}", true_winner=1)

        ab_report = router.get_report()
        assert len(ab_report.variants) == 2
        assert ab_report.p_value <= 1.0
