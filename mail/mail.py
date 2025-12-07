"""
メール送信モジュール

SMTP経由でメールを送信するためのユーティリティ。
添付ファイル、HTML本文、複数宛先に対応。
"""

import logging
import os
import smtplib
from dataclasses import dataclass, field
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Self

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """メール送信に関するエラー"""


class AttachmentError(Exception):
    """添付ファイルに関するエラー"""


@dataclass
class SmtpConfig:
    """SMTP接続設定"""

    server: str
    port: int
    email: str
    password: str
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> Self:
        """環境変数から設定を読み込む"""
        server = os.environ.get("SMTP_SERVER")
        port = os.environ.get("SMTP_PORT")
        email = os.environ.get("SMTP_EMAIL")
        password = os.environ.get("SMTP_PASSWORD")

        if not all([server, port, email, password]):
            missing = [
                name
                for name, val in [
                    ("SMTP_SERVER", server),
                    ("SMTP_PORT", port),
                    ("SMTP_EMAIL", email),
                    ("SMTP_PASSWORD", password),
                ]
                if not val
            ]
            raise ValueError(f"環境変数が未設定: {', '.join(missing)}")

        return cls(
            server=server,
            port=int(port),
            email=email,
            password=password,
        )


@dataclass
class Email:
    """メールメッセージ"""

    to: list[str]
    subject: str
    body: str
    html_body: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.to, str):
            self.to = [self.to]
        self.attachments = [Path(p) for p in self.attachments]

    def all_recipients(self) -> list[str]:
        """すべての宛先を取得"""
        return self.to + self.cc + self.bcc


class EmailSender:
    """メール送信クライアント"""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    def send(self, email: Email) -> None:
        """メールを送信する"""
        if not email.to:
            raise EmailSendError("宛先が指定されていません")

        msg = self._build_message(email)

        try:
            self._send_via_smtp(msg, email.all_recipients())
            logger.info("メール送信完了: %s", email.subject)
        except smtplib.SMTPAuthenticationError as e:
            raise EmailSendError("SMTP認証に失敗しました") from e
        except smtplib.SMTPException as e:
            raise EmailSendError(f"SMTP送信エラー: {e}") from e

    def _build_message(self, email: Email) -> MIMEMultipart:
        """MIMEメッセージを構築"""
        msg = MIMEMultipart("alternative" if email.html_body else "mixed")
        msg["From"] = self._config.email
        msg["To"] = ", ".join(email.to)
        msg["Subject"] = email.subject

        if email.cc:
            msg["Cc"] = ", ".join(email.cc)

        msg.attach(MIMEText(email.body, "plain", "utf-8"))

        if email.html_body:
            msg.attach(MIMEText(email.html_body, "html", "utf-8"))

        for path in email.attachments:
            self._attach_file(msg, path)

        return msg

    def _attach_file(self, msg: MIMEMultipart, path: Path) -> None:
        """添付ファイルを追加"""
        if not path.exists():
            logger.warning("添付ファイルが見つかりません: %s", path)
            return

        try:
            data = path.read_bytes()
        except OSError as e:
            raise AttachmentError(f"ファイル読み込み失敗: {path}") from e

        part = MIMEBase("application", "octet-stream")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)
        logger.info("添付ファイル追加: %s", path.name)

    def _send_via_smtp(self, msg: MIMEMultipart, recipients: list[str]) -> None:
        """SMTPサーバー経由で送信"""
        connect = smtplib.SMTP_SSL if self._config.use_tls else smtplib.SMTP

        with connect(self._config.server, self._config.port) as server:
            server.login(self._config.email, self._config.password)
            server.sendmail(self._config.email, recipients, msg.as_string())


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    *,
    attachments: list[str] | None = None,
    html_body: str | None = None,
    config: SmtpConfig | None = None,
) -> None:
    """
    シンプルなメール送信関数

    Args:
        to: 宛先（単一または複数）
        subject: 件名
        body: 本文
        attachments: 添付ファイルパスのリスト
        html_body: HTML本文（オプション）
        config: SMTP設定（省略時は環境変数から取得）

    Raises:
        EmailSendError: 送信に失敗した場合
        ValueError: 設定が不正な場合
    """
    if config is None:
        config = SmtpConfig.from_env()

    email = Email(
        to=to if isinstance(to, list) else [to],
        subject=subject,
        body=body,
        html_body=html_body,
        attachments=[Path(p) for p in (attachments or [])],
    )

    sender = EmailSender(config)
    sender.send(email)


if __name__ == "__main__":
    # 開発用: 環境変数を設定してテスト
    # export SMTP_SERVER=smtp.example.com
    # export SMTP_PORT=465
    # export SMTP_EMAIL=your_email@example.com
    # export SMTP_PASSWORD=your_password

    send_email(
        to="recipient@example.com",
        subject="Daily Report",
        body="This is the daily report for today.",
        attachments=["path/to/attachment_file.pdf"],
    )
