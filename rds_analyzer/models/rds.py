"""
RDS インスタンス データモデル

設計意図:
- AWS RDS の全設定パラメータを網羅
- Pydantic による型安全なバリデーション
- Aurora Serverless v2 の ACU ベース設定にも対応
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EngineType(str, Enum):
    """RDS エンジン種別"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    AURORA_MYSQL = "aurora-mysql"
    AURORA_POSTGRESQL = "aurora-postgresql"
    MARIADB = "mariadb"
    ORACLE = "oracle-ee"
    SQLSERVER = "sqlserver-ee"


class StorageType(str, Enum):
    """ストレージタイプ（AWS課金区分に対応）"""
    GP2 = "gp2"    # 汎用SSD 旧世代
    GP3 = "gp3"    # 汎用SSD 新世代（gp2より20%安価）
    IO1 = "io1"    # プロビジョンドIOPS SSD
    MAGNETIC = "standard"  # マグネティック（レガシー）


class InstanceClass(str, Enum):
    """RDS インスタンスクラス（主要クラスのみ）"""
    # バースト可能
    T3_MICRO = "db.t3.micro"
    T3_SMALL = "db.t3.small"
    T3_MEDIUM = "db.t3.medium"
    T3_LARGE = "db.t3.large"
    T4G_MEDIUM = "db.t4g.medium"
    T4G_LARGE = "db.t4g.large"
    # 汎用
    M5_LARGE = "db.m5.large"
    M5_XLARGE = "db.m5.xlarge"
    M5_2XLARGE = "db.m5.2xlarge"
    M5_4XLARGE = "db.m5.4xlarge"
    M6G_LARGE = "db.m6g.large"
    M6G_XLARGE = "db.m6g.xlarge"
    M6G_2XLARGE = "db.m6g.2xlarge"
    # メモリ最適化
    R5_LARGE = "db.r5.large"
    R5_XLARGE = "db.r5.xlarge"
    R5_2XLARGE = "db.r5.2xlarge"
    R5_4XLARGE = "db.r5.4xlarge"
    R6G_LARGE = "db.r6g.large"
    R6G_XLARGE = "db.r6g.xlarge"
    R6G_2XLARGE = "db.r6g.2xlarge"


class MultiAZConfig(str, Enum):
    """マルチAZ設定"""
    SINGLE_AZ = "single-az"
    MULTI_AZ = "multi-az"
    MULTI_AZ_CLUSTER = "multi-az-cluster"  # Aurora クラスター


class AuroraServerlessConfig(BaseModel):
    """Aurora Serverless v2 設定"""
    min_acu: float = Field(ge=0.5, le=128.0, description="最小 ACU (Aurora Capacity Unit)")
    max_acu: float = Field(ge=1.0, le=128.0, description="最大 ACU")

    @field_validator("max_acu")
    @classmethod
    def max_must_exceed_min(cls, v: float, info) -> float:
        if "min_acu" in info.data and v <= info.data["min_acu"]:
            raise ValueError("max_acu は min_acu より大きい必要があります")
        return v


class RDSInstance(BaseModel):
    """
    RDS インスタンス設定モデル

    CloudWatch / Cost Explorer から取得する情報と
    手動設定情報を統合した中心データモデル
    """
    # 識別情報
    instance_id: str = Field(description="RDS インスタンス識別子")
    db_name: Optional[str] = Field(default=None, description="データベース名")
    engine: EngineType = Field(description="DBエンジン種別")
    engine_version: str = Field(description="エンジンバージョン")
    region: str = Field(default="ap-northeast-1", description="AWSリージョン")

    # インスタンス設定
    instance_class: str = Field(description="インスタンスクラス（db.r5.large等）")
    multi_az: bool = Field(default=False, description="マルチAZ有効フラグ")
    multi_az_config: MultiAZConfig = Field(
        default=MultiAZConfig.SINGLE_AZ,
        description="マルチAZ構成種別"
    )

    # ストレージ設定
    storage_type: StorageType = Field(description="ストレージタイプ")
    allocated_storage_gb: int = Field(ge=20, description="割り当てストレージ容量(GB)")
    provisioned_iops: Optional[int] = Field(
        default=None,
        description="プロビジョンドIOPS(io1/gp3のみ)"
    )

    # レプリカ設定
    read_replica_count: int = Field(default=0, ge=0, le=5, description="リードレプリカ数")

    # バックアップ設定
    backup_retention_days: int = Field(default=7, ge=0, le=35, description="自動バックアップ保持日数")
    snapshot_storage_gb: float = Field(default=0.0, ge=0, description="スナップショット容量(GB)")

    # Aurora Serverless 設定（Auroraの場合のみ有効）
    serverless_config: Optional[AuroraServerlessConfig] = Field(
        default=None,
        description="Aurora Serverless v2 設定"
    )

    # 運用情報
    created_at: Optional[datetime] = Field(default=None, description="インスタンス作成日時")
    monthly_uptime_hours: float = Field(
        default=730.0,
        description="月間稼働時間（730h = 24h × 365d / 12）"
    )

    # タグ
    tags: dict[str, str] = Field(default_factory=dict, description="AWSタグ")

    @property
    def is_aurora(self) -> bool:
        """Aurora エンジンかどうか"""
        return self.engine in (EngineType.AURORA_MYSQL, EngineType.AURORA_POSTGRESQL)

    @property
    def is_serverless(self) -> bool:
        """Aurora Serverless かどうか"""
        return self.is_aurora and self.serverless_config is not None

    @property
    def total_storage_instances(self) -> int:
        """ストレージ課金対象インスタンス数（マルチAZは2倍）"""
        base = 2 if self.multi_az else 1
        return base + self.read_replica_count
