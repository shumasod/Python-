"""
RDS パフォーマンス分析エンジン

設計意図:
- CloudWatch メトリクスからボトルネックを検知
- 各メトリクスに閾値ベースの多段階判定（HEALTHY/WARNING/CRITICAL）を適用
- スコアリングにより総合的なパフォーマンス健全性を定量化

閾値設定根拠:
- AWS のベストプラクティスガイドに基づく
- CPU 80%以上: インスタンスが高負荷状態（スケールアップ推奨）
- Memory: 割り当てメモリの 10% 未満が空き → 圧迫状態
- IOPS: プロビジョンド上限の 90% 超 → 枯渇リスク
- Connections: 最大接続数の 80% 超 → 枯渇リスク
"""

from __future__ import annotations

import logging
from typing import Optional

from ..models.metrics import (
    MetricsHistory,
    PerformanceAnalysisResult,
    PerformanceStatus,
)
from ..models.rds import EngineType, RDSInstance, StorageType
from .cost_analyzer import CostAnalyzer, INSTANCE_SPECS, GP3_FREE_IOPS

logger = logging.getLogger(__name__)

# ============================================================
# パフォーマンス判定閾値
# ============================================================

# CPU 利用率閾値 (%)
CPU_WARNING_THRESHOLD = 70.0
CPU_CRITICAL_THRESHOLD = 85.0

# 空きメモリ閾値（割り当てメモリに対する割合）
MEMORY_WARNING_RATIO = 0.15   # 15% 未満 → WARNING
MEMORY_CRITICAL_RATIO = 0.05  # 5% 未満 → CRITICAL

# IOPS 使用率閾値（プロビジョンド上限に対する割合）
IOPS_WARNING_RATIO = 0.75
IOPS_CRITICAL_RATIO = 0.90

# コネクション使用率閾値（最大接続数に対する割合）
CONNECTION_WARNING_RATIO = 0.70
CONNECTION_CRITICAL_RATIO = 0.85

# ストレージ使用率閾値
STORAGE_WARNING_RATIO = 0.80   # 80% 超 → WARNING
STORAGE_CRITICAL_RATIO = 0.90  # 90% 超 → CRITICAL

# ディスクキュー深度閾値
DISK_QUEUE_WARNING = 1.0
DISK_QUEUE_CRITICAL = 5.0

# レイテンシ閾値 (ms)
LATENCY_READ_WARNING_MS = 20.0
LATENCY_READ_CRITICAL_MS = 50.0
LATENCY_WRITE_WARNING_MS = 20.0
LATENCY_WRITE_CRITICAL_MS = 50.0

# gp2 ストレージの IOPS 上限計算（3 IOPS/GB、最大 16000 IOPS）
GP2_IOPS_PER_GB = 3
GP2_MAX_IOPS = 16000
GP2_BASELINE_MIN_IOPS = 100


