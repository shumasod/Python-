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


# ============================================================
# _load_prediction_log / _compare_prediction（未カバー行）
# ============================================================

class TestLoadPredictionLogBranches:
    def test_bad_json_falls_through(self, tmp_path, monkeypatch):
        """破損 JSON ファイルは読み飛ばして None を返すこと"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", tmp_path)

        (tmp_path / "bad_race.json").write_text("NOT JSON", encoding="utf-8")
        result = fb._load_prediction_log("bad_race")
        assert result is None

    def test_ab_test_fallback_found(self, tmp_path, monkeypatch):
        """prediction_logs になくても ab_test_logs から見つかること"""
        import app.api.feedback as fb
        pred_dir = tmp_path / "prediction_logs"
        pred_dir.mkdir()
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", pred_dir)

        ab_dir = tmp_path / "data" / "ab_test_logs"
        ab_dir.mkdir(parents=True)
        entry = {"race_id": "ab_race_001", "proba": [0.3, 0.2, 0.1, 0.2, 0.1, 0.1]}
        (ab_dir / "test.jsonl").write_text(json.dumps(entry), encoding="utf-8")

        # Change CWD so Path("data/ab_test_logs") resolves to tmp_path/data/ab_test_logs
        monkeypatch.chdir(tmp_path)
        result = fb._load_prediction_log("ab_race_001")
        assert result is not None
        assert result["race_id"] == "ab_race_001"

    def test_ab_test_fallback_bad_json_line_skipped(self, tmp_path, monkeypatch):
        """AB ログの行が破損 JSON のとき読み飛ばして None を返すこと"""
        import app.api.feedback as fb
        pred_dir = tmp_path / "prediction_logs"
        pred_dir.mkdir()
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", pred_dir)

        ab_dir = tmp_path / "data" / "ab_test_logs"
        ab_dir.mkdir(parents=True)
        (ab_dir / "test.jsonl").write_text("NOT_JSON\n{\"race_id\": \"other\"}\n", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        result = fb._load_prediction_log("ab_race_missing")
        assert result is None

    def test_ab_test_fallback_oserror_skipped(self, tmp_path, monkeypatch):
        """AB ログファイルを開けない場合（OSError）は読み飛ばして None を返すこと"""
        import app.api.feedback as fb
        pred_dir = tmp_path / "prediction_logs"
        pred_dir.mkdir()
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", pred_dir)

        ab_dir = tmp_path / "data" / "ab_test_logs"
        ab_dir.mkdir(parents=True)
        # ディレクトリを .jsonl 名にすると open() が IsADirectoryError (OSError) を投げる
        (ab_dir / "oserr.jsonl").mkdir()

        monkeypatch.chdir(tmp_path)
        result = fb._load_prediction_log("any_race")
        assert result is None

    def test_compare_prediction_no_proba(self, monkeypatch):
        """win_probabilities も proba もない予測ログのとき None フィールドを返すこと"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "_load_prediction_log", lambda rid: {"race_id": rid})

        from app.api.feedback import RaceResultRequest
        req = RaceResultRequest(true_winner=1)
        result = fb._compare_prediction(req, "r_no_proba")
        assert result["is_correct"] is None
        assert result["predicted_winner"] is None

    def test_result_summary_with_prediction_rank(self, tmp_path, monkeypatch):
        """prediction_rank が記録されているとき avg_prediction_rank が計算されること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        # prediction_rank 付きのファイルを直接書く
        record = {
            "race_id": "r1",
            "true_winner": 1,
            "recorded_at": "2026-04-20T12:00:00+00:00",
            "is_correct": True,
            "prediction_rank": 1,
            "predicted_winner": 1,
        }
        (tmp_path / "r1.json").write_text(json.dumps(record), encoding="utf-8")
        record2 = {**record, "race_id": "r2", "prediction_rank": 3, "is_correct": False}
        (tmp_path / "r2.json").write_text(json.dumps(record2), encoding="utf-8")

        resp = client.get("/api/v1/result/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["n_results"] == 2
        assert body["hit_rate"] == pytest.approx(0.5, abs=0.01)
        assert body["avg_prediction_rank"] == pytest.approx(2.0, abs=0.01)

    def test_record_result_ab_test_notification(self, tmp_path, monkeypatch):
        """A/B テスト通知が例外なく呼ばれること（import 失敗は無視）"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", tmp_path)

        resp = client.post("/api/v1/result/ab_notify_test", json={"true_winner": 2})
        assert resp.status_code == 200

    def test_record_result_calls_global_router(self, tmp_path, monkeypatch):
        """_global_router が存在するとき record_result が呼ばれること"""
        from unittest.mock import MagicMock
        import app.api.feedback as fb
        import app.model.ab_test as ab_module

        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", tmp_path)

        mock_router = MagicMock()
        monkeypatch.setattr(ab_module, "_global_router", mock_router, raising=False)

        resp = client.post("/api/v1/result/ab_router_test", json={"true_winner": 3})
        assert resp.status_code == 200
        mock_router.record_result.assert_called_once_with(
            race_id="ab_router_test", true_winner=3
        )


class TestResultSummaryCorruptFile:
    def test_corrupt_json_skipped_in_summary(self, tmp_path, monkeypatch):
        """壊れた JSON ファイルはサマリー集計でスキップされること"""
        import app.api.feedback as fb
        monkeypatch.setattr(fb, "RESULT_LOG_DIR", tmp_path)

        # 正常ファイル
        good = {
            "race_id": "r_ok", "true_winner": 1,
            "recorded_at": "2026-04-20T12:00:00+00:00",
            "is_correct": True, "prediction_rank": 1, "predicted_winner": 1,
        }
        (tmp_path / "r_ok.json").write_text(json.dumps(good), encoding="utf-8")

        # 破損ファイル
        (tmp_path / "r_bad.json").write_text("CORRUPT{{{", encoding="utf-8")

        resp = client.get("/api/v1/result/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["n_results"] == 1  # 正常ファイルだけカウント
