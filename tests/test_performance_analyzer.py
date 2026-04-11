"""
パフォーマンス分析エンジン テスト

設計意図:
- 各メトリクスの閾値判定ロジックを境界値テスト
- CRITICAL/WARNING/HEALTHY の判定が正しいことを確認
- 総合スコアの計算ロジックをテスト
"""

import pytest
from datetime import datetime, timedelta, timezone

from rds_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer
from rds_analyzer.models.metrics import MetricsHistory, MetricsStatistics, PerformanceStatus
from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType


def make_stats(avg: float, max_val: float, min_val: float = None) -> MetricsStatistics:
    """テスト用の統計オブジェクトを生成するヘルパー"""
    if min_val is None:
        min_val = avg * 0.5
    return MetricsStatistics(
        avg=avg,
        max=max_val,
        min=min_val,
        p95=max_val * 0.95,
        p99=max_val * 0.99,
        sample_count=288,  # 24h × 12サンプル/h
    )


@pytest.fixture
def perf_analyzer():
    return PerformanceAnalyzer()


@pytest.fixture
def base_instance():
    return RDSInstance(
        instance_id="test-001",
        engine=EngineType.MYSQL,
        engine_version="8.0",
        instance_class="db.m5.large",
        region="ap-northeast-1",
        multi_az=False,
        storage_type=StorageType.GP2,
        allocated_storage_gb=100,
    )


def make_healthy_metrics(instance_id: str = "test-001") -> MetricsHistory:
    """正常なメトリクス（全指標が健全範囲）"""
    now = datetime.now(tz=timezone.utc)
    gb = 1024 ** 3
    return MetricsHistory(
        instance_id=instance_id,
        period_start=now - timedelta(hours=24),
        period_end=now,
        cpu_utilization=make_stats(40.0, 60.0),
        freeable_memory_bytes=make_stats(3.0 * gb, 4.0 * gb, 2.5 * gb),
        read_iops=make_stats(200.0, 400.0),
        write_iops=make_stats(100.0, 200.0),
        read_latency_ms=make_stats(5.0, 10.0),
        write_latency_ms=make_stats(5.0, 10.0),
        disk_queue_depth=make_stats(0.2, 0.5),
        database_connections=make_stats(50.0, 80.0),
        network_receive_bps=make_stats(1_000_000, 5_000_000),
        network_transmit_bps=make_stats(1_000_000, 5_000_000),
        free_storage_bytes=make_stats(60 * gb, 65 * gb, 55 * gb),
    )


class TestCPUAnalysis:
    """CPU分析テスト"""

    def test_healthy_cpu(self, perf_analyzer, base_instance):
        """CPU 40% は HEALTHY"""
        metrics = make_healthy_metrics()
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.cpu_status == PerformanceStatus.HEALTHY
        assert result.cpu_bottleneck_detected is False

    def test_critical_cpu(self, perf_analyzer, base_instance):
        """CPU 90% は CRITICAL"""
        metrics = make_healthy_metrics()
        metrics.cpu_utilization = make_stats(90.0, 98.0)
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.cpu_status == PerformanceStatus.CRITICAL
        assert result.cpu_bottleneck_detected is True

    def test_warning_cpu(self, perf_analyzer, base_instance):
        """CPU 75% は WARNING"""
        metrics = make_healthy_metrics()
        metrics.cpu_utilization = make_stats(75.0, 82.0)
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.cpu_status == PerformanceStatus.WARNING
        assert result.cpu_bottleneck_detected is True


class TestMemoryAnalysis:
    """メモリ分析テスト"""

    def test_healthy_memory(self, perf_analyzer, base_instance):
        """メモリ十分な状態は HEALTHY"""
        metrics = make_healthy_metrics()
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.memory_status == PerformanceStatus.HEALTHY
        assert result.memory_pressure_detected is False

    def test_critical_memory(self, perf_analyzer, base_instance):
        """メモリがほぼ枯渇状態は CRITICAL"""
        metrics = make_healthy_metrics()
        gb = 1024 ** 3
        # db.m5.large は 8GB RAM → 5% = 400MB 未満で CRITICAL
        metrics.freeable_memory_bytes = make_stats(
            avg=0.3 * gb,    # 300MB (avg)
            max_val=0.5 * gb,
            min_val=0.2 * gb,  # 200MB (min) - CRITICAL
        )
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.memory_status == PerformanceStatus.CRITICAL
        assert result.memory_pressure_detected is True


class TestIOAnalysis:
    """I/O分析テスト"""

    def test_healthy_io(self, perf_analyzer, base_instance):
        """IOPS 使用率が低い場合は HEALTHY"""
        metrics = make_healthy_metrics()
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.io_status == PerformanceStatus.HEALTHY

    def test_gp2_iops_limit_calculation(self, perf_analyzer, base_instance):
        """gp2 のIOPS上限は 3 IOPS/GB（100GB → 300 IOPS）"""
        limit = perf_analyzer.get_iops_limit(base_instance)
        assert limit == 300  # 100GB × 3 = 300

    def test_gp2_large_volume_iops_limit(self, perf_analyzer, base_instance):
        """gp2 は最大 16000 IOPS"""
        large_instance = base_instance.model_copy(update={"allocated_storage_gb": 10000})
        limit = perf_analyzer.get_iops_limit(large_instance)
        assert limit == 16000  # 上限値

    def test_gp3_default_iops_limit(self, perf_analyzer, base_instance):
        """gp3 デフォルトは 3000 IOPS"""
        gp3_instance = base_instance.model_copy(update={"storage_type": StorageType.GP3})
        limit = perf_analyzer.get_iops_limit(gp3_instance)
        assert limit == 3000

    def test_high_disk_queue_warning(self, perf_analyzer, base_instance):
        """ディスクキュー深度が高い場合は WARNING"""
        metrics = make_healthy_metrics()
        metrics.disk_queue_depth = make_stats(1.5, 3.0)
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.io_status in (PerformanceStatus.WARNING, PerformanceStatus.CRITICAL)


class TestConnectionAnalysis:
    """コネクション分析テスト"""

    def test_healthy_connections(self, perf_analyzer, base_instance):
        """接続数が少ない場合は HEALTHY"""
        metrics = make_healthy_metrics()
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.connection_status == PerformanceStatus.HEALTHY

    def test_high_connections_critical(self, perf_analyzer, base_instance):
        """接続数が最大接続数の 90% を超えると CRITICAL"""
        metrics = make_healthy_metrics()
        # db.m5.large MySQL の最大接続数 = 8GB × 75 = 600
        metrics.database_connections = make_stats(500.0, 550.0)
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.connection_status in (PerformanceStatus.CRITICAL, PerformanceStatus.WARNING)


class TestHealthScore:
    """総合健全性スコアテスト"""

    def test_all_healthy_high_score(self, perf_analyzer, base_instance):
        """全指標が正常な場合は高スコア"""
        metrics = make_healthy_metrics()
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.health_score >= 80

    def test_critical_cpu_reduces_score(self, perf_analyzer, base_instance):
        """CPU CRITICAL は大きくスコアを下げる"""
        healthy_metrics = make_healthy_metrics()
        critical_metrics = make_healthy_metrics()
        critical_metrics.cpu_utilization = make_stats(92.0, 99.0)

        healthy_result = perf_analyzer.analyze(base_instance, healthy_metrics)
        critical_result = perf_analyzer.analyze(base_instance, critical_metrics)

        assert critical_result.health_score < healthy_result.health_score

    def test_score_range_valid(self, perf_analyzer, base_instance):
        """スコアは常に 0〜100 の範囲"""
        metrics = make_healthy_metrics()
        result = perf_analyzer.analyze(base_instance, metrics)
        assert 0 <= result.health_score <= 100
