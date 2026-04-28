"""
ML 異常検知 + コスト予測 テスト
"""

import pytest
from rds_analyzer.analyzers.ml_anomaly_detector import MLAnomalyDetector


@pytest.fixture
def detector():
    return MLAnomalyDetector(z_score_threshold=3.0)


class TestAnomalyDetection:

    def test_normal_values_not_anomaly(self, detector):
        """正常な値は異常として検知されない"""
        values = [40.0, 42.0, 38.0, 41.0, 39.0, 40.5, 41.2, 40.8]
        result = detector.detect_metric_anomalies(values, "cpu_pct")
        assert result.is_anomaly is False

    def test_spike_detected(self, detector):
        """急激なスパイクを検知する"""
        values = [40.0, 41.0, 39.0, 40.5, 42.0, 41.0, 40.0, 95.0]  # 最後だけ異常
        result = detector.detect_metric_anomalies(values, "cpu_pct")
        assert result.is_anomaly is True
        assert result.z_score > 2.0

    def test_insufficient_samples(self, detector):
        """サンプル数が少ない場合は異常なし"""
        result = detector.detect_metric_anomalies([50.0], "cpu_pct")
        assert result.is_anomaly is False

    def test_anomaly_score_range(self, detector):
        """異常スコアは 0 以上"""
        values = [10.0, 12.0, 11.0, 13.0, 10.5]
        result = detector.detect_metric_anomalies(values, "test")
        assert result.anomaly_score >= 0.0


class TestCostForecast:

    def test_forecast_returns_correct_count(self, detector):
        """指定した月数の予測を返す"""
        history = [
            ("2024-01", 450.0), ("2024-02", 460.0), ("2024-03", 470.0),
            ("2024-04", 480.0), ("2024-05", 490.0),
        ]
        forecasts = detector.forecast_monthly_costs(history, forecast_months=3)
        assert len(forecasts) == 3

    def test_increasing_trend_detected(self, detector):
        """上昇トレンドのコストデータで 'increasing' を返す"""
        history = [(f"2024-{i:02d}", 400.0 + i * 50) for i in range(1, 7)]
        forecasts = detector.forecast_monthly_costs(history, forecast_months=2)
        assert any(f.trend == "increasing" for f in forecasts)

    def test_insufficient_history_returns_empty(self, detector):
        """履歴が 3 件未満のときは空リストを返す"""
        history = [("2024-01", 400.0), ("2024-02", 420.0)]
        forecasts = detector.forecast_monthly_costs(history, forecast_months=3)
        assert forecasts == []

    def test_confidence_interval_valid(self, detector):
        """信頼区間は lower <= predicted <= upper"""
        history = [(f"2024-{i:02d}", 400.0 + i * 10) for i in range(1, 7)]
        forecasts = detector.forecast_monthly_costs(history, forecast_months=2)
        for f in forecasts:
            assert f.lower_bound_usd <= f.predicted_cost_usd <= f.upper_bound_usd

    def test_predicted_cost_not_negative(self, detector):
        """予測コストは負にならない"""
        history = [(f"2024-{i:02d}", 500.0 - i * 60) for i in range(1, 7)]
        forecasts = detector.forecast_monthly_costs(history, forecast_months=3)
        for f in forecasts:
            assert f.predicted_cost_usd >= 0.0


class TestCostTrend:

    def test_stable_trend(self, detector):
        """変化が少ない履歴は stable"""
        history = [("2024-01", 500.0), ("2024-02", 502.0), ("2024-03", 498.0)]
        result = detector.calculate_cost_trend(history)
        assert result["trend"] == "stable"

    def test_increasing_trend(self, detector):
        """毎月 10% 増加は increasing"""
        history = [
            ("2024-01", 400.0), ("2024-02", 440.0),
            ("2024-03", 480.0), ("2024-04", 530.0),
        ]
        result = detector.calculate_cost_trend(history)
        assert result["trend"] == "increasing"
        assert result["monthly_change_rate_pct"] > 5.0
