"""
AWS Lambda ハンドラー

設計意図:
- EventBridge (旧CloudWatch Events) により 5 分間隔で自動実行
- CloudWatch メトリクスを収集して DynamoDB / API Gateway に転送
- Lambda 関数は最小権限の IAM ロールで実行
- エラー時は CloudWatch Logs に記録し、SNS でアラート

Lambda 環境変数:
    API_ENDPOINT: FastAPI エンドポイント URL
    REGION: AWS リージョン（デフォルト: ap-northeast-1）
    COLLECTION_PERIOD_HOURS: 収集期間（デフォルト: 1）
    LOG_LEVEL: ログレベル（デフォルト: INFO）

IAM ロール（LambdaExecutionRole）に必要な権限:
    cloudwatch:GetMetricData
    rds:DescribeDBInstances
    ce:GetCostAndUsage (オプション)
    ssm:GetParameter (API エンドポイント取得用)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# 環境変数
API_ENDPOINT = os.environ.get("API_ENDPOINT", "http://localhost:8000")
REGION = os.environ.get("REGION", "ap-northeast-1")
COLLECTION_PERIOD_HOURS = int(os.environ.get("COLLECTION_PERIOD_HOURS", "1"))


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda エントリーポイント

    EventBridge から 5 分間隔で呼び出される
    全 RDS インスタンスのメトリクスを収集して API に転送する

    Args:
        event: EventBridge イベント（詳細は不使用）
        context: Lambda コンテキスト

    Returns:
        実行結果サマリー
    """
    logger.info("RDS メトリクス収集 Lambda 開始")

    try:
        results = _collect_and_forward_metrics()
        logger.info("収集完了: %d インスタンス処理", len(results["processed"]))
        return {
            "statusCode": 200,
            "body": json.dumps(results, ensure_ascii=False),
        }
    except Exception as e:
        logger.error("Lambda 実行エラー: %s", str(e), exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}, ensure_ascii=False),
        }


def _collect_and_forward_metrics() -> dict:
    """
    RDS インスタンス一覧を取得し、各インスタンスのメトリクスを収集する
    """
    # CloudWatch コレクター初期化
    # Lambda ではインスタンスプロファイルの IAM ロールが自動的に使用される
    from rds_analyzer.collectors.cloudwatch_collector import CloudWatchCollector
    collector = CloudWatchCollector(region_name=REGION)

    # RDS インスタンス一覧を取得
    instances = collector.list_rds_instances()
    logger.info("対象インスタンス数: %d", len(instances))

    processed = []
    errors = []

    for instance_info in instances:
        instance_id = instance_info["instance_id"]
        try:
            # メトリクス収集
            metrics = collector.collect_metrics_history(
                instance_id=instance_id,
                period_hours=COLLECTION_PERIOD_HOURS,
            )

            # API エンドポイントに転送
            _forward_metrics_to_api(instance_id, metrics)
            processed.append(instance_id)

        except Exception as e:
            logger.error(
                "インスタンス %s のメトリクス収集エラー: %s",
                instance_id, str(e)
            )
            errors.append({"instance_id": instance_id, "error": str(e)})

    return {
        "processed": processed,
        "errors": errors,
        "total": len(instances),
    }


def _forward_metrics_to_api(instance_id: str, metrics) -> None:
    """
    収集したメトリクスを FastAPI エンドポイントに転送する

    注: 本番環境では DynamoDB への直接書き込みも検討
    """
    import urllib.request
    import urllib.error

    gb_to_bytes = 1024 ** 3
    period_hours = int(metrics.period_hours)

    payload = {
        "instance_id": instance_id,
        "period_hours": max(1, period_hours),
        "cpu_avg_pct": metrics.cpu_utilization.avg,
        "cpu_max_pct": metrics.cpu_utilization.max,
        "cpu_p95_pct": metrics.cpu_utilization.p95,
        "freeable_memory_avg_gb": metrics.freeable_memory_bytes.avg / gb_to_bytes,
        "freeable_memory_min_gb": metrics.freeable_memory_bytes.min / gb_to_bytes,
        "read_iops_avg": metrics.read_iops.avg,
        "write_iops_avg": metrics.write_iops.avg,
        "read_iops_max": metrics.read_iops.max,
        "write_iops_max": metrics.write_iops.max,
        "read_latency_avg_ms": metrics.read_latency_ms.avg,
        "write_latency_avg_ms": metrics.write_latency_ms.avg,
        "connections_avg": metrics.database_connections.avg,
        "connections_max": metrics.database_connections.max,
        "free_storage_gb": metrics.free_storage_bytes.avg / gb_to_bytes,
        "disk_queue_depth_avg": metrics.disk_queue_depth.avg,
    }

    url = f"{API_ENDPOINT}/api/v1/rds/{instance_id}/metrics"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"API エラー: {response.status}")
        logger.debug("メトリクス転送完了: %s", instance_id)
    except urllib.error.URLError as e:
        logger.error("API 転送エラー %s: %s", instance_id, str(e))
        raise
