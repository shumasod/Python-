"""
CloudWatch メトリクス収集コレクター

設計意図:
- CloudWatch GetMetricStatistics API を使用して RDS メトリクスを収集
- boto3 を使用した AWS SDK アクセス
- IAM ロールによる認証（キーハードコード禁止）
- エラー時のリトライと部分取得に対応

必要な IAM 権限:
    cloudwatch:GetMetricStatistics
    cloudwatch:GetMetricData
    rds:DescribeDBInstances
    rds:DescribeDBClusters
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from ..models.metrics import MetricsHistory, MetricsStatistics

logger = logging.getLogger(__name__)

# CloudWatch メトリクス名定義
CW_NAMESPACE = "AWS/RDS"
CW_METRICS = {
    "cpu_utilization": "CPUUtilization",
    "freeable_memory": "FreeableMemory",
    "read_iops": "ReadIOPS",
    "write_iops": "WriteIOPS",
    "read_latency": "ReadLatency",
    "write_latency": "WriteLatency",
    "disk_queue_depth": "DiskQueueDepth",
    "database_connections": "DatabaseConnections",
    "network_receive": "NetworkReceiveThroughput",
    "network_transmit": "NetworkTransmitThroughput",
    "free_storage": "FreeStorageSpace",
    "swap_usage": "SwapUsage",
}

# CloudWatch の統計タイプ
STATISTICS = ["Average", "Maximum", "Minimum", "p95", "p99"]

# メトリクス取得の粒度（秒）: 5分間隔
PERIOD_SECONDS = 300


class CloudWatchCollector:
    """
    CloudWatch から RDS メトリクスを収集するコレクター

    5 分間隔で CloudWatch に問い合わせ、
    指定期間のメトリクス集計を生成する
    """

    def __init__(
        self,
        region_name: str = "ap-northeast-1",
        session: Optional[boto3.Session] = None,
    ):
        """
        Args:
            region_name: AWS リージョン
            session: boto3 セッション（テスト時にモックを注入可能）
        """
        self._session = session or boto3.Session()
        self._client = self._session.client("cloudwatch", region_name=region_name)
        self._region = region_name

    def collect_metrics_history(
        self,
        instance_id: str,
        period_hours: int = 24,
        end_time: Optional[datetime] = None,
    ) -> MetricsHistory:
        """
        指定期間の RDS メトリクス集計を収集する

        Args:
            instance_id: RDS インスタンスID（DBInstanceIdentifier）
            period_hours: 集計期間（時間）
            end_time: 集計終了時刻（None の場合は現在時刻）

        Returns:
            MetricsHistory: 期間内の全メトリクス集計
        """
        end_time = end_time or datetime.now(tz=timezone.utc)
        start_time = end_time - timedelta(hours=period_hours)

        logger.info(
            "CloudWatch メトリクス取得開始",
            instance_id=instance_id,
            period_hours=period_hours,
        )

        # GetMetricData API で複数メトリクスを一括取得（APIコール数を削減）
        metric_data_queries = self._build_metric_data_queries(instance_id)

        try:
            results = self._fetch_metric_data(
                metric_data_queries, start_time, end_time
            )
        except (ClientError, BotoCoreError) as e:
            logger.error(
                "CloudWatch API エラー",
                instance_id=instance_id,
                error=str(e),
            )
            raise

        # 取得したデータを集計統計に変換
        stats_map = self._aggregate_to_statistics(results)

        return self._build_metrics_history(
            instance_id=instance_id,
            stats_map=stats_map,
            period_start=start_time,
            period_end=end_time,
        )

    def list_rds_instances(self) -> list[dict]:
        """
        RDS インスタンスの一覧を取得する

        Returns:
            インスタンス情報のリスト
        """
        rds_client = self._session.client("rds", region_name=self._region)
        instances = []

        try:
            paginator = rds_client.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db in page["DBInstances"]:
                    instances.append({
                        "instance_id": db["DBInstanceIdentifier"],
                        "engine": db["Engine"],
                        "engine_version": db["EngineVersion"],
                        "instance_class": db["DBInstanceClass"],
                        "status": db["DBInstanceStatus"],
                        "multi_az": db["MultiAZ"],
                        "storage_type": db["StorageType"],
                        "allocated_storage_gb": db["AllocatedStorage"],
                        "iops": db.get("Iops"),
                        "region": self._region,
                    })
        except (ClientError, BotoCoreError) as e:
            logger.error("RDS インスタンス一覧取得エラー: %s", str(e))
            raise

        logger.info("RDS インスタンス %d 件を取得", len(instances))
        return instances

    # ----------------------------------------------------------
    # プライベートメソッド
    # ----------------------------------------------------------

    def _build_metric_data_queries(self, instance_id: str) -> list[dict]:
        """
        GetMetricData API 用のクエリリストを構築する

        各メトリクスの Average / Maximum / Minimum を取得
        p95/p99 は Extended Statistics で別途取得
        """
        queries = []
        dimension = {
            "Name": "DBInstanceIdentifier",
            "Value": instance_id,
        }

        for key, metric_name in CW_METRICS.items():
            for stat in ["Average", "Maximum", "Minimum"]:
                queries.append({
                    "Id": f"{key}_{stat.lower()}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": CW_NAMESPACE,
                            "MetricName": metric_name,
                            "Dimensions": [dimension],
                        },
                        "Period": PERIOD_SECONDS,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                })

            # パーセンタイル統計
            for pct in ["p95", "p99"]:
                queries.append({
                    "Id": f"{key}_{pct}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": CW_NAMESPACE,
                            "MetricName": metric_name,
                            "Dimensions": [dimension],
                        },
                        "Period": PERIOD_SECONDS,
                        "Stat": pct,
                    },
                    "ReturnData": True,
                })

        return queries

    def _fetch_metric_data(
        self,
        queries: list[dict],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[float]]:
        """
        CloudWatch GetMetricData API を呼び出す

        一度に最大 500 クエリ（制限に注意）
        """
        results: dict[str, list[float]] = {}

        # API制限に対応してバッチ分割（500クエリ/リクエスト）
        batch_size = 500
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]
            response = self._client.get_metric_data(
                MetricDataQueries=batch,
                StartTime=start_time,
                EndTime=end_time,
            )

            for result in response["MetricDataResults"]:
                results[result["Id"]] = result.get("Values", [])

        return results

    def _aggregate_to_statistics(
        self, results: dict[str, list[float]]
    ) -> dict[str, MetricsStatistics]:
        """
        CloudWatch の時系列データを集計統計に変換する
        """
        import statistics as stats_lib

        stats_map: dict[str, MetricsStatistics] = {}

        for key in CW_METRICS.keys():
            avg_values = results.get(f"{key}_average", [])
            max_values = results.get(f"{key}_maximum", [])
            min_values = results.get(f"{key}_minimum", [])
            p95_values = results.get(f"{key}_p95", [])
            p99_values = results.get(f"{key}_p99", [])

            if not avg_values:
                # データなしの場合はデフォルト値
                stats_map[key] = MetricsStatistics(
                    avg=0.0, max=0.0, min=0.0, p95=0.0, p99=0.0, sample_count=0
                )
                continue

            stats_map[key] = MetricsStatistics(
                avg=sum(avg_values) / len(avg_values),
                max=max(max_values) if max_values else 0.0,
                min=min(min_values) if min_values else 0.0,
                p95=sum(p95_values) / len(p95_values) if p95_values else max(avg_values),
                p99=sum(p99_values) / len(p99_values) if p99_values else max(avg_values),
                sample_count=len(avg_values),
            )

        return stats_map

    def _build_metrics_history(
        self,
        instance_id: str,
        stats_map: dict[str, MetricsStatistics],
        period_start: datetime,
        period_end: datetime,
    ) -> MetricsHistory:
        """MetricsHistory オブジェクトを構築する"""
        default_stats = MetricsStatistics(
            avg=0.0, max=0.0, min=0.0, p95=0.0, p99=0.0, sample_count=0
        )

        return MetricsHistory(
            instance_id=instance_id,
            period_start=period_start,
            period_end=period_end,
            cpu_utilization=stats_map.get("cpu_utilization", default_stats),
            freeable_memory_bytes=stats_map.get("freeable_memory", default_stats),
            read_iops=stats_map.get("read_iops", default_stats),
            write_iops=stats_map.get("write_iops", default_stats),
            read_latency_ms=stats_map.get("read_latency", default_stats),
            write_latency_ms=stats_map.get("write_latency", default_stats),
            disk_queue_depth=stats_map.get("disk_queue_depth", default_stats),
            database_connections=stats_map.get("database_connections", default_stats),
            network_receive_bps=stats_map.get("network_receive", default_stats),
            network_transmit_bps=stats_map.get("network_transmit", default_stats),
            free_storage_bytes=stats_map.get("free_storage", default_stats),
        )
