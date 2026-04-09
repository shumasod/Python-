"""
FastAPI エンドポイントの統合テスト
モデルをモックして依存関係を排除
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ---- モックモデルの戻り値 ----
MOCK_PREDICT_RESULT = {
    "win_probabilities": [0.35, 0.22, 0.15, 0.12, 0.09, 0.07],
    "trifecta": [
        {"combination": [1, 2, 3], "probability": 0.042, "rank": 1},
        {"combination": [1, 2, 4], "probability": 0.038, "rank": 2},
    ],
    "recommendations": [
        {
            "combination": [1, 2, 3],
            "probability": 0.042,
            "odds": 25.0,
            "expected_value": 1.05,
            "kelly_fraction": 0.02,
            "note": "期待値 1.05",
        }
    ],
}

VALID_REQUEST = {
    "race_id": "test_001",
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


class TestHealthCheck:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestPredictEndpoint:
    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_valid_request(self, mock_predict):
        """正常なリクエストで200が返ることを確認"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert resp.status_code == 200

    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_response_structure(self, mock_predict):
        """レスポンスに必須フィールドが含まれることを確認"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        body = resp.json()
        assert "win_probabilities" in body
        assert "trifecta" in body
        assert "recommendations" in body

    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_win_proba_length(self, mock_predict):
        """win_probabilities が6要素であることを確認"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert len(resp.json()["win_probabilities"]) == 6

    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_race_id_propagated(self, mock_predict):
        """race_id がレスポンスに含まれることを確認"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert resp.json()["race_id"] == "test_001"

    def test_invalid_boat_count(self):
        """6艇以外のリクエストで 422 が返ることを確認"""
        bad_request = {
            "race": {
                "boats": [
                    {"boat_number": 1, "racer_rank": "A1", "win_rate": 20.0}
                ]  # 1艇しかない
            }
        }
        resp = client.post("/api/v1/predict", json=bad_request)
        assert resp.status_code == 422

    def test_missing_race_field(self):
        """race フィールドがない場合に 422 が返ることを確認"""
        resp = client.post("/api/v1/predict", json={"race_id": "no_race"})
        assert resp.status_code == 422

    @patch(
        "app.api.predict.predict_race",
        side_effect=FileNotFoundError("モデルなし"),
    )
    def test_model_not_found(self, mock_predict):
        """モデル未学習の場合に 503 が返ることを確認"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert resp.status_code == 503