class PerformanceAnalyzer:
    """
    RDS パフォーマンス分析エンジン

    メトリクス履歴から各種ボトルネックを検知し、
    総合健全性スコアを算出する
    """

    def __init__(self):
        self._cost_analyzer = CostAnalyzer()

    # ----------------------------------------------------------
    # パブリック API
    # ----------------------------------------------------------

    def analyze(
        self,
        instance: RDSInstance,
        metrics: MetricsHistory,
    ) -> PerformanceAnalysisResult:
        """
        メトリクス履歴から総合パフォーマンス分析を実行

        Args:
            instance: RDS インスタンス設定
            metrics: 分析対象期間のメトリクス集計

        Returns:
            PerformanceAnalysisResult: 各項目の判定結果と総合スコア
        """
        from datetime import datetime

        # 1. CPU 分析
        cpu_status, cpu_bottleneck = self._analyze_cpu(metrics)

        # 2. メモリ分析
        memory_status, memory_pressure = self._analyze_memory(instance, metrics)
        freeable_memory_avg_gb = metrics.freeable_memory_bytes.avg / (1024 ** 3)

        # 3. I/O 分析
        iops_limit = self._get_iops_limit(instance)
        io_status, io_bottleneck, iops_limit_pct = self._analyze_io(
            instance, metrics, iops_limit
        )

        # 4. コネクション分析
        max_connections = self._cost_analyzer.get_max_connections(instance)
        conn_status, conn_bottleneck, conn_limit_pct = self._analyze_connections(
            metrics, max_connections
        )

        # 5. ストレージ分析
        allocated_storage_bytes = instance.allocated_storage_gb * (1024 ** 3)
        free_storage_bytes = metrics.free_storage_bytes.avg
        storage_used_bytes = allocated_storage_bytes - free_storage_bytes
        storage_utilization_pct = storage_used_bytes / allocated_storage_bytes * 100 if allocated_storage_bytes > 0 else 0.0
        storage_status = self._evaluate_storage_status(storage_utilization_pct)

        # 6. 総合スコア算出
        health_score = self._calculate_health_score(
            cpu_status=cpu_status,
            memory_status=memory_status,
            io_status=io_status,
            conn_status=conn_status,
            storage_status=storage_status,
        )

        return PerformanceAnalysisResult(
            instance_id=instance.instance_id,
            analyzed_at=datetime.utcnow(),
            # CPU
            cpu_status=cpu_status,
            cpu_avg_pct=metrics.cpu_utilization.avg,
            cpu_max_pct=metrics.cpu_utilization.max,
            cpu_bottleneck_detected=cpu_bottleneck,
            # メモリ
            memory_status=memory_status,
            freeable_memory_avg_gb=freeable_memory_avg_gb,
            memory_pressure_detected=memory_pressure,
            # I/O
            io_status=io_status,
            avg_total_iops=metrics.avg_total_iops,
            max_total_iops=metrics.max_total_iops,
            iops_limit_pct=iops_limit_pct,
            io_bottleneck_detected=io_bottleneck,
            # コネクション
            connection_status=conn_status,
            avg_connections=metrics.database_connections.avg,
            max_connections=float(max_connections),
            connection_limit_pct=conn_limit_pct,
            connection_bottleneck_detected=conn_bottleneck,
            # ストレージ
            storage_status=storage_status,
            free_storage_gb=free_storage_bytes / (1024 ** 3),
            storage_utilization_pct=storage_utilization_pct,
            # 総合スコア
            health_score=health_score,
        )

    def get_iops_limit(self, instance: RDSInstance) -> int:
        """インスタンスのIOPS上限を返す（外部公開用）"""
        return self._get_iops_limit(instance)

    # ----------------------------------------------------------
    # 個別メトリクス分析
    # ----------------------------------------------------------

    def _analyze_cpu(
        self, metrics: MetricsHistory
    ) -> tuple[PerformanceStatus, bool]:
        """
        CPU 使用率分析

        avg と p95 の両方を考慮
        p95 が高い場合はスパイク問題として WARNING 扱い
        """
        avg_cpu = metrics.cpu_utilization.avg
        p95_cpu = metrics.cpu_utilization.p95

        # 平均が Critical 閾値超え
        if avg_cpu >= CPU_CRITICAL_THRESHOLD:
            logger.info(
                "CPU CRITICAL: instance=%s avg=%.1f%%",
                metrics.instance_id, avg_cpu
            )
            return PerformanceStatus.CRITICAL, True

        # p95 が Critical 閾値超え（スパイクが頻発）
        if p95_cpu >= CPU_CRITICAL_THRESHOLD:
            return PerformanceStatus.WARNING, True

        # 平均または p95 が Warning 閾値超え
        if avg_cpu >= CPU_WARNING_THRESHOLD or p95_cpu >= CPU_WARNING_THRESHOLD:
            return PerformanceStatus.WARNING, True

        return PerformanceStatus.HEALTHY, False

    def _analyze_memory(
        self,
        instance: RDSInstance,
        metrics: MetricsHistory,
    ) -> tuple[PerformanceStatus, bool]:
        """
        メモリ使用率分析

        FreeableMemory の絶対値ではなく、
        インスタンスの総メモリに対する割合で評価
        """
        specs = INSTANCE_SPECS.get(instance.instance_class, {})
        total_memory_gb = specs.get("memory_gb", 8)
        total_memory_bytes = total_memory_gb * (1024 ** 3)

        avg_free_bytes = metrics.freeable_memory_bytes.avg
        min_free_bytes = metrics.freeable_memory_bytes.min

        free_ratio_avg = avg_free_bytes / total_memory_bytes if total_memory_bytes > 0 else 1.0
        free_ratio_min = min_free_bytes / total_memory_bytes if total_memory_bytes > 0 else 1.0

        # 最小空き容量が Critical しきい値未満
        if free_ratio_min < MEMORY_CRITICAL_RATIO:
            return PerformanceStatus.CRITICAL, True

        # 平均または最小空き容量が Warning しきい値未満
        if free_ratio_avg < MEMORY_WARNING_RATIO or free_ratio_min < MEMORY_WARNING_RATIO:
            return PerformanceStatus.WARNING, True

        return PerformanceStatus.HEALTHY, False

    def _analyze_io(
        self,
        instance: RDSInstance,
        metrics: MetricsHistory,
        iops_limit: int,
    ) -> tuple[PerformanceStatus, bool, float]:
        """
        I/O パフォーマンス分析

        IOPS 使用率 + ディスクキュー深度 + レイテンシを総合評価
        """
        avg_total_iops = metrics.avg_total_iops
        iops_limit_pct = (avg_total_iops / iops_limit * 100) if iops_limit > 0 else 0.0

        # ディスクキュー深度チェック
        avg_queue = metrics.disk_queue_depth.avg
        max_queue = metrics.disk_queue_depth.max

        # レイテンシチェック
        avg_read_latency = metrics.read_latency_ms.avg
        avg_write_latency = metrics.write_latency_ms.avg

        # IOPS 上限への接近度
        iops_ratio = avg_total_iops / iops_limit if iops_limit > 0 else 0.0

        critical_conditions = [
            iops_ratio >= IOPS_CRITICAL_RATIO,
            avg_queue >= DISK_QUEUE_CRITICAL,
            avg_read_latency >= LATENCY_READ_CRITICAL_MS,
            avg_write_latency >= LATENCY_WRITE_CRITICAL_MS,
        ]

        warning_conditions = [
            iops_ratio >= IOPS_WARNING_RATIO,
            avg_queue >= DISK_QUEUE_WARNING,
            avg_read_latency >= LATENCY_READ_WARNING_MS,
            avg_write_latency >= LATENCY_WRITE_WARNING_MS,
        ]

        if any(critical_conditions):
            logger.info(
                "I/O CRITICAL: instance=%s iops_ratio=%.1f%% queue=%.1f",
                metrics.instance_id, iops_ratio * 100, avg_queue
            )
            return PerformanceStatus.CRITICAL, True, iops_limit_pct

        if any(warning_conditions):
            return PerformanceStatus.WARNING, True, iops_limit_pct

        return PerformanceStatus.HEALTHY, False, iops_limit_pct

    def _analyze_connections(
        self,
        metrics: MetricsHistory,
        max_connections: int,
    ) -> tuple[PerformanceStatus, bool, float]:
        """
        DB コネクション分析

        最大接続数に対する現在の使用率を評価
        接続数枯渇はアプリケーション障害に直結するため厳しめに判定
        """
        avg_connections = metrics.database_connections.avg
        max_observed = metrics.database_connections.max

        # 最大観測値で評価（一時的なスパイクも重視）
        conn_ratio = max_observed / max_connections if max_connections > 0 else 0.0
        conn_limit_pct = conn_ratio * 100

        if conn_ratio >= CONNECTION_CRITICAL_RATIO:
            logger.info(
                "Connections CRITICAL: instance=%s ratio=%.1f%%",
                metrics.instance_id, conn_ratio * 100
            )
            return PerformanceStatus.CRITICAL, True, conn_limit_pct

        if conn_ratio >= CONNECTION_WARNING_RATIO:
            return PerformanceStatus.WARNING, True, conn_limit_pct

        return PerformanceStatus.HEALTHY, False, conn_limit_pct

    # ----------------------------------------------------------
    # ヘルパーメソッド
    # ----------------------------------------------------------

    def _get_iops_limit(self, instance: RDSInstance) -> int:
        """
        ストレージタイプとサイズからIOPS上限を算出

        gp2: 3 IOPS/GB（ベースライン）、最大 16000 IOPS
        gp3: プロビジョンド設定値（デフォルト 3000）
        io1: プロビジョンド設定値
        """
        if instance.storage_type == StorageType.GP2:
            baseline = max(
                GP2_BASELINE_MIN_IOPS,
                instance.allocated_storage_gb * GP2_IOPS_PER_GB
            )
            return min(baseline, GP2_MAX_IOPS)

        elif instance.storage_type == StorageType.GP3:
            if instance.provisioned_iops and instance.provisioned_iops > GP3_FREE_IOPS:
                return instance.provisioned_iops
            return GP3_FREE_IOPS  # gp3 デフォルト 3000 IOPS

        elif instance.storage_type == StorageType.IO1:
            return instance.provisioned_iops or 3000

        else:
            return 400  # マグネティックストレージのデフォルト上限

    @staticmethod
    def _evaluate_storage_status(storage_utilization_pct: float) -> PerformanceStatus:
        """ストレージ使用率からステータスを評価"""
        if storage_utilization_pct >= STORAGE_CRITICAL_RATIO * 100:
            return PerformanceStatus.CRITICAL
        elif storage_utilization_pct >= STORAGE_WARNING_RATIO * 100:
            return PerformanceStatus.WARNING
        return PerformanceStatus.HEALTHY

    @staticmethod
    def _calculate_health_score(
        cpu_status: PerformanceStatus,
        memory_status: PerformanceStatus,
        io_status: PerformanceStatus,
        conn_status: PerformanceStatus,
        storage_status: PerformanceStatus,
    ) -> int:
        """
        総合健全性スコアを算出（0〜100）

        各メトリクスのステータスから減点方式でスコアを計算
        CRITICAL は大きくペナルティ、WARNING は小さいペナルティ
        """
        # ベーススコア
        base_score = 100

        # 各ステータスのペナルティ点数
        status_penalty = {
            PerformanceStatus.HEALTHY: 0,
            PerformanceStatus.WARNING: 10,
            PerformanceStatus.CRITICAL: 25,
            PerformanceStatus.UNKNOWN: 5,
        }

        # 重み付きペナルティ（CPU/IOは重視）
        weighted_penalties = [
            (cpu_status, 1.5),       # CPU は最重要
            (io_status, 1.5),        # I/O も同様
            (conn_status, 1.2),      # 接続数は障害直結
            (memory_status, 1.0),    # メモリ
            (storage_status, 0.8),   # ストレージは緩め
        ]

        total_penalty = sum(
            status_penalty[status] * weight
            for status, weight in weighted_penalties
        )

        return max(0, min(100, int(base_score - total_penalty)))
