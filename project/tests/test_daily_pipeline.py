"""
scripts/run_daily_pipeline.py のテスト
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# フィクスチャ
# ============================================================

MOCK_PREDICT_RESULT = {
    "win_probabilities": [0.35, 0.22, 0.15, 0.12, 0.09, 0.07],
    "trifecta": [
        {"combination": [1, 2, 3], "probability": 0.042, "rank": 1},
        {"combination": [1, 2, 4], "probability": 0.038, "rank": 2},
        {"combination": [1, 3, 2], "probability": 0.031, "rank": 3},
    ],
    "recommendations": [],
}


# ============================================================
# build_sample_race_data
# ============================================================

class TestBuildSampleRaceData:
    def test_returns_6_boats(self):
        """6 艇分のデータが返ること"""
        from scripts.run_daily_pipeline import build_sample_race_data
        data = build_sample_race_data("01", 1)
        assert len(data["boats"]) == 6

    def test_boat_numbers_1_to_6(self):
        """艇番が 1〜6 であること"""
        from scripts.run_daily_pipeline import build_sample_race_data
        data = build_sample_race_data("01", 1)
        boat_nums = [b["boat_number"] for b in data["boats"]]
        assert boat_nums == [1, 2, 3, 4, 5, 6]

    def test_weather_field_present(self):
        """weather フィールドが含まれること"""
        from scripts.run_daily_pipeline import build_sample_race_data
        data = build_sample_race_data("01", 1)
        assert "weather" in data
        assert "wind_speed" in data["weather"]

    def test_win_odds_embedded(self):
        """win_odds を渡すと odds フィールドに格納されること"""
        from scripts.run_daily_pipeline import build_sample_race_data
        odds = {"1": 2.5, "2": 3.0}
        data = build_sample_race_data("01", 1, win_odds=odds)
        assert data["odds"] == odds

    def test_no_odds_no_field(self):
        """win_odds=None のとき odds フィールドがないこと"""
        from scripts.run_daily_pipeline import build_sample_race_data
        data = build_sample_race_data("01", 1, win_odds=None)
        assert "odds" not in data

    def test_reproducible_with_same_seed(self):
        """同じ場コード・レース番号では同一の結果を返すこと"""
        from scripts.run_daily_pipeline import build_sample_race_data
        d1 = build_sample_race_data("06", 3)
        d2 = build_sample_race_data("06", 3)
        assert d1["boats"][0]["win_rate"] == d2["boats"][0]["win_rate"]

    def test_different_seeds_differ(self):
        """異なる場コード・レース番号では結果が変わること"""
        from scripts.run_daily_pipeline import build_sample_race_data
        d1 = build_sample_race_data("01", 1)
        d2 = build_sample_race_data("06", 9)
        assert d1["boats"][0]["win_rate"] != d2["boats"][0]["win_rate"]


# ============================================================
# run_race_prediction
# ============================================================

class TestRunRacePrediction:
    def test_returns_prediction_log(self):
        """正常時に予測ログ dict を返すこと"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            log = run_race_prediction("01", "20260420", 1, dry_run=True)
        assert log is not None
        assert log["race_id"] == "20260420_01_R01"
        assert "win_probabilities" in log

    def test_top1_boat_correct(self):
        """最高確率の艇番が top1_boat に入ること"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            log = run_race_prediction("01", "20260420", 2, dry_run=True)
        # proba[0]=0.35 が最大 → 1号艇
        assert log["top1_boat"] == 1

    def test_model_not_found_returns_none(self):
        """モデル未学習のとき None を返すこと（例外を伝播させない）"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch(
            "scripts.run_daily_pipeline.predict_race",
            side_effect=FileNotFoundError("モデルなし"),
        ):
            log = run_race_prediction("01", "20260420", 1, dry_run=True)
        assert log is None

    def test_predict_error_returns_none(self):
        """予測エラーのとき None を返すこと（パイプライン継続）"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch(
            "scripts.run_daily_pipeline.predict_race",
            side_effect=RuntimeError("不正な入力"),
        ):
            log = run_race_prediction("01", "20260420", 1, dry_run=True)
        assert log is None

    def test_dry_run_flag_saved(self):
        """dry_run フラグがログに記録されること"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            log = run_race_prediction("01", "20260420", 1, dry_run=True)
        assert log["dry_run"] is True

    def test_race_id_format(self):
        """race_id が date_jyo_Rnn 形式であること"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            log = run_race_prediction("06", "20260420", 12, dry_run=True)
        assert log["race_id"] == "20260420_06_R12"

    def test_trifecta_top3_included(self):
        """三連単上位3組み合わせがログに含まれること"""
        from scripts.run_daily_pipeline import run_race_prediction
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            log = run_race_prediction("01", "20260420", 1, dry_run=True)
        assert len(log["trifecta_top3"]) == 3


# ============================================================
# save_prediction_log
# ============================================================

class TestSavePredictionLog:
    def test_creates_json_file(self, tmp_path, monkeypatch):
        """JSON ファイルが作成されること"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)

        log = {
            "race_id": "20260420_01_R01",
            "jyo_code": "01",
            "race_date": "20260420",
            "race_no": 1,
            "win_probabilities": [1/6] * 6,
            "top1_boat": 1,
            "trifecta_top3": [[1, 2, 3]],
            "win_odds": {},
            "dry_run": True,
            "predicted_at": "2026-04-20T00:00:00+00:00",
        }
        path = pl.save_prediction_log(log)
        assert path.exists()

    def test_json_content_correct(self, tmp_path, monkeypatch):
        """保存内容が正しいこと"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)

        log = {
            "race_id": "20260420_02_R05",
            "jyo_code": "02",
            "race_date": "20260420",
            "race_no": 5,
            "win_probabilities": [0.4, 0.2, 0.1, 0.1, 0.1, 0.1],
            "top1_boat": 1,
            "trifecta_top3": [[1, 2, 3]],
            "win_odds": {"1": 2.5},
            "dry_run": False,
            "predicted_at": "2026-04-20T01:00:00+00:00",
        }
        path = pl.save_prediction_log(log)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["race_id"] == "20260420_02_R05"
        assert loaded["top1_boat"] == 1


# ============================================================
# build_daily_summary
# ============================================================

class TestBuildDailySummary:
    def _make_logs(self, n: int):
        logs = []
        for i in range(n):
            logs.append({
                "race_id": f"20260420_01_R{i+1:02d}",
                "top1_boat": (i % 6) + 1,
                "win_probabilities": [1/6] * 6,
            })
        return logs

    def test_contains_date(self):
        """サマリーに日付が含まれること"""
        from scripts.run_daily_pipeline import build_daily_summary
        msg = build_daily_summary(self._make_logs(3), ["01"], "20260420")
        assert "20260420" in msg

    def test_contains_jyo_codes(self):
        """場コードが含まれること"""
        from scripts.run_daily_pipeline import build_daily_summary
        msg = build_daily_summary(self._make_logs(2), ["01", "06"], "20260420")
        assert "01" in msg
        assert "06" in msg

    def test_shows_total_count(self):
        """予測レース数が表示されること"""
        from scripts.run_daily_pipeline import build_daily_summary
        msg = build_daily_summary(self._make_logs(6), ["01"], "20260420")
        assert "6" in msg

    def test_failed_results_counted(self):
        """None（失敗）がカウントされること"""
        from scripts.run_daily_pipeline import build_daily_summary
        logs = self._make_logs(4) + [None, None]
        msg = build_daily_summary(logs, ["01"], "20260420")
        assert "失敗" in msg

    def test_truncates_at_5(self):
        """6件以上は先頭5件の詳細のみ表示されること"""
        from scripts.run_daily_pipeline import build_daily_summary
        msg = build_daily_summary(self._make_logs(10), ["01"], "20260420")
        assert "他" in msg or "..." in msg


# ============================================================
# main() フロー
# ============================================================

class TestMainFlow:
    def test_dry_run_completes(self, tmp_path, monkeypatch, capsys):
        """--dry-run で例外なく完了すること"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_daily_pipeline.py",
            "--jyo", "01",
            "--races", "1", "2",
            "--dry-run", "--no-notify",
        ])
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            pl.main()
        out = capsys.readouterr().out
        assert "成功" in out

    def test_logs_saved(self, tmp_path, monkeypatch):
        """--dry-run で予測ログが保存されること"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_daily_pipeline.py",
            "--jyo", "01", "--races", "1",
            "--dry-run", "--no-notify",
        ])
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            pl.main()
        saved = list(tmp_path.glob("*.json"))
        assert len(saved) == 1

    def test_no_save_skips_logging(self, tmp_path, monkeypatch):
        """--no-save で JSON が作られないこと"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_daily_pipeline.py",
            "--jyo", "01", "--races", "1",
            "--dry-run", "--no-notify", "--no-save",
        ])
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            pl.main()
        assert list(tmp_path.glob("*.json")) == []

    def test_notify_called_on_success(self, tmp_path, monkeypatch):
        """通知フラグなしで notify_sync が呼ばれること"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_daily_pipeline.py",
            "--jyo", "01", "--races", "1",
            "--dry-run",
        ])
        mock_notify = MagicMock()
        monkeypatch.setattr(pl, "notify_sync", mock_notify)
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            pl.main()
        mock_notify.assert_called_once()

    def test_multiple_jyo_codes(self, tmp_path, monkeypatch):
        """複数場コードで正しいレース数が処理されること"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_daily_pipeline.py",
            "--jyo", "01", "06",
            "--races", "1", "2",
            "--dry-run", "--no-notify",
        ])
        with patch("scripts.run_daily_pipeline.predict_race", return_value=MOCK_PREDICT_RESULT):
            pl.main()
        # 場×レース = 2×2 = 4件
        assert len(list(tmp_path.glob("*.json"))) == 4

    def test_all_fail_no_notify(self, tmp_path, monkeypatch):
        """全件失敗時は通知が送られないこと"""
        import scripts.run_daily_pipeline as pl
        monkeypatch.setattr(pl, "PREDICTION_LOG_DIR", tmp_path)
        monkeypatch.setattr(sys, "argv", [
            "run_daily_pipeline.py",
            "--jyo", "01", "--races", "1",
            "--dry-run",
        ])
        mock_notify = MagicMock()
        monkeypatch.setattr(pl, "notify_sync", mock_notify)
        with patch(
            "scripts.run_daily_pipeline.predict_race",
            side_effect=FileNotFoundError("no model"),
        ):
            pl.main()
        mock_notify.assert_not_called()
