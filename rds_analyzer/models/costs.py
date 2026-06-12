"""
コスト データモデル

設計意図:
- AWS料金体系の全コンポーネントを網羅
- 月次/日次コストの両方に対応
- 前月比異常検知のための履歴保持
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class CostBreakdown(BaseModel):
    """
    コスト内訳モデル

    RDS の主要4コストコンポーネントを分離して保持
    AWS Cost Explorer の category に対応
    """
    # コンピュートコスト（インスタンス時間課金）
    compute_cost_usd: float = Field(ge=0.0, description="コンピュートコスト(USD)")

    # ストレージコスト
    storage_cost_usd: float = Field(ge=0.0, description="ストレージコスト(USD)")

    # IOPS コスト（io1 / gp3 のプロビジョンドIOPS分）
    iops_cost_usd: float = Field(default=0.0, ge=0.0, description="IOPSコスト(USD)")

    # データ転送コスト
    transfer_cost_usd: float = Field(default=0.0, ge=0.0, description="データ転送コスト(USD)")

    # バックアップ/スナップショットコスト
    backup_cost_usd: float = Field(default=0.0, ge=0.0, description="バックアップコスト(USD)")

    # リードレプリカコスト（含む場合）
    replica_compute_cost_usd: float = Field(default=0.0, ge=0.0, description="レプリカコンピュートコスト(USD)")

    @property
    def total_cost_usd(self) -> float:
        """合計コスト(USD)"""
        return (
            self.compute_cost_usd
            + self.storage_cost_usd
            + self.iops_cost_usd
            + self.transfer_cost_usd
            + self.backup_cost_usd
            + self.replica_compute_cost_usd
        )

    @property
    def compute_ratio_pct(self) -> float:
        """コンピュートコスト比率(%)"""
        if self.total_cost_usd == 0:
            return 0.0
        return (self.compute_cost_usd + self.replica_compute_cost_usd) / self.total_cost_usd * 100

    @property
    def storage_ratio_pct(self) -> float:
        """ストレージ+IOPSコスト比率(%)"""
        if self.total_cost_usd == 0:
            return 0.0
        return (self.storage_cost_usd + self.iops_cost_usd) / self.total_cost_usd * 100


class MonthlyCostReport(BaseModel):
    """
    月次コストレポート

    1インスタンスの1ヶ月分コストレポート
    """
    instance_id: str
    month: date = Field(description="対象月（YYYY-MM-01形式）")
    breakdown: CostBreakdown
    currency: str = Field(default="USD")

    # 最適化後の推定コスト
    optimized_cost_usd: Optional[float] = Field(
        default=None,
        description="推奨設定適用後の推定月次コスト(USD)"
    )

    @property
    def potential_savings_usd(self) -> float:
        """推定節約額(USD/月)"""
        if self.optimized_cost_usd is None:
            return 0.0
        return max(0.0, self.breakdown.total_cost_usd - self.optimized_cost_usd)

    @property
    def savings_ratio_pct(self) -> float:
        """節約率(%)"""
        if self.breakdown.total_cost_usd == 0:
            return 0.0
        return self.potential_savings_usd / self.breakdown.total_cost_usd * 100


class CostAnomaly(BaseModel):
    """
    コスト異常検知結果

    前月比または移動平均からの逸脱を表現
    """
    instance_id: str
    detected_at: date
    anomaly_type: str = Field(description="異常種別（突然の増加/急な減少等）")

    current_month_cost_usd: float
    previous_month_cost_usd: float
    change_ratio_pct: float = Field(description="前月比変化率(%)")

    # 異常と判定した閾値
    threshold_pct: float = Field(description="異常判定閾値(%)")
    is_anomaly: bool

    description: str = Field(description="異常内容の説明")


class CostEfficiencyScore(BaseModel):
    """
    コスト効率スコア

    リソース使用率とコストのバランスを0〜100で評価
    """
    instance_id: str
    score: int = Field(ge=0, le=100, description="コスト効率スコア(0〜100)")

    # スコア算出根拠
    cpu_efficiency_score: int = Field(ge=0, le=100, description="CPU効率スコア")
    storage_efficiency_score: int = Field(ge=0, le=100, description="ストレージ効率スコア")
    iops_efficiency_score: int = Field(ge=0, le=100, description="IOPS効率スコア")

    # スコア解釈
    grade: str = Field(description="スコアグレード(A/B/C/D/F)")
    summary: str = Field(description="スコアのサマリーコメント")

    @classmethod
    def grade_from_score(cls, score: int) -> str:
        """スコアからグレードを算出"""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"
