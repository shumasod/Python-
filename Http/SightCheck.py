#!/usr/bin/env python3
"""
ウェブサイト変更監視ツール (SightCheck)

指定されたWebページの特定要素を監視し、変更があれば通知・記録する。
複数の通知チャネル（Slack、メール、Webhook）に対応。

Usage:
    python sightcheck.py --url https://example.com --selector "div.content"
    python sightcheck.py --config config.json
    python sightcheck.py --url https://example.com --once  # 一回のみ実行
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import logging
import os
import signal
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =============================================================================
# Constants
# =============================================================================

VERSION = "2.0.0"
DEFAULT_USER_AGENT = f"SightCheck/{VERSION} (+https://github.com/example/sightcheck)"
DEFAULT_TIMEOUT = 15
DEFAULT_INTERVAL = 60
MIN_INTERVAL = 5

# =============================================================================
# Configuration
# =============================================================================


class ChangeDetectionMode(Enum):
    """変更検出モード"""

    TEXT = "text"  # テキスト内容の比較
    HASH = "hash"  # ハッシュ比較（高速）
    DIFF = "diff"  # 差分検出（詳細）


@dataclass
class NotificationConfig:
    """通知設定"""

    enabled: bool = False

    # Slack
    slack_webhook_url: str | None = None
    slack_channel: str | None = None

    # Email
    email_enabled: bool = False
    email_smtp_host: str = "localhost"
    email_smtp_port: int = 587
    email_from: str = ""
    email_to: list[str] = field(default_factory=list)
    email_username: str | None = None
    email_password: str | None = None

    # Generic Webhook
    webhook_url: str | None = None
    webhook_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    """監視設定"""

    url: str = "https://example.com"
    selector: str = "body"
    output_file: Path = field(default_factory=lambda: Path("content.txt"))
    history_dir: Path = field(default_factory=lambda: Path("history"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))

    # Timing
    check_interval: int = DEFAULT_INTERVAL
    timeout: int = DEFAULT_TIMEOUT

    # HTTP
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = DEFAULT_USER_AGENT
    headers: dict[str, str] = field(default_factory=dict)

    # Detection
    detection_mode: ChangeDetectionMode = ChangeDetectionMode.TEXT
    ignore_whitespace: bool = True
    keep_history: bool = True
    max_history_files: int = 100

    # Notification
    notification: NotificationConfig = field(default_factory=NotificationConfig)

    def __post_init__(self) -> None:
        if isinstance(self.output_file, str):
            self.output_file = Path(self.output_file)
        if isinstance(self.history_dir, str):
            self.history_dir = Path(self.history_dir)
        if isinstance(self.log_dir, str):
            self.log_dir = Path(self.log_dir)
        if isinstance(self.detection_mode, str):
            self.detection_mode = ChangeDetectionMode(self.detection_mode)

    @classmethod
    def from_json(cls, path: str | Path) -> Config:
        """JSONファイルから設定を読み込み"""
        json_path = Path(path)

        if not json_path.exists():
            logging.warning("設定ファイルが見つかりません: %s（デフォルト使用）", path)
            return cls()

        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Notification config
            notif_data = data.pop("notification", {})
            notification = NotificationConfig(**notif_data) if notif_data else NotificationConfig()

            return cls(notification=notification, **data)

        except json.JSONDecodeError as e:
            logging.error("JSON解析エラー: %s", e)
            return cls()
        except Exception as e:
            logging.exception("設定読み込みエラー: %s", e)
            return cls()

    def to_json(self, path: str | Path) -> None:
        """設定をJSONファイルに保存"""
        data = asdict(self)
        data["output_file"] = str(self.output_file)
        data["history_dir"] = str(self.history_dir)
        data["log_dir"] = str(self.log_dir)
        data["detection_mode"] = self.detection_mode.value

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# =============================================================================
# Logging
# =============================================================================


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """ロガーをセットアップ"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"sightcheck_{datetime.now():%Y%m%d}.log"

    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    return logging.getLogger(__name__)


