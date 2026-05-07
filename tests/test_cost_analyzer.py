"""
コスト分析エンジン テスト

設計意図:
- 各課金コンポーネントの計算ロジックを単体テスト
- AWS料金に基づく期待値を定義（推定値として許容誤差あり）
- スコアリングロジックの境界値テスト
"""

import pytest
from rds_analyzer.analyzers.cost_analyzer import (
    CostAnalyzer,
    INSTANCE_HOURLY_RATES,
    STORAGE_RATES,
)
from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType


@pytest.fixture
def cost_analyzer():
    """テスト用コストアナライザー（月730時間）"""
    return CostAnalyzer(monthly_hours=730.0)


@pytest.fixture
def base_instance():
    """基本的なRDSインスタンス設定（テスト用）"""
    return RDSInstance(
        instance_id="test-mysql-001",
        engine=EngineType.MYSQL,
        engine_version="8.0",
        instance_class="db.m5.large",
        region="ap-northeast-1",
        multi_az=False,
        storage_type=StorageType.GP2,
        allocated_storage_gb=100,
        backup_retention_days=7,
        snapshot_storage_gb=80.0,
    )


class TestComputeCost:
    """コンピュートコスト計算テスト"""

    def test_single_az_compute_cost(self, cost_analyzer, base_instance):
        """シングルAZのコンピュートコスト計算"""
        breakdown, details = cost_analyzer.calculate_monthly_cost(base_instance)
        expected = INSTANCE_HOURLY_RATES["db.m5.large"] * 730
        assert abs(breakdown.compute_cost_usd - expected) < 0.01

    def test_multi_az_compute_cost_is_double(self, cost_analyzer, base_instance):
        """マルチAZのコンピュートコストはシングルAZの2倍"""
        base_instance.multi_az = True
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance)
        expected = INSTANCE_HOURLY_RATES["db.m5.large"] * 730 * 2
        assert abs(breakdown.compute_cost_usd - expected) < 0.01

    def test_read_replica_cost(self, cost_analyzer, base_instance):
        """リードレプリカのコスト計算"""
        base_instance.read_replica_count = 2
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance)
        expected_replica = INSTANCE_HOURLY_RATES["db.m5.large"] * 730 * 2
        assert abs(breakdown.replica_compute_cost_usd - expected_replica) < 0.01


class TestStorageCost:
    """ストレージコスト計算テスト"""

    def test_gp2_storage_cost(self, cost_analyzer, base_instance):
        """gp2 ストレージコスト計算"""
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance)
        expected = 100 * STORAGE_RATES[StorageType.GP2]
        assert abs(breakdown.storage_cost_usd - expected) < 0.01

    def test_gp3_cheaper_than_gp2(self, cost_analyzer, base_instance):
        """gp3 は gp2 より安い"""
        gp3_instance = base_instance.model_copy(
            update={"storage_type": StorageType.GP3}
        )
        gp2_breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance)
        gp3_breakdown, _ = cost_analyzer.calculate_monthly_cost(gp3_instance)
        assert gp3_breakdown.storage_cost_usd < gp2_breakdown.storage_cost_usd

    def test_multi_az_storage_double(self, cost_analyzer, base_instance):
        """マルチAZのストレージは2倍"""
        single_az = base_instance.model_copy(update={"multi_az": False})
        multi_az = base_instance.model_copy(update={"multi_az": True})
        single_breakdown, _ = cost_analyzer.calculate_monthly_cost(single_az)
        multi_breakdown, _ = cost_analyzer.calculate_monthly_cost(multi_az)
        assert abs(multi_breakdown.storage_cost_usd - single_breakdown.storage_cost_usd * 2) < 0.01

    def test_gp2_to_gp3_savings_positive(self, cost_analyzer, base_instance):
        """gp2→gp3 移行で正の節約額が算出される"""
        savings = cost_analyzer.estimate_gp3_savings(base_instance)
        assert savings > 0

    def test_gp3_instance_no_savings(self, cost_analyzer, base_instance):
        """既に gp3 の場合は節約額ゼロ"""
        gp3_instance = base_instance.model_copy(
            update={"storage_type": StorageType.GP3}
        )
        savings = cost_analyzer.estimate_gp3_savings(gp3_instance)
        assert savings == 0.0


