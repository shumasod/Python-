"""
API スキーマ定義

設計意図:
- リクエスト/レスポンスの型安全性を Pydantic で保証
- フロントエンドとの JSON インターフェースを明確化
- OpenAPI (Swagger) 自動生成のためのドキュメントを付与
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..models.costs import CostBreakdown, CostEfficiencyScore
from ..models.metrics import PerformanceAnalysisResult
from ..analyzers.recommendation_engine import Recommendation


class RDSInstanceRequest(BaseModel):
    """RDS インスタンス登録/更新リクエスト"""
    instance_id: str = Field(description="RDS インスタンスID")
    engine: str = Field(description="DBエンジン (mysql/postgresql/aurora-mysql等)")
    engine_version: str = Field(description="エンジンバージョン")
    instance_class: str = Field(description="インスタンスクラス")
    region: str = Field(default="ap-northeast-1")
    multi_az: bool = Field(default=False)
    storage_type: str = Field(description="ストレージタイプ (gp2/gp3/io1)")
    allocated_storage_gb: int = Field(ge=20)
    provisioned_iops: Optional[int] = Field(default=None)
    read_replica_count: int = Field(default=0, ge=0, le=5)
    backup_retention_days: int = Field(default=7)
    snapshot_storage_gb: float = Field(default=0.0)
    tags: dict[str, str] = Field(default_factory=dict)


class MetricsInputRequest(BaseModel):
    """メトリクス手動入力リクエスト（CloudWatch API 使用不可時の代替）"""
    instance_id: str
    period_hours: int = Field(default=24, description="集計期間（時間）")

    # CPU
    cpu_avg_pct: float = Field(ge=0, le=100)
    cpu_max_pct: float = Field(ge=0, le=100)
    cpu_p95_pct: float = Field(ge=0, le=100)

    # メモリ (GB)
    freeable_memory_avg_gb: float = Field(ge=0)
    freeable_memory_min_gb: float = Field(ge=0)

    # IOPS
    read_iops_avg: float = Field(ge=0)
    write_iops_avg: float = Field(ge=0)
    read_iops_max: float = Field(ge=0)
    write_iops_max: float = Field(ge=0)

    # レイテンシ (ms)
    read_latency_avg_ms: float = Field(ge=0)
    write_latency_avg_ms: float = Field(ge=0)

    # コネクション
    connections_avg: float = Field(ge=0)
    connections_max: float = Field(ge=0)

    # ストレージ (GB)
    free_storage_gb: float = Field(ge=0)

    # その他
    disk_queue_depth_avg: float = Field(default=0, ge=0)


class CostSummaryResponse(BaseModel):
    """コストサマリーレスポンス"""
    instance_id: str
    month: str = Field(description="対象月 (YYYY-MM)")
    total_cost_usd: float
    breakdown: dict[str, float] = Field(description="コスト内訳")
    cost_efficiency_score: int = Field(description="コスト効率スコア (0-100)")
    grade: str = Field(description="スコアグレード (A/B/C/D/F)")
    potential_savings_usd: float = Field(description="推定削減可能額(USD/月)")


class PerformanceSummaryResponse(BaseModel):
    """パフォーマンスサマリーレスポンス"""
    instance_id: str
    health_score: int
    status_summary: str
    bottlenecks: list[str]
    cpu_avg_pct: float
    memory_free_gb: float
    avg_total_iops: float
    avg_connections: float


class RDSSummaryResponse(BaseModel):
    """
    GET /rds/summary レスポンス

    全インスタンスの概要（コスト + スコア）
    """
    total_instances: int
    total_monthly_cost_usd: float
    total_potential_savings_usd: float
    instances: list[InstanceSummaryItem]


class InstanceSummaryItem(BaseModel):
    """インスタンスサマリーアイテム"""
    instance_id: str
    engine: str
    instance_class: str
    region: str
    monthly_cost_usd: float
    cost_efficiency_score: int
    health_score: int
    top_recommendation: Optional[str] = None


class AnalysisResponse(BaseModel):
    """
    GET /rds/{id}/analysis レスポンス

    特定インスタンスの詳細分析結果
    """
    instance_id: str
    analyzed_at: datetime

    # コスト分析
    cost: CostSummaryResponse

    # パフォーマンス分析
    performance: PerformanceSummaryResponse

    # 分析期間
    analysis_period_hours: int

    # 警告・注意事項
    warnings: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    """
    GET /rds/{id}/recommendations レスポンス

    改善提案リスト
    """
    instance_id: str
    generated_at: datetime
    total_recommendations: int
    total_potential_savings_usd: float
    recommendations: list[RecommendationItem]


class RecommendationItem(BaseModel):
    """改善提案アイテム（APIレスポンス用）"""
    id: str
    type: str
    priority: str
    title: str
    description: str
    current_config: str
    recommended_config: str
    estimated_monthly_savings_usd: float
    estimated_performance_improvement_pct: float
    implementation_complexity: int
    action_steps: list[str]
    impact_summary: str


class HealthCheckResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str = "ok"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
