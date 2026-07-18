"""
FastAPI エンドポイント テスト

設計意図:
- TestClient を使用した API 統合テスト
- 各エンドポイントのレスポンス構造を検証
- エラーケース（404, 422）の動作確認
"""

import json
import pytest
from fastapi.testclient import TestClient

from rds_analyzer.main import app


@pytest.fixture
def client():
    """テスト用 FastAPI クライアント"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_instance_payload():
    """サンプルインスタンス登録ペイロード"""
    return {
        "instance_id": "test-api-mysql-001",
        "engine": "mysql",
        "engine_version": "8.0.35",
        "instance_class": "db.m5.large",
        "region": "ap-northeast-1",
        "multi_az": False,
        "storage_type": "gp2",
        "allocated_storage_gb": 100,
        "backup_retention_days": 7,
        "snapshot_storage_gb": 80.0,
        "tags": {"Environment": "test"},
    }


@pytest.fixture
def sample_metrics_payload():
    """サンプルメトリクスペイロード"""
    return {
        "instance_id": "test-api-mysql-001",
        "period_hours": 24,
        "cpu_avg_pct": 45.0,
        "cpu_max_pct": 70.0,
        "cpu_p95_pct": 65.0,
        "freeable_memory_avg_gb": 3.5,
        "freeable_memory_min_gb": 2.5,
        "read_iops_avg": 200.0,
        "write_iops_avg": 100.0,
        "read_iops_max": 400.0,
        "write_iops_max": 250.0,
        "read_latency_avg_ms": 5.0,
        "write_latency_avg_ms": 6.0,
        "connections_avg": 80.0,
        "connections_max": 120.0,
        "free_storage_gb": 55.0,
        "disk_queue_depth_avg": 0.2,
    }


class TestHealthCheck:
    def test_health_check_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestInstanceRegistration:
    def test_register_instance_success(self, client, sample_instance_payload):
        response = client.post("/api/v1/rds", json=sample_instance_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["instance_id"] == "test-api-mysql-001"

    def test_register_invalid_engine_fails(self, client, sample_instance_payload):
        payload = {**sample_instance_payload, "engine": "invalid-db"}
        response = client.post("/api/v1/rds", json=payload)
        assert response.status_code == 422

    def test_register_invalid_storage_fails(self, client, sample_instance_payload):
        payload = {**sample_instance_payload, "storage_type": "ssd-xyz"}
        response = client.post("/api/v1/rds", json=payload)
        assert response.status_code == 422


class TestMetricsSubmission:
    def test_submit_metrics_success(
        self, client, sample_instance_payload, sample_metrics_payload
    ):
        # インスタンスを先に登録
        client.post("/api/v1/rds", json=sample_instance_payload)
        response = client.post(
            "/api/v1/rds/test-api-mysql-001/metrics",
            json=sample_metrics_payload,
        )
        assert response.status_code == 200

    def test_submit_metrics_unknown_instance_fails(
        self, client, sample_metrics_payload
    ):
        payload = {**sample_metrics_payload, "instance_id": "non-existent"}
        response = client.post(
            "/api/v1/rds/non-existent/metrics",
            json={**sample_metrics_payload, "instance_id": "non-existent"},
        )
        assert response.status_code == 404


class TestAnalysis:
    @pytest.fixture(autouse=True)
    def setup_instance_and_metrics(
        self, client, sample_instance_payload, sample_metrics_payload
    ):
        """全テスト前にインスタンスとメトリクスを準備"""
        client.post("/api/v1/rds", json=sample_instance_payload)
        client.post(
            "/api/v1/rds/test-api-mysql-001/metrics",
            json=sample_metrics_payload,
        )

    def test_get_analysis_success(self, client):
        response = client.get("/api/v1/rds/test-api-mysql-001/analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["instance_id"] == "test-api-mysql-001"
        assert "cost" in data
        assert "performance" in data

    def test_analysis_cost_structure(self, client):
        response = client.get("/api/v1/rds/test-api-mysql-001/analysis")
        cost = response.json()["cost"]
        assert "total_cost_usd" in cost
        assert "breakdown" in cost
        assert "cost_efficiency_score" in cost
        assert 0 <= cost["cost_efficiency_score"] <= 100

    def test_analysis_performance_structure(self, client):
        response = client.get("/api/v1/rds/test-api-mysql-001/analysis")
        perf = response.json()["performance"]
        assert "health_score" in perf
        assert 0 <= perf["health_score"] <= 100

    def test_analysis_not_found(self, client):
        response = client.get("/api/v1/rds/nonexistent/analysis")
        assert response.status_code == 404

    def test_get_recommendations_success(self, client):
        response = client.get("/api/v1/rds/test-api-mysql-001/recommendations")
        assert response.status_code == 200
        data = response.json()
        assert data["instance_id"] == "test-api-mysql-001"
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)


class TestSummary:
    def test_empty_summary(self, client):
        """インスタンス未登録でも空リストが返る"""
        response = client.get("/api/v1/rds/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_instances" in data
        assert "total_monthly_cost_usd" in data

    def test_summary_with_instance(
        self, client, sample_instance_payload, sample_metrics_payload
    ):
        """登録済みインスタンスが summary に含まれる"""
        client.post("/api/v1/rds", json=sample_instance_payload)
        client.post(
            "/api/v1/rds/test-api-mysql-001/metrics",
            json=sample_metrics_payload,
        )
        response = client.get("/api/v1/rds/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_instances"] >= 1
        assert data["total_monthly_cost_usd"] > 0


class TestRecommendationsSort:
    """GET /rds/{id}/recommendations?sort= ソートのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, client, sample_instance_payload, sample_metrics_payload):
        client.post("/api/v1/rds", json=sample_instance_payload)
        client.post(
            "/api/v1/rds/test-api-mysql-001/metrics",
            json=sample_metrics_payload,
        )

    def test_sort_by_savings(self, client):
        resp = client.get(
            "/api/v1/rds/test-api-mysql-001/recommendations?sort=savings"
        )
        assert resp.status_code == 200
        recs = resp.json()["recommendations"]
        savings = [r["estimated_monthly_savings_usd"] for r in recs]
        assert savings == sorted(savings, reverse=True)

    def test_sort_by_complexity(self, client):
        resp = client.get(
            "/api/v1/rds/test-api-mysql-001/recommendations?sort=complexity"
        )
        assert resp.status_code == 200
        recs = resp.json()["recommendations"]
        complexities = [r["implementation_complexity"] for r in recs]
        assert complexities == sorted(complexities)

    def test_sort_default_priority(self, client):
        resp = client.get("/api/v1/rds/test-api-mysql-001/recommendations")
        assert resp.status_code == 200

    def test_invalid_sort_returns_422(self, client):
        resp = client.get(
            "/api/v1/rds/test-api-mysql-001/recommendations?sort=invalid"
        )
        assert resp.status_code == 422

    def test_sort_not_found_returns_404(self, client):
        resp = client.get(
            "/api/v1/rds/no-such/recommendations?sort=savings"
        )
        assert resp.status_code == 404


