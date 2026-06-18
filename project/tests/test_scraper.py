"""
scraper.py のテスト

実際の HTTP リクエストは送らない。requests.Session と
CircuitBreaker をモックして動作を検証する。
"""
import csv
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# check_robots
# ============================================================

class TestCheckRobots:
    def test_allowed_url_returns_true(self):
        """robots.txt が許可している URL で True を返すこと"""
        import scraper
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = True

        with patch("scraper.urllib.robotparser.RobotFileParser", return_value=mock_rp):
            assert scraper.check_robots("https://example.com/allowed") is True

    def test_disallowed_url_returns_false(self):
        """robots.txt が禁止している URL で False を返すこと"""
        import scraper
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False

        with patch("scraper.urllib.robotparser.RobotFileParser", return_value=mock_rp):
            assert scraper.check_robots("https://example.com/disallowed") is False

    def test_robots_read_failure_returns_true(self):
        """robots.txt の読み込み失敗時はアクセスを許可（True）すること"""
        import scraper
        mock_rp = MagicMock()
        mock_rp.read.side_effect = Exception("network error")
        mock_rp.can_fetch.return_value = True

        with patch("scraper.urllib.robotparser.RobotFileParser", return_value=mock_rp):
            assert scraper.check_robots("https://example.com/any") is True


# ============================================================
# fetch_page
# ============================================================

class TestFetchPage:
    def test_dry_run_returns_none(self):
        """dry_run=True のとき None を返すこと（HTTP リクエストなし）"""
        import scraper
        result = scraper.fetch_page("https://example.com", dry_run=True)
        assert result is None

    def test_robots_disallowed_returns_none(self):
        """robots.txt が禁止するURLで None を返すこと"""
        import scraper
        with patch("scraper.check_robots", return_value=False):
            result = scraper.fetch_page("https://example.com/forbidden")
        assert result is None

    def test_successful_fetch_returns_html(self):
        """正常レスポンス時に HTML 文字列を返すこと"""
        import scraper
        mock_resp = MagicMock()
        mock_resp.text = "<html>test</html>"
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.url = "https://example.com"
        mock_resp.status_code = 200

        with patch("scraper.check_robots", return_value=True), \
             patch("scraper._site_cb") as mock_cb:
            mock_cb.execute.return_value = mock_resp
            result = scraper.fetch_page("https://example.com")

        assert result == "<html>test</html>"

    def test_circuit_open_returns_none(self):
        """サーキットブレーカー OPEN 時に None を返すこと"""
        import scraper
        from app.utils.retry import CircuitOpenError

        with patch("scraper.check_robots", return_value=True), \
             patch("scraper._site_cb") as mock_cb:
            mock_cb.execute.side_effect = CircuitOpenError("OPEN")
            result = scraper.fetch_page("https://example.com")

        assert result is None

    def test_404_returns_none(self):
        """404 HTTP エラー時に None を返すこと"""
        import scraper
        mock_response = MagicMock()
        mock_response.status_code = 404
        http_err = requests.exceptions.HTTPError(response=mock_response)

        with patch("scraper.check_robots", return_value=True), \
             patch("scraper._site_cb") as mock_cb:
            mock_cb.execute.side_effect = http_err
            result = scraper.fetch_page("https://example.com")

        assert result is None

    def test_request_exception_returns_none(self):
        """一般的なリクエストエラー時に None を返すこと"""
        import scraper
        with patch("scraper.check_robots", return_value=True), \
             patch("scraper._site_cb") as mock_cb:
            mock_cb.execute.side_effect = requests.exceptions.ConnectionError("down")
            result = scraper.fetch_page("https://example.com")

        assert result is None


# ============================================================
# parse_race_results
# ============================================================

