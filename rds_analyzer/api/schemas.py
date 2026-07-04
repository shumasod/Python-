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


# ============================================================
# カバリングインデックス分析
# ============================================================

class QueryPatternRequest(BaseModel):
    """クエリパターン入力 (カバリングインデックス分析用)"""
    query_id: str = Field(default="", description="クエリ識別子（任意）")
    table_name: str = Field(description="対象テーブル名")
    schema_name: str = Field(default="public", description="スキーマ名 (PostgreSQL)")

    filter_columns: list[str] = Field(
        default_factory=list,
        description="WHERE/JOIN 条件カラム (インデックスキー候補)",
    )
    sort_columns: list[str] = Field(
        default_factory=list, description="ORDER BY カラム"
    )
    group_columns: list[str] = Field(
        default_factory=list, description="GROUP BY カラム"
    )
    select_columns: list[str] = Field(
        default_factory=list,
        description="SELECT カラム (空 = SELECT *、カバリング判定不能)",
    )

    execution_count_per_day: float = Field(default=0, ge=0, description="1日あたり実行回数")
    avg_rows_examined: float = Field(default=0, ge=0, description="平均スキャン行数")
    avg_rows_returned: float = Field(default=1, ge=1, description="平均返却行数")
    avg_latency_ms: float = Field(default=0, ge=0, description="平均実行時間 (ms)")
    query_text: Optional[str] = Field(default=None, description="クエリ文字列（参考）")


class ExistingIndexRequest(BaseModel):
    """既存インデックス入力"""
    index_name: str
    table_name: str
    key_columns: list[str] = Field(description="キーカラム (順序通り)")
    include_columns: list[str] = Field(
        default_factory=list, description="INCLUDE カラム (PostgreSQL 11+)"
    )
    is_unique: bool = False
    index_type: str = Field(default="BTREE")


class IndexAnalysisApiRequest(BaseModel):
    """POST /rds/{id}/index-analysis リクエスト"""
    engine: Optional[str] = Field(
        default=None,
        description="エンジン種別 (mysql/mariadb/postgresql)。省略時はインスタンスのエンジンを使用",
    )
    queries: list[QueryPatternRequest] = Field(description="分析対象クエリパターン一覧")
    existing_indexes: list[ExistingIndexRequest] = Field(
        default_factory=list, description="既存インデックス一覧"
    )


class CoveringIndexRecommendationResponse(BaseModel):
    """カバリングインデックス推奨アイテム"""
    recommendation_id: str
    table_name: str
    priority: str = Field(description="critical / high / medium / low")
    reason: str
    key_columns: list[str]
    include_columns: list[str] = Field(description="PostgreSQL INCLUDE カラム")
    estimated_scan_ratio: float = Field(description="rows_examined / rows_returned 比率")
    estimated_latency_improvement_pct: float
    estimated_daily_rows_saved: float
    affected_query_count: int
    create_statement_mysql: str
    create_statement_postgresql: str


class IndexAnalysisResponse(BaseModel):
    """POST /rds/{id}/index-analysis レスポンス"""
    instance_id: str
    analyzed_at: datetime
    engine: str
    total_queries_analyzed: int
    queries_already_covered: int
    queries_needing_index: int
    estimated_total_improvement_pct: float
    recommendations: list[CoveringIndexRecommendationResponse]


class StorageProjectionResponse(BaseModel):
    """GET /rds/{id}/storage-projection レスポンス"""
    instance_id: str
    allocated_gb: float
    current_free_gb: float
    current_used_gb: float
    trend_gb_per_day: float
    days_until_full: Optional[float] = None
    projected_full_date: Optional[str] = None
    confidence: str
