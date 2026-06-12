"""
メトリクス データモデル

設計意図:
- CloudWatch から取得する全RDS メトリクスを定義
- 時系列データの集計統計（avg/max/p95）を保持
- パフォーマンスステータスの閾値判定を内包
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PerformanceStatus(str, Enum):
    """パフォーマンス健全性ステータス"""
    HEALTHY = "healthy"        # 正常
    WARNING = "warning"        # 警告（要監視）
    CRITICAL = "critical"      # 危険（即時対応推奨）
    UNKNOWN = "unknown"        # データ不足


class MetricsSnapshot(BaseModel):
    """
    特定時点のメトリクススナップショット

    CloudWatch GetMetricStatistics API の
    1データポイントに対応
    """
    timestamp: datetime = Field(description="メトリクス取得時刻")
    instance_id: str = Field(description="RDS インスタンスID")

    # CPU
    cpu_utilization_pct: float = Field(
        ge=0.0, le=100.0,
        description="CPU使用率(%)"
    )

    # メモリ
    freeable_memory_bytes: float = Field(
        ge=0.0,
        description="空きメモリ量(bytes)"
    )
    swap_usage_bytes: float = Field(
        default=0.0, ge=0.0,
        description="スワップ使用量(bytes)"
    )

    # IOPS
    read_iops: float = Field(ge=0.0, description="読み取りIOPS")
    write_iops: float = Field(ge=0.0, description="書き込みIOPS")

    # レイテンシ
    read_latency_ms: float = Field(ge=0.0, description="読み取りレイテンシ(ms)")
    write_latency_ms: float = Field(ge=0.0, description="書き込みレイテンシ(ms)")

    # ディスクキュー
    disk_queue_depth: float = Field(ge=0.0, description="ディスクキュー深度")

    # コネクション
    database_connections: int = Field(ge=0, description="DB接続数")

    # ネットワーク
    network_receive_throughput_bps: float = Field(ge=0.0, description="受信スループット(bytes/s)")
    network_transmit_throughput_bps: float = Field(ge=0.0, description="送信スループット(bytes/s)")

    # ストレージ
    free_storage_space_bytes: float = Field(ge=0.0, description="空きストレージ(bytes)")

    @property
    def total_iops(self) -> float:
        """合計IOPS"""
        return self.read_iops + self.write_iops

    @property
    def freeable_memory_gb(self) -> float:
        """空きメモリ(GB)"""
        return self.freeable_memory_bytes / (1024 ** 3)

    @property
    def free_storage_gb(self) -> float:
        """空きストレージ(GB)"""
        return self.free_storage_space_bytes / (1024 ** 3)


class MetricsStatistics(BaseModel):
    """
    メトリクスの集計統計

    分析エンジンが使用する統計値セット
    """
    avg: float = Field(description="平均値")
    max: float = Field(description="最大値")
    min: float = Field(description="最小値")
    p95: float = Field(description="95パーセンタイル（スパイク検知に使用）")
    p99: float = Field(description="99パーセンタイル")
    sample_count: int = Field(description="サンプル数")


class MetricsHistory(BaseModel):
    """
    期間内のメトリクス集計履歴

    分析エンジンへの入力となる主要データ構造
    通常は過去24時間または1週間の集計値を保持
    """
    instance_id: str
    period_start: datetime
    period_end: datetime

    # 各メトリクスの統計
    cpu_utilization: MetricsStatistics
    freeable_memory_bytes: MetricsStatistics
    read_iops: MetricsStatistics
    write_iops: MetricsStatistics
    read_latency_ms: MetricsStatistics
    write_latency_ms: MetricsStatistics
    disk_queue_depth: MetricsStatistics
    database_connections: MetricsStatistics
    network_receive_bps: MetricsStatistics
    network_transmit_bps: MetricsStatistics
    free_storage_bytes: MetricsStatistics

    @property
    def period_hours(self) -> float:
        """分析対象期間（時間）"""
        delta = self.period_end - self.period_start
        return delta.total_seconds() / 3600

    @property
    def avg_total_iops(self) -> float:
        """平均合計IOPS"""
        return self.read_iops.avg + self.write_iops.avg

    @property
    def max_total_iops(self) -> float:
        """最大合計IOPS"""
        return self.read_iops.max + self.write_iops.max


class PerformanceAnalysisResult(BaseModel):
    """
    パフォーマンス分析結果

    各メトリクスのボトルネック判定と
    健全性スコアを保持
    """
    instance_id: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    # CPU分析
    cpu_status: PerformanceStatus
    cpu_avg_pct: float
    cpu_max_pct: float
    cpu_bottleneck_detected: bool = False

    # メモリ分析
    memory_status: PerformanceStatus
    freeable_memory_avg_gb: float
    memory_pressure_detected: bool = False

    # I/O分析
    io_status: PerformanceStatus
    avg_total_iops: float
    max_total_iops: float
    iops_limit_pct: float = Field(description="IOPS上限に対する使用率(%)")
    io_bottleneck_detected: bool = False

    # コネクション分析
    connection_status: PerformanceStatus
    avg_connections: float
    max_connections: float
    connection_limit_pct: float = Field(description="接続数上限に対する使用率(%)")
    connection_bottleneck_detected: bool = False

    # ストレージ分析
    storage_status: PerformanceStatus
    free_storage_gb: float
    storage_utilization_pct: float

    # 総合スコア（0〜100）
    health_score: int = Field(ge=0, le=100, description="パフォーマンス健全性スコア")

    @property
    def has_any_bottleneck(self) -> bool:
        """いずれかのボトルネックが検知されているか"""
        return any([
            self.cpu_bottleneck_detected,
            self.memory_pressure_detected,
            self.io_bottleneck_detected,
            self.connection_bottleneck_detected,
        ])

    @property
    def critical_issues(self) -> list[str]:
        """CRITICAL ステータスの問題一覧"""
        issues = []
        if self.cpu_status == PerformanceStatus.CRITICAL:
            issues.append("CPU使用率が危険水準")
        if self.memory_status == PerformanceStatus.CRITICAL:
            issues.append("メモリ不足が深刻")
        if self.io_status == PerformanceStatus.CRITICAL:
            issues.append("I/Oボトルネックが深刻")
        if self.connection_status == PerformanceStatus.CRITICAL:
            issues.append("接続数が危険水準")
        return issues
