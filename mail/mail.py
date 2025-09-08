import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 465
SENDER_EMAIL = "your_email@example.com"
SENDER_PASSWORD = "your_password"
RECEIVER_EMAIL = "recipient@example.com"


def send_email(
    subject: str,
    body: str,
    attachments: Optional[List[str]] = None,
    sender_email: str = SENDER_EMAIL,
    sender_password: str = SENDER_PASSWORD,
    receiver_email: str = RECEIVER_EMAIL,
    smtp_server: str = SMTP_SERVER,
    smtp_port: int = SMTP_PORT
) -> None:
    """
    メールを送信する関数

    :param subject: メール件名
    :param body: 本文
    :param attachments: 添付ファイルのパスリスト
    :param sender_email: 送信元アドレス
    :param sender_password: 送信元パスワード
    :param receiver_email: 送信先アドレス
    :param smtp_server: SMTPサーバ
    :param smtp_port: SMTPポート
    """
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # 添付ファイル処理
    if attachments:
        for path in attachments:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{os.path.basename(path)}"'
                        )
                        msg.attach(part)
                        logging.info(f"添付ファイルを追加: {path}")
                except OSError as e:
                    logging.error(f"ファイルを開けませんでした: {path} - {e}")

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
            logging.info("メールが正常に送信されました。")
    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP認証に失敗しました。")
    except smtplib.SMTPException as e:
        logging.error(f"SMTPエラーが発生しました: {e}")
    except Exception as e:
        logging.exception(f"予期しないエラーが発生しました: {e}")


if __name__ == "__main__":
    send_email(
        subject="Daily Report",
        body="This is the daily report for today.",
        attachments=["path/to/attachment_file.pdf"]
    )