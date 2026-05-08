"""
CloudWatchCollector / LambdaHandler テスト（AWS API は mock）
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from rds_analyzer.collectors.cloudwatch_collector import (
    CloudWatchCollector,
    CW_METRICS,
)
from rds_analyzer.models.metrics import MetricsHistory, MetricsStatistics


# ──────────────────────────────────────────────────────────────
# ヘルパー
# ──────────────────────────────────────────────────────────────

def _fake_metric_data_results(value: float = 50.0) -> dict:
    """GetMetricData のレスポンス mock"""
    results = []
    for key in CW_METRICS:
        for stat in ["average", "maximum", "minimum", "p95", "p99"]:
            results.append({"Id": f"{key}_{stat}", "Values": [value, value]})
    return {"MetricDataResults": results}


def _make_collector(mock_cw=None, mock_rds=None):
    session = MagicMock()
    cw_client = mock_cw or MagicMock()
    rds_client = mock_rds or MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        cw_client if svc == "cloudwatch" else rds_client
    )
    return CloudWatchCollector(region_name="ap-northeast-1", session=session), cw_client, rds_client


# ──────────────────────────────────────────────────────────────
# collect_metrics_history
# ──────────────────────────────────────────────────────────────

class TestCollectMetricsHistory:

    def test_returns_metrics_history(self):
        """正常系: MetricsHistory が返る"""
        collector, cw, _ = _make_collector()
        cw.get_metric_data.return_value = _fake_metric_data_results(60.0)

        result = collector.collect_metrics_history("db-001", period_hours=24)

        assert isinstance(result, MetricsHistory)
        assert result.instance_id == "db-001"

    def test_cpu_avg_populated(self):
        """CPU の avg が CloudWatch 値から計算される"""
        collector, cw, _ = _make_collector()
        cw.get_metric_data.return_value = _fake_metric_data_results(40.0)

        result = collector.collect_metrics_history("db-001")
        assert result.cpu_utilization.avg == pytest.approx(40.0)

    def test_period_applied(self):
        """period_hours が start_time / end_time に反映される"""
        collector, cw, _ = _make_collector()
        cw.get_metric_data.return_value = _fake_metric_data_results()

        result = collector.collect_metrics_history("db-001", period_hours=6)
        delta = result.period_end - result.period_start
        # 秒単位で誤差 60 秒以内
        assert abs(delta.total_seconds() - 6 * 3600) < 60

    def test_empty_values_use_defaults(self):
        """データがないメトリクスはデフォルト (0) になる"""
        collector, cw, _ = _make_collector()
        # 全て空
        empty_results = [{"Id": f"{k}_{s}", "Values": []}
                         for k in CW_METRICS for s in ["average","maximum","minimum","p95","p99"]]
        cw.get_metric_data.return_value = {"MetricDataResults": empty_results}

        result = collector.collect_metrics_history("db-001")
        assert result.cpu_utilization.avg == 0.0
        assert result.cpu_utilization.sample_count == 0

    def test_cloudwatch_error_propagates(self):
        """ClientError は呼び出し元に伝播する"""
        from botocore.exceptions import ClientError
        collector, cw, _ = _make_collector()
        cw.get_metric_data.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "GetMetricData",
        )
        with pytest.raises(ClientError):
            collector.collect_metrics_history("db-001")


# ──────────────────────────────────────────────────────────────
# list_rds_instances
# ──────────────────────────────────────────────────────────────

class TestListRDSInstances:

    def _fake_db_instance(self, iid="db-001", engine="mysql"):
        return {
            "DBInstanceIdentifier": iid,
            "Engine": engine,
            "EngineVersion": "8.0",
            "DBInstanceClass": "db.m5.large",
            "DBInstanceStatus": "available",
            "MultiAZ": False,
            "StorageType": "gp2",
            "AllocatedStorage": 100,
        }

    def test_returns_list(self):
        collector, _, rds = _make_collector()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"DBInstances": [self._fake_db_instance("db-001"), self._fake_db_instance("db-002")]}
        ]
        rds.get_paginator.return_value = paginator

        result = collector.list_rds_instances()
        assert len(result) == 2
        assert result[0]["instance_id"] == "db-001"

    def test_empty_account_returns_empty(self):
        collector, _, rds = _make_collector()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"DBInstances": []}]
        rds.get_paginator.return_value = paginator

        result = collector.list_rds_instances()
        assert result == []

    def test_rds_error_propagates(self):
        from botocore.exceptions import ClientError
        collector, _, rds = _make_collector()
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DescribeDBInstances"
        )
        rds.get_paginator.return_value = paginator
        with pytest.raises(ClientError):
            collector.list_rds_instances()


# ──────────────────────────────────────────────────────────────
# _aggregate_to_statistics
# ──────────────────────────────────────────────────────────────

class TestAggregateToStatistics:

    def test_average_computed_correctly(self):
        collector, _, _ = _make_collector()
        raw = {
            "cpu_utilization_average": [10.0, 20.0, 30.0],
            "cpu_utilization_maximum": [35.0],
            "cpu_utilization_minimum": [5.0],
            "cpu_utilization_p95": [32.0],
            "cpu_utilization_p99": [34.0],
        }
        for key in CW_METRICS:
            if key == "cpu_utilization":
                continue
            for stat in ["average", "maximum", "minimum", "p95", "p99"]:
                raw[f"{key}_{stat}"] = []

        stats_map = collector._aggregate_to_statistics(raw)
        assert stats_map["cpu_utilization"].avg == pytest.approx(20.0)
        assert stats_map["cpu_utilization"].sample_count == 3

    def test_missing_key_defaults_to_zero(self):
        collector, _, _ = _make_collector()
        # 全キーを空にする
        raw = {f"{k}_{s}": [] for k in CW_METRICS
               for s in ["average", "maximum", "minimum", "p95", "p99"]}
        stats_map = collector._aggregate_to_statistics(raw)
        for key in CW_METRICS:
            assert stats_map[key].avg == 0.0


# ──────────────────────────────────────────────────────────────
# Lambda ハンドラー
# ──────────────────────────────────────────────────────────────

class TestLambdaHandler:

    @patch("rds_analyzer.collectors.lambda_handler._collect_and_forward_metrics")
    def test_success_returns_200(self, mock_collect):
        from rds_analyzer.collectors.lambda_handler import lambda_handler
        mock_collect.return_value = {"processed": ["db-001"], "errors": [], "total": 1}
        result = lambda_handler({}, None)
        assert result["statusCode"] == 200

    @patch("rds_analyzer.collectors.lambda_handler._collect_and_forward_metrics")
    def test_exception_returns_500(self, mock_collect):
        from rds_analyzer.collectors.lambda_handler import lambda_handler
        mock_collect.side_effect = RuntimeError("timeout")
        result = lambda_handler({}, None)
        assert result["statusCode"] == 500

    @patch("urllib.request.urlopen")
    @patch("rds_analyzer.collectors.cloudwatch_collector.CloudWatchCollector")
    def test_collect_and_forward_calls_api(self, MockCW, mock_urlopen):
        from rds_analyzer.collectors.lambda_handler import _collect_and_forward_metrics
        from tests.rds_conftest import make_metrics

        mock_cw = MagicMock()
        mock_cw.list_rds_instances.return_value = [
            {"instance_id": "db-001", "engine": "mysql"}
        ]
        mock_cw.collect_metrics_history.return_value = make_metrics("db-001")
        MockCW.return_value = mock_cw

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _collect_and_forward_metrics()
        assert "db-001" in result["processed"]
        assert result["errors"] == []

    @patch("urllib.request.urlopen")
    @patch("rds_analyzer.collectors.cloudwatch_collector.CloudWatchCollector")
    def test_api_error_goes_to_errors_list(self, MockCW, mock_urlopen):
        from rds_analyzer.collectors.lambda_handler import _collect_and_forward_metrics
        import urllib.error
        from tests.rds_conftest import make_metrics

        mock_cw = MagicMock()
        mock_cw.list_rds_instances.return_value = [
            {"instance_id": "db-fail", "engine": "mysql"}
        ]
        mock_cw.collect_metrics_history.return_value = make_metrics("db-fail")
        MockCW.return_value = mock_cw

        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        result = _collect_and_forward_metrics()
        assert result["processed"] == []
        assert len(result["errors"]) == 1
        assert result["errors"][0]["instance_id"] == "db-fail"
