"""
app/api/scoring.py のテスト

スコアリング集計ロジックと API エンドポイントを検証する。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import verify_api_key

app.dependency_overrides[verify_api_key] = lambda: "test-key"
client = TestClient(app)


# ============================================================
# フィクスチャ
# ============================================================

def _write_prediction(path: Path, race_id: str, win_proba: list,
                      jyo_code: str = "01", race_date: str = "20260420",
                      race_no: int = 1) -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = {
        "race_id":          race_id,
        "jyo_code":         jyo_code,
        "race_date":        race_date,
        "race_no":          race_no,
        "win_probabilities": win_proba,
        "top1_boat":        win_proba.index(max(win_proba)) + 1,
        "trifecta_top3":    [[1, 2, 3]],
        "win_odds":         {},
        "dry_run":          True,
        "predicted_at":     "2026-04-20T00:00:00+00:00",
    }
    (path / f"{race_id}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )


def _write_result(path: Path, race_id: str, true_winner: int,
                  race_date: str = "20260420") -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = {
        "race_id":     race_id,
        "true_winner": true_winner,
        "race_date":   race_date,
        "recorded_at": "2026-04-20T12:00:00+00:00",
        "is_correct":  None,
        "prediction_rank": None,
    }
    (path / f"{race_id}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )


# ============================================================
# _score_pair (unit)
# ============================================================

class TestLoadJson:
    def test_load_json_corrupt_returns_none(self, tmp_path):
        """破損 JSON ファイルのとき None を返すこと"""
        from app.api.scoring import _load_json
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("CORRUPT{{{", encoding="utf-8")
        assert _load_json(bad_path) is None

    def test_load_json_missing_returns_none(self, tmp_path):
        """存在しないファイルのとき None を返すこと"""
        from app.api.scoring import _load_json
        assert _load_json(tmp_path / "nonexistent.json") is None


class TestScorePair:
    def test_correct_prediction(self):
        """1号艇が最高確率かつ実際の1着のとき is_correct=True"""
        from app.api.scoring import _score_pair
        pred   = {"race_id": "r1", "win_probabilities": [0.5, 0.2, 0.1, 0.1, 0.05, 0.05]}
        result = {"true_winner": 1}
        score  = _score_pair(pred, result)
        assert score.is_correct is True
        assert score.predicted_winner == 1
        assert score.prediction_rank == 1

    def test_wrong_prediction(self):
        """1号艇最高確率だが3号艇が実際の1着のとき is_correct=False"""
        from app.api.scoring import _score_pair
        pred   = {"race_id": "r1", "win_probabilities": [0.5, 0.2, 0.15, 0.1, 0.03, 0.02]}
        result = {"true_winner": 3}
        score  = _score_pair(pred, result)
        assert score.is_correct is False
        assert score.prediction_rank == 3   # 3号艇は確率3位

    def test_accepts_proba_field(self):
        """旧形式 "proba" フィールドも受け付けること"""
        from app.api.scoring import _score_pair
        pred   = {"race_id": "r1", "proba": [0.1, 0.5, 0.1, 0.1, 0.1, 0.1]}
        result = {"true_winner": 2}
        score  = _score_pair(pred, result)
        assert score.is_correct is True
        assert score.predicted_winner == 2

    def test_no_proba_returns_none_fields(self):
        """proba なしのとき比較フィールドが None"""
        from app.api.scoring import _score_pair
        score = _score_pair({"race_id": "r1"}, {"true_winner": 1})
        assert score.is_correct is None
        assert score.predicted_winner is None


# ============================================================
# _collect_scores (unit)
# ============================================================

class TestCollectScores:
    def test_matched_pair_scored(self, tmp_path, monkeypatch):
        """予測と結果が両方あるレースは has_prediction/has_result=True"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        _write_prediction(pred_dir, "r1", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_result(result_dir, "r1", true_winner=1)

        scores = sc._collect_scores()
        assert len(scores) == 1
        assert scores[0].has_prediction and scores[0].has_result

    def test_prediction_only(self, tmp_path, monkeypatch):
        """予測のみ: has_result=False"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)
        result_dir.mkdir()

        _write_prediction(pred_dir, "r2", [1/6] * 6)

        scores = sc._collect_scores()
        assert len(scores) == 1
        assert scores[0].has_prediction is True
        assert scores[0].has_result is False

    def test_result_only(self, tmp_path, monkeypatch):
        """結果のみ: has_prediction=False"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)
        pred_dir.mkdir()

        _write_result(result_dir, "r3", true_winner=4)

        scores = sc._collect_scores()
        assert scores[0].has_prediction is False
        assert scores[0].has_result is True

    def test_empty_dirs_returns_empty(self, tmp_path, monkeypatch):
        """空ディレクトリで空リストを返すこと"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "preds";  pred_dir.mkdir()
        result_dir = tmp_path / "results"; result_dir.mkdir()
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)
        assert sc._collect_scores() == []


# ============================================================
# GET /api/v1/scoring
# ============================================================

class TestScoringEndpoint:
    def test_returns_200(self, tmp_path, monkeypatch):
        """エンドポイントが 200 を返すこと"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"; pred_dir.mkdir()
        result_dir = tmp_path / "race_results";    result_dir.mkdir()
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        resp = client.get("/api/v1/scoring")
        assert resp.status_code == 200

    def test_response_schema(self, tmp_path, monkeypatch):
        """レスポンスに必須フィールドが含まれること"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"; pred_dir.mkdir()
        result_dir = tmp_path / "race_results";    result_dir.mkdir()
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        body = client.get("/api/v1/scoring").json()
        for key in ("n_predictions", "n_results", "n_scored", "hit_rate", "by_date", "by_venue"):
            assert key in body

    def test_hit_rate_correct(self, tmp_path, monkeypatch):
        """2勝1敗のとき hit_rate ≈ 0.667"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        # 1号艇最高確率 → 1着が来れば的中
        _write_prediction(pred_dir, "r1", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_prediction(pred_dir, "r2", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_prediction(pred_dir, "r3", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
        _write_result(result_dir, "r1", true_winner=1)   # 的中
        _write_result(result_dir, "r2", true_winner=1)   # 的中
        _write_result(result_dir, "r3", true_winner=3)   # 外れ

        body = client.get("/api/v1/scoring").json()
        assert body["n_scored"] == 3
        assert body["n_correct"] == 2
        assert abs(body["hit_rate"] - 2/3) < 0.01

    def test_by_date_grouping(self, tmp_path, monkeypatch):
        """日別集計が by_date に含まれること"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        _write_prediction(pred_dir, "20260420_01_R01", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1],
                          race_date="20260420")
        _write_result(result_dir, "20260420_01_R01", true_winner=1)

        body = client.get("/api/v1/scoring").json()
        assert len(body["by_date"]) >= 1
        assert any(d["date"] == "20260420" for d in body["by_date"])

    def test_by_venue_grouping(self, tmp_path, monkeypatch):
        """場別集計が by_venue に含まれること"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        _write_prediction(pred_dir, "20260420_06_R01", [0.5, 0.1, 0.1, 0.1, 0.1, 0.1],
                          jyo_code="06")
        _write_result(result_dir, "20260420_06_R01", true_winner=1)

        body = client.get("/api/v1/scoring").json()
        assert any(v["jyo_code"] == "06" for v in body["by_venue"])


# ============================================================
# GET /api/v1/scoring/race/{race_id}
# ============================================================

class TestRaceScoreEndpoint:
    def test_both_present_returns_200(self, tmp_path, monkeypatch):
        """予測と結果が両方あるとき 200 を返すこと"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        _write_prediction(pred_dir, "r_single", [0.4, 0.2, 0.1, 0.1, 0.1, 0.1])
        _write_result(result_dir, "r_single", true_winner=1)

        resp = client.get("/api/v1/scoring/race/r_single")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_correct"] is True
        assert body["predicted_winner"] == 1

    def test_missing_returns_404(self, tmp_path, monkeypatch):
        """予測も結果もないとき 404 を返すこと"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"; pred_dir.mkdir()
        result_dir = tmp_path / "race_results";    result_dir.mkdir()
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        resp = client.get("/api/v1/scoring/race/no_such_race")
        assert resp.status_code == 404

    def test_prediction_only_returns_200(self, tmp_path, monkeypatch):
        """予測のみでも 200 を返すこと（has_result=False）"""
        import app.api.scoring as sc
        pred_dir   = tmp_path / "prediction_logs"
        result_dir = tmp_path / "race_results"; result_dir.mkdir()
        monkeypatch.setattr(sc, "PREDICTION_LOG_DIR", pred_dir)
        monkeypatch.setattr(sc, "RESULT_LOG_DIR",     result_dir)

        _write_prediction(pred_dir, "r_pred_only", [1/6] * 6)

        resp = client.get("/api/v1/scoring/race/r_pred_only")
        assert resp.status_code == 200
        assert resp.json()["has_prediction"] is True
        assert resp.json()["has_result"] is False


# ============================================================
# feedback.py の _load_prediction_log 修正テスト
# ============================================================

class TestLoadPredictionLogFix:
    def test_reads_from_prediction_logs_dir(self, tmp_path, monkeypatch):
        """data/prediction_logs/{race_id}.json を読み込めること"""
        import app.api.feedback as fb

        pred_dir = tmp_path / "prediction_logs"
        pred_dir.mkdir()
        record = {
            "race_id":          "r_fix",
            "win_probabilities": [0.4, 0.2, 0.1, 0.1, 0.1, 0.1],
        }
        (pred_dir / "r_fix.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        # モジュール変数を tmp_path 以下に向ける
        monkeypatch.setattr(fb, "PREDICTION_LOG_DIR", pred_dir)

        result = fb._load_prediction_log("r_fix")
        assert result is not None
        assert "win_probabilities" in result

    def test_compare_uses_win_probabilities(self, tmp_path, monkeypatch):
        """win_probabilities フィールドで比較が動くこと"""
        from app.api.feedback import _compare_prediction, RaceResultRequest
        import app.api.feedback as fb

        pred_log = {
            "race_id":          "r_cmp",
            "win_probabilities": [0.5, 0.1, 0.1, 0.1, 0.1, 0.1],
        }
        monkeypatch.setattr(fb, "_load_prediction_log", lambda rid: pred_log)

        req = RaceResultRequest(true_winner=1)
        cmp = _compare_prediction(req, "r_cmp")

        assert cmp["predicted_winner"] == 1
        assert cmp["is_correct"] is True
