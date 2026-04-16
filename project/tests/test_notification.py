"""
app/utils/notification.py のテスト

実際の HTTP リクエストは送らない。
requests.post をモックして動作を検証する。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# send_slack
# ============================================================

class TestSendSlack:
    def test_no_url_returns_false(self, monkeypatch):
        """Webhook URL 未設定時に False を返すこと"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "")
        assert notif.send_slack("test") is False

    def test_explicit_url_sends_post(self, monkeypatch):
        """URL を引数で渡したとき requests.post が呼ばれること"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch("requests.post", return_value=mock_resp) as mock_post:
            import app.utils.notification as notif
            result = notif.send_slack("hello", webhook_url="https://hooks.slack.com/test")
        assert result is True
        mock_post.assert_called_once()

    def test_request_exception_returns_false(self, monkeypatch):
        """HTTP エラー時に False を返すこと（例外を握りつぶす）"""
        import requests
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "https://hooks.slack.com/x")
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            assert notif.send_slack("msg") is False

    def test_http_error_returns_false(self, monkeypatch):
        """HTTPError 時に False を返すこと"""
        import requests
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "https://hooks.slack.com/x")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        with patch("requests.post", return_value=mock_resp):
            assert notif.send_slack("msg") is False

    def test_message_included_in_payload(self, monkeypatch):
        """メッセージが payload の "text" フィールドに含まれること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "https://hooks.slack.com/x")
        captured = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        def fake_post(url, json, timeout):
            captured["json"] = json
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            notif.send_slack("テストメッセージ")

        assert captured["json"]["text"] == "テストメッセージ"


# ============================================================
# send_line
# ============================================================

class TestSendLine:
    def test_no_token_returns_false(self, monkeypatch):
        """LINE トークン未設定時に False を返すこと"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_LINE_TOKEN", "")
        assert notif.send_line("test") is False

    def test_explicit_token_sends_post(self):
        """トークンを引数で渡したとき requests.post が呼ばれること"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch("requests.post", return_value=mock_resp) as mock_post:
            import app.utils.notification as notif
            result = notif.send_line("hello", token="test_token_abc")
        assert result is True
        mock_post.assert_called_once()

    def test_request_exception_returns_false(self, monkeypatch):
        """接続エラー時に False を返すこと"""
        import requests
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_LINE_TOKEN", "tok")
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            assert notif.send_line("msg") is False

    def test_message_truncated_to_1000(self, monkeypatch):
        """メッセージが 1000 文字以上のとき切り詰められること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_LINE_TOKEN", "tok")
        captured = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        def fake_post(url, headers, data, timeout):
            captured["data"] = data
            return mock_resp

        long_msg = "あ" * 2000
        with patch("requests.post", side_effect=fake_post):
            notif.send_line(long_msg)

        # data["message"] は "\n" + 最大1000文字
        assert len(captured["data"]["message"]) <= 1001  # "\n" + 1000

    def test_auth_header_contains_token(self, monkeypatch):
        """Authorization ヘッダーにトークンが含まれること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_LINE_TOKEN", "mytoken123")
        captured = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        def fake_post(url, headers, data, timeout):
            captured["headers"] = headers
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            notif.send_line("msg")

        assert "mytoken123" in captured["headers"]["Authorization"]


# ============================================================
# notify (async)
# ============================================================

class TestNotifyAsync:
    @pytest.mark.anyio
    async def test_disabled_returns_empty_dict(self, monkeypatch):
        """NOTIFY_ENABLED=false のとき空 dict を返すこと"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", False)
        result = await notif.notify("テスト")
        assert result == {}

    @pytest.mark.anyio
    async def test_no_webhooks_returns_empty_dict(self, monkeypatch):
        """ENABLED=true だが webhook/token 未設定のとき空 dict を返すこと"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", True)
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "")
        monkeypatch.setattr(notif, "_LINE_TOKEN", "")
        result = await notif.notify("テスト")
        assert result == {}

    @pytest.mark.anyio
    async def test_slack_channel_called(self, monkeypatch):
        """ENABLED=true + Slack URL 設定時に Slack へ送信されること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", True)
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "https://hooks.slack.com/x")
        monkeypatch.setattr(notif, "_LINE_TOKEN", "")

        with patch("app.utils.notification.send_slack", return_value=True) as mock_slack:
            result = await notif.notify("hello", channels=["slack"])

        assert "slack" in result
        assert result["slack"] is True

    @pytest.mark.anyio
    async def test_line_channel_called(self, monkeypatch):
        """ENABLED=true + LINE トークン設定時に LINE へ送信されること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", True)
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "")
        monkeypatch.setattr(notif, "_LINE_TOKEN", "tok")

        with patch("app.utils.notification.send_line", return_value=True) as mock_line:
            result = await notif.notify("hello", channels=["line"])

        assert "line" in result
        assert result["line"] is True