# =============================================================================
# HTTP Client
# =============================================================================


class HttpClient:
    """HTTP クライアント"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """リトライ付きセッションを作成"""
        session = requests.Session()

        headers = {"User-Agent": self._config.user_agent}
        headers.update(self._config.headers)
        session.headers.update(headers)

        retry_strategy = Retry(
            total=self._config.max_retries,
            backoff_factor=self._config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def fetch(self, url: str) -> requests.Response | None:
        """URLを取得"""
        try:
            response = self._session.get(url, timeout=self._config.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response
        except requests.RequestException as e:
            logging.error("HTTP取得エラー: %s", e)
            return None

    def close(self) -> None:
        """セッションを閉じる"""
        self._session.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# =============================================================================
# Content Parser
# =============================================================================


@dataclass
class ParsedContent:
    """パース済みコンテンツ"""

    text: str
    html: str
    element_count: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def hash(self) -> str:
        """コンテンツのハッシュ"""
        return hashlib.sha256(self.text.encode()).hexdigest()

    @property
    def normalized_text(self) -> str:
        """正規化されたテキスト"""
        return " ".join(self.text.split())


class ContentParser:
    """HTMLコンテンツパーサー"""

    def __init__(self, selector: str) -> None:
        self._selector = selector

    def parse(self, html: str) -> ParsedContent:
        """HTMLをパースして指定要素を抽出"""
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(self._selector)

        if not elements:
            logging.warning("セレクタに一致する要素がありません: %s", self._selector)
            return ParsedContent(text="", html="", element_count=0)

        texts = [elem.get_text(separator=" ", strip=True) for elem in elements]
        htmls = [str(elem) for elem in elements]

        return ParsedContent(
            text="\n".join(filter(None, texts)),
            html="\n".join(htmls),
            element_count=len(elements),
        )


# =============================================================================
# Change Detector
# =============================================================================


@dataclass
class ChangeResult:
    """変更検出結果"""

    changed: bool
    old_content: str
    new_content: str
    diff_lines: list[str] = field(default_factory=list)
    change_ratio: float = 0.0


class ChangeDetector:
    """変更検出"""

    def __init__(self, mode: ChangeDetectionMode, ignore_whitespace: bool = True) -> None:
        self._mode = mode
        self._ignore_whitespace = ignore_whitespace

    def detect(self, old_content: str, new_content: str) -> ChangeResult:
        """変更を検出"""
        old_normalized = self._normalize(old_content)
        new_normalized = self._normalize(new_content)

        if self._mode == ChangeDetectionMode.HASH:
            old_hash = hashlib.sha256(old_normalized.encode()).hexdigest()
            new_hash = hashlib.sha256(new_normalized.encode()).hexdigest()
            changed = old_hash != new_hash
        else:
            changed = old_normalized != new_normalized

        diff_lines = []
        change_ratio = 0.0

        if changed and self._mode == ChangeDetectionMode.DIFF:
            diff_lines = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="previous",
                tofile="current",
                lineterm="",
            ))

            matcher = difflib.SequenceMatcher(None, old_normalized, new_normalized)
            change_ratio = 1.0 - matcher.ratio()

        return ChangeResult(
            changed=changed,
            old_content=old_content,
            new_content=new_content,
            diff_lines=diff_lines,
            change_ratio=change_ratio,
        )

    def _normalize(self, content: str) -> str:
        """コンテンツを正規化"""
        if self._ignore_whitespace:
            return " ".join(content.split())
        return content


# =============================================================================
# Storage
# =============================================================================


class ContentStorage:
    """コンテンツ保存"""

    def __init__(
        self,
        output_file: Path,
        history_dir: Path,
        keep_history: bool = True,
        max_history: int = 100,
    ) -> None:
        self._output_file = output_file
        self._history_dir = history_dir
        self._keep_history = keep_history
        self._max_history = max_history

    def load(self) -> str:
        """保存済みコンテンツを読み込み"""
        try:
            if self._output_file.exists() and self._output_file.stat().st_size > 0:
                return self._output_file.read_text(encoding="utf-8")
        except Exception as e:
            logging.error("ファイル読み込みエラー: %s", e)
        return ""

    def save(self, content: str) -> None:
        """コンテンツを保存"""
        self._atomic_write(self._output_file, content)

        if self._keep_history:
            self._save_history(content)

    def _atomic_write(self, path: Path, content: str) -> None:
        """アトミック書き込み"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            os.replace(tmp_path, path)
            logging.info("ファイル保存: %s", path)

        except Exception as e:
            logging.error("ファイル書き込みエラー: %s", e)

    def _save_history(self, content: str) -> None:
        """履歴を保存"""
        self._history_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_file = self._history_dir / f"content_{timestamp}.txt"

        self._atomic_write(history_file, content)
        self._cleanup_history()

    def _cleanup_history(self) -> None:
        """古い履歴を削除"""
        history_files = sorted(self._history_dir.glob("content_*.txt"))

        if len(history_files) > self._max_history:
            for old_file in history_files[: -self._max_history]:
                try:
                    old_file.unlink()
                    logging.debug("古い履歴を削除: %s", old_file)
                except Exception as e:
                    logging.warning("履歴削除エラー: %s", e)


