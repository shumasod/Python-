"""
RDS コスト分析エンジン

設計意図:
- AWS 公式料金表（ap-northeast-1 東京リージョン）に準拠した計算
- 料金は推定値であり、実際の請求額と異なる場合があります
- 全料金は USD 建て
- gp2 → gp3 移行など具体的な節約額を算出

料金参照: https://aws.amazon.com/rds/mysql/pricing/ (2024年版)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..models.costs import CostBreakdown, CostEfficiencyScore, MonthlyCostReport, CostAnomaly
from ..models.rds import RDSInstance, StorageType, EngineType

logger = logging.getLogger(__name__)

# ============================================================
# 料金定数（ap-northeast-1 東京リージョン、USD/時間 or USD/GB-月）
# 注: 推定値。実際の料金は AWS 公式サイトを参照してください
# ============================================================

# インスタンス時間料金 (On-Demand, Single-AZ, USD/時間)
INSTANCE_HOURLY_RATES: dict[str, float] = {
    # T3 系（バースト可能）
    "db.t3.micro": 0.026,
    "db.t3.small": 0.052,
    "db.t3.medium": 0.104,
    "db.t3.large": 0.208,
    # T4g 系（Graviton2）
    "db.t4g.medium": 0.093,
    "db.t4g.large": 0.187,
    # M5 系（汎用）
    "db.m5.large": 0.214,
    "db.m5.xlarge": 0.428,
    "db.m5.2xlarge": 0.856,
    "db.m5.4xlarge": 1.712,
    # M6g 系（Graviton2 汎用）
    "db.m6g.large": 0.183,
    "db.m6g.xlarge": 0.365,
    "db.m6g.2xlarge": 0.730,
    # R5 系（メモリ最適化）
    "db.r5.large": 0.300,
    "db.r5.xlarge": 0.600,
    "db.r5.2xlarge": 1.200,
    "db.r5.4xlarge": 2.400,
    "db.r5.8xlarge": 4.800,
    # R6g 系（Graviton2 メモリ最適化）
    "db.r6g.large": 0.255,
    "db.r6g.xlarge": 0.510,
    "db.r6g.2xlarge": 1.020,
    "db.r6g.4xlarge": 2.040,
    # Aurora 専用インスタンス
    "db.r6g.large.aurora": 0.255,
    "db.r6g.xlarge.aurora": 0.510,
}

# マルチAZ 料金は Single-AZ の 2倍（スタンバイインスタンス分）
MULTI_AZ_MULTIPLIER = 2.0

# ストレージ料金 (USD/GB-月)
STORAGE_RATES: dict[str, float] = {
    StorageType.GP2: 0.138,   # gp2: $0.138/GB-月
    StorageType.GP3: 0.115,   # gp3: $0.115/GB-月（gp2比 約17%安）
    StorageType.IO1: 0.138,   # io1: $0.138/GB-月 + IOPS料金
    StorageType.MAGNETIC: 0.10,
}

# IOPS 料金 (USD/IOPS-月)
IOPS_RATES: dict[str, float] = {
    StorageType.IO1: 0.111,   # io1: $0.111/IOPS-月
    StorageType.GP3: 0.020,   # gp3: 3000 IOPS まで無料、超過分 $0.020/IOPS-月
}

# GP3 無料 IOPS しきい値
GP3_FREE_IOPS = 3000
GP3_FREE_THROUGHPUT_MBPS = 125

# データ転送料金 (USD/GB)
# 注: AZ内は無料、インターネット向けは段階課金
DATA_TRANSFER_RATES = {
    "internet_first_10tb": 0.114,    # 最初の 10TB/月
    "internet_next_40tb": 0.089,     # 次の 40TB/月
    "internet_next_100tb": 0.086,    # 次の 100TB/月
    "same_region_az_cross": 0.01,    # 同リージョン AZ 間
    "az_internal": 0.00,             # 同 AZ 内
}

# バックアップストレージ料金 (USD/GB-月)
BACKUP_STORAGE_RATE = 0.095  # バックアップストレージ（DB容量超過分）

# Aurora Serverless v2 ACU 料金 (USD/ACU-時間)
AURORA_SERVERLESS_ACU_RATE = 0.12

# インスタンスクラスの vCPU / メモリ仕様
INSTANCE_SPECS: dict[str, dict] = {
    "db.t3.micro":   {"vcpu": 2, "memory_gb": 1},
    "db.t3.small":   {"vcpu": 2, "memory_gb": 2},
    "db.t3.medium":  {"vcpu": 2, "memory_gb": 4},
    "db.t3.large":   {"vcpu": 2, "memory_gb": 8},
    "db.t4g.medium": {"vcpu": 2, "memory_gb": 4},
    "db.t4g.large":  {"vcpu": 2, "memory_gb": 8},
    "db.m5.large":   {"vcpu": 2, "memory_gb": 8},
    "db.m5.xlarge":  {"vcpu": 4, "memory_gb": 16},
    "db.m5.2xlarge": {"vcpu": 8, "memory_gb": 32},
    "db.m5.4xlarge": {"vcpu": 16, "memory_gb": 64},
    "db.m6g.large":  {"vcpu": 2, "memory_gb": 8},
    "db.m6g.xlarge": {"vcpu": 4, "memory_gb": 16},
    "db.m6g.2xlarge":{"vcpu": 8, "memory_gb": 32},
    "db.r5.large":   {"vcpu": 2, "memory_gb": 16},
    "db.r5.xlarge":  {"vcpu": 4, "memory_gb": 32},
    "db.r5.2xlarge": {"vcpu": 8, "memory_gb": 64},
    "db.r5.4xlarge": {"vcpu": 16, "memory_gb": 128},
    "db.r5.8xlarge": {"vcpu": 32, "memory_gb": 256},
    "db.r6g.large":  {"vcpu": 2, "memory_gb": 16},
    "db.r6g.xlarge": {"vcpu": 4, "memory_gb": 32},
    "db.r6g.2xlarge":{"vcpu": 8, "memory_gb": 64},
    "db.r6g.4xlarge":{"vcpu": 16, "memory_gb": 128},
}

# DB エンジンごとの最大接続数目安（memory_gb * 係数）
MAX_CONNECTIONS_FACTOR: dict[str, float] = {
    EngineType.MYSQL: 75,
    EngineType.POSTGRESQL: 100,
    EngineType.AURORA_MYSQL: 90,
    EngineType.AURORA_POSTGRESQL: 100,
    EngineType.MARIADB: 75,
}


@dataclass
class CostComponentDetail:
    """コストコンポーネントの詳細計算結果（デバッグ・監査用）"""
    name: str
    unit_price: float
    quantity: float
    unit: str
    subtotal_usd: float
    notes: str = ""


class CostAnalyzer:
    """
    RDS コスト分析エンジン

    インスタンス設定とメトリクスからコストを算出し、
    最適化可能なコンポーネントを特定する
    """

    def __init__(self, monthly_hours: float = 730.0):
        """
        Args:
            monthly_hours: 月間稼働時間（デフォルト 730h = 24h × 365d / 12）
        """
        self.monthly_hours = monthly_hours

    # ----------------------------------------------------------
    # パブリック API
    # ----------------------------------------------------------

    def calculate_monthly_cost(
        self,
        instance: RDSInstance,
        data_transfer_gb: float = 0.0,
    ) -> tuple[CostBreakdown, list[CostComponentDetail]]:
        """
        月次コストを算出する

        Args:
            instance: RDS インスタンス設定
            data_transfer_gb: 月間データ転送量(GB)（インターネット向け）

        Returns:
            (CostBreakdown, 詳細コンポーネントリスト)
        """
        details: list[CostComponentDetail] = []

        # 1. コンピュートコスト
        compute_cost, compute_detail = self._compute_cost(instance)
        details.extend(compute_detail)

        # 2. リードレプリカコスト
        replica_cost, replica_detail = self._replica_cost(instance)
        details.extend(replica_detail)

        # 3. ストレージコスト
        storage_cost, storage_detail = self._storage_cost(instance)
        details.extend(storage_detail)

        # 4. IOPS コスト
        iops_cost, iops_detail = self._iops_cost(instance)
        details.extend(iops_detail)

        # 5. データ転送コスト
        transfer_cost, transfer_detail = self._transfer_cost(data_transfer_gb)
        details.extend(transfer_detail)

        # 6. バックアップコスト
        backup_cost, backup_detail = self._backup_cost(instance)
        details.extend(backup_detail)

        breakdown = CostBreakdown(
            compute_cost_usd=compute_cost,
            storage_cost_usd=storage_cost,
            iops_cost_usd=iops_cost,
            transfer_cost_usd=transfer_cost,
            backup_cost_usd=backup_cost,
            replica_compute_cost_usd=replica_cost,
        )
        return breakdown, details

    def calculate_efficiency_score(
        self,
        instance: RDSInstance,
        breakdown: CostBreakdown,
        avg_cpu_pct: float,
        avg_iops_used: float,
        storage_used_gb: float,
    ) -> CostEfficiencyScore:
        """
        コスト効率スコアを算出する（0〜100）

        低CPU利用率・IOPS余裕があるほどコスト非効率
        高CPU/IOPS利用率でも適切なインスタンスならスコアは高い
        """
        # CPU 効率スコア（20〜80% 利用が理想）
        cpu_score = self._cpu_efficiency_score(avg_cpu_pct)

        # ストレージ効率スコア（80%以上使用で効率的）
        total_storage = instance.allocated_storage_gb
        storage_utilization = storage_used_gb / total_storage if total_storage > 0 else 0
        storage_score = self._storage_efficiency_score(storage_utilization)

        # IOPS 効率スコア（プロビジョンドIOPS使用率）
        iops_score = self._iops_efficiency_score(instance, avg_iops_used)

        # 加重平均（CPU を重視）
        total_score = int(cpu_score * 0.5 + storage_score * 0.25 + iops_score * 0.25)
        grade = CostEfficiencyScore.grade_from_score(total_score)

        summary = self._generate_efficiency_summary(
            total_score, avg_cpu_pct, storage_utilization, breakdown
        )

        return CostEfficiencyScore(
            instance_id=instance.instance_id,
            score=total_score,
            cpu_efficiency_score=cpu_score,
            storage_efficiency_score=storage_score,
            iops_efficiency_score=iops_score,
            grade=grade,
            summary=summary,
        )

    def detect_cost_anomaly(
        self,
        instance_id: str,
        current_cost: float,
        previous_cost: float,
        threshold_pct: float = 20.0,
    ) -> CostAnomaly:
        """
        前月比コスト異常を検知する

        Args:
            threshold_pct: 異常と判定する変化率しきい値(%)
        """
        if previous_cost == 0:
            change_ratio = 100.0 if current_cost > 0 else 0.0
        else:
            change_ratio = (current_cost - previous_cost) / previous_cost * 100

        is_anomaly = abs(change_ratio) >= threshold_pct

        if change_ratio > threshold_pct:
            anomaly_type = "cost_spike"
            description = f"コストが前月比 {change_ratio:.1f}% 増加しています。スケールアップや予期しないリソース追加の可能性があります。"
        elif change_ratio < -threshold_pct:
            anomaly_type = "cost_drop"
            description = f"コストが前月比 {abs(change_ratio):.1f}% 減少しています。インスタンス停止やスケールダウンを確認してください。"
        else:
            anomaly_type = "normal"
            description = "コストは正常範囲内です。"

        from datetime import date
        return CostAnomaly(
            instance_id=instance_id,
            detected_at=date.today(),
            anomaly_type=anomaly_type,
            current_month_cost_usd=current_cost,
            previous_month_cost_usd=previous_cost,
            change_ratio_pct=change_ratio,
            threshold_pct=threshold_pct,
            is_anomaly=is_anomaly,
            description=description,
        )

    def estimate_gp3_savings(self, instance: RDSInstance) -> float:
        """
        gp2 → gp3 移行による節約額を試算する (USD/月)

        gp3 は gp2 比で約 17% 安くなる（東京リージョン）
        """
        if instance.storage_type != StorageType.GP2:
            return 0.0

        gp2_cost = instance.allocated_storage_gb * STORAGE_RATES[StorageType.GP2]
        # マルチAZ/レプリカ分も考慮
        gp2_cost *= instance.total_storage_instances

        gp3_cost = instance.allocated_storage_gb * STORAGE_RATES[StorageType.GP3]
        gp3_cost *= instance.total_storage_instances

        return gp2_cost - gp3_cost

    def get_instance_specs(self, instance_class: str) -> dict:
        """インスタンスクラスのスペック情報を取得"""
        return INSTANCE_SPECS.get(instance_class, {"vcpu": 0, "memory_gb": 0})

    def get_max_connections(self, instance: RDSInstance) -> int:
        """インスタンスクラスに対する最大接続数の目安を返す"""
        specs = self.get_instance_specs(instance.instance_class)
        memory_gb = specs.get("memory_gb", 4)
        factor = MAX_CONNECTIONS_FACTOR.get(instance.engine, 75)
        # PostgreSQL 系: DBInstanceClassMemory / 9531392 が目安
        # MySQL 系: max_connections はメモリに依存
        return int(memory_gb * factor)

    # ----------------------------------------------------------
    # プライベートメソッド（各コスト計算）
    # ----------------------------------------------------------

    def _compute_cost(
        self, instance: RDSInstance
    ) -> tuple[float, list[CostComponentDetail]]:
        """コンピュートコスト計算"""
        hourly_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0.0)
        if hourly_rate == 0.0:
            logger.warning(
                "インスタンスクラス %s の料金が未定義です。推定値を使用します。",
                instance.instance_class
            )
            hourly_rate = 0.5  # 未知クラスのデフォルト

        multi_az_multiplier = MULTI_AZ_MULTIPLIER if instance.multi_az else 1.0
        monthly_cost = hourly_rate * self.monthly_hours * multi_az_multiplier

        details = [
            CostComponentDetail(
                name="コンピュート（プライマリ）",
                unit_price=hourly_rate,
                quantity=self.monthly_hours,
                unit="時間",
                subtotal_usd=hourly_rate * self.monthly_hours,
                notes=f"インスタンスクラス: {instance.instance_class}",
            )
        ]

        if instance.multi_az:
            details.append(
                CostComponentDetail(
                    name="コンピュート（マルチAZ スタンバイ）",
                    unit_price=hourly_rate,
                    quantity=self.monthly_hours,
                    unit="時間",
                    subtotal_usd=hourly_rate * self.monthly_hours,
                    notes="マルチAZ スタンバイインスタンス分",
                )
            )

        return monthly_cost, details

    def _replica_cost(
        self, instance: RDSInstance
    ) -> tuple[float, list[CostComponentDetail]]:
        """リードレプリカコスト計算"""
        if instance.read_replica_count == 0:
            return 0.0, []

        hourly_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0.5)
        replica_cost = hourly_rate * self.monthly_hours * instance.read_replica_count

        details = [
            CostComponentDetail(
                name=f"リードレプリカ x{instance.read_replica_count}",
                unit_price=hourly_rate,
                quantity=self.monthly_hours * instance.read_replica_count,
                unit="時間",
                subtotal_usd=replica_cost,
                notes="リードレプリカはプライマリと同率で課金",
            )
        ]
        return replica_cost, details

    def _storage_cost(
        self, instance: RDSInstance
    ) -> tuple[float, list[CostComponentDetail]]:
        """ストレージコスト計算"""
        rate_per_gb = STORAGE_RATES.get(instance.storage_type, 0.138)
        # マルチAZ では 2 倍のストレージ、レプリカ分も加算
        total_storage = instance.allocated_storage_gb * instance.total_storage_instances
        monthly_cost = total_storage * rate_per_gb

        details = [
            CostComponentDetail(
                name=f"ストレージ ({instance.storage_type})",
                unit_price=rate_per_gb,
                quantity=total_storage,
                unit="GB-月",
                subtotal_usd=monthly_cost,
                notes=(
                    f"マルチAZ: {instance.multi_az}, "
                    f"レプリカ数: {instance.read_replica_count}, "
                    f"合計 {total_storage}GB"
                ),
            )
        ]
        return monthly_cost, details

    def _iops_cost(
        self, instance: RDSInstance
    ) -> tuple[float, list[CostComponentDetail]]:
        """プロビジョンドIOPS コスト計算"""
        if instance.storage_type == StorageType.IO1:
            if not instance.provisioned_iops:
                return 0.0, []
            rate = IOPS_RATES[StorageType.IO1]
            cost = instance.provisioned_iops * rate * instance.total_storage_instances
            return cost, [
                CostComponentDetail(
                    name="プロビジョンドIOPS (io1)",
                    unit_price=rate,
                    quantity=instance.provisioned_iops * instance.total_storage_instances,
                    unit="IOPS-月",
                    subtotal_usd=cost,
                    notes=f"設定IOPS: {instance.provisioned_iops}",
                )
            ]

        elif instance.storage_type == StorageType.GP3:
            if not instance.provisioned_iops or instance.provisioned_iops <= GP3_FREE_IOPS:
                return 0.0, []
            # 3000 IOPS 超過分のみ課金
            billable_iops = instance.provisioned_iops - GP3_FREE_IOPS
            rate = IOPS_RATES[StorageType.GP3]
            cost = billable_iops * rate * instance.total_storage_instances
            return cost, [
                CostComponentDetail(
                    name="プロビジョンドIOPS超過分 (gp3)",
                    unit_price=rate,
                    quantity=billable_iops * instance.total_storage_instances,
                    unit="IOPS-月",
                    subtotal_usd=cost,
                    notes=f"設定IOPS: {instance.provisioned_iops} (3000 IOPS 無料枠超過分)",
                )
            ]

        return 0.0, []

    def _transfer_cost(
        self, data_transfer_gb: float
    ) -> tuple[float, list[CostComponentDetail]]:
        """データ転送コスト計算（インターネット向け）"""
        if data_transfer_gb <= 0:
            return 0.0, []

        cost = 0.0
        remaining = data_transfer_gb

        # 段階課金の計算
        tiers = [
            (10 * 1024, DATA_TRANSFER_RATES["internet_first_10tb"]),    # 〜10TB
            (40 * 1024, DATA_TRANSFER_RATES["internet_next_40tb"]),      # 〜50TB
            (100 * 1024, DATA_TRANSFER_RATES["internet_next_100tb"]),    # 〜150TB
        ]

        for tier_gb, rate in tiers:
            if remaining <= 0:
                break
            chunk = min(remaining, tier_gb)
            cost += chunk * rate
            remaining -= chunk

        if remaining > 0:
            cost += remaining * DATA_TRANSFER_RATES["internet_next_100tb"]

        return cost, [
            CostComponentDetail(
                name="データ転送（インターネット向け）",
                unit_price=DATA_TRANSFER_RATES["internet_first_10tb"],
                quantity=data_transfer_gb,
                unit="GB",
                subtotal_usd=cost,
                notes="段階課金適用",
            )
        ]

    def _backup_cost(
        self, instance: RDSInstance
    ) -> tuple[float, list[CostComponentDetail]]:
        """バックアップストレージコスト計算"""
        if instance.snapshot_storage_gb <= instance.allocated_storage_gb:
            # 割り当てストレージ以下のバックアップは無料
            return 0.0, []

        billable_backup_gb = instance.snapshot_storage_gb - instance.allocated_storage_gb
        cost = billable_backup_gb * BACKUP_STORAGE_RATE

        return cost, [
            CostComponentDetail(
                name="バックアップストレージ",
                unit_price=BACKUP_STORAGE_RATE,
                quantity=billable_backup_gb,
                unit="GB-月",
                subtotal_usd=cost,
                notes=f"割り当て容量 {instance.allocated_storage_gb}GB 超過分のみ課金",
            )
        ]

    # ----------------------------------------------------------
    # スコア算出ヘルパー
    # ----------------------------------------------------------

    @staticmethod
    def _cpu_efficiency_score(avg_cpu_pct: float) -> int:
        """
        CPU使用率からコスト効率スコアを算出

        20〜80% が理想的な利用率範囲
        低すぎると過剰スペック（コスト無駄）
        高すぎるとパフォーマンス問題のリスク
        """
        if 20 <= avg_cpu_pct <= 80:
            # 理想範囲内: 線形スコアリング（50%使用率が最高スコア）
            score = 100 - abs(avg_cpu_pct - 50) * 0.8
        elif avg_cpu_pct < 20:
            # 低使用率: 過剰スペックの可能性
            score = avg_cpu_pct * 2.5  # 0% → 0点、20% → 50点
        else:
            # 高使用率 (>80%): ボトルネックリスク
            score = max(0, 100 - (avg_cpu_pct - 80) * 3)
        return max(0, min(100, int(score)))

    @staticmethod
    def _storage_efficiency_score(utilization_ratio: float) -> int:
        """
        ストレージ使用率からコスト効率スコアを算出

        70%以上の使用率が理想
        低使用率はオーバープロビジョニング
        """
        if utilization_ratio >= 0.9:
            return 90  # 高使用率（容量逼迫リスクを若干ペナルティ）
        elif utilization_ratio >= 0.7:
            return 100
        elif utilization_ratio >= 0.5:
            return 80
        elif utilization_ratio >= 0.3:
            return 60
        else:
            return max(0, int(utilization_ratio * 100))

    @staticmethod
    def _iops_efficiency_score(instance: RDSInstance, avg_iops_used: float) -> int:
        """
        IOPS使用効率スコア

        プロビジョンドIOPSが設定されている場合のみ評価
        """
        if instance.storage_type in (StorageType.GP2, StorageType.MAGNETIC):
            return 80  # gp2 は最大IOPS が容量依存のため中間スコア

        if not instance.provisioned_iops:
            return 80

        utilization = avg_iops_used / instance.provisioned_iops
        if utilization >= 0.7:
            return 100
        elif utilization >= 0.5:
            return 80
        elif utilization >= 0.3:
            return 60
        else:
            return max(20, int(utilization * 100))

    @staticmethod
    def _generate_efficiency_summary(
        score: int,
        avg_cpu_pct: float,
        storage_utilization: float,
        breakdown: CostBreakdown,
    ) -> str:
        """スコアサマリーコメントを生成"""
        if score >= 90:
            return "コスト効率は優秀です。現在の設定は最適に近い状態です。"
        elif score >= 75:
            return f"コスト効率は良好です。CPU使用率 {avg_cpu_pct:.0f}%、ストレージ使用率 {storage_utilization*100:.0f}%。"
        elif score >= 60:
            concerns = []
            if avg_cpu_pct < 20:
                concerns.append(f"CPU使用率が低い({avg_cpu_pct:.0f}%) - スケールダウンを検討")
            if storage_utilization < 0.5:
                concerns.append(f"ストレージ使用率が低い({storage_utilization*100:.0f}%)")
            return "改善の余地があります: " + "、".join(concerns)
        else:
            return (
                f"コスト効率が低い状態です。"
                f"CPU使用率 {avg_cpu_pct:.0f}%、月次コスト ${breakdown.total_cost_usd:.2f}。"
                "インスタンスサイズの見直しを強く推奨します。"
            )
