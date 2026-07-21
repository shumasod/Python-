"""
インデックス分析データモデル

カバリングインデックス分析のための入力・出力モデル定義
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QueryPattern(BaseModel):
    """クエリパターン（カバリングインデックス分析の入力単位）"""

    query_id: str = Field(default="", description="クエリ識別子")
    table_name: str = Field(description="対象テーブル名")
    schema_name: str = Field(default="public", description="スキーマ名 (PostgreSQL)")

    # カラム使用状況
    filter_columns: list[str] = Field(
        default_factory=list,
        description="WHERE/JOIN 条件で使用するカラム (インデックスキー候補)",
    )
    sort_columns: list[str] = Field(
        default_factory=list,
        description="ORDER BY で使用するカラム",
    )
    group_columns: list[str] = Field(
        default_factory=list,
        description="GROUP BY で使用するカラム",
    )
    select_columns: list[str] = Field(
        default_factory=list,
        description="SELECT で取得するカラム (空 = SELECT *、判定不能)",
    )

    # クエリ統計
    execution_count_per_day: float = Field(default=0, ge=0, description="1日あたりの実行回数")
    avg_rows_examined: float = Field(default=0, ge=0, description="平均スキャン行数")
    avg_rows_returned: float = Field(default=1, ge=1, description="平均返却行数")
    avg_latency_ms: float = Field(default=0, ge=0, description="平均実行時間 (ms)")

    query_text: Optional[str] = Field(default=None, description="クエリ文字列 (参考情報)")


class ExistingIndex(BaseModel):
    """既存インデックス情報"""

    index_name: str
    table_name: str
    key_columns: list[str] = Field(description="インデックスキーカラム (順序通り)")
    include_columns: list[str] = Field(
        default_factory=list,
        description="INCLUDE カラム (PostgreSQL 11+ / SQL Server)",
    )
    is_unique: bool = False
    index_type: str = Field(default="BTREE", description="BTREE / HASH / GIN / GiST")


class IndexAnalysisRequest(BaseModel):
    """カバリングインデックス分析リクエスト"""

    instance_id: str
    engine: str = Field(description="mysql / mariadb / postgresql")
    queries: list[QueryPattern]
    existing_indexes: list[ExistingIndex] = Field(default_factory=list)


class CoveringIndexRecommendation(BaseModel):
    """カバリングインデックス推奨"""

    recommendation_id: str
    table_name: str
    key_columns: list[str] = Field(description="インデックスキーカラム")
    include_columns: list[str] = Field(
        default_factory=list,
        description="PostgreSQL INCLUDE カラム (非キー列)",
    )

    priority: str = Field(description="critical / high / medium / low")
    reason: str
    affected_query_ids: list[str] = Field(default_factory=list)

    estimated_scan_ratio: float = Field(
        description="改善前の rows_examined / rows_returned 比率"
    )
    estimated_latency_improvement_pct: float
    estimated_daily_rows_saved: float

    create_statement_mysql: str = Field(description="MySQL/MariaDB 用 CREATE INDEX 文")
    create_statement_postgresql: str = Field(description="PostgreSQL 用 CREATE INDEX 文")


class IndexAnalysisResult(BaseModel):
    """カバリングインデックス分析結果"""

    instance_id: str
    analyzed_at: datetime
    engine: str

    total_queries_analyzed: int
    queries_already_covered: int
    queries_needing_index: int

    recommendations: list[CoveringIndexRecommendation]

    estimated_total_improvement_pct: float = Field(
        description="推奨インデックス適用後の推定改善効果 (%)"
    )