# =============================================================================
# Notifiers
# =============================================================================


class Notifier(ABC):
    """通知の基底クラス"""

    @abstractmethod
    def notify(self, message: str, details: dict[str, Any] | None = None) -> bool:
        """通知を送信"""


class SlackNotifier(Notifier):
    """Slack通知"""

    def __init__(self, webhook_url: str, channel: str | None = None) -> None:
        self._webhook_url = webhook_url
        self._channel = channel

    def notify(self, message: str, details: dict[str, Any] | None = None) -> bool:
        try:
            payload: dict[str, Any] = {"text": message}

            if self._channel:
                payload["channel"] = self._channel

            if details:
                attachments = [{
                    "color": "warning",
                    "fields": [
                        {"title": k, "value": str(v)[:100], "short": True}
                        for k, v in details.items()
                    ],
                }]
                payload["attachments"] = attachments

            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logging.info("Slack通知送信成功")
            return True

        except Exception as e:
            logging.error("Slack通知エラー: %s", e)
            return False


class WebhookNotifier(Notifier):
    """汎用Webhook通知"""

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}

    def notify(self, message: str, details: dict[str, Any] | None = None) -> bool:
        try:
            payload = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "details": details or {},
            }

            response = requests.post(
                self._url,
                json=payload,
                headers=self._headers,
                timeout=10,
            )
            response.raise_for_status()
            logging.info("Webhook通知送信成功")
            return True

        except Exception as e:
            logging.error("Webhook通知エラー: %s", e)
            return False


