"""
ML 異常検知 + コスト予測 + ストレージ残量予測 テスト
"""

import pytest
from datetime import date
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
        """急激なスパイクを検知する（移動平均偏差でも検知）"""
        # 通常 40 前後が続いた後に 95 へ急上昇 → 移動平均から 100%+ 乖離
        values = [40.0, 41.0, 39.0, 40.5, 42.0, 41.0, 40.0, 95.0]
        result = detector.detect_metric_anomalies(values, "cpu_pct")
        # 移動平均偏差 = |95 - ~41| / ~41 ≈ 1.3 > 0.5 → 異常検知
        assert result.is_anomaly is True
        assert result.anomaly_score > 0.5

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


class TestStorageProjection:
    """project_storage_growth のテスト"""

    # 1 GB = 1024^3 bytes
    GB = 1024 ** 3

    def test_growing_usage_projects_days_until_full(self, detector):
        """使用量が増加している場合、days_until_full が正の値で返る"""
        allocated_gb = 100.0
        # 空き容量が 50GB → 40GB → 30GB → 20GB → 10GB と減少（毎時 10GB 減）
        history = [50.0 * self.GB, 40.0 * self.GB, 30.0 * self.GB, 20.0 * self.GB, 10.0 * self.GB]
        result = detector.project_storage_growth(history, allocated_gb, interval_hours=1.0)

        assert result["days_until_full"] is not None
        assert result["days_until_full"] > 0
        assert result["projected_full_date"] is not None
        # 10GB 残り、毎時 10GB 消費 → 約 1時間 → 1/24 日
        # 実際は線形回帰なので厳密な1/24とは異なるが正であることを確認
        assert result["trend_gb_per_day"] < 0  # 減少トレンド

    def test_stable_usage_returns_none(self, detector):
        """使用量が横ばい（増加なし）の場合、days_until_full は None"""
        allocated_gb = 100.0
        history = [50.0 * self.GB] * 10  # 変化なし
        result = detector.project_storage_growth(history, allocated_gb)

        assert result["days_until_full"] is None
        assert result["projected_full_date"] is None

    def test_shrinking_usage_returns_none(self, detector):
        """空き容量が増加している（使用量減少）場合、days_until_full は None"""
        allocated_gb = 100.0
        # 空き容量が増加 → slope >= 0
        history = [10.0 * self.GB, 20.0 * self.GB, 30.0 * self.GB, 40.0 * self.GB]
        result = detector.project_storage_growth(history, allocated_gb)

        assert result["days_until_full"] is None
        assert result["projected_full_date"] is None
        assert result["trend_gb_per_day"] >= 0

    def test_fewer_than_2_data_points_returns_none(self, detector):
        """データが 1 点以下の場合、days_until_full は None"""
        allocated_gb = 100.0
        result = detector.project_storage_growth([30.0 * self.GB], allocated_gb)

        assert result["days_until_full"] is None
        assert result["projected_full_date"] is None

    def test_confidence_high_for_168_or_more_points(self, detector):
        """168 点以上（1週間分・毎時）は confidence = 'high'"""
        allocated_gb = 200.0
        # 空き容量が減少する 168 点のデータ（200GB→32GB）
        start = 200.0 * self.GB
        end = 32.0 * self.GB
        history = [start - (start - end) * i / 167 for i in range(168)]
        result = detector.project_storage_growth(history, allocated_gb, interval_hours=1.0)
        assert result["confidence"] == "high"

    def test_confidence_medium_for_24_to_167_points(self, detector):
        """24〜167 点は confidence = 'medium'"""
        allocated_gb = 100.0
        history = [50.0 * self.GB - i * 0.5 * self.GB for i in range(24)]
        result = detector.project_storage_growth(history, allocated_gb, interval_hours=1.0)
        assert result["confidence"] == "medium"

    def test_confidence_low_for_fewer_than_24_points(self, detector):
        """24 点未満は confidence = 'low'"""
        allocated_gb = 100.0
        history = [50.0 * self.GB, 49.0 * self.GB, 48.0 * self.GB]
        result = detector.project_storage_growth(history, allocated_gb, interval_hours=1.0)
        assert result["confidence"] == "low"

    def test_current_used_gb_equals_allocated_minus_free(self, detector):
        """current_used_gb = allocated_gb - current_free_gb"""
        allocated_gb = 100.0
        free_bytes = 30.0 * self.GB
        history = [40.0 * self.GB, 35.0 * self.GB, free_bytes]
        result = detector.project_storage_growth(history, allocated_gb, interval_hours=1.0)

        expected_free_gb = free_bytes / self.GB
        assert abs(result["current_free_gb"] - expected_free_gb) < 1e-3
        assert abs(result["current_used_gb"] - (allocated_gb - expected_free_gb)) < 1e-3

    def test_projected_full_date_is_future(self, detector):
        """projected_full_date は今日以降の日付"""
        allocated_gb = 100.0
        # 空き容量が緩やかに減少（数百日後に満杯）
        history = [60.0 * self.GB - i * 0.001 * self.GB for i in range(24)]
        result = detector.project_storage_growth(history, allocated_gb, interval_hours=1.0)

        if result["projected_full_date"] is not None:
            projected = date.fromisoformat(result["projected_full_date"])
            assert projected >= date.today()