class TestIOPSCost:
    """IOPSコスト計算テスト"""

    def test_io1_iops_cost(self, cost_analyzer, base_instance):
        """io1 プロビジョンドIOPSのコスト計算"""
        io1_instance = base_instance.model_copy(update={
            "storage_type": StorageType.IO1,
            "provisioned_iops": 3000,
        })
        breakdown, _ = cost_analyzer.calculate_monthly_cost(io1_instance)
        assert breakdown.iops_cost_usd > 0

    def test_gp3_free_iops_no_charge(self, cost_analyzer, base_instance):
        """gp3 の 3000 IOPS 以下は無料"""
        gp3_instance = base_instance.model_copy(update={
            "storage_type": StorageType.GP3,
            "provisioned_iops": 3000,
        })
        breakdown, _ = cost_analyzer.calculate_monthly_cost(gp3_instance)
        assert breakdown.iops_cost_usd == 0.0

    def test_gp3_excess_iops_charged(self, cost_analyzer, base_instance):
        """gp3 の 3000 IOPS 超過分は課金される"""
        gp3_instance = base_instance.model_copy(update={
            "storage_type": StorageType.GP3,
            "provisioned_iops": 6000,
        })
        breakdown, _ = cost_analyzer.calculate_monthly_cost(gp3_instance)
        assert breakdown.iops_cost_usd > 0


class TestBackupCost:
    """バックアップコスト計算テスト"""

    def test_backup_within_storage_free(self, cost_analyzer, base_instance):
        """スナップショット容量がストレージ以下は無料"""
        # base_instance は allocated=100GB, snapshot=80GB → 無料
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance)
        assert breakdown.backup_cost_usd == 0.0

    def test_backup_excess_charged(self, cost_analyzer, base_instance):
        """スナップショット容量がストレージ超過分は課金"""
        instance = base_instance.model_copy(update={"snapshot_storage_gb": 200.0})
        breakdown, _ = cost_analyzer.calculate_monthly_cost(instance)
        assert breakdown.backup_cost_usd > 0


class TestEfficiencyScore:
    """コスト効率スコア計算テスト"""

    def test_ideal_cpu_score_high(self, cost_analyzer):
        """CPU 使用率 50% 付近は高スコア"""
        score = CostAnalyzer._cpu_efficiency_score(50.0)
        assert score >= 95

    def test_low_cpu_score_low(self, cost_analyzer):
        """CPU 使用率 5% は低スコア（過剰スペック）"""
        score = CostAnalyzer._cpu_efficiency_score(5.0)
        assert score < 20

    def test_high_cpu_score_low(self, cost_analyzer):
        """CPU 使用率 95% は低スコア（ボトルネックリスク）: 100 - (95-80)*3 = 55"""
        score = CostAnalyzer._cpu_efficiency_score(95.0)
        # 15% 超過 * 3点/% = 45ペナルティ → 55点。60未満が妥当な閾値
        assert score < 60

    def test_score_range_valid(self, cost_analyzer):
        """スコアは常に 0〜100 の範囲"""
        for cpu_pct in [0, 5, 20, 50, 80, 95, 100]:
            score = CostAnalyzer._cpu_efficiency_score(float(cpu_pct))
            assert 0 <= score <= 100, f"CPU {cpu_pct}% のスコアが範囲外: {score}"


class TestCostAnomaly:
    """コスト異常検知テスト"""

    def test_spike_detected(self, cost_analyzer):
        """前月比 30% 増加を異常として検知"""
        anomaly = cost_analyzer.detect_cost_anomaly(
            "test-001",
            current_cost=1300.0,
            previous_cost=1000.0,
            threshold_pct=20.0,
        )
        assert anomaly.is_anomaly is True
        assert anomaly.anomaly_type == "cost_spike"

    def test_normal_change_not_anomaly(self, cost_analyzer):
        """前月比 10% 増加は正常範囲"""
        anomaly = cost_analyzer.detect_cost_anomaly(
            "test-001",
            current_cost=1100.0,
            previous_cost=1000.0,
            threshold_pct=20.0,
        )
        assert anomaly.is_anomaly is False

    def test_zero_previous_cost(self, cost_analyzer):
        """前月コストがゼロの場合もエラーにならない"""
        anomaly = cost_analyzer.detect_cost_anomaly(
            "test-001",
            current_cost=500.0,
            previous_cost=0.0,
        )
        assert anomaly.change_ratio_pct == 100.0

    def test_cost_drop_detected(self, cost_analyzer):
        """前月比 30% 減少を cost_drop として検知"""
        anomaly = cost_analyzer.detect_cost_anomaly(
            "test-001",
            current_cost=700.0,
            previous_cost=1000.0,
            threshold_pct=20.0,
        )
        assert anomaly.is_anomaly is True
        assert anomaly.anomaly_type == "cost_drop"


class TestDataTransferCost:
    """データ転送コスト計算テスト"""

    def test_zero_transfer_no_cost(self, cost_analyzer, base_instance):
        """転送量 0 の場合コストなし"""
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance, data_transfer_gb=0.0)
        assert breakdown.transfer_cost_usd == 0.0

    def test_small_transfer_cost_positive(self, cost_analyzer, base_instance):
        """少量の転送データでコスト発生"""
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance, data_transfer_gb=100.0)
        assert breakdown.transfer_cost_usd > 0.0

    def test_large_transfer_tiered(self, cost_analyzer, base_instance):
        """10TB 超で段階課金が適用される"""
        bd_small, _ = cost_analyzer.calculate_monthly_cost(base_instance, data_transfer_gb=1024.0)
        bd_large, _ = cost_analyzer.calculate_monthly_cost(base_instance, data_transfer_gb=20_000.0)
        # 大量転送は単価が安くなるため比例以下
        assert bd_large.transfer_cost_usd > bd_small.transfer_cost_usd


