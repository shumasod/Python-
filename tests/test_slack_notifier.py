"""
SlackNotifier テスト（HTTP 送信は mock）
"""

import json
import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from rds_analyzer.notifications.slack_notifier import SlackNotifier, PRIORITY_COLORS
from rds_analyzer.analyzers.recommendation_engine import (
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from rds_analyzer.analyzers.cost_analyzer import CostAnalyzer
from rds_analyzer.models.costs import CostAnomaly
from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType
from tests.rds_conftest import make_metrics
from rds_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer


def _notifier(url="https://hooks.slack.com/fake"):
    return SlackNotifier(webhook_url=url, notify_threshold="low")


def _make_rec(priority=RecommendationPriority.HIGH, savings=100.0):
    return Recommendation(
        recommendation_id="rec_001",
        type=RecommendationType.STORAGE_TYPE_CHANGE,
        priority=priority,
        title="gp2→gp3 移行",
        description="ストレージを gp3 に変更してください",
        current_config="gp2",
        recommended_config="gp3",
        estimated_monthly_savings_usd=savings,
    )


def _make_perf(cpu_avg=90.0):
    inst = RDSInstance(
        instance_id="test-001",
        engine=EngineType.MYSQL,
        engine_version="8.0",
        instance_class="db.m5.large",
        region="ap-northeast-1",
        multi_az=False,
        storage_type=StorageType.GP2,
        allocated_storage_gb=100,
    )
    metrics = make_metrics(inst.instance_id, cpu_avg=cpu_avg, cpu_max=cpu_avg + 5)
    return PerformanceAnalyzer().analyze(inst, metrics)


class TestIsConfigured:

    def test_configured_with_url(self):
        n = SlackNotifier(webhook_url="https://hooks.slack.com/fake")
        assert n.is_configured is True

    def test_not_configured_without_url(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        n = SlackNotifier(webhook_url=None)
        assert n.is_configured is False

    def test_unconfigured_notify_returns_false(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        n = SlackNotifier(webhook_url=None)
        perf = _make_perf()
        result = n.notify_performance_alert("db-001", perf)
        assert result is False


class TestSendMechanism:

    def _mock_urlopen(self, status=200):
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_send_success_returns_true(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(200)
        n = _notifier()
        result = n._send(text="hello")
        assert result is True

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_send_non_200_returns_false(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(500)
        n = _notifier()
        result = n._send(text="hello")
        assert result is False

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_send_url_error_returns_false(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        n = _notifier()
        result = n._send(text="hello")
        assert result is False

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_payload_contains_text(self, mock_urlopen):
        captured = []

        def capture(req, timeout=None):
            captured.append(json.loads(req.data.decode()))
            return self._mock_urlopen(200)

        mock_urlopen.side_effect = capture
        n = _notifier()
        n._send(text="test message")
        assert captured[0]["text"] == "test message"


class TestPerformanceAlert:

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_bottleneck_triggers_send(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        n = _notifier()
        perf = _make_perf(cpu_avg=92.0)
        result = n.notify_performance_alert("db-001", perf)
        assert result is True
        mock_urlopen.assert_called_once()

    def test_healthy_instance_no_send(self):
        n = _notifier()
        perf = _make_perf(cpu_avg=40.0)
        # 健全な場合は has_any_bottleneck=False → 送信しない
        if not perf.has_any_bottleneck:
            result = n.notify_performance_alert("db-001", perf)
            assert result is False


class TestRecommendationsNotify:

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_recommendations_sent(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        n = _notifier()
        recs = [_make_rec(RecommendationPriority.HIGH, 200.0)]
        result = n.notify_recommendations("db-001", recs, total_savings_usd=200.0)
        assert result is True

    def test_threshold_filters_low_priority(self):
        n = SlackNotifier(webhook_url="https://hooks.slack.com/fake", notify_threshold="high")
        recs = [_make_rec(RecommendationPriority.LOW, 50.0)]
        # LOW は HIGH 閾値でフィルタされる → 送信なし
        with patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen") as m:
            result = n.notify_recommendations("db-001", recs, total_savings_usd=50.0)
        assert result is False

    def test_empty_recommendations_no_send(self):
        n = _notifier()
        result = n.notify_recommendations("db-001", [], total_savings_usd=0.0)
        assert result is False


class TestCostAnomalyNotify:

    @patch("rds_analyzer.notifications.slack_notifier.urllib.request.urlopen")
    def test_anomaly_sends_notification(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        n = _notifier()
        anomaly = CostAnomaly(
            instance_id="db-001",
            is_anomaly=True,
            anomaly_type="cost_spike",
            current_month_cost_usd=1300.0,
            previous_month_cost_usd=1000.0,
            change_ratio_pct=30.0,
            threshold_pct=20.0,
            description="コストが急増しています",
            detected_at=date.today(),
        )
        result = n.notify_cost_anomaly(anomaly, "db-001")
        assert result is True

    def test_non_anomaly_no_send(self):
        n = _notifier()
        anomaly = CostAnomaly(
            instance_id="db-001",
            is_anomaly=False,
            anomaly_type="none",
            current_month_cost_usd=1050.0,
            previous_month_cost_usd=1000.0,
            change_ratio_pct=5.0,
            threshold_pct=20.0,
            description="正常範囲",
            detected_at=date.today(),
        )
        result = n.notify_cost_anomaly(anomaly, "db-001")
        assert result is False


class TestBlockBuilders:

    def test_section_block_structure(self):
        block = SlackNotifier._section_block("hello")
        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"
        assert block["text"]["text"] == "hello"

    def test_divider_block(self):
        block = SlackNotifier._divider_block()
        assert block["type"] == "divider"

    def test_fields_block(self):
        block = SlackNotifier._fields_block(["a", "b"])
        assert block["type"] == "section"
        assert len(block["fields"]) == 2

    def test_context_block(self):
        block = SlackNotifier._context_block("ctx")
        assert block["type"] == "context"
        assert block["elements"][0]["text"] == "ctx"
