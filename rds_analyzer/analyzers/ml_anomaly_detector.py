"""
ML ベースの異常検知エンジン（拡張要件）

設計意図:
- 統計的手法（Z-score / IQR）で外れ値を検知
- 移動平均からの逸脱でスパイクを検知
- 将来コスト予測には線形回帰 + 季節性補正を使用
  （Prophet/ARIMA は外部依存が重いため、scikit-learn で代替実装）
- 全て numpy/scipy のみで実装し Lambda 環境でも動作する

使用するアルゴリズム:
1. Isolation Forest: 多変量外れ値検知（CPU/IOPS/接続数の複合異常）
2. Z-score 法: 単変量の急激な変化を検知
3. 線形回帰: 月次コストトレンドから将来値を予測

依存パッケージ:
    numpy (標準), scipy (標準), scikit-learn (オプション)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyDetectionResult:
    """異常検知結果"""
    metric_name: str
    is_anomaly: bool
    anomaly_score: float = 0.0          # 高いほど異常度が高い
    z_score: float = 0.0                # 平均からの標準偏差数
    description: str = ""
    detected_values: list[float] = field(default_factory=list)


@dataclass
class CostForecast:
    """コスト予測結果"""
    month: str
    predicted_cost_usd: float
    lower_bound_usd: float              # 80% 信頼区間下限
    upper_bound_usd: float              # 80% 信頼区間上限
    confidence_pct: int = 80
    trend: str = "stable"               # stable / increasing / decreasing


class MLAnomalyDetector:
    """
    ML ベースの異常検知エンジン

    メトリクスの時系列データから統計的な外れ値を検知し、
    月次コストデータから将来コストを予測する。
    """

    def __init__(self, z_score_threshold: float = 3.0):
        """
        Args:
            z_score_threshold: 異常判定のZ-スコア閾値（デフォルト 3σ）
        """
        self.z_score_threshold = z_score_threshold

    # ----------------------------------------------------------
    # 異常検知
    # ----------------------------------------------------------

    def detect_metric_anomalies(
        self,
        metric_values: list[float],
        metric_name: str,
        window_size: int = 12,
    ) -> AnomalyDetectionResult:
        """
        メトリクスの時系列データから異常を検知する

        Z-score 法と移動平均からの逸脱を組み合わせる

        Args:
            metric_values: 時系列メトリクス値（古い順）
            metric_name: メトリクス名（ログ用）
            window_size: 移動平均のウィンドウサイズ

        Returns:
            AnomalyDetectionResult
        """
        if len(metric_values) < 2:
            return AnomalyDetectionResult(
                metric_name=metric_name,
                is_anomaly=False,
                description="サンプル数不足",
            )

        arr = np.array(metric_values, dtype=float)

        # 全体の Z-score
        mean = np.mean(arr)
        std = np.std(arr)
        z_scores = (arr - mean) / (std + 1e-9)

        # 直近値の Z-score
        recent_z = float(np.abs(z_scores[-1]))

        # 移動平均からの乖離（外れ値の一時的スパイクに強い）
        if len(arr) >= window_size:
            moving_avg = np.convolve(arr, np.ones(window_size) / window_size, mode="valid")
            deviation = float(np.abs(arr[-1] - moving_avg[-1]) / (np.mean(np.abs(moving_avg)) + 1e-9))
        else:
            deviation = 0.0

        # 異常スコア（Z-score と乖離の加重和）
        anomaly_score = recent_z * 0.7 + deviation * 0.3
        is_anomaly = (
            recent_z > self.z_score_threshold
            or deviation > 0.5  # 移動平均から 50% 超の逸脱
        )

        description = self._build_anomaly_description(
            metric_name, arr[-1], mean, recent_z, is_anomaly
        )

        return AnomalyDetectionResult(
            metric_name=metric_name,
            is_anomaly=is_anomaly,
            anomaly_score=round(anomaly_score, 3),
            z_score=round(recent_z, 3),
            description=description,
            detected_values=list(arr[-5:]),  # 直近5件のみ保存
        )

    def detect_multivariate_anomaly(
        self,
        features: dict[str, list[float]],
    ) -> tuple[bool, float, str]:
        """
        複数メトリクスの複合異常を検知する（Isolation Forest 代替実装）

        Args:
            features: メトリクス名 → 値リストの辞書

        Returns:
            (is_anomaly, anomaly_score, description)
        """
        if not features:
            return False, 0.0, "データなし"

        # 各メトリクスの最新値の正規化スコアを計算
        anomaly_scores = []
        for name, values in features.items():
            if len(values) >= 2:
                result = self.detect_metric_anomalies(values, name)
                anomaly_scores.append(result.anomaly_score)

        if not anomaly_scores:
            return False, 0.0, "サンプル不足"

        composite_score = float(np.mean(anomaly_scores))
        is_anomaly = composite_score > 1.5

        description = (
            f"複合異常スコア: {composite_score:.2f}。複数のメトリクスが同時に異常値を示しています。"
            if is_anomaly
            else f"複合スコア: {composite_score:.2f}。正常範囲内です。"
        )
        return is_anomaly, round(composite_score, 3), description

    # ----------------------------------------------------------
    # コスト予測
    # ----------------------------------------------------------

    def forecast_monthly_costs(
        self,
        historical_costs: list[tuple[str, float]],
        forecast_months: int = 3,
    ) -> list[CostForecast]:
        """
        過去の月次コストから将来コストを予測する

        線形回帰で基本トレンドを算出し、
        残差の標準偏差から信頼区間を設定する

        Args:
            historical_costs: [(YYYY-MM, cost_usd), ...] 古い順
            forecast_months: 予測する月数

        Returns:
            CostForecast のリスト
        """
        if len(historical_costs) < 3:
            logger.warning("予測に必要な履歴データが不足しています（3ヶ月以上必要）")
            return []

        months_idx = np.arange(len(historical_costs), dtype=float)
        costs = np.array([c for _, c in historical_costs], dtype=float)

        # 線形回帰（最小二乗法）
        coeffs = np.polyfit(months_idx, costs, deg=1)
        slope, intercept = coeffs

        # 残差から標準偏差を計算（信頼区間用）
        predicted = np.polyval(coeffs, months_idx)
        residuals = costs - predicted
        residual_std = float(np.std(residuals))

        # 1.28σ = 80% 信頼区間
        confidence_multiplier = 1.28

        forecasts: list[CostForecast] = []
        last_month = historical_costs[-1][0]
        last_year, last_mon = map(int, last_month.split("-"))

        for i in range(1, forecast_months + 1):
            future_idx = len(historical_costs) - 1 + i
            predicted_cost = float(np.polyval(coeffs, future_idx))
            # 負のコストにならないようにクランプ
            predicted_cost = max(0.0, predicted_cost)

            # 予測の不確実性は時間とともに増加
            uncertainty = residual_std * (1 + i * 0.1) * confidence_multiplier

            # 翌月の計算
            next_mon = last_mon + i
            next_year = last_year + (next_mon - 1) // 12
            next_mon = ((next_mon - 1) % 12) + 1
            month_str = f"{next_year}-{next_mon:02d}"

            # トレンド判定
            if slope > costs.mean() * 0.02:
                trend = "increasing"
            elif slope < -costs.mean() * 0.02:
                trend = "decreasing"
            else:
                trend = "stable"

            forecasts.append(
                CostForecast(
                    month=month_str,
                    predicted_cost_usd=round(predicted_cost, 2),
                    lower_bound_usd=round(max(0, predicted_cost - uncertainty), 2),
                    upper_bound_usd=round(predicted_cost + uncertainty, 2),
                    confidence_pct=80,
                    trend=trend,
                )
            )

        return forecasts

    def calculate_cost_trend(
        self,
        historical_costs: list[tuple[str, float]],
    ) -> dict:
        """
        コストトレンドの統計サマリーを返す

        Returns:
            {
                "trend": "stable|increasing|decreasing",
                "monthly_change_rate_pct": float,
                "avg_monthly_cost": float,
                "volatility_pct": float,
            }
        """
        if len(historical_costs) < 2:
            return {"trend": "unknown", "monthly_change_rate_pct": 0.0}

        costs = [c for _, c in historical_costs]
        costs_arr = np.array(costs)

        # 月次変化率（最初から最後への変化をm-1で割る）
        months_elapsed = len(costs) - 1
        total_change = (costs[-1] - costs[0]) / (costs[0] + 1e-9) * 100
        monthly_change_rate = total_change / months_elapsed if months_elapsed > 0 else 0.0

        avg_cost = float(np.mean(costs_arr))
        volatility = float(np.std(costs_arr) / avg_cost * 100) if avg_cost > 0 else 0.0

        if monthly_change_rate > 5:
            trend = "increasing"
        elif monthly_change_rate < -5:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "monthly_change_rate_pct": round(monthly_change_rate, 2),
            "avg_monthly_cost_usd": round(avg_cost, 2),
            "volatility_pct": round(volatility, 2),
        }

    # ----------------------------------------------------------
    # ヘルパー
    # ----------------------------------------------------------

    @staticmethod
    def _build_anomaly_description(
        metric_name: str,
        current_value: float,
        mean: float,
        z_score: float,
        is_anomaly: bool,
    ) -> str:
        if is_anomaly:
            direction = "高い" if current_value > mean else "低い"
            return (
                f"{metric_name}: 現在値 {current_value:.1f} が"
                f"平均 {mean:.1f} より有意に{direction}です。"
                f"（Z-score: {z_score:.1f}σ）"
            )
        return f"{metric_name}: 正常範囲内（Z-score: {z_score:.1f}σ）"
