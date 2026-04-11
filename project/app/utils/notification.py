"""
通知モジュール
Slack / LINE Notify へのメッセージ送信を担当する

環境変数:
  SLACK_WEBHOOK_URL  : Slack Incoming Webhook URL
  LINE_NOTIFY_TOKEN  : LINE Notify アクセストークン
  NOTIFY_ENABLED     : "true" で通知を有効化（デフォルト: false）

使い方:
  from app.utils.notification import notify

  # 非同期
  await notify("予測完了: 1号艇 42% (レースID: 001)")

  # 同期（スクリプトから）
  import asyncio
  asyncio.run(notify("モデル再学習完了"))
"""
import asyncio
import os
from typing import Optional

import requests

from app.utils.logger import get_logger

logger = get_logger(__name__)

_ENABLED         = os.getenv("NOTIFY_ENABLED", "false").lower() == "true"
_SLACK_WEBHOOK   = os.getenv("SLACK_WEBHOOK_URL", "")
_LINE_TOKEN      = os.getenv("LINE_NOTIFY_TOKEN", "")


# ============================================================
# Slack 通知
# ============================================================

def send_slack(message: str, webhook_url: str = "") -> bool:
    """
    Slack Incoming Webhook にメッセージを送信する

    Args:
        message: 送信テキスト（Markdown 使用可）
        webhook_url: Webhook URL（省略時は環境変数）

    Returns:
        True=成功, False=失敗
    """
    url = webhook_url or _SLACK_WEBHOOK
    if not url:
        logger.debug("SLACK_WEBHOOK_URL が未設定のため Slack 通知をスキップします")
        return False

    try:
        resp = requests.post(
            url,
            json={"text": message},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Slack 通知を送信しました")
        return True
    except requests.RequestException as e:
        logger.warning(f"Slack 通知に失敗しました: {e}")
        return False


# ============================================================
# LINE Notify
# ============================================================

def send_line(message: str, token: str = "") -> bool:
    """
    LINE Notify にメッセージを送信する

    Args:
        message: 送信テキスト（最大 1000 文字）
        token: LINE Notify アクセストークン（省略時は環境変数）

    Returns:
        True=成功, False=失敗
    """
    t = token or _LINE_TOKEN
    if not t:
        logger.debug("LINE_NOTIFY_TOKEN が未設定のため LINE 通知をスキップします")
        return False

    try:
        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {t}"},
            data={"message": f"\n{message[:1000]}"},  # LINE は改行が必要
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("LINE 通知を送信しました")
        return True
    except requests.RequestException as e:
        logger.warning(f"LINE 通知に失敗しました: {e}")
        return False


# ============================================================
# 統合インターフェース
# ============================================================

async def notify(
    message: str,
    channels: Optional[list[str]] = None,
) -> dict[str, bool]:
    """
    設定済みチャンネルに通知を送信する非同期関数

    Args:
        message: 通知メッセージ
        channels: 送信チャンネルリスト ["slack", "line"]
                  None の場合は設定済み全チャンネルに送信

    Returns:
        チャンネル名→成否のdict
    """
    if not _ENABLED:
        logger.debug("NOTIFY_ENABLED=false のため通知をスキップします")
        return {}

    targets = channels or ["slack", "line"]
    results: dict[str, bool] = {}

    loop = asyncio.get_event_loop()

    if "slack" in targets and _SLACK_WEBHOOK:
        results["slack"] = await loop.run_in_executor(
            None, send_slack, message
        )

    if "line" in targets and _LINE_TOKEN:
        results["line"] = await loop.run_in_executor(
            None, send_line, message
        )

    return results


def notify_sync(message: str, channels: Optional[list[str]] = None) -> dict[str, bool]:
    """
    同期版通知関数（スクリプト・Airflow DAGから使用）

    Args:
        message: 通知メッセージ
        channels: 送信チャンネルリスト

    Returns:
        チャンネル名→成否のdict
    """
    if not _ENABLED:
        return {}

    targets = channels or ["slack", "line"]
    results: dict[str, bool] = {}

    if "slack" in targets:
        results["slack"] = send_slack(message)
    if "line" in targets:
        results["line"] = send_line(message)

    return results


# ============================================================
# テンプレートメッセージ
# ============================================================

def build_prediction_summary(race_id: str, win_proba: list[float]) -> str:
    """
    予測結果の通知メッセージを生成する

    Args:
        race_id: レースID
        win_proba: 1号艇〜6号艇の1着確率リスト

    Returns:
        フォーマット済みメッセージ文字列
    """
    top = sorted(
        enumerate(win_proba, start=1),
        key=lambda x: x[1],
        reverse=True,
    )[:3]

    lines = [f"🏁 【競艇予測】{race_id}"]
    for rank, (boat, prob) in enumerate(top, start=1):
        bar = "█" * int(prob * 20)
        lines.append(f"  {rank}位: {boat}号艇 {prob*100:.1f}% {bar}")

    return "\n".join(lines)


def build_retrain_summary(version: str, metrics: dict) -> str:
    """
    再学習完了の通知メッセージを生成する

    Args:
        version: モデルバージョン文字列
        metrics: 評価メトリクス辞書

    Returns:
        フォーマット済みメッセージ文字列
    """
    ll  = metrics.get("cv_logloss_mean", 0)
    acc = metrics.get("cv_accuracy_mean", 0)
    n   = metrics.get("n_samples", 0)

    return (
        f"✅ 【モデル再学習完了】\n"
        f"  バージョン: {version}\n"
        f"  LogLoss  : {ll:.4f}\n"
        f"  Accuracy : {acc*100:.1f}%\n"
        f"  サンプル数: {n:,}"
    )
