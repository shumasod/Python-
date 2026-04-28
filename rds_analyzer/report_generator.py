"""
Markdown レポート生成エンジン

設計意図:
- 分析結果を人間が読みやすい Markdown レポートとして出力
- CI/CD パイプラインや Slack への投稿にも使用可能なテキスト形式
- テーブル・コードブロック・絵文字を活用した見やすいレイアウト
- PDF 変換は外部ツール（pandoc / weasyprint）に委譲

使用方法:
    from rds_analyzer.report_generator import ReportGenerator
    gen = ReportGenerator()
    md = gen.generate(instance, cost_breakdown, perf_result, recommendations)
    print(md)
    gen.save(md, "report.md")
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .analyzers.recommendation_engine import Recommendation, RecommendationPriority
from .models.costs import CostBreakdown, CostEfficiencyScore
from .models.metrics import PerformanceAnalysisResult, PerformanceStatus
from .models.rds import RDSInstance

# ステータス絵文字マップ
STATUS_EMOJI = {
    PerformanceStatus.HEALTHY: "✅",
    PerformanceStatus.WARNING: "⚠️",
    PerformanceStatus.CRITICAL: "🔴",
    PerformanceStatus.UNKNOWN: "❓",
}

PRIORITY_EMOJI = {
    RecommendationPriority.CRITICAL: "🔴",
    RecommendationPriority.HIGH: "🟠",
    RecommendationPriority.MEDIUM: "🟡",
    RecommendationPriority.LOW: "⚪",
}


class ReportGenerator:
    """
    RDS 分析結果の Markdown レポートを生成するクラス

    分析エンジンの出力を受け取り、運用チームが参照しやすい
    レポート文書を生成する。
    """

    def generate(
        self,
        instance: RDSInstance,
        cost_breakdown: CostBreakdown,
        cost_score: CostEfficiencyScore,
        perf_result: PerformanceAnalysisResult,
        recommendations: list[Recommendation],
        report_period: str = "過去 24 時間",
    ) -> str:
        """
        Markdown レポートを生成する

        Args:
            instance: RDS インスタンス設定
            cost_breakdown: コスト内訳
            cost_score: コスト効率スコア
            perf_result: パフォーマンス分析結果
            recommendations: 改善提案リスト
            report_period: 分析対象期間の説明文

        Returns:
            Markdown 形式のレポート文字列
        """
        sections = [
            self._header(instance, report_period),
            self._executive_summary(cost_breakdown, cost_score, perf_result, recommendations),
            self._cost_section(instance, cost_breakdown, cost_score),
            self._performance_section(perf_result),
            self._recommendations_section(recommendations),
            self._footer(),
        ]
        return "\n\n".join(sections)

    def save(self, content: str, path: str | Path) -> None:
        """レポートをファイルに保存する"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # ----------------------------------------------------------
    # セクション生成メソッド
    # ----------------------------------------------------------

    def _header(self, instance: RDSInstance, report_period: str) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        return f"""# RDS コスト・パフォーマンス分析レポート

| 項目 | 値 |
|------|-----|
| インスタンス ID | `{instance.instance_id}` |
| エンジン | {instance.engine.value} {instance.engine_version} |
| インスタンスクラス | `{instance.instance_class}` |
| リージョン | {instance.region} |
| マルチAZ | {"有効" if instance.multi_az else "無効"} |
| ストレージ | {instance.storage_type.value} / {instance.allocated_storage_gb}GB |
| 分析期間 | {report_period} |
| レポート生成日時 | {now} |

> ⚠️ **注意**: コスト計算値は推定値です。実際の請求額は AWS Console でご確認ください。"""

    def _executive_summary(
        self,
        cost_breakdown: CostBreakdown,
        cost_score: CostEfficiencyScore,
        perf_result: PerformanceAnalysisResult,
        recommendations: list[Recommendation],
    ) -> str:
        total_savings = sum(
            max(0, r.estimated_monthly_savings_usd) for r in recommendations
        )
        critical_count = sum(
            1 for r in recommendations
            if r.priority == RecommendationPriority.CRITICAL
        )

        perf_emoji = STATUS_EMOJI.get(
            PerformanceStatus.CRITICAL if perf_result.has_any_bottleneck else PerformanceStatus.HEALTHY,
            "❓"
        )

        return f"""## エグゼクティブサマリー

| 指標 | 値 | 評価 |
|------|-----|------|
| 月次コスト（推定） | **${cost_breakdown.total_cost_usd:.2f}** | - |
| コスト効率スコア | **{cost_score.score}/100** (Grade {cost_score.grade}) | {self._score_emoji(cost_score.score)} |
| パフォーマンス健全性スコア | **{perf_result.health_score}/100** | {perf_emoji} |
| 改善提案数 | {len(recommendations)} 件（緊急: {critical_count} 件） | - |
| 推定節約可能額 | **${total_savings:.1f}/月** | 💰 |

{cost_score.summary}"""

    def _cost_section(
        self,
        instance: RDSInstance,
        breakdown: CostBreakdown,
        score: CostEfficiencyScore,
    ) -> str:
        rows = [
            ("コンピュート", breakdown.compute_cost_usd + breakdown.replica_compute_cost_usd),
            ("ストレージ", breakdown.storage_cost_usd),
            ("IOPS", breakdown.iops_cost_usd),
            ("データ転送", breakdown.transfer_cost_usd),
            ("バックアップ", breakdown.backup_cost_usd),
        ]

        table_rows = "\n".join(
            f"| {name} | ${cost:.2f} | {cost / breakdown.total_cost_usd * 100:.1f}% |"
            for name, cost in rows
            if cost > 0
        )

        return f"""## コスト分析

### 月次コスト内訳（推定値）

| コンポーネント | 金額 (USD) | 割合 |
|--------------|-----------|------|
{table_rows}
| **合計** | **${breakdown.total_cost_usd:.2f}** | 100% |

### コスト効率スコア: {score.score}/100 (Grade {score.grade})

- **CPU 効率**: {score.cpu_efficiency_score}/100
- **ストレージ効率**: {score.storage_efficiency_score}/100
- **IOPS 効率**: {score.iops_efficiency_score}/100"""

    def _performance_section(self, perf: PerformanceAnalysisResult) -> str:
        cpu_emoji = STATUS_EMOJI[perf.cpu_status]
        mem_emoji = STATUS_EMOJI[perf.memory_status]
        io_emoji = STATUS_EMOJI[perf.io_status]
        conn_emoji = STATUS_EMOJI[perf.connection_status]
        stor_emoji = STATUS_EMOJI[perf.storage_status]

        bottlenecks_md = ""
        if perf.critical_issues:
            issues = "\n".join(f"- 🔴 {issue}" for issue in perf.critical_issues)
            bottlenecks_md = f"\n### 検知されたボトルネック\n\n{issues}"

        return f"""## パフォーマンス分析

### 総合健全性スコア: {perf.health_score}/100

| メトリクス | 値 | ステータス |
|-----------|-----|----------|
| CPU使用率（平均） | {perf.cpu_avg_pct:.1f}% | {cpu_emoji} {perf.cpu_status.value} |
| CPU使用率（最大） | {perf.cpu_max_pct:.1f}% | - |
| 空きメモリ（平均） | {perf.freeable_memory_avg_gb:.2f} GB | {mem_emoji} {perf.memory_status.value} |
| 合計IOPS（平均） | {perf.avg_total_iops:.0f} | {io_emoji} {perf.io_status.value} |
| IOPS使用率 | {perf.iops_limit_pct:.1f}% | - |
| DB接続数（平均） | {perf.avg_connections:.0f} | {conn_emoji} {perf.connection_status.value} |
| 接続数使用率 | {perf.connection_limit_pct:.1f}% | - |
| ストレージ使用率 | {perf.storage_utilization_pct:.1f}% | {stor_emoji} {perf.storage_status.value} |
| 空きストレージ | {perf.free_storage_gb:.1f} GB | - |
{bottlenecks_md}"""

    def _recommendations_section(self, recommendations: list[Recommendation]) -> str:
        if not recommendations:
            return "## 改善提案\n\n✅ 現時点での改善提案はありません。"

        total_savings = sum(
            max(0, r.estimated_monthly_savings_usd) for r in recommendations
        )

        recs_md = ""
        for i, rec in enumerate(recommendations, 1):
            priority_emoji = PRIORITY_EMOJI[rec.priority]
            savings_str = (
                f"💰 ${rec.estimated_monthly_savings_usd:.1f}/月 節約"
                if rec.estimated_monthly_savings_usd > 0
                else f"📈 ${abs(rec.estimated_monthly_savings_usd):.1f}/月 追加コスト"
                if rec.estimated_monthly_savings_usd < 0
                else "効果: パフォーマンス改善"
            )

            steps_md = "\n".join(
                f"   {j}. {step}" for j, step in enumerate(rec.action_steps, 1)
            ) if rec.action_steps else ""

            recs_md += f"""
### {i}. {priority_emoji} {rec.title}

- **優先度**: {rec.priority.value.upper()} | **種別**: {rec.type.value}
- **効果**: {savings_str}
- **実装難易度**: {'★' * rec.implementation_complexity}{'☆' * (5 - rec.implementation_complexity)}

{rec.description}

| | 現在 | 推奨 |
|-|------|------|
| 設定 | `{rec.current_config}` | `{rec.recommended_config}` |

**アクションステップ:**

{steps_md}
"""

        return f"""## 改善提案 ({len(recommendations)} 件)

> 推定節約合計: **${total_savings:.1f}/月**（推定値）
{recs_md}"""

    def _footer(self) -> str:
        return """---

*このレポートは RDS Cost & Performance Analyzer により自動生成されました。*
*コスト数値はすべて推定値であり、AWS 公式請求額とは異なる場合があります。*
*実際の対応前に AWS Console および担当アーキテクトへの確認を推奨します。*"""

    @staticmethod
    def _score_emoji(score: int) -> str:
        if score >= 80:
            return "✅"
        elif score >= 60:
            return "⚠️"
        else:
            return "🔴"
