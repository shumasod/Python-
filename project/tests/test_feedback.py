"""
レース結果フィードバック API のテスト
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import verify_api_key

app.dependency_overrides[verify_api_key] = lambda: "test-key"
client = TestClient(app)

MOCK_PREDICT_RESULT = {
    "win_probabilities": [0.35, 0.22, 0.15, 0.12, 0.09, 0.07],
    "trifecta": [{"combination": [1, 2, 3], "probability": 0.042, "rank": 1}],
    "recommendations": [],
}

VALID_RESULT_BODY = {"true_winner": 1}


# ============================================================
# POST /result/{race_id}
# ============================================================

class TestRecordResult:
    def test_record_result_ok(self, tmp_path, monkeypatch):
        """正常な結果記録で 200 が返ること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        resp = client.post("/api/v1/result/race_test_001", json=VALID_RESULT_BODY)
        assert resp.status_code == 200
        body = resp.json()
        assert body["race_id"] == "race_test_001"
        assert body["true_winner"] == 1
        assert "recorded_at" in body

    def test_record_result_creates_json_file(self, tmp_path, monkeypatch):
        """JSON ファイルが生成されること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        client.post("/api/v1/result/race_file_001", json=VALID_RESULT_BODY)
        assert (tmp_path / "race_file_001.json").exists()

    def test_record_result_duplicate_returns_409(self, tmp_path, monkeypatch):
        """同じ race_id に2回記録すると 409 が返ること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        client.post("/api/v1/result/race_dup_001", json=VALID_RESULT_BODY)
        resp = client.post("/api/v1/result/race_dup_001", json=VALID_RESULT_BODY)
        assert resp.status_code == 409

    def test_record_result_invalid_winner(self, tmp_path, monkeypatch):
        """艇番が範囲外（0 や 7）で 422 が返ること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        resp = client.post("/api/v1/result/race_bad_001", json={"true_winner": 7})
        assert resp.status_code == 422

        resp2 = client.post("/api/v1/result/race_bad_002", json={"true_winner": 0})
        assert resp2.status_code == 422

    def test_record_result_with_all_fields(self, tmp_path, monkeypatch):
        """全フィールド指定でも正常に記録できること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        body = {
            "true_winner": 3,
            "second_place": 1,
            "third_place": 5,
            "official_odds": {"trifecta": 150.0, "win": 4.5},
            "note": "強風でインコース不利",
        }
        resp = client.post("/api/v1/result/race_full_001", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["second_place"] == 1
        assert data["third_place"] == 5


# ============================================================
# GET /result/{race_id}
# ============================================================

class TestGetResult:
    def test_get_existing_result(self, tmp_path, monkeypatch):
        """記録済み結果が取得できること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        client.post("/api/v1/result/race_get_001", json=VALID_RESULT_BODY)
        resp = client.get("/api/v1/result/race_get_001")
        assert resp.status_code == 200
        assert resp.json()["true_winner"] == 1

    def test_get_nonexistent_result_returns_404(self, tmp_path, monkeypatch):
        """存在しない race_id で 404 が返ること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        resp = client.get("/api/v1/result/nonexistent_race")
        assert resp.status_code == 404


# ============================================================
# GET /result/summary
# ============================================================

class TestResultSummary:
    def _post_results(self, tmp_path, monkeypatch, pairs):
        """(race_id, winner) のリストを一括登録"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)
        for race_id, winner in pairs:
            client.post(f"/api/v1/result/{race_id}", json={"true_winner": winner})

    def test_summary_empty(self, tmp_path, monkeypatch):
        """レース記録がない場合 n_results=0 を返すこと"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        resp = client.get("/api/v1/result/summary")
        assert resp.status_code == 200
        assert resp.json()["n_results"] == 0

    def test_summary_count(self, tmp_path, monkeypatch):
        """記録数が n_results に反映されること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        for i in range(5):
            client.post(f"/api/v1/result/sum_race_{i}", json={"true_winner": 1})

        resp = client.get("/api/v1/result/summary")
        assert resp.json()["n_results"] == 5

    def test_summary_structure(self, tmp_path, monkeypatch):
        """サマリーに必要なフィールドが含まれること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        client.post("/api/v1/result/sum_struct_001", json={"true_winner": 2})
        resp = client.get("/api/v1/result/summary")
        body = resp.json()
        assert "n_results" in body
        assert "hit_rate" in body
        assert "top3_hit_rate" in body
        assert "avg_prediction_rank" in body


# ============================================================
# POST /predict/batch
# ============================================================

class TestBatchPredict:
    BOAT = {
        "boat_number": 1,
        "racer_rank": "A1",
        "win_rate": 20.0,
        "motor_score": 55.0,
        "course_win_rate": 30.0,
        "start_timing": 0.18,
        "motor_2rate": 40.0,
        "boat_2rate": 38.0,
        "recent_3_avg": 3.0,
    }

    def _make_race(self, race_id: str) -> dict:
        return {
            "race_id": race_id,
            "race": {
                "boats": [{**self.BOAT, "boat_number": i} for i in range(1, 7)],
                "weather": {"condition": "晴", "wind_speed": 2.0, "water_temp": 22.0},
            },
        }

    def test_batch_predict_ok(self):
        """バッチ予測が正常に返ること"""
        with patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT):
            resp = client.post(
                "/api/v1/predict/batch",
                json={"races": [self._make_race(f"r{i}") for i in range(3)]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["succeeded"] == 3
        assert body["failed"] == 0
        assert len(body["results"]) == 3

    def test_batch_predict_partial_failure(self):
        """一部エラーでも残りの結果が返ること"""
        call_count = 0

        def flaky_predict(race_data):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise FileNotFoundError("モデルなし")
            return MOCK_PREDICT_RESULT

        with patch("app.api.predict.predict_race", side_effect=flaky_predict):
            resp = client.post(
                "/api/v1/predict/batch",
                json={"races": [self._make_race(f"r{i}") for i in range(3)]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["succeeded"] == 2
        assert body["failed"] == 1

    def test_batch_empty_races_rejected(self):
        """races が空リストで 422 が返ること"""
        resp = client.post("/api/v1/predict/batch", json={"races": []})
        assert resp.status_code == 422

    def test_batch_too_many_races_rejected(self):
        """21件以上で 422 が返ること"""
        races = [self._make_race(f"r{i}") for i in range(21)]
        resp = client.post("/api/v1/predict/batch", json={"races": races})
        assert resp.status_code == 422

    def test_batch_result_structure(self):
        """各結果に race_id・status が含まれること"""
        with patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT):
            resp = client.post(
                "/api/v1/predict/batch",
                json={"races": [self._make_race("batch_r1")]},
            )
        body = resp.json()
        result = body["results"][0]
        assert result["race_id"] == "batch_r1"
        assert result["status"] == "success"
        assert "win_probabilities" in result
