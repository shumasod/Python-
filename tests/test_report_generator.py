"""
ReportGenerator テスト
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from rds_analyzer.report_generator import ReportGenerator
from rds_analyzer.analyzers.cost_analyzer import CostAnalyzer
from rds_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer
from rds_analyzer.analyzers.recommendation_engine import RecommendationEngine
from rds_analyzer.models.rds import EngineType, RDSInstance, StorageType
from tests.rds_conftest import make_metrics, make_stats


@pytest.fixture
def instance():
    return RDSInstance(
        instance_id="report-test-001",
        engine=EngineType.MYSQL,
        engine_version="8.0",
        instance_class="db.m5.large",
        region="ap-northeast-1",
        multi_az=False,
        storage_type=StorageType.GP2,
        allocated_storage_gb=100,
        snapshot_storage_gb=80.0,
    )


@pytest.fixture
def analysis_data(instance):
    cost_analyzer = CostAnalyzer()
    perf_analyzer = PerformanceAnalyzer()
    rec_engine = RecommendationEngine()
    metrics = make_metrics(instance.instance_id, cpu_avg=40.0, cpu_max=65.0)

    breakdown, _ = cost_analyzer.calculate_monthly_cost(instance)
    perf_result = perf_analyzer.analyze(instance, metrics)
    cost_score = cost_analyzer.calculate_efficiency_score(
        instance, breakdown,
        avg_cpu_pct=metrics.cpu_utilization.avg,
        avg_iops_used=metrics.read_iops.avg + metrics.write_iops.avg,
        storage_used_gb=instance.allocated_storage_gb - metrics.free_storage_bytes.avg / (1024**3),
    )
    recommendations = rec_engine.generate_recommendations(instance, perf_result, breakdown)

    return breakdown, cost_score, perf_result, recommendations


@pytest.fixture
def generator():
    return ReportGenerator()


class TestReportGeneration:

    def test_generate_returns_string(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        assert isinstance(md, str)
        assert len(md) > 100

    def test_header_contains_instance_id(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        assert instance.instance_id in md

    def test_report_contains_cost_disclaimer(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        assert "推定値" in md

    def test_report_contains_all_sections(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        assert "エグゼクティブサマリー" in md
        assert "コスト分析" in md
        assert "パフォーマンス分析" in md
        assert "改善提案" in md

    def test_report_shows_total_cost(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        assert f"${breakdown.total_cost_usd:.2f}" in md

    def test_no_recommendations_section(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, _ = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, [])
        assert "現時点での改善提案はありません" in md

    def test_footer_present(self, generator, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        assert "自動生成" in md


class TestIndexSection:
    """ReportGenerator のカバリングインデックスセクションテスト"""

    @pytest.fixture
    def index_recs(self):
        from rds_analyzer.models.index import CoveringIndexRecommendation
        return [
            CoveringIndexRecommendation(
                recommendation_id="idx_001",
                table_name="orders",
                key_columns=["status", "created_at"],
                include_columns=["id", "amount"],
                priority="high",
                reason="`orders` で平均 1000:1 のスキャンが発生",
                affected_query_ids=["q1", "q2"],
                estimated_scan_ratio=1000.0,
                estimated_latency_improvement_pct=90.0,
                estimated_daily_rows_saved=500000.0,
                create_statement_mysql="CREATE INDEX `idx_orders_covering_001` ON `orders` (`status`, `created_at`, `id`, `amount`);",
                create_statement_postgresql='CREATE INDEX "idx_orders_covering_001" ON "orders" ("status", "created_at") INCLUDE ("id", "amount");',
            )
        ]

    def test_index_section_included_when_provided(
        self, generator, instance, analysis_data, index_recs
    ):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(
            instance, breakdown, cost_score, perf_result, recs,
            index_recommendations=index_recs,
        )
        assert "カバリングインデックス推奨" in md
        assert "orders" in md

    def test_index_section_not_included_when_empty(
        self, generator, instance, analysis_data
    ):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(
            instance, breakdown, cost_score, perf_result, recs,
            index_recommendations=[],
        )
        assert "カバリングインデックス推奨" not in md

    def test_index_section_shows_create_statements(
        self, generator, instance, analysis_data, index_recs
    ):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(
            instance, breakdown, cost_score, perf_result, recs,
            index_recommendations=index_recs,
        )
        assert "CREATE INDEX" in md
        assert "INCLUDE" in md  # PostgreSQL INCLUDE 句

    def test_index_section_shows_improvement_pct(
        self, generator, instance, analysis_data, index_recs
    ):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(
            instance, breakdown, cost_score, perf_result, recs,
            index_recommendations=index_recs,
        )
        assert "90%" in md or "90" in md

    def test_score_emoji_low_score(self, generator):
        """スコア < 60 の場合に 🔴 を返す"""
        assert generator._score_emoji(30) == "🔴"
        assert generator._score_emoji(59) == "🔴"

    def test_score_emoji_medium_score(self, generator):
        assert generator._score_emoji(60) == "⚠️"
        assert generator._score_emoji(79) == "⚠️"

    def test_score_emoji_high_score(self, generator):
        assert generator._score_emoji(80) == "✅"


class TestReportSave:

    def test_save_creates_file(self, generator, tmp_path, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        out = tmp_path / "report.md"
        generator.save(md, out)
        assert out.exists()
        assert out.read_text(encoding="utf-8") == md

    def test_save_creates_parent_dirs(self, generator, tmp_path, instance, analysis_data):
        breakdown, cost_score, perf_result, recs = analysis_data
        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        out = tmp_path / "nested" / "dir" / "report.md"
        generator.save(md, out)
        assert out.exists()


class TestRecommendationGroups:
    """提案のグループ化テスト"""

    def test_recommendations_grouped_by_type(self, generator, instance):
        """同種別の提案が同じカテゴリ見出し配下にまとめられる"""
        from rds_analyzer.analyzers.recommendation_engine import (
            Recommendation, RecommendationPriority, RecommendationType,
        )
        recs = [
            Recommendation(
                recommendation_id="rec_001",
                type=RecommendationType.SCALE_DOWN,
                priority=RecommendationPriority.MEDIUM,
                title="インスタンスクラス縮小",
                description="CPU利用率が低い",
                current_config="db.r5.xlarge",
                recommended_config="db.r5.large",
                estimated_monthly_savings_usd=150.0,
                implementation_complexity=2,
            ),
            Recommendation(
                recommendation_id="rec_002",
                type=RecommendationType.STORAGE_TYPE_CHANGE,
                priority=RecommendationPriority.LOW,
                title="gp3 への移行",
                description="コスト削減",
                current_config="gp2",
                recommended_config="gp3",
                estimated_monthly_savings_usd=20.0,
                implementation_complexity=1,
            ),
            Recommendation(
                recommendation_id="rec_003",
                type=RecommendationType.SCALE_DOWN,
                priority=RecommendationPriority.LOW,
                title="バックアップ期間短縮",
                description="30日から7日へ",
                current_config="30日",
                recommended_config="7日",
                estimated_monthly_savings_usd=10.0,
                implementation_complexity=1,
            ),
        ]
        from rds_analyzer.analyzers.cost_analyzer import CostAnalyzer
        from rds_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer
        from tests.rds_conftest import make_metrics
        cost_analyzer = CostAnalyzer()
        perf_analyzer = PerformanceAnalyzer()
        metrics = make_metrics(instance.instance_id, cpu_avg=40.0, cpu_max=65.0)
        breakdown, _ = cost_analyzer.calculate_monthly_cost(instance)
        cost_score = cost_analyzer.calculate_efficiency_score(
            instance, breakdown,
            avg_cpu_pct=metrics.cpu_utilization.avg,
            avg_iops_used=metrics.read_iops.avg + metrics.write_iops.avg,
            storage_used_gb=instance.allocated_storage_gb - metrics.free_storage_bytes.avg / (1024**3),
        )
        perf_result = perf_analyzer.analyze(instance, metrics)

        md = generator.generate(instance, breakdown, cost_score, perf_result, recs)
        # カテゴリ見出しが含まれることを確認
        assert "### カテゴリ:" in md
        # SCALE_DOWN が1グループにまとまること（2件）
        scale_down_idx = md.index("スケールダウン")
        assert "インスタンスクラス縮小" in md[scale_down_idx:]

    def test_empty_recommendations_no_category_headers(self, generator, instance):
        """提案なしのとき カテゴリ見出しが出力されない"""
        from rds_analyzer.analyzers.cost_analyzer import CostAnalyzer
        from rds_analyzer.analyzers.performance_analyzer import PerformanceAnalyzer
        from tests.rds_conftest import make_metrics
        cost_analyzer = CostAnalyzer()
        perf_analyzer = PerformanceAnalyzer()
        metrics = make_metrics(instance.instance_id, cpu_avg=40.0, cpu_max=65.0)
        breakdown, _ = cost_analyzer.calculate_monthly_cost(instance)
        cost_score = cost_analyzer.calculate_efficiency_score(
            instance, breakdown,
            avg_cpu_pct=metrics.cpu_utilization.avg,
            avg_iops_used=metrics.read_iops.avg + metrics.write_iops.avg,
            storage_used_gb=instance.allocated_storage_gb - metrics.free_storage_bytes.avg / (1024**3),
        )
        perf_result = perf_analyzer.analyze(instance, metrics)

        md = generator.generate(instance, breakdown, cost_score, perf_result, [])
        assert "### カテゴリ:" not in md
        assert "現時点での改善提案はありません" in md