class EmailNotifier(Notifier):
    """メール通知"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        from_addr: str,
        to_addrs: list[str],
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._from_addr = from_addr
        self._to_addrs = to_addrs
        self._username = username
        self._password = password

    def notify(self, message: str, details: dict[str, Any] | None = None) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText

            body = message
            if details:
                body += "\n\n詳細:\n" + "\n".join(f"  {k}: {v}" for k, v in details.items())

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = "[SightCheck] ウェブサイト変更検出"
            msg["From"] = self._from_addr
            msg["To"] = ", ".join(self._to_addrs)

            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                if self._username and self._password:
                    server.login(self._username, self._password)
                server.send_message(msg)

            logging.info("メール通知送信成功")
            return True

        except Exception as e:
            logging.error("メール通知エラー: %s", e)
            return False


class NotificationManager:
    """通知マネージャー"""

    def __init__(self, config: NotificationConfig) -> None:
        self._notifiers: list[Notifier] = []
        self._setup_notifiers(config)

    def _setup_notifiers(self, config: NotificationConfig) -> None:
        """通知機能をセットアップ"""
        if not config.enabled:
            return

        if config.slack_webhook_url:
            self._notifiers.append(
                SlackNotifier(config.slack_webhook_url, config.slack_channel)
            )

        if config.webhook_url:
            self._notifiers.append(
                WebhookNotifier(config.webhook_url, config.webhook_headers)
            )

        if config.email_enabled and config.email_to:
            self._notifiers.append(
                EmailNotifier(
                    config.email_smtp_host,
                    config.email_smtp_port,
                    config.email_from,
                    config.email_to,
                    config.email_username,
                    config.email_password,
                )
            )

    def notify_change(self, url: str, change_result: ChangeResult) -> None:
        """変更を通知"""
        if not self._notifiers:
            return

        message = f"🔔 ウェブサイトの変更を検出しました\nURL: {url}"

        details = {
            "変更率": f"{change_result.change_ratio * 100:.1f}%",
            "検出時刻": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if change_result.diff_lines:
            diff_preview = "".join(change_result.diff_lines[:20])
            details["差分（抜粋）"] = diff_preview[:500]

        for notifier in self._notifiers:
            try:
                notifier.notify(message, details)
            except Exception as e:
                logging.error("通知送信エラー: %s", e)


# =============================================================================
# Monitor
# =============================================================================


@dataclass
class MonitorStats:
    """監視統計"""

    start_time: datetime = field(default_factory=datetime.now)
    total_checks: int = 0
    changes_detected: int = 0
    errors: int = 0

    def __str__(self) -> str:
        runtime = datetime.now() - self.start_time
        return (
            f"稼働時間: {runtime}, "
            f"チェック: {self.total_checks}, "
            f"変更検出: {self.changes_detected}, "
            f"エラー: {self.errors}"
        )


class WebsiteMonitor:
    """ウェブサイト監視"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = HttpClient(config)
        self._parser = ContentParser(config.selector)
        self._detector = ChangeDetector(config.detection_mode, config.ignore_whitespace)
        self._storage = ContentStorage(
            config.output_file,
            config.history_dir,
            config.keep_history,
            config.max_history_files,
        )
        self._notification = NotificationManager(config.notification)
        self._stats = MonitorStats()
        self._running = False

    def check_once(self) -> ChangeResult | None:
        """一回チェックを実行"""
        logging.info("チェック開始: %s", self._config.url)
        self._stats.total_checks += 1

        response = self._client.fetch(self._config.url)
        if response is None:
            self._stats.errors += 1
            return None

        parsed = self._parser.parse(response.text)
        logging.info(
            "取得: %d要素, %d文字",
            parsed.element_count,
            len(parsed.text),
        )

        old_content = self._storage.load()
        result = self._detector.detect(old_content, parsed.text)

        if result.changed:
            logging.info("変更を検出しました")
            self._stats.changes_detected += 1
            self._storage.save(parsed.text)
            self._notification.notify_change(self._config.url, result)

        return result

    def run(self) -> None:
        """継続監視を実行"""
        self._running = True
        interval = max(MIN_INTERVAL, self._config.check_interval)

        logging.info("監視開始 (間隔: %d秒)", interval)
        logging.info("設定: URL=%s, セレクタ=%s", self._config.url, self._config.selector)

        # シグナルハンドラ
        def handle_signal(sig: int, _: Any) -> None:
            logging.info("停止シグナル受信")
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while self._running:
                self.check_once()
                logging.info("次回チェック: %d秒後 | %s", interval, self._stats)

                # 中断可能なスリープ
                for _ in range(interval):
                    if not self._running:
                        break
                    time.sleep(1)

        finally:
            self._client.close()
            logging.info("監視終了 | %s", self._stats)

    @property
    def stats(self) -> MonitorStats:
