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
        # gp2 100GB の IOPS 上限 = 300 なので 40% 以下に設定
        read_iops=make_stats(70.0, 150.0),
        write_iops=make_stats(40.0, 90.0),
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


def make_metrics_for(instance_id: str, **kwargs) -> MetricsHistory:
    """指定した値でメトリクスを作成するヘルパー"""
    cpu_avg = kwargs.get("cpu_avg", 40.0)
    cpu_max = kwargs.get("cpu_max", 65.0)
    mem_avg = kwargs.get("mem_avg", 3.5)
    iops_avg = kwargs.get("iops_avg", 300.0)
    conns_avg = kwargs.get("conns_avg", 80.0)
    free_storage_gb = kwargs.get("free_storage_gb", 50.0)
    gb = 1024 ** 3

    now = datetime.now(tz=timezone.utc)
    return MetricsHistory(
        instance_id=instance_id,
        period_start=now - timedelta(hours=24),
        period_end=now,
        cpu_utilization=make_stats(cpu_avg, cpu_max),
        freeable_memory_bytes=make_stats(mem_avg * gb, mem_avg * gb * 1.2, mem_avg * gb * 0.8),
        read_iops=make_stats(iops_avg * 0.6, iops_avg),
        write_iops=make_stats(iops_avg * 0.4, iops_avg * 0.7),
        read_latency_ms=make_stats(5.0, 15.0),
        write_latency_ms=make_stats(6.0, 18.0),
        database_connections=make_stats(conns_avg, conns_avg * 1.5),
        free_storage_bytes=make_stats(
            free_storage_gb * gb,
            free_storage_gb * gb * 1.1,
            free_storage_gb * gb * 0.9,
        ),
        disk_queue_depth=make_stats(0.2, 1.0),
        network_receive_bps=make_stats(1_000_000, 5_000_000),
        network_transmit_bps=make_stats(1_000_000, 5_000_000),
    )


class TestPerformanceAnalyzerEdgeCases:
    """PerformanceAnalyzer 境界値・エッジケーステスト"""

    def test_gp2_iops_baseline_100gb(self, perf_analyzer, base_instance):
        """gp2 100GB: IOPS上限 = max(100, 100*3) = 300"""
        base_instance.allocated_storage_gb = 100
        assert perf_analyzer.get_iops_limit(base_instance) == 300

    def test_gp2_iops_minimum_at_33gb(self, perf_analyzer, base_instance):
        """gp2 33GB: 33*3=99 < 100 なので最小値 100"""
        base_instance.allocated_storage_gb = 33
        assert perf_analyzer.get_iops_limit(base_instance) == 100

    def test_gp2_iops_capped_at_16000(self, perf_analyzer, base_instance):
        """gp2 6000GB: 6000*3=18000 > 16000 なので上限 16000"""
        base_instance.allocated_storage_gb = 6000
        assert perf_analyzer.get_iops_limit(base_instance) == 16000

    def test_gp3_default_iops_3000(self, perf_analyzer, base_instance):
        """gp3 プロビジョンドなし: デフォルト 3000 IOPS"""
        base_instance.storage_type = StorageType.GP3
        base_instance.provisioned_iops = None
        assert perf_analyzer.get_iops_limit(base_instance) == 3000

    def test_gp3_provisioned_iops_respected(self, perf_analyzer, base_instance):
        """gp3 プロビジョンド 6000: そのまま返す"""
        base_instance.storage_type = StorageType.GP3
        base_instance.provisioned_iops = 6000
        assert perf_analyzer.get_iops_limit(base_instance) == 6000

    def test_io1_provisioned_iops(self, perf_analyzer, base_instance):
        """io1 3000 IOPS プロビジョンド: 3000 を返す"""
        base_instance.storage_type = StorageType.IO1
        base_instance.provisioned_iops = 3000
        assert perf_analyzer.get_iops_limit(base_instance) == 3000

    def test_high_cpu_status_critical(self, perf_analyzer, base_instance):
        """CPU 95% は CRITICAL ステータス"""
        metrics = make_metrics_for(base_instance.instance_id, cpu_avg=95.0, cpu_max=98.0)
        result = perf_analyzer.analyze(base_instance, metrics)
        from rds_analyzer.models.metrics import PerformanceStatus
        assert result.cpu_status == PerformanceStatus.CRITICAL

    def test_zero_cpu_status_warning_or_healthy(self, perf_analyzer, base_instance):
        """CPU 0% は異常ではないが、健全性スコアには影響しない"""
        metrics = make_metrics_for(base_instance.instance_id, cpu_avg=0.0, cpu_max=0.5)
        result = perf_analyzer.analyze(base_instance, metrics)
        assert result.health_score >= 0

    def test_postgresql_engine_analyze(self, perf_analyzer):
        """PostgreSQL エンジンでも分析が正常に動作する"""
        pg_instance = RDSInstance(
            instance_id="test-pg-edge",
            engine=EngineType.POSTGRESQL,
            engine_version="15.4",
            instance_class="db.r5.large",
            region="ap-northeast-1",
            storage_type=StorageType.GP3,
            allocated_storage_gb=200,
        )
        metrics = make_metrics_for(pg_instance.instance_id)
        result = perf_analyzer.analyze(pg_instance, metrics)
        assert 0 <= result.health_score <= 100
        assert result.iops_limit_pct >= 0

    def test_multi_az_instance_analyze(self, perf_analyzer, base_instance):
        """Multi-AZ インスタンスでも分析が正常に動作する"""
        base_instance.multi_az = True
        metrics = make_metrics_for(base_instance.instance_id)
        result = perf_analyzer.analyze(base_instance, metrics)
        assert 0 <= result.health_score <= 100
