"""
RDS Analyzer テスト用共通フィクスチャ

全テストで共有するモデル・メトリクスフィクスチャ
"""

import pytest
from datetime import datetime, timedelta, timezone

from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType
from rds_analyzer.models.metrics import MetricsHistory, MetricsStatistics


def make_stats(avg: float, max_val: float, min_val: float = None, n: int = 288) -> MetricsStatistics:
    """テスト用統計オブジェクト生成ヘルパー（rds_conftest から import して使用）"""
    m = min_val if min_val is not None else avg * 0.5
    return MetricsStatistics(
        avg=avg, max=max_val, min=m,
        p95=max_val * 0.95, p99=max_val * 0.99, sample_count=n
    )


def make_metrics(instance_id: str, cpu_avg: float = 40.0, cpu_max: float = 65.0) -> MetricsHistory:
    """カスタマイズ可能なメトリクスオブジェクトを生成"""
    now = datetime.now(tz=timezone.utc)
    gb = 1024 ** 3
    return MetricsHistory(
        instance_id=instance_id,
        period_start=now - timedelta(hours=24),
        period_end=now,
        cpu_utilization=make_stats(cpu_avg, cpu_max),
        freeable_memory_bytes=make_stats(3.0 * gb, 4.5 * gb, 2.5 * gb),
        read_iops=make_stats(150.0, 300.0),
        write_iops=make_stats(80.0, 160.0),
        read_latency_ms=make_stats(4.0, 9.0),
        write_latency_ms=make_stats(5.0, 11.0),
        disk_queue_depth=make_stats(0.2, 0.6),
        database_connections=make_stats(45.0, 75.0),
        network_receive_bps=make_stats(500_000, 2_000_000),
        network_transmit_bps=make_stats(500_000, 2_000_000),
        free_storage_bytes=make_stats(120 * gb, 130 * gb, 110 * gb),
    )
