"""
AWS Cost Explorer コスト収集コレクター

設計意図:
- Cost Explorer API から RDS の実際のコストデータを取得
- 月次コスト実績をサービス/リソースタグ別に集計
- 予測コスト（GetCostForecast）による将来コスト見積もり
- コスト異常検知のための前月比算出

必要な IAM 権限:
    ce:GetCostAndUsage
    ce:GetCostForecast
    ce:GetDimensionValues

注意: Cost Explorer API は月額 $0.01/リクエストの課金が発生します
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)


class CostExplorerCollector:
    """
    AWS Cost Explorer から RDS コストデータを収集するコレクター
    """

    def __init__(
        self,
        session: Optional[boto3.Session] = None,
    ):
        """
        Args:
            session: boto3 セッション
        """
        # Cost Explorer は us-east-1 エンドポイントのみ
        self._session = session or boto3.Session()
        self._client = self._session.client("ce", region_name="us-east-1")

    def get_monthly_rds_costs(
        self,
        start_date: date,
        end_date: date,
        instance_id: Optional[str] = None,
    ) -> dict:
        """
        指定期間の RDS コストを取得する

        Args:
            start_date: 集計開始日
            end_date: 集計終了日
            instance_id: 特定インスタンスのみ取得する場合（タグフィルタ）

        Returns:
            コストデータ辞書
        """
        filters: dict = {
            "Dimensions": {
                "Key": "SERVICE",
                "Values": ["Amazon Relational Database Service"],
            }
        }

        # インスタンスIDによるタグフィルタ（タグが設定されている場合）
        if instance_id:
            filters = {
                "And": [
                    filters,
                    {
                        "Tags": {
                            "Key": "DBInstanceIdentifier",
                            "Values": [instance_id],
                        }
                    },
                ]
            }

        try:
            response = self._client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Filter=filters,
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
                ],
                Metrics=["BlendedCost", "UsageQuantity"],
            )
        except (ClientError, BotoCoreError) as e:
            logger.error("Cost Explorer API エラー: %s", str(e))
            raise

        return self._parse_cost_response(response)

    def get_cost_forecast(
        self,
        instance_id: Optional[str] = None,
        forecast_months: int = 3,
    ) -> dict:
        """
        将来コストの予測を取得する

        Args:
            forecast_months: 予測期間（月数）

        Returns:
            予測コストデータ
        """
        today = date.today()
        forecast_start = date(today.year, today.month, 1) + timedelta(days=32)
        forecast_start = forecast_start.replace(day=1)

        # 最終日を計算
        end_month = forecast_start.month + forecast_months - 1
        end_year = forecast_start.year + (end_month - 1) // 12
        end_month = ((end_month - 1) % 12) + 1
        forecast_end = date(end_year, end_month, 28) + timedelta(days=4)
        forecast_end = forecast_end.replace(day=1)

        try:
            response = self._client.get_cost_forecast(
                TimePeriod={
                    "Start": forecast_start.strftime("%Y-%m-%d"),
                    "End": forecast_end.strftime("%Y-%m-%d"),
                },
                Metric="BLENDED_COST",
                Granularity="MONTHLY",
                Filter={
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": ["Amazon Relational Database Service"],
                    }
                },
                PredictionIntervalLevel=80,  # 80% 信頼区間
            )
        except (ClientError, BotoCoreError) as e:
            logger.warning("コスト予測 API エラー（費用が発生するため一部環境では無効）: %s", str(e))
            return {}

        return self._parse_forecast_response(response)

    def get_previous_months_costs(
        self,
        num_months: int = 3,
        instance_id: Optional[str] = None,
    ) -> list[dict]:
        """
        過去 N ヶ月のコストを取得する（前月比異常検知用）

        Args:
            num_months: 取得する月数
        """
        today = date.today()
        costs = []

        for i in range(num_months, 0, -1):
            # 月初・月末を計算
            target_month = date(today.year, today.month, 1) - timedelta(days=1)
            for _ in range(i - 1):
                target_month = date(
                    target_month.year, target_month.month, 1
                ) - timedelta(days=1)

            month_start = date(target_month.year, target_month.month, 1)
            next_month = (month_start + timedelta(days=32)).replace(day=1)

            try:
                monthly_cost = self.get_monthly_rds_costs(
                    start_date=month_start,
                    end_date=next_month,
                    instance_id=instance_id,
                )
                monthly_cost["month"] = month_start.strftime("%Y-%m")
                costs.append(monthly_cost)
            except Exception as e:
                logger.warning("月次コスト取得エラー %s: %s", month_start.strftime("%Y-%m"), str(e))

        return costs

    # ----------------------------------------------------------
    # レスポンスパース
    # ----------------------------------------------------------

    @staticmethod
    def _parse_cost_response(response: dict) -> dict:
        """Cost Explorer レスポンスをパースして集計する"""
        total_cost = 0.0
        usage_type_costs: dict[str, float] = {}

        for time_period in response.get("ResultsByTime", []):
            for group in time_period.get("Groups", []):
                usage_type = group["Keys"][0]
                cost = float(group["Metrics"]["BlendedCost"]["Amount"])
                total_cost += cost
                usage_type_costs[usage_type] = usage_type_costs.get(usage_type, 0.0) + cost

        # 課金タイプ別に分類
        compute_cost = sum(
            v for k, v in usage_type_costs.items()
            if any(
                keyword in k
                for keyword in ["InstanceUsage", "Multi-AZUsage", "Aurora:ServerlessUsage"]
            )
        )
        storage_cost = sum(
            v for k, v in usage_type_costs.items()
            if any(keyword in k for keyword in ["StorageUsage", "GP2-Storage", "GP3-Storage"])
        )
        iops_cost = sum(
            v for k, v in usage_type_costs.items()
            if "PIOPS" in k or "ProvisionalIOPS" in k
        )
        transfer_cost = sum(
            v for k, v in usage_type_costs.items()
            if "DataTransfer" in k
        )
        backup_cost = sum(
            v for k, v in usage_type_costs.items()
            if "BackupUsage" in k
        )

        return {
            "total_usd": round(total_cost, 4),
            "compute_usd": round(compute_cost, 4),
            "storage_usd": round(storage_cost, 4),
            "iops_usd": round(iops_cost, 4),
            "transfer_usd": round(transfer_cost, 4),
            "backup_usd": round(backup_cost, 4),
            "usage_type_breakdown": usage_type_costs,
        }

    @staticmethod
    def _parse_forecast_response(response: dict) -> dict:
        """コスト予測レスポンスをパースする"""
        forecasts = []
        for period in response.get("ForecastResultsByTime", []):
            forecasts.append({
                "month": period["TimePeriod"]["Start"][:7],
                "mean_cost_usd": float(period["MeanValue"]),
                "lower_bound_usd": float(period.get("PredictionIntervalLowerBound", 0)),
                "upper_bound_usd": float(period.get("PredictionIntervalUpperBound", 0)),
            })

        total_forecast = float(response.get("Total", {}).get("Amount", 0))
        return {
            "total_forecast_usd": round(total_forecast, 4),
            "monthly_forecasts": forecasts,
        }
