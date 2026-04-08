"""
RDS 改善提案エンジン

設計意図:
- パフォーマンス分析結果とコスト情報を組み合わせ、具体的な改善提案を生成
- 提案は優先度付き（CRITICAL/HIGH/MEDIUM/LOW）
- 節約額・改善効果の定量的な見積もりを付与
- AWS ベストプラクティスに準拠した提案内容

提案カテゴリ:
1. インスタンスサイズ変更（スケールアップ/ダウン）
2. ストレージタイプ変更（gp2→gp3）
3. リードレプリカ追加（読み取り負荷分散）
4. Aurora への移行
5. Aurora Serverless 化
6. マルチAZ 有効化（可用性向上）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..models.costs import CostBreakdown
from ..models.metrics import PerformanceAnalysisResult, PerformanceStatus
from ..models.rds import EngineType, InstanceClass, RDSInstance, StorageType
from .cost_analyzer import CostAnalyzer, INSTANCE_HOURLY_RATES, INSTANCE_SPECS

logger = logging.getLogger(__name__)


class RecommendationPriority(str, Enum):
    """提案優先度"""
    CRITICAL = "critical"   # 即時対応が必要
    HIGH = "high"           # 早急に対応推奨
    MEDIUM = "medium"       # 計画的な対応を推奨
    LOW = "low"             # 余裕のある対応でよい


class RecommendationType(str, Enum):
    """提案種別"""
    SCALE_UP = "scale_up"                         # スケールアップ
    SCALE_DOWN = "scale_down"                     # スケールダウン
    STORAGE_TYPE_CHANGE = "storage_type_change"   # ストレージタイプ変更
    ADD_READ_REPLICA = "add_read_replica"          # リードレプリカ追加
    AURORA_MIGRATION = "aurora_migration"          # Aurora 移行
    AURORA_SERVERLESS = "aurora_serverless"        # Aurora Serverless 化
    ENABLE_MULTI_AZ = "enable_multi_az"           # マルチAZ 有効化
    OPTIMIZE_BACKUP = "optimize_backup"            # バックアップ設定最適化
    UPGRADE_GRAVITON = "upgrade_graviton"          # Graviton インスタンスへ移行
    REDUCE_CONNECTIONS = "reduce_connections"      # コネクション削減（PgBouncer等）


@dataclass
class Recommendation:
    """
    改善提案

    一つの改善アクションを表現するデータクラス
    """
    recommendation_id: str
    type: RecommendationType
    priority: RecommendationPriority
    title: str
    description: str

    # 現在の設定
    current_config: str

    # 推奨設定
    recommended_config: str

    # 定量的な効果
    estimated_monthly_savings_usd: float = 0.0
    estimated_performance_improvement_pct: float = 0.0

    # 実装難易度（1: 簡単〜5: 複雑）
    implementation_complexity: int = 2

    # 実装手順
    action_steps: list[str] = field(default_factory=list)

    # 参考リンク
    reference_url: str = ""

    @property
    def impact_summary(self) -> str:
        """インパクトサマリー文字列"""
        parts = []
        if self.estimated_monthly_savings_usd > 0:
            parts.append(f"月額 ${self.estimated_monthly_savings_usd:.1f} 削減")
        if self.estimated_performance_improvement_pct > 0:
            parts.append(f"パフォーマンス {self.estimated_performance_improvement_pct:.0f}% 改善見込み")
        return " / ".join(parts) if parts else "コスト・パフォーマンス最適化"


class RecommendationEngine:
    """
    RDS 改善提案生成エンジン

    パフォーマンス分析結果とコスト情報から
    優先度付きの改善提案リストを生成する
    """

    # インスタンスサイズのアップグレードマップ（同系列）
    _SCALE_UP_MAP: dict[str, str] = {
        "db.t3.micro":   "db.t3.small",
        "db.t3.small":   "db.t3.medium",
        "db.t3.medium":  "db.t3.large",
        "db.t3.large":   "db.m5.large",
        "db.t4g.medium": "db.t4g.large",
        "db.t4g.large":  "db.m6g.large",
        "db.m5.large":   "db.m5.xlarge",
        "db.m5.xlarge":  "db.m5.2xlarge",
        "db.m5.2xlarge": "db.m5.4xlarge",
        "db.r5.large":   "db.r5.xlarge",
        "db.r5.xlarge":  "db.r5.2xlarge",
        "db.r5.2xlarge": "db.r5.4xlarge",
    }

    # インスタンスサイズのダウングレードマップ
    _SCALE_DOWN_MAP: dict[str, str] = {v: k for k, v in _SCALE_UP_MAP.items()}

    # Graviton 移行マップ（x86 → Graviton2）
    _GRAVITON_MAP: dict[str, str] = {
        "db.t3.medium":  "db.t4g.medium",
        "db.t3.large":   "db.t4g.large",
        "db.m5.large":   "db.m6g.large",
        "db.m5.xlarge":  "db.m6g.xlarge",
        "db.m5.2xlarge": "db.m6g.2xlarge",
        "db.r5.large":   "db.r6g.large",
        "db.r5.xlarge":  "db.r6g.xlarge",
        "db.r5.2xlarge": "db.r6g.2xlarge",
        "db.r5.4xlarge": "db.r6g.4xlarge",
    }

    def __init__(self):
        self._cost_analyzer = CostAnalyzer()
        self._recommendation_counter = 0

    # ----------------------------------------------------------
    # パブリック API
    # ----------------------------------------------------------

    def generate_recommendations(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
        cost_breakdown: CostBreakdown,
    ) -> list[Recommendation]:
        """
        改善提案リストを生成する

        Args:
            instance: RDS インスタンス設定
            performance: パフォーマンス分析結果
            cost_breakdown: 現在の月次コスト内訳

        Returns:
            優先度順にソートされた改善提案リスト
        """
        recommendations: list[Recommendation] = []
        self._recommendation_counter = 0

        # 1. CPU ボトルネック対策
        if performance.cpu_bottleneck_detected:
            rec = self._recommend_scale_up(instance, performance, cost_breakdown)
            if rec:
                recommendations.append(rec)

        # 2. メモリ不足対策
        if performance.memory_pressure_detected:
            rec = self._recommend_memory_scale_up(instance, performance, cost_breakdown)
            if rec:
                recommendations.append(rec)

        # 3. 低CPU → スケールダウン
        if not performance.cpu_bottleneck_detected and performance.cpu_avg_pct < 20:
            rec = self._recommend_scale_down(instance, performance, cost_breakdown)
            if rec:
                recommendations.append(rec)

        # 4. gp2 → gp3 ストレージ移行
        if instance.storage_type == StorageType.GP2:
            rec = self._recommend_gp3_migration(instance, cost_breakdown)
            recommendations.append(rec)

        # 5. I/O ボトルネック → リードレプリカ追加
        if performance.io_bottleneck_detected and instance.read_replica_count == 0:
            rec = self._recommend_read_replica(instance, performance, cost_breakdown)
            recommendations.append(rec)

        # 6. コネクション過多 → コネクションプール
        if performance.connection_bottleneck_detected:
            rec = self._recommend_connection_pooling(instance, performance)
            recommendations.append(rec)

        # 7. Aurora 移行提案（高負荷または高可用性が必要な場合）
        if self._should_recommend_aurora(instance, performance):
            rec = self._recommend_aurora_migration(instance, performance, cost_breakdown)
            recommendations.append(rec)

        # 8. Aurora Serverless 提案（低負荷・断続的ワークロード）
        if self._should_recommend_serverless(instance, performance):
            rec = self._recommend_aurora_serverless(instance, cost_breakdown)
            recommendations.append(rec)

        # 9. Graviton インスタンス移行
        graviton_rec = self._recommend_graviton(instance, cost_breakdown)
        if graviton_rec:
            recommendations.append(graviton_rec)

        # 10. マルチAZ 推奨（本番環境で未設定の場合）
        if not instance.multi_az:
            rec = self._recommend_multi_az(instance, cost_breakdown)
            recommendations.append(rec)

        # 優先度順（CRITICAL > HIGH > MEDIUM > LOW）でソート
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        recommendations.sort(key=lambda r: (priority_order[r.priority], -r.estimated_monthly_savings_usd))

        return recommendations

    # ----------------------------------------------------------
    # 個別提案生成メソッド
    # ----------------------------------------------------------

    def _recommend_scale_up(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
        cost_breakdown: CostBreakdown,
    ) -> Optional[Recommendation]:
        """CPU/メモリボトルネックに対するスケールアップ提案"""
        next_class = self._SCALE_UP_MAP.get(instance.instance_class)
        if not next_class:
            logger.warning("スケールアップ先が見つかりません: %s", instance.instance_class)
            return None

        current_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0)
        next_rate = INSTANCE_HOURLY_RATES.get(next_class, 0)
        additional_cost = (next_rate - current_rate) * 730

        current_specs = INSTANCE_SPECS.get(instance.instance_class, {})
        next_specs = INSTANCE_SPECS.get(next_class, {})

        priority = (
            RecommendationPriority.CRITICAL
            if performance.cpu_status == PerformanceStatus.CRITICAL
            else RecommendationPriority.HIGH
        )

        return Recommendation(
            recommendation_id=self._next_id("scale_up"),
            type=RecommendationType.SCALE_UP,
            priority=priority,
            title=f"インスタンスタイプをアップグレード: {instance.instance_class} → {next_class}",
            description=(
                f"CPU使用率が平均 {performance.cpu_avg_pct:.1f}%（最大 {performance.cpu_max_pct:.1f}%）"
                "に達しています。インスタンスをアップグレードしてパフォーマンスを改善してください。"
            ),
            current_config=f"{instance.instance_class} ({current_specs.get('vcpu', '?')}vCPU / {current_specs.get('memory_gb', '?')}GB RAM)",
            recommended_config=f"{next_class} ({next_specs.get('vcpu', '?')}vCPU / {next_specs.get('memory_gb', '?')}GB RAM)",
            estimated_monthly_savings_usd=-additional_cost,  # コスト増加
            estimated_performance_improvement_pct=40.0,
            implementation_complexity=2,
            action_steps=[
                "メンテナンスウィンドウを設定する",
                f"AWS コンソール または CLI でインスタンスクラスを {next_class} に変更",
                "apply immediately または次のメンテナンスウィンドウを選択",
                "変更後の CPU 使用率を CloudWatch で確認",
            ],
            reference_url="https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html",
        )

    def _recommend_memory_scale_up(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
        cost_breakdown: CostBreakdown,
    ) -> Optional[Recommendation]:
        """メモリ不足に対するR系インスタンスへの移行提案"""
        # メモリ最適化インスタンスへの移行を提案
        current_specs = INSTANCE_SPECS.get(instance.instance_class, {})
        current_memory = current_specs.get("memory_gb", 0)

        # R5/R6g 系への移行を推奨
        r_class_map = {
            "db.t3.large":   "db.r5.large",
            "db.m5.large":   "db.r5.large",
            "db.m5.xlarge":  "db.r5.xlarge",
            "db.m5.2xlarge": "db.r5.2xlarge",
            "db.m6g.large":  "db.r6g.large",
            "db.m6g.xlarge": "db.r6g.xlarge",
        }

        recommended_class = r_class_map.get(instance.instance_class)
        if not recommended_class:
            recommended_class = self._SCALE_UP_MAP.get(instance.instance_class, instance.instance_class)

        next_specs = INSTANCE_SPECS.get(recommended_class, {})
        current_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0)
        next_rate = INSTANCE_HOURLY_RATES.get(recommended_class, 0)
        additional_cost = (next_rate - current_rate) * 730

        priority = (
            RecommendationPriority.CRITICAL
            if performance.memory_status == PerformanceStatus.CRITICAL
            else RecommendationPriority.HIGH
        )

        return Recommendation(
            recommendation_id=self._next_id("memory"),
            type=RecommendationType.SCALE_UP,
            priority=priority,
            title=f"メモリ最適化インスタンスへ移行: {instance.instance_class} → {recommended_class}",
            description=(
                f"空きメモリが {performance.freeable_memory_avg_gb:.1f}GB と少ない状態です。"
                "メモリ最適化インスタンス(R系)への移行でスワップを解消できます。"
            ),
            current_config=f"{instance.instance_class} (メモリ {current_memory}GB)",
            recommended_config=f"{recommended_class} (メモリ {next_specs.get('memory_gb', '?')}GB)",
            estimated_monthly_savings_usd=-additional_cost,
            estimated_performance_improvement_pct=30.0,
            implementation_complexity=2,
            action_steps=[
                "現在のメモリ使用量のピーク時間帯を CloudWatch で特定",
                f"インスタンスクラスを {recommended_class} に変更",
                "innodb_buffer_pool_size (MySQL) または shared_buffers (PostgreSQL) を調整",
                "変更後の FreeableMemory を監視",
            ],
        )

    def _recommend_scale_down(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
        cost_breakdown: CostBreakdown,
    ) -> Optional[Recommendation]:
        """低使用率インスタンスのスケールダウン提案"""
        smaller_class = self._SCALE_DOWN_MAP.get(instance.instance_class)
        if not smaller_class:
            return None

        current_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0)
        smaller_rate = INSTANCE_HOURLY_RATES.get(smaller_class, 0)
        monthly_savings = (current_rate - smaller_rate) * 730

        if instance.multi_az:
            monthly_savings *= 2  # マルチAZ は 2 倍節約

        current_specs = INSTANCE_SPECS.get(instance.instance_class, {})
        smaller_specs = INSTANCE_SPECS.get(smaller_class, {})

        return Recommendation(
            recommendation_id=self._next_id("scale_down"),
            type=RecommendationType.SCALE_DOWN,
            priority=RecommendationPriority.MEDIUM,
            title=f"インスタンスをダウングレード: {instance.instance_class} → {smaller_class}",
            description=(
                f"CPU使用率が平均 {performance.cpu_avg_pct:.1f}% と低い状態が続いています。"
                f"小さいインスタンスクラスに変更することで月額 ${monthly_savings:.0f} の削減が見込めます。"
            ),
            current_config=f"{instance.instance_class} ({current_specs.get('vcpu', '?')}vCPU / {current_specs.get('memory_gb', '?')}GB RAM)",
            recommended_config=f"{smaller_class} ({smaller_specs.get('vcpu', '?')}vCPU / {smaller_specs.get('memory_gb', '?')}GB RAM)",
            estimated_monthly_savings_usd=monthly_savings,
            estimated_performance_improvement_pct=0.0,
            implementation_complexity=2,
            action_steps=[
                "過去 4 週間の CPU/メモリ使用率の推移を確認",
                "ピーク時間帯でも余裕があることを確認",
                f"インスタンスクラスを {smaller_class} に変更（次のメンテナンスウィンドウで適用）",
                "変更後のパフォーマンスを 1 週間モニタリング",
            ],
        )

    def _recommend_gp3_migration(
        self,
        instance: RDSInstance,
        cost_breakdown: CostBreakdown,
    ) -> Recommendation:
        """gp2 → gp3 ストレージ移行提案"""
        monthly_savings = self._cost_analyzer.estimate_gp3_savings(instance)

        return Recommendation(
            recommendation_id=self._next_id("gp3"),
            type=RecommendationType.STORAGE_TYPE_CHANGE,
            priority=RecommendationPriority.HIGH,
            title="ストレージを gp2 から gp3 にアップグレード",
            description=(
                f"gp3 は gp2 と比較してストレージコストが約 17% 安く、"
                f"デフォルトで 3,000 IOPS と 125 MB/s のスループットが無料で提供されます。"
                f"月額 ${monthly_savings:.1f} の削減が見込めます（推定値）。"
            ),
            current_config=f"gp2: {instance.allocated_storage_gb}GB (${cost_breakdown.storage_cost_usd:.1f}/月)",
            recommended_config=f"gp3: {instance.allocated_storage_gb}GB (推定 ${cost_breakdown.storage_cost_usd - monthly_savings:.1f}/月)",
            estimated_monthly_savings_usd=monthly_savings,
            estimated_performance_improvement_pct=20.0,
            implementation_complexity=1,
            action_steps=[
                "AWS コンソール > RDS > データベースを選択",
                "「変更」を選択してストレージタイプを gp3 に変更",
                "IOPS とスループットの設定値を確認（gp3 デフォルト: 3000 IOPS / 125 MB/s）",
                "「すぐに適用」を選択（短時間のダウンタイムなしで変更可能）",
            ],
            reference_url="https://aws.amazon.com/blogs/database/amazon-rds-now-supports-gp3-storage-volumes/",
        )

    def _recommend_read_replica(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
        cost_breakdown: CostBreakdown,
    ) -> Recommendation:
        """読み取り負荷分散のためのリードレプリカ追加提案"""
        hourly_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0)
        replica_monthly_cost = hourly_rate * 730

        priority = (
            RecommendationPriority.HIGH
            if performance.io_status == PerformanceStatus.CRITICAL
            else RecommendationPriority.MEDIUM
        )

        return Recommendation(
            recommendation_id=self._next_id("replica"),
            type=RecommendationType.ADD_READ_REPLICA,
            priority=priority,
            title="リードレプリカを追加して読み取り負荷を分散",
            description=(
                f"I/O ボトルネックを検知しました（IOPS使用率: {performance.iops_limit_pct:.1f}%）。"
                "リードレプリカを追加することで読み取りクエリをオフロードし、"
                "プライマリへの負荷を軽減できます。"
            ),
            current_config=f"レプリカなし (IOPS使用率: {performance.iops_limit_pct:.1f}%)",
            recommended_config=f"リードレプリカ x1 追加 (${replica_monthly_cost:.0f}/月 の追加コスト)",
            estimated_monthly_savings_usd=-replica_monthly_cost,  # コスト増加
            estimated_performance_improvement_pct=50.0,
            implementation_complexity=2,
            action_steps=[
                "読み取りクエリの割合をアプリケーションログで確認",
                "AWS コンソールでリードレプリカを作成",
                "アプリケーションの DB 接続を読み取りエンドポイントに切り替え",
                "プライマリの IOPS が改善されることを確認",
            ],
        )

    def _recommend_connection_pooling(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
    ) -> Recommendation:
        """コネクション過多に対するコネクションプール提案"""
        return Recommendation(
            recommendation_id=self._next_id("conn_pool"),
            type=RecommendationType.REDUCE_CONNECTIONS,
            priority=RecommendationPriority.HIGH,
            title="コネクションプールを導入して接続数を削減",
            description=(
                f"DB 接続数が最大接続数の {performance.connection_limit_pct:.1f}% に達しています。"
                "PgBouncer (PostgreSQL) または ProxySQL (MySQL) の導入を推奨します。"
                "RDS Proxy も有効な選択肢です。"
            ),
            current_config=f"接続数: {int(performance.avg_connections)} (上限の {performance.connection_limit_pct:.0f}%)",
            recommended_config="RDS Proxy または PgBouncer / ProxySQL を経由した接続",
            estimated_monthly_savings_usd=0.0,
            estimated_performance_improvement_pct=30.0,
            implementation_complexity=3,
            action_steps=[
                "RDS Proxy の有効化（Lambda / コンテナワークロードに特に有効）",
                "または PgBouncer をプライマリの前段に配置",
                "アプリケーションの接続先をプロキシエンドポイントに変更",
                "接続数の推移を CloudWatch で確認",
            ],
            reference_url="https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html",
        )

    def _recommend_aurora_migration(
        self,
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
        cost_breakdown: CostBreakdown,
    ) -> Recommendation:
        """Aurora への移行提案"""
        aurora_engine = (
            EngineType.AURORA_MYSQL
            if instance.engine in (EngineType.MYSQL, EngineType.MARIADB)
            else EngineType.AURORA_POSTGRESQL
        )

        return Recommendation(
            recommendation_id=self._next_id("aurora"),
            type=RecommendationType.AURORA_MIGRATION,
            priority=RecommendationPriority.MEDIUM,
            title=f"Amazon Aurora ({aurora_engine.value}) への移行を検討",
            description=(
                "Aurora は RDS と比較して最大 5 倍（MySQL）または 3 倍（PostgreSQL）の"
                "パフォーマンスを提供します。"
                "ストレージは自動拡張（最大 128TiB）で管理が容易になります。"
            ),
            current_config=f"{instance.engine.value} on {instance.instance_class}",
            recommended_config=f"{aurora_engine.value} (Aurora クラスター構成)",
            estimated_monthly_savings_usd=0.0,
            estimated_performance_improvement_pct=60.0,
            implementation_complexity=4,
            action_steps=[
                "AWS DMS (Database Migration Service) でマイグレーション計画を策定",
                "Aurora クラスターを作成（既存 RDS のスナップショットから復元可能）",
                "アプリケーションを Aurora エンドポイントに切り替え",
                "パフォーマンスを旧環境と比較検証",
                "旧 RDS インスタンスをフリーズして一定期間監視後に削除",
            ],
            reference_url="https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Migrate.html",
        )

    def _recommend_aurora_serverless(
        self,
        instance: RDSInstance,
        cost_breakdown: CostBreakdown,
    ) -> Recommendation:
        """Aurora Serverless v2 への移行提案"""
        # 現在のコストと Serverless の推定コストを比較
        current_monthly = cost_breakdown.total_cost_usd
        # Serverless は低負荷時に大幅削減できる（推定 40% 削減）
        estimated_savings = current_monthly * 0.35

        return Recommendation(
            recommendation_id=self._next_id("serverless"),
            type=RecommendationType.AURORA_SERVERLESS,
            priority=RecommendationPriority.LOW,
            title="Aurora Serverless v2 への移行を検討（断続的ワークロード向け）",
            description=(
                "負荷が低い時間帯が長い断続的なワークロードには、"
                "Aurora Serverless v2 が最適です。"
                "使用量に応じた ACU 課金で、アイドル時のコストを大幅に削減できます。"
            ),
            current_config=f"プロビジョンド: {instance.instance_class} (${current_monthly:.0f}/月)",
            recommended_config="Aurora Serverless v2 (0.5〜128 ACU、使用量課金)",
            estimated_monthly_savings_usd=estimated_savings,
            estimated_performance_improvement_pct=0.0,
            implementation_complexity=4,
            action_steps=[
                "CloudWatch でアイドル時間を確認（6時間以上のアイドルがある場合に特に有効）",
                "Aurora Serverless v2 クラスターを作成",
                "min_capacity / max_capacity (ACU) を設定",
                "アプリケーションエンドポイントを切り替え",
            ],
            reference_url="https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html",
        )

    def _recommend_graviton(
        self,
        instance: RDSInstance,
        cost_breakdown: CostBreakdown,
    ) -> Optional[Recommendation]:
        """Graviton2 インスタンスへの移行提案（x86 インスタンスのみ）"""
        graviton_class = self._GRAVITON_MAP.get(instance.instance_class)
        if not graviton_class:
            return None

        current_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0)
        graviton_rate = INSTANCE_HOURLY_RATES.get(graviton_class, 0)
        monthly_savings = (current_rate - graviton_rate) * 730

        if instance.multi_az:
            monthly_savings *= 2

        if monthly_savings <= 0:
            return None

        return Recommendation(
            recommendation_id=self._next_id("graviton"),
            type=RecommendationType.UPGRADE_GRAVITON,
            priority=RecommendationPriority.MEDIUM,
            title=f"Graviton2 インスタンスへ移行: {instance.instance_class} → {graviton_class}",
            description=(
                f"Graviton2 インスタンス ({graviton_class}) は同等性能でコストが"
                f"約 10〜20% 安くなります。"
                f"月額 ${monthly_savings:.1f} の削減が見込めます（推定値）。"
            ),
            current_config=f"{instance.instance_class} (${current_rate}/時間)",
            recommended_config=f"{graviton_class} (${graviton_rate}/時間)",
            estimated_monthly_savings_usd=monthly_savings,
            estimated_performance_improvement_pct=10.0,
            implementation_complexity=2,
            action_steps=[
                "Graviton2 対応のエンジンバージョンを確認（MySQL 8.0.23+、PostgreSQL 12.6+）",
                f"インスタンスクラスを {graviton_class} に変更",
                "変更後のパフォーマンスを確認（通常は同等以上）",
            ],
            reference_url="https://aws.amazon.com/rds/graviton/",
        )

    def _recommend_multi_az(
        self,
        instance: RDSInstance,
        cost_breakdown: CostBreakdown,
    ) -> Recommendation:
        """マルチAZ 有効化提案（可用性向上）"""
        hourly_rate = INSTANCE_HOURLY_RATES.get(instance.instance_class, 0)
        additional_monthly_cost = hourly_rate * 730  # スタンバイインスタンス分

        return Recommendation(
            recommendation_id=self._next_id("multi_az"),
            type=RecommendationType.ENABLE_MULTI_AZ,
            priority=RecommendationPriority.MEDIUM,
            title="マルチAZ を有効化して高可用性を確保",
            description=(
                "現在シングル AZ 構成です。本番環境ではマルチ AZ を有効化することで、"
                "AZ 障害時の自動フェイルオーバー（通常 1〜2 分以内）が可能になります。"
                f"追加コスト: 月額 ${additional_monthly_cost:.0f}（推定値）。"
            ),
            current_config="シングル AZ（可用性 99.95%）",
            recommended_config="マルチ AZ（可用性 99.99%+）",
            estimated_monthly_savings_usd=-additional_monthly_cost,  # コスト増加
            estimated_performance_improvement_pct=0.0,
            implementation_complexity=1,
            action_steps=[
                "本番環境での重要度と SLA 要件を確認",
                "AWS コンソールでマルチ AZ を有効化",
                "フェイルオーバーテストを実施（任意）",
            ],
            reference_url="https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html",
        )

    # ----------------------------------------------------------
    # ヘルパーメソッド
    # ----------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        """一意な提案IDを生成"""
        self._recommendation_counter += 1
        return f"{prefix}_{self._recommendation_counter:03d}"

    @staticmethod
    def _should_recommend_aurora(
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
    ) -> bool:
        """Aurora 移行提案を出すべきか判定"""
        if instance.is_aurora:
            return False
        # 高負荷かつ MySQL/PostgreSQL の場合
        return (
            performance.cpu_avg_pct > 60
            or performance.io_bottleneck_detected
        ) and instance.engine in (
            EngineType.MYSQL,
            EngineType.POSTGRESQL,
            EngineType.MARIADB,
        )

    @staticmethod
    def _should_recommend_serverless(
        instance: RDSInstance,
        performance: PerformanceAnalysisResult,
    ) -> bool:
        """Aurora Serverless 提案を出すべきか判定"""
        if instance.is_serverless:
            return False
        # 低CPU（断続的ワークロード）かつ Aurora 対応エンジン
        return (
            performance.cpu_avg_pct < 30
            and instance.engine in (
                EngineType.MYSQL,
                EngineType.POSTGRESQL,
                EngineType.AURORA_MYSQL,
                EngineType.AURORA_POSTGRESQL,
                EngineType.MARIADB,
            )
        )