class TestParseRaceResults:
    def test_empty_html_returns_empty_list(self):
        """テーブルがない HTML で空リストを返すこと"""
        import scraper
        result = scraper.parse_race_results("<html><body></body></html>", "01", "20260412")
        assert result == []

    def test_parses_table_rows(self):
        """テーブル行をパースして辞書リストを返すこと"""
        import scraper
        html = """
        <html><body>
        <table class="is-w748">
          <tbody>
            <tr>
              <td>1</td><td>1</td><td>1</td>
              <td>R0001</td><td>テスト選手</td><td>1:50.0</td>
            </tr>
          </tbody>
        </table>
        </body></html>
        """
        result = scraper.parse_race_results(html, "01", "20260412")
        assert len(result) == 1
        assert result[0]["jyo_code"] == "01"
        assert result[0]["date"] == "20260412"

    def test_skips_short_rows(self):
        """カラム数が6未満の行をスキップすること"""
        import scraper
        html = """
        <html><body>
        <table class="is-w748">
          <tbody>
            <tr><td>1</td><td>2</td></tr>
          </tbody>
        </table>
        </body></html>
        """
        result = scraper.parse_race_results(html, "01", "20260412")
        assert result == []


# ============================================================
# parse_racer_info
# ============================================================

class TestParseRacerInfo:
    def test_empty_html_returns_empty(self):
        """テーブルがない HTML で空リストを返すこと"""
        import scraper
        assert scraper.parse_racer_info("<html></html>") == []

    def test_skips_rows_with_too_few_cells(self):
        """カラム数が5未満の行をスキップすること"""
        import scraper
        html = """
        <html><body>
        <table class="is-w748">
          <tbody><tr><td>a</td><td>b</td></tr></tbody>
        </table>
        </body></html>
        """
        assert scraper.parse_racer_info(html) == []


# ============================================================
# save_to_csv
# ============================================================

class TestSaveToCsv:
    def test_saves_records_to_csv(self, tmp_path, monkeypatch):
        """レコードが CSV に保存されること"""
        import scraper
        monkeypatch.setattr(scraper, "OUTPUT_DIR", tmp_path / "scraped")

        records = [{"date": "20260412", "jyo_code": "01", "race_no": "1"}]
        scraper.save_to_csv(records, "test_results.csv")

        files = list((tmp_path / "scraped").glob("*.csv"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "20260412" in content

    def test_empty_records_does_not_create_file(self, tmp_path, monkeypatch):
        """空リストのとき何もしないこと"""
        import scraper
        monkeypatch.setattr(scraper, "OUTPUT_DIR", tmp_path / "scraped")
        scraper.save_to_csv([], "empty.csv")
        assert not (tmp_path / "scraped" / "empty.csv").exists()

    def test_appends_to_existing_file(self, tmp_path, monkeypatch):
        """既存ファイルに追記すること（ヘッダーは1回のみ）"""
        import scraper
        monkeypatch.setattr(scraper, "OUTPUT_DIR", tmp_path / "scraped")

        rec = [{"date": "20260412", "jyo_code": "01"}]
        scraper.save_to_csv(rec, "out.csv")
        scraper.save_to_csv(rec, "out.csv")

        path = tmp_path / "scraped" / "out.csv"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3  # header + 2 rows


# ============================================================
# scrape_race_results（ドライラン）
# ============================================================

class TestScrapeRaceResults:
    def test_dry_run_returns_empty_list(self):
        """dry_run=True で HTTP リクエストを送らず空リストを返すこと"""
        import scraper
        from datetime import date

        result = scraper.scrape_race_results(
            start_date=date(2026, 4, 12),
            end_date=date(2026, 4, 12),
            jyo_codes=["01"],
            dry_run=True,
        )
        assert result == []

    def test_dry_run_does_not_sleep(self):
        """dry_run=True のとき polite_sleep が呼ばれないこと"""
        import scraper
        from datetime import date

        with patch("scraper.polite_sleep") as mock_sleep:
            scraper.scrape_race_results(
                start_date=date(2026, 4, 12),
                end_date=date(2026, 4, 12),
                jyo_codes=["01"],
                dry_run=True,
            )
        mock_sleep.assert_not_called()


# ============================================================
# polite_sleep
# ============================================================

class TestPoliteSleep:
    def test_sleeps_within_range(self):
        """MIN_SLEEP〜MAX_SLEEP の範囲でスリープすること"""
        import scraper
        sleep_calls = []
        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            scraper.polite_sleep()

        assert len(sleep_calls) == 1
        assert scraper.MIN_SLEEP <= sleep_calls[0] <= scraper.MAX_SLEEP