class TestCostHistory:
    @pytest.fixture(autouse=True)
    def setup(self, client, sample_instance_payload):
        client.post("/api/v1/rds", json=sample_instance_payload)

    def test_post_cost_history_success(self, client):
        history = [
            {"month": f"2024-{i:02d}", "cost_usd": 400.0 + i * 10}
            for i in range(1, 7)
        ]
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/cost-history", json=history
        )
        assert resp.status_code == 200
        assert "6 件" in resp.json()["message"]

    def test_post_cost_history_not_found(self, client):
        resp = client.post(
            "/api/v1/rds/no-such-instance/cost-history", json=[]
        )
        assert resp.status_code == 404


class TestForecast:
    @pytest.fixture(autouse=True)
    def setup(self, client, sample_instance_payload):
        client.post("/api/v1/rds", json=sample_instance_payload)
        history = [
            {"month": f"2024-{i:02d}", "cost_usd": 400.0 + i * 20}
            for i in range(1, 7)
        ]
        client.post(
            "/api/v1/rds/test-api-mysql-001/cost-history", json=history
        )

    def test_forecast_success(self, client):
        resp = client.get("/api/v1/rds/test-api-mysql-001/forecast?months=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "forecasts" in data
        assert len(data["forecasts"]) == 3
        assert "trend" in data

    def test_forecast_insufficient_history(self, client, sample_instance_payload):
        # 別インスタンスで履歴なし
        payload = {**sample_instance_payload, "instance_id": "no-history-inst"}
        client.post("/api/v1/rds", json=payload)
        resp = client.get("/api/v1/rds/no-history-inst/forecast")
        assert resp.status_code == 400

    def test_forecast_not_found(self, client):
        resp = client.get("/api/v1/rds/nonexistent/forecast")
        assert resp.status_code == 404


class TestReport:
    @pytest.fixture(autouse=True)
    def setup(self, client, sample_instance_payload, sample_metrics_payload):
        client.post("/api/v1/rds", json=sample_instance_payload)
        client.post(
            "/api/v1/rds/test-api-mysql-001/metrics",
            json=sample_metrics_payload,
        )

    def test_report_success(self, client):
        resp = client.get("/api/v1/rds/test-api-mysql-001/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
        assert "test-api-mysql-001" in data["markdown"]
        assert "推定値" in data["markdown"]

    def test_report_not_found(self, client):
        resp = client.get("/api/v1/rds/no-such/report")
        assert resp.status_code == 404

    def test_report_no_metrics(self, client, sample_instance_payload):
        payload = {**sample_instance_payload, "instance_id": "no-metrics-inst"}
        client.post("/api/v1/rds", json=payload)
        resp = client.get("/api/v1/rds/no-metrics-inst/report")
        assert resp.status_code == 404


class TestIndexAnalysis:
    """POST /rds/{id}/index-analysis エンドポイントのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, client, sample_instance_payload):
        client.post("/api/v1/rds", json=sample_instance_payload)

    def test_basic_recommendation_returned(self, client):
        """フルスキャンクエリに対してカバリングインデックスが推奨される"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "query_id": "q1",
                        "table_name": "orders",
                        "filter_columns": ["status"],
                        "select_columns": ["id", "amount"],
                        "avg_rows_examined": 10000,
                        "avg_rows_returned": 10,
                        "execution_count_per_day": 100,
                        "avg_latency_ms": 80.0,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_queries_analyzed"] == 1
        assert data["queries_needing_index"] == 1
        assert len(data["recommendations"]) == 1

        rec = data["recommendations"][0]
        assert rec["table_name"] == "orders"
        assert "status" in rec["key_columns"]
        assert rec["priority"] in ("critical", "high", "medium", "low")
        assert rec["estimated_scan_ratio"] == 1000.0
        assert rec["estimated_latency_improvement_pct"] > 0

    def test_mysql_create_statement_has_all_columns(self, client):
        """MySQL用 CREATE INDEX 文にキー列と SELECT 列が含まれる"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "table_name": "orders",
                        "filter_columns": ["user_id"],
                        "sort_columns": ["created_at"],
                        "select_columns": ["total", "status"],
                        "avg_rows_examined": 5000,
                        "avg_rows_returned": 5,
                    }
                ]
            },
        )
        stmt = resp.json()["recommendations"][0]["create_statement_mysql"]
        assert "CREATE INDEX" in stmt
        assert "`orders`" in stmt
        assert "`user_id`" in stmt

    def test_postgresql_include_clause_generated(self, client):
        """PostgreSQL用 CREATE INDEX 文に INCLUDE 句が含まれる"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "engine": "postgresql",
                "queries": [
                    {
                        "table_name": "users",
                        "filter_columns": ["email"],
                        "select_columns": ["name", "created_at"],
                        "avg_rows_examined": 10000,
                        "avg_rows_returned": 1,
                        "execution_count_per_day": 500,
                    }
                ],
            },
        )
        stmt = resp.json()["recommendations"][0]["create_statement_postgresql"]
        assert "CREATE INDEX" in stmt
        assert "INCLUDE" in stmt
        assert '"name"' in stmt or '"created_at"' in stmt

    def test_already_covered_query_not_recommended(self, client):
        """既存インデックスでカバー済みのクエリは推奨しない"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "table_name": "products",
                        "filter_columns": ["category_id"],
                        "select_columns": ["name", "price"],
                        "avg_rows_examined": 500,
                        "avg_rows_returned": 5,
                    }
                ],
                "existing_indexes": [
                    {
                        "index_name": "idx_products_covering",
                        "table_name": "products",
                        "key_columns": ["category_id", "name", "price"],
                    }
                ],
            },
        )
        data = resp.json()
        assert data["queries_already_covered"] == 1
        assert data["queries_needing_index"] == 0
        assert data["recommendations"] == []

    def test_no_where_clause_no_recommendation(self, client):
        """WHERE 句なしクエリは推奨しない"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "table_name": "logs",
                        "filter_columns": [],
                        "select_columns": ["id", "message"],
                        "avg_rows_examined": 1000000,
                        "avg_rows_returned": 1000000,
                    }
                ]
            },
        )
        assert resp.json()["recommendations"] == []

    def test_engine_defaults_to_instance_engine(self, client):
        """engine 省略時はインスタンスのエンジン (mysql) を使用"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "table_name": "t",
                        "filter_columns": ["a"],
                        "select_columns": ["b"],
                        "avg_rows_examined": 10000,
                        "avg_rows_returned": 10,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["engine"] == "mysql"

    def test_multiple_queries_multiple_tables(self, client):
        """複数テーブルのクエリは別々に推奨される"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "query_id": "q1",
                        "table_name": "orders",
                        "filter_columns": ["status"],
                        "avg_rows_examined": 1000,
                        "avg_rows_returned": 5,
                    },
                    {
                        "query_id": "q2",
                        "table_name": "products",
                        "filter_columns": ["category"],
                        "avg_rows_examined": 2000,
                        "avg_rows_returned": 10,
                    },
                ]
            },
        )
        data = resp.json()
        assert data["total_queries_analyzed"] == 2
        tables = {r["table_name"] for r in data["recommendations"]}
        assert "orders" in tables
        assert "products" in tables

    def test_affected_query_count_in_response(self, client):
        """affected_query_count が正しく返る"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "query_id": "q1",
                        "table_name": "orders",
                        "filter_columns": ["user_id", "status"],
                        "select_columns": ["id"],
                        "avg_rows_examined": 1000,
                        "avg_rows_returned": 5,
                    }
                ]
            },
        )
        rec = resp.json()["recommendations"][0]
        assert rec["affected_query_count"] >= 1

    def test_not_found_returns_404(self, client):
        """存在しないインスタンスは 404"""
        resp = client.post(
            "/api/v1/rds/no-such-instance/index-analysis",
            json={"queries": []},
        )
        assert resp.status_code == 404

    def test_empty_queries_returns_zero_recommendations(self, client):
        """クエリなしの場合は空の推奨リスト"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={"queries": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_queries_analyzed"] == 0
        assert data["recommendations"] == []

    def test_response_contains_improvement_pct(self, client):
        """estimated_total_improvement_pct がレスポンスに含まれる"""
        resp = client.post(
            "/api/v1/rds/test-api-mysql-001/index-analysis",
            json={
                "queries": [
                    {
                        "table_name": "events",
                        "filter_columns": ["type"],
                        "select_columns": ["payload"],
                        "avg_rows_examined": 50000,
                        "avg_rows_returned": 50,
                    }
                ]
            },
        )
        data = resp.json()
        assert "estimated_total_improvement_pct" in data
        assert data["estimated_total_improvement_pct"] > 0


class TestNotify:
    @pytest.fixture(autouse=True)
    def setup(self, client, sample_instance_payload, sample_metrics_payload):
        client.post("/api/v1/rds", json=sample_instance_payload)
        client.post(
            "/api/v1/rds/test-api-mysql-001/metrics",
            json=sample_metrics_payload,
        )

    def test_notify_no_webhook_returns_skipped(self, client):
        """Webhook URL 未設定のとき skipped が返る"""
        resp = client.post("/api/v1/rds/test-api-mysql-001/notify")
        assert resp.status_code == 200
        data = resp.json()
        # Webhook 未設定なので skipped または sent=false
        assert "skipped" in data or data.get("performance_alert_sent") is False

    def test_notify_not_found(self, client):
        resp = client.post("/api/v1/rds/no-such/notify")
        assert resp.status_code == 404
