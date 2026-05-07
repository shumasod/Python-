"""
RecommendationEngine テスト
"""

import pytest
from rds_analyzer.analyzers.recommendation_engine import (
    RecommendationEngine,
    RecommendationPriority,
    RecommendationType,
)
from rds_analyzer.analyzers.cost_analyzer import CostAnalyzer
from rds_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer
from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType
from tests.rds_conftest import make_metrics, make_stats


def make_instance(**kwargs) -> RDSInstance:
    defaults = dict(
        instance_id="test-001",
        engine=EngineType.MYSQL,
        engine_version="8.0",
        instance_class="db.m5.large",
        region="ap-northeast-1",
        multi_az=False,
        storage_type=StorageType.GP2,
        allocated_storage_gb=100,
    )
    defaults.update(kwargs)
    return RDSInstance(**defaults)


def make_cost_breakdown(instance):
    return CostAnalyzer().calculate_monthly_cost(instance)[0]


def make_perf(instance, cpu_avg=40.0, cpu_max=60.0):
    metrics = make_metrics(instance.instance_id, cpu_avg=cpu_avg, cpu_max=cpu_max)
    return PerformanceAnalyzer().analyze(instance, metrics)


@pytest.fixture
def engine():
    return RecommendationEngine()


class TestGp3Migration:

    def test_gp2_always_gets_gp3_recommendation(self, engine):
        inst = make_instance(storage_type=StorageType.GP2)
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.STORAGE_TYPE_CHANGE in types

    def test_gp3_no_storage_recommendation(self, engine):
        inst = make_instance(storage_type=StorageType.GP3)
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.STORAGE_TYPE_CHANGE not in types

    def test_gp3_rec_has_positive_savings(self, engine):
        inst = make_instance(storage_type=StorageType.GP2, allocated_storage_gb=200)
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        gp3_recs = [r for r in recs if r.type == RecommendationType.STORAGE_TYPE_CHANGE]
        assert len(gp3_recs) == 1
        assert gp3_recs[0].estimated_monthly_savings_usd > 0


class TestScaleDown:

    def test_low_cpu_triggers_scale_down(self, engine):
        inst = make_instance(instance_class="db.m5.xlarge")
        perf = make_perf(inst, cpu_avg=5.0, cpu_max=12.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.SCALE_DOWN in types

    def test_scale_down_has_savings(self, engine):
        inst = make_instance(instance_class="db.m5.xlarge")
        perf = make_perf(inst, cpu_avg=5.0, cpu_max=10.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        scale_down = [r for r in recs if r.type == RecommendationType.SCALE_DOWN]
        assert len(scale_down) == 1
        assert scale_down[0].estimated_monthly_savings_usd > 0

    def test_smallest_instance_no_scale_down(self, engine):
        inst = make_instance(instance_class="db.t3.micro")
        perf = make_perf(inst, cpu_avg=3.0, cpu_max=6.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.SCALE_DOWN not in types


class TestGraviton:

    def test_x86_gets_graviton_recommendation(self, engine):
        inst = make_instance(instance_class="db.m5.large")
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.UPGRADE_GRAVITON in types

    def test_graviton_instance_no_recommendation(self, engine):
        inst = make_instance(instance_class="db.m6g.large")
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.UPGRADE_GRAVITON not in types

    def test_multi_az_graviton_savings_doubled(self, engine):
        single = make_instance(instance_class="db.m5.large", multi_az=False)
        multi = make_instance(instance_class="db.m5.large", multi_az=True)
        perf_s = make_perf(single)
        perf_m = make_perf(multi)
        bd_s = make_cost_breakdown(single)
        bd_m = make_cost_breakdown(multi)

        recs_s = engine.generate_recommendations(single, perf_s, bd_s)
        recs_m = engine.generate_recommendations(multi, perf_m, bd_m)

        savings_s = next(r.estimated_monthly_savings_usd for r in recs_s if r.type == RecommendationType.UPGRADE_GRAVITON)
        savings_m = next(r.estimated_monthly_savings_usd for r in recs_m if r.type == RecommendationType.UPGRADE_GRAVITON)
        assert abs(savings_m - savings_s * 2) < 0.01


class TestMultiAz:

    def test_single_az_gets_multi_az_recommendation(self, engine):
        inst = make_instance(multi_az=False)
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.ENABLE_MULTI_AZ in types

    def test_multi_az_no_enable_recommendation(self, engine):
        inst = make_instance(multi_az=True)
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.ENABLE_MULTI_AZ not in types


class TestPriorityOrdering:

    def test_critical_comes_before_low(self, engine):
        """CRITICAL 提案は LOW 提案より前に来る"""
        from rds_analyzer.models.metrics import PerformanceStatus
        from tests.test_performance_analyzer import make_healthy_metrics, make_stats

        inst = make_instance()
        metrics = make_healthy_metrics()
        metrics.cpu_utilization = make_stats(92.0, 99.0)
        perf = PerformanceAnalyzer().analyze(inst, metrics)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)

        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        priorities = [priority_order[r.priority] for r in recs]
        assert priorities == sorted(priorities)

    def test_recommendations_not_empty(self, engine):
        """常に最低1件の提案がある（gp2 or multi-az）"""
        inst = make_instance(storage_type=StorageType.GP2, multi_az=False)
        perf = make_perf(inst)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        assert len(recs) >= 1


class TestAuroraRecommendation:

    def test_high_cpu_mysql_gets_aurora_rec(self, engine):
        """CPU > 60% の MySQL インスタンスは Aurora 移行提案を受ける"""
        inst = make_instance(engine=EngineType.MYSQL, instance_class="db.m5.xlarge")
        perf = make_perf(inst, cpu_avg=70.0, cpu_max=85.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.AURORA_MIGRATION in types

    def test_aurora_instance_no_aurora_rec(self, engine):
        """既に Aurora の場合は Aurora 移行提案なし"""
        inst = make_instance(engine=EngineType.AURORA_MYSQL)
        perf = make_perf(inst, cpu_avg=70.0, cpu_max=85.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        types = [r.type for r in recs]
        assert RecommendationType.AURORA_MIGRATION not in types


class TestImpactSummary:

    def test_positive_savings_in_impact_summary(self, engine):
        inst = make_instance(instance_class="db.m5.xlarge", storage_type=StorageType.GP2)
        perf = make_perf(inst, cpu_avg=5.0, cpu_max=10.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        for rec in recs:
            summary = rec.impact_summary
            assert isinstance(summary, str)
            assert len(summary) > 0

    def test_recommendation_id_unique(self, engine):
        inst = make_instance(storage_type=StorageType.GP2, multi_az=False)
        perf = make_perf(inst, cpu_avg=5.0, cpu_max=10.0)
        bd = make_cost_breakdown(inst)
        recs = engine.generate_recommendations(inst, perf, bd)
        ids = [r.recommendation_id for r in recs]
        assert len(ids) == len(set(ids))
