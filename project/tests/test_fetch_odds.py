"""
fetch_odds.py のテスト
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# fetch_win_odds
# ============================================================

class TestFetchWinOdds:
    def test_dry_run_returns_six_boats(self):
        """dry_run=True で6艇分のオッズが返ること"""
        from scripts.fetch_odds import fetch_win_odds

        odds = fetch_win_odds("01", "20260412", 1, dry_run=True)
        assert len(odds) == 6
        for boat in ["1", "2", "3", "4", "5", "6"]:
            assert boat in odds
            assert isinstance(odds[boat], float)

    def test_dry_run_inner_boat_lower_odds(self):
        """内側コース（1号艇）のオッズが外側（6号艇）より低いこと"""
        from scripts.fetch_odds import fetch_win_odds

        odds = fetch_win_odds("01", "20260412", 1, dry_run=True)
        assert odds["1"] < odds["6"]

    def test_network_error_returns_empty(self):
        """接続エラー時（リトライ上限到達後）に空dictを返すこと"""
        from scripts.fetch_odds import fetch_win_odds

        with patch("scripts.fetch_odds._fetch_html", return_value=None):
            result = fetch_win_odds("01", "20260412", 1, dry_run=False)
        assert result == {}

    def test_success_returns_parsed_odds(self):
        """正常レスポンス時にパース結果を返すこと"""
        from scripts.fetch_odds import fetch_win_odds

        dummy_html = "<html><body>mock</body></html>"
        expected = {"1": 2.5, "2": 4.0}

        with patch("scripts.fetch_odds._fetch_html", return_value=dummy_html), \
             patch("scripts.fetch_odds._parse_win_odds", return_value=expected):
            result = fetch_win_odds("01", "20260412", 1, dry_run=False)

        assert result == expected


# ============================================================
# fetch_trifecta_odds
# ============================================================

class TestFetchTrifectaOdds:
    def test_dry_run_returns_120_combos(self):
        """dry_run=True で120通りの三連単オッズが返ること"""
        from scripts.fetch_odds import fetch_trifecta_odds

        odds = fetch_trifecta_odds("01", "20260412", 1, dry_run=True)
        assert len(odds) == 120  # 6P3 = 120

    def test_dry_run_key_format(self):
        """キーが "a-b-c" フォーマットであること"""
        from scripts.fetch_odds import fetch_trifecta_odds

        odds = fetch_trifecta_odds("01", "20260412", 1, dry_run=True)
        for key in odds:
            parts = key.split("-")
            assert len(parts) == 3
            assert all(p.isdigit() for p in parts)

    def test_network_error_returns_empty(self):
        """接続エラー時に空dictを返すこと"""
        from scripts.fetch_odds import fetch_trifecta_odds

        with patch("scripts.fetch_odds._fetch_html", return_value=None):
            result = fetch_trifecta_odds("01", "20260412", 1, dry_run=False)
        assert result == {}

    def test_success_returns_parsed_odds(self):
        """正常レスポンス時にパース結果を返すこと"""
        from scripts.fetch_odds import fetch_trifecta_odds

        dummy_html = "<html><body>mock</body></html>"
        expected = {"1-2-3": 12.5, "2-1-3": 30.0}

        with patch("scripts.fetch_odds._fetch_html", return_value=dummy_html), \
             patch("scripts.fetch_odds._parse_trifecta_odds", return_value=expected):
            result = fetch_trifecta_odds("01", "20260412", 1, dry_run=False)

        assert result == expected


# ============================================================
# _fetch_html（サーキットブレーカー統合）
# ============================================================

class TestFetchHtml:
    def test_circuit_open_returns_none(self):
        """`CircuitOpenError` 発生時に None を返すこと"""
        from scripts.fetch_odds import _fetch_html
        from app.utils.retry import CircuitOpenError

        with patch("scripts.fetch_odds._odds_cb") as mock_cb:
            mock_cb.execute.side_effect = CircuitOpenError("OPEN")
            result = _fetch_html("http://example.com", {})

        assert result is None

    def test_http_error_returns_none(self):
        """HTTP エラー時に None を返すこと"""
        from scripts.fetch_odds import _fetch_html

        mock_response = MagicMock()
        mock_response.status_code = 503
        http_err = requests.exceptions.HTTPError(response=mock_response)

        with patch("scripts.fetch_odds._odds_cb") as mock_cb:
            mock_cb.execute.side_effect = http_err
            result = _fetch_html("http://example.com", {})

        assert result is None

    def test_request_exception_returns_none(self):
        """RequestException 時に None を返すこと"""
        from scripts.fetch_odds import _fetch_html

        with patch("scripts.fetch_odds._odds_cb") as mock_cb:
            mock_cb.execute.side_effect = requests.exceptions.ConnectionError("down")
            result = _fetch_html("http://example.com", {})

        assert result is None

    def test_success_returns_html(self):
        """正常時に HTML 文字列を返すこと"""
        from scripts.fetch_odds import _fetch_html

        mock_resp = MagicMock()
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.text = "<html>ok</html>"

        with patch("scripts.fetch_odds._odds_cb") as mock_cb:
            mock_cb.execute.return_value = mock_resp
            result = _fetch_html("http://example.com", {"hd": "20260412"})

        assert result == "<html>ok</html>"


# ============================================================
# save_odds / load_odds
# ============================================================

class TestSaveLoadOdds:
    def test_save_creates_file(self, tmp_path, monkeypatch):
        """save_odds がファイルを作成すること"""
        import scripts.fetch_odds as fo_module
        monkeypatch.setattr(fo_module, "OUTPUT_DIR", tmp_path / "odds")

        from scripts.fetch_odds import save_odds

        data = {"win_odds": {"1": 2.3}, "trifecta_odds": {}}
        path = save_odds(data, "01", "20260412", 3)

        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["win_odds"]["1"] == 2.3

    def test_load_returns_none_when_missing(self, tmp_path, monkeypatch):
        """存在しないファイルで None を返すこと"""
        import scripts.fetch_odds as fo_module
        monkeypatch.setattr(fo_module, "OUTPUT_DIR", tmp_path / "odds")

        from scripts.fetch_odds import load_odds

        assert load_odds("99", "20990101", 99) is None

    def test_save_then_load_roundtrip(self, tmp_path, monkeypatch):
        """保存→読み込みのラウンドトリップが正確なこと"""
        import scripts.fetch_odds as fo_module
        monkeypatch.setattr(fo_module, "OUTPUT_DIR", tmp_path / "odds")

        from scripts.fetch_odds import save_odds, load_odds

        data = {
            "jyo_code": "02",
            "race_no": 5,
            "win_odds": {"1": 1.5, "6": 50.0},
        }
        save_odds(data, "02", "20260412", 5)
        loaded = load_odds("02", "20260412", 5)

        assert loaded is not None
        assert loaded["win_odds"]["6"] == 50.0


# ============================================================
# predict_with_odds
# ============================================================

class TestPredictWithOdds:
    def test_api_success_returns_json(self):
        """API 呼び出し成功時にレスポンス dict を返すこと"""
        from scripts.fetch_odds import predict_with_odds

        expected = {"recommendations": [{"combination": [1, 2, 3], "probability": 0.1}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp):
            result = predict_with_odds({}, {"1": 2.0}, api_key="test-key")

        assert result == expected

    def test_api_failure_returns_none(self):
        """API 呼び出し失敗時に None を返すこと"""
        from scripts.fetch_odds import predict_with_odds

        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            result = predict_with_odds({}, {})

        assert result is None

    def test_api_key_added_to_headers(self):
        """api_key が X-API-Key ヘッダーに設定されること"""
        from scripts.fetch_odds import predict_with_odds

        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        captured = {}

        def fake_post(url, json, headers, timeout):
            captured["headers"] = headers
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            predict_with_odds({}, {}, api_key="secret-key")

        assert captured["headers"].get("X-API-Key") == "secret-key"

    def test_no_api_key_no_header(self):
        """api_key が空文字のとき X-API-Key ヘッダーがないこと"""
        from scripts.fetch_odds import predict_with_odds

        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        captured = {}

        def fake_post(url, json, headers, timeout):
            captured["headers"] = headers
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            predict_with_odds({}, {}, api_key="")

        assert "X-API-Key" not in captured["headers"]