# ============================================================
# notify_sync
# ============================================================

class TestNotifySync:
    def test_disabled_returns_empty(self, monkeypatch):
        """無効時に空 dict を返すこと"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", False)
        assert notif.notify_sync("msg") == {}

    def test_slack_called_when_configured(self, monkeypatch):
        """Slack が設定済みのとき send_slack が呼ばれること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", True)
        monkeypatch.setattr(notif, "_SLACK_WEBHOOK", "https://x")
        with patch("app.utils.notification.send_slack", return_value=True) as mock_s:
            notif.notify_sync("hi", channels=["slack"])
        mock_s.assert_called_once_with("hi")

    def test_line_called_when_configured(self, monkeypatch):
        """LINE が設定済みのとき send_line が呼ばれること"""
        import app.utils.notification as notif
        monkeypatch.setattr(notif, "_ENABLED", True)
        monkeypatch.setattr(notif, "_LINE_TOKEN", "tok")
        with patch("app.utils.notification.send_line", return_value=True) as mock_l:
            notif.notify_sync("hi", channels=["line"])
        mock_l.assert_called_once_with("hi")


# ============================================================
# build_prediction_summary
# ============================================================

class TestBuildPredictionSummary:
    def test_contains_race_id(self):
        """レースIDがメッセージに含まれること"""
        from app.utils.notification import build_prediction_summary
        msg = build_prediction_summary("race_001", [0.4, 0.2, 0.15, 0.1, 0.1, 0.05])
        assert "race_001" in msg

    def test_shows_top_3(self):
        """上位3艇が含まれること"""
        from app.utils.notification import build_prediction_summary
        msg = build_prediction_summary("r1", [0.4, 0.3, 0.15, 0.05, 0.05, 0.05])
        # 上位3位の表示を確認（1位・2位・3位）
        assert "1位" in msg
        assert "2位" in msg
        assert "3位" in msg

    def test_highest_prob_is_first(self):
        """最高確率の艇が1位に表示されること"""
        from app.utils.notification import build_prediction_summary
        # 3号艇が最高確率
        proba = [0.1, 0.1, 0.5, 0.1, 0.1, 0.1]
        msg = build_prediction_summary("r1", proba)
        lines = [l for l in msg.splitlines() if "1位" in l]
        assert len(lines) == 1
        assert "3号艇" in lines[0]

    def test_probability_displayed_as_percentage(self):
        """確率がパーセント表示されること"""
        from app.utils.notification import build_prediction_summary
        msg = build_prediction_summary("r1", [1/6]*6)
        assert "%" in msg


# ============================================================
# build_retrain_summary
# ============================================================

class TestBuildRetrainSummary:
    def test_contains_version(self):
        """バージョン名が含まれること"""
        from app.utils.notification import build_retrain_summary
        msg = build_retrain_summary("boat_race_model_v20260412_1", {
            "cv_logloss_mean": 1.5, "cv_accuracy_mean": 0.28, "n_samples": 12000
        })
        assert "boat_race_model_v20260412_1" in msg

    def test_contains_metrics(self):
        """LogLoss / Accuracy / サンプル数が含まれること"""
        from app.utils.notification import build_retrain_summary
        msg = build_retrain_summary("v1", {
            "cv_logloss_mean": 1.4567, "cv_accuracy_mean": 0.3, "n_samples": 5000
        })
        assert "1.4567" in msg
        assert "30.0" in msg    # 0.3 → 30.0%
        assert "5,000" in msg   # カンマ区切り

    def test_missing_metrics_use_defaults(self):
        """メトリクスが欠けていてもエラーにならないこと"""
        from app.utils.notification import build_retrain_summary
        msg = build_retrain_summary("v1", {})
        assert "v1" in msg
