"""
Slack 通知モジュール（拡張要件）

設計意図:
- Webhook URL を使った Slack Block Kit 通知
- 重要度別の色分け（赤/橙/黄/緑）でひと目でわかる通知
- CRITICAL アラートは @channel メンション付き
- Lambda から直接呼び出せるシンプルな設計

環境変数:
    SLACK_WEBHOOK_URL: Slack Incoming Webhook URL
    SLACK_CHANNEL: 通知先チャンネル（オプション。#rds-alerts 等）
    SLACK_NOTIFY_THRESHOLD: 通知を出す最小優先度 (critical/high/medium)

Webhook URL の取得:
    Slack App 管理画面 → Incoming Webhooks → Add New Webhook to Workspace
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..analyzers.recommendation_engine import Recommendation, RecommendationPriority
from ..models.costs import CostAnomaly
from ..models.metrics import PerformanceAnalysisResult, PerformanceStatus

logger = logging.getLogger(__name__)

# 優先度別の色（Slack Attachment の color フィールド）
PRIORITY_COLORS = {
    RecommendationPriority.CRITICAL: "#FF0000",
    RecommendationPriority.HIGH: "#FF8C00",
    RecommendationPriority.MEDIUM: "#FFD700",
    RecommendationPriority.LOW: "#808080",
}

STATUS_COLORS = {
    PerformanceStatus.HEALTHY: "#22c55e",
    PerformanceStatus.WARNING: "#f59e0b",
    PerformanceStatus.CRITICAL: "#ef4444",
    PerformanceStatus.UNKNOWN: "#6b7280",
}


@dataclass
class SlackMessage:
    """Slack メッセージ構造体"""
    text: str
    blocks: list[dict]
    attachments: list[dict] = None
    channel: Optional[str] = None


class SlackNotifier:
    """
    Slack 通知クライアント

    Incoming Webhook を使用して Slack に通知を送信する。
    Block Kit を使用してリッチなメッセージを構成する。
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        channel: Optional[str] = None,
        notify_threshold: str = "high",
    ):
        """
        Args:
            webhook_url: Slack Incoming Webhook URL（None の場合は環境変数から取得）
            channel: 通知先チャンネル（Webhook のデフォルトチャンネルを上書き）
            notify_threshold: 通知する最小優先度（critical/high/medium/low）
        """
        self._webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self._channel = channel or os.environ.get("SLACK_CHANNEL", "")
        self._threshold = RecommendationPriority(notify_threshold.lower())

        if not self._webhook_url:
            logger.warning(
                "SLACK_WEBHOOK_URL が設定されていません。Slack 通知は無効です。"
            )

    @property
    def is_configured(self) -> bool:
        """Webhook URL が設定されているか"""
        return bool(self._webhook_url)

    # ----------------------------------------------------------
    # パブリック API
    # ----------------------------------------------------------

    def notify_performance_alert(
        self,
        instance_id: str,
        perf_result: PerformanceAnalysisResult,
        region: str = "ap-northeast-1",
    ) -> bool:
        """
        パフォーマンスアラートを通知する

        CRITICAL または WARNING のボトルネックがある場合のみ送信
        """
        if not self.is_configured:
            return False

        if not perf_result.has_any_bottleneck:
            return False

        # ボトルネック一覧を構築
        issues = perf_result.critical_issues
        status_color = (
            STATUS_COLORS[PerformanceStatus.CRITICAL]
            if any(
                s == PerformanceStatus.CRITICAL
                for s in [
                    perf_result.cpu_status,
                    perf_result.memory_status,
                    perf_result.io_status,
                    perf_result.connection_status,
                ]
            )
            else STATUS_COLORS[PerformanceStatus.WARNING]
        )

        blocks = [
            self._section_block(
                f"*🚨 RDS パフォーマンスアラート*\n"
                f"インスタンス: `{instance_id}` | リージョン: {region}"
            ),
            self._divider_block(),
            self._fields_block([
                f"*健全性スコア*\n{perf_result.health_score}/100",
                f"*CPU 使用率*\n{perf_result.cpu_avg_pct:.1f}% (avg)",
                f"*空きメモリ*\n{perf_result.freeable_memory_avg_gb:.2f} GB",
                f"*IOPS 使用率*\n{perf_result.iops_limit_pct:.1f}%",
            ]),
        ]

        if issues:
            issue_text = "\n".join(f"• {issue}" for issue in issues)
            blocks.append(self._section_block(f"*検知された問題:*\n{issue_text}"))

        blocks.append(self._context_block(
            f"分析時刻: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        ))

        attachments = [{"color": status_color, "blocks": blocks}]
        return self._send(text=f"⚠️ RDS アラート: {instance_id}", attachments=attachments)

    def notify_recommendations(
        self,
        instance_id: str,
        recommendations: list[Recommendation],
        total_savings_usd: float,
    ) -> bool:
        """
        改善提案通知を送信する

        閾値以上の優先度を持つ提案のみ通知
        """
        if not self.is_configured:
            return False

        # 優先度フィルタリング
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        threshold_idx = priority_order[self._threshold]
        filtered = [
            r for r in recommendations
            if priority_order[r.priority] <= threshold_idx
        ]

        if not filtered:
            return False

        blocks = [
            self._section_block(
                f"*💡 RDS 改善提案 - `{instance_id}`*\n"
                f"{len(filtered)} 件の提案（推定節約: *${total_savings_usd:.1f}/月*）"
            ),
            self._divider_block(),
        ]

        for i, rec in enumerate(filtered[:5], 1):  # 最大5件
            priority_label = {
                RecommendationPriority.CRITICAL: "🔴 緊急",
                RecommendationPriority.HIGH: "🟠 高",
                RecommendationPriority.MEDIUM: "🟡 中",
                RecommendationPriority.LOW: "⚪ 低",
            }[rec.priority]

            savings_text = (
                f"💰 ${rec.estimated_monthly_savings_usd:.1f}/月 節約"
                if rec.estimated_monthly_savings_usd > 0
                else ""
            )

            blocks.append(self._section_block(
                f"*{i}. [{priority_label}] {rec.title}*\n"
                f"{rec.description[:120]}{'...' if len(rec.description) > 120 else ''}\n"
                f"{savings_text}"
            ))

        blocks.append(self._context_block(
            f"生成時刻: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        ))

        # 最上位優先度に合わせた色
        top_priority = filtered[0].priority if filtered else RecommendationPriority.LOW
        color = PRIORITY_COLORS[top_priority]
        attachments = [{"color": color, "blocks": blocks}]

        return self._send(
            text=f"💡 改善提案: {instance_id} ({len(filtered)}件)",
            attachments=attachments,
        )

    def notify_cost_anomaly(
        self,
        anomaly: CostAnomaly,
        instance_id: str,
    ) -> bool:
        """
        コスト異常を通知する
        """
        if not self.is_configured or not anomaly.is_anomaly:
            return False

        direction = "急増" if anomaly.change_ratio_pct > 0 else "急減"
        color = "#FF0000" if anomaly.change_ratio_pct > 0 else "#0000FF"

        blocks = [
            self._section_block(
                f"*💸 RDS コスト異常検知 - `{instance_id}`*\n"
                f"コストが前月比 *{anomaly.change_ratio_pct:+.1f}%* {direction}しています"
            ),
            self._fields_block([
                f"*今月コスト（推定）*\n${anomaly.current_month_cost_usd:.2f}",
                f"*前月コスト（推定）*\n${anomaly.previous_month_cost_usd:.2f}",
                f"*変化率*\n{anomaly.change_ratio_pct:+.1f}%",
                f"*閾値*\n±{anomaly.threshold_pct:.0f}%",
            ]),
            self._section_block(anomaly.description),
            self._context_block(
                f"検知日: {anomaly.detected_at.strftime('%Y-%m-%d')}"
            ),
        ]

        attachments = [{"color": color, "blocks": blocks}]
        return self._send(
            text=f"💸 コスト異常: {instance_id} ({anomaly.change_ratio_pct:+.1f}%)",
            attachments=attachments,
        )

    # ----------------------------------------------------------
    # Block Kit ヘルパー
    # ----------------------------------------------------------

    @staticmethod
    def _section_block(text: str) -> dict:
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    @staticmethod
    def _divider_block() -> dict:
        return {"type": "divider"}

    @staticmethod
    def _fields_block(fields: list[str]) -> dict:
        return {
            "type": "section",
            "fields": [{"type": "mrkdwn", "text": f} for f in fields],
        }

    @staticmethod
    def _context_block(text: str) -> dict:
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": text}],
        }

    # ----------------------------------------------------------
    # HTTP 送信
    # ----------------------------------------------------------

    def _send(
        self,
        text: str,
        blocks: Optional[list[dict]] = None,
        attachments: Optional[list[dict]] = None,
    ) -> bool:
        """
        Slack Webhook に POST する

        Returns:
            True: 送信成功, False: 失敗
        """
        payload: dict = {"text": text}
        if self._channel:
            payload["channel"] = self._channel
        if blocks:
            payload["blocks"] = blocks
        if attachments:
            payload["attachments"] = attachments

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.debug("Slack 通知送信完了")
                    return True
                logger.warning("Slack 送信失敗: status=%d", resp.status)
                return False
        except urllib.error.URLError as e:
            logger.error("Slack 送信エラー: %s", str(e))
            return False
