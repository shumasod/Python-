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
