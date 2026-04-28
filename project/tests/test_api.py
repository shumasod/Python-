"""
FastAPI エンドポイントの統合テスト
モデルをモックして依存関係を排除
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import verify_api_key

# 認証を無効化（テスト用）
app.dependency_overrides[verify_api_key] = lambda: "test-key"

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


# ============================================================
# バッチ予測エンドポイント
# ============================================================

def _make_batch_request(n: int):
    """n 件のバッチ予測リクエストを組み立てる"""
    return {
        "races": [
            {
                "race_id": f"r_{i}",
                "race": VALID_REQUEST["race"],
            }
            for i in range(n)
        ]
    }


class TestPredictBatchEndpoint:
    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_batch_success(self, mock_predict):
        """3 件のバッチが全て成功すること"""
        resp = client.post("/api/v1/predict/batch", json=_make_batch_request(3))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["succeeded"] == 3
        assert body["failed"] == 0
        assert len(body["results"]) == 3

    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_batch_race_ids_preserved(self, mock_predict):
        """結果に元の race_id が含まれること"""
        resp = client.post("/api/v1/predict/batch", json=_make_batch_request(2))
        ids = [r["race_id"] for r in resp.json()["results"]]
        assert ids == ["r_0", "r_1"]

    @patch(
        "app.api.predict.predict_race",
        side_effect=FileNotFoundError("モデルなし"),
    )
    def test_batch_model_not_found_records_failure(self, mock_predict):
        """モデル未学習時に失敗として記録されること（全体は200）"""
        resp = client.post("/api/v1/predict/batch", json=_make_batch_request(2))
        assert resp.status_code == 200
        body = resp.json()
        assert body["failed"] == 2
        assert body["succeeded"] == 0
        assert all(r["status"] == "error" for r in body["results"])

    @patch("app.api.predict.predict_race", return_value=MOCK_PREDICT_RESULT)
    def test_batch_mixed_success_failure(self, mock_predict):
        """一部が失敗しても全体は200で返ること"""
        call_count = {"n": 0}

        def _side_effect(race):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("不正な入力")
            return MOCK_PREDICT_RESULT

        mock_predict.side_effect = _side_effect
        resp = client.post("/api/v1/predict/batch", json=_make_batch_request(3))
        assert resp.status_code == 200
        body = resp.json()
        assert body["succeeded"] == 2
        assert body["failed"] == 1

    def test_batch_empty_list_rejected(self):
        """空のレースリストは 422 で拒否されること"""
        resp = client.post("/api/v1/predict/batch", json={"races": []})
        assert resp.status_code == 422

    def test_batch_over_max_rejected(self):
        """上限 20 件超で 422 が返ること"""
        resp = client.post("/api/v1/predict/batch", json=_make_batch_request(21))
        assert resp.status_code == 422


# ============================================================
# /stats エンドポイント
# ============================================================

class TestStatsEndpoint:
    def test_stats_returns_json(self):
        """/stats が JSON を返すこと（DB/キャッシュ未接続でもエラーなく動く）"""
        resp = client.get("/api/v1/stats?days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert "db" in body

    def test_stats_accepts_days_param(self):
        """days パラメータを受け付けること"""
        resp = client.get("/api/v1/stats?days=30")
        assert resp.status_code == 200


# ============================================================
# /cache/{race_id} 削除エンドポイント
# ============================================================

class TestInvalidateCacheEndpoint:
    def test_delete_returns_200(self):
        """DELETE /cache/{race_id} が 200 を返すこと"""
        resp = client.delete("/api/v1/cache/race_001")
        assert resp.status_code == 200
        body = resp.json()
        # race_id が返る、もしくはキャッシュ無効メッセージが返る
        assert "race_id" in body or "message" in body

    @patch("app.api.predict._CACHE_AVAILABLE", False)
    def test_delete_cache_unavailable_returns_message(self):
        """_CACHE_AVAILABLE=False のとき 'キャッシュが無効' メッセージを返すこと"""
        resp = client.delete("/api/v1/cache/race_xyz")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body


# ============================================================
# predict.py の未カバーパス
# ============================================================

class TestPredictCacheHitPath:
    @patch("app.api.predict._CACHE_AVAILABLE", True)
    @patch("app.api.predict.get_cached_prediction", new_callable=AsyncMock)
    def test_cache_hit_returns_cached_true(self, mock_get_cache):
        """キャッシュヒット時に cached=True でレスポンスを返すこと"""
        mock_get_cache.return_value = MOCK_PREDICT_RESULT
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert resp.status_code == 200
        assert resp.json()["cached"] is True

    @patch("app.api.predict.predict_race", side_effect=ValueError("bad value"))
    def test_predict_value_error_returns_422(self, mock_predict):
        """predict_race が ValueError を投げたとき 422 が返ること"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert resp.status_code == 422

    @patch("app.api.predict.predict_race", side_effect=RuntimeError("unexpected"))
    def test_predict_generic_exception_returns_500(self, mock_predict):
        """predict_race が予期しない例外を投げたとき 500 が返ること"""
        resp = client.post("/api/v1/predict", json=VALID_REQUEST)
        assert resp.status_code == 500


class TestStatsDbUnavailable:
    @patch("app.api.predict._DB_AVAILABLE", False)
    def test_stats_db_unavailable_message(self):
        """_DB_AVAILABLE=False のとき asyncpg 未インストールメッセージが返ること"""
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "db" in body
        assert "message" in body["db"]


class TestBatchCacheHitPath:
    @patch("app.api.predict._CACHE_AVAILABLE", True)
    @patch("app.api.predict.get_cached_prediction", new_callable=AsyncMock)
    def test_batch_cache_hit_returns_cached_true(self, mock_get_cache):
        """バッチ予測でキャッシュヒット時に cached=True が含まれること"""
        mock_get_cache.return_value = MOCK_PREDICT_RESULT
        resp = client.post("/api/v1/predict/batch", json=_make_batch_request(2))
        assert resp.status_code == 200
        body = resp.json()
        assert body["succeeded"] == 2
        assert all(r.get("cached") is True for r in body["results"])