class TestUnknownInstanceClass:
    """未定義インスタンスクラスの処理テスト"""

    def test_unknown_class_uses_default_rate(self, cost_analyzer):
        """未定義インスタンスクラスはデフォルト料金で計算"""
        instance = RDSInstance(
            instance_id="unknown-class-001",
            engine=EngineType.MYSQL,
            engine_version="8.0",
            instance_class="db.x99.enormous",  # 存在しないクラス
            region="ap-northeast-1",
            multi_az=False,
            storage_type=StorageType.GP2,
            allocated_storage_gb=100,
        )
        breakdown, _ = cost_analyzer.calculate_monthly_cost(instance)
        assert breakdown.compute_cost_usd > 0.0


class TestIOPSEfficiencyScore:
    """IOPS効率スコアのテスト"""

    def test_high_iops_utilization_high_score(self, cost_analyzer):
        """IOPS 使用率 80% は高スコア"""
        instance = RDSInstance(
            instance_id="io1-001",
            engine=EngineType.MYSQL,
            engine_version="8.0",
            instance_class="db.m5.large",
            region="ap-northeast-1",
            multi_az=False,
            storage_type=StorageType.IO1,
            allocated_storage_gb=100,
            provisioned_iops=3000,
        )
        score = CostAnalyzer._iops_efficiency_score(instance, avg_iops_used=2400.0)
        assert score >= 80

    def test_low_iops_utilization_low_score(self, cost_analyzer):
        """IOPS 使用率 10% は低スコア"""
        instance = RDSInstance(
            instance_id="io1-002",
            engine=EngineType.MYSQL,
            engine_version="8.0",
            instance_class="db.m5.large",
            region="ap-northeast-1",
            multi_az=False,
            storage_type=StorageType.IO1,
            allocated_storage_gb=100,
            provisioned_iops=3000,
        )
        score = CostAnalyzer._iops_efficiency_score(instance, avg_iops_used=100.0)
        assert score < 60

    def test_gp2_fixed_mid_score(self, cost_analyzer):
        """gp2 は固定の中間スコアを返す"""
        instance = RDSInstance(
            instance_id="gp2-001",
            engine=EngineType.MYSQL,
            engine_version="8.0",
            instance_class="db.m5.large",
            region="ap-northeast-1",
            multi_az=False,
            storage_type=StorageType.GP2,
            allocated_storage_gb=100,
        )
        score = CostAnalyzer._iops_efficiency_score(instance, avg_iops_used=100.0)
        assert score == 80


class TestCostModelProperties:
    """CostBreakdown / MonthlyCostReport のプロパティテスト"""

    def test_compute_ratio_zero_total(self):
        """合計コスト 0 でゼロ除算しない"""
        from rds_analyzer.models.costs import CostBreakdown
        bd = CostBreakdown(compute_cost_usd=0.0, storage_cost_usd=0.0)
        assert bd.compute_ratio_pct == 0.0
        assert bd.storage_ratio_pct == 0.0

    def test_compute_ratio_sum(self, base_instance, cost_analyzer):
        """コンピュート比率 + ストレージ比率 ≦ 100"""
        breakdown, _ = cost_analyzer.calculate_monthly_cost(base_instance)
        assert breakdown.compute_ratio_pct + breakdown.storage_ratio_pct <= 100.1

    def test_monthly_report_savings(self):
        """MonthlyCostReport の節約額プロパティ"""
        from datetime import date
        from rds_analyzer.models.costs import CostBreakdown, MonthlyCostReport
        bd = CostBreakdown(compute_cost_usd=300.0, storage_cost_usd=50.0)
        report = MonthlyCostReport(
            instance_id="test",
            month=date.today(),
            breakdown=bd,
            optimized_cost_usd=280.0,
        )
        assert report.potential_savings_usd == pytest.approx(70.0, abs=0.01)
        assert report.savings_ratio_pct > 0

    def test_monthly_report_no_optimization(self):
        """最適化コストなしのとき節約額ゼロ"""
        from datetime import date
        from rds_analyzer.models.costs import CostBreakdown, MonthlyCostReport
        bd = CostBreakdown(compute_cost_usd=300.0, storage_cost_usd=50.0)
        report = MonthlyCostReport(
            instance_id="test",
            month=date.today(),
            breakdown=bd,
            optimized_cost_usd=None,
        )
        assert report.potential_savings_usd == 0.0
