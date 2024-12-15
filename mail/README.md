日報メールを自動送信するPythonスクリプトを作成するための手順と設定方法を説明します。このスクリプトでは、SMTPを使用してメールを送信します。

### 1. 必要なライブラリのインストール

Pythonでメールを送信するには、標準ライブラリの`smtplib`と`email`を使用します。これらは通常Pythonに含まれていますが、必要に応じてインストールすることもできます。

```bash
pip install secure-smtplib
```

### 2. スクリプトの作成

以下に、日報メールを送信するPythonスクリプトの基本的な作成方法を示します。

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

def send_daily_report_email():
    # 送信元の設定
    sender_email = "your_email@example.com"
    sender_password = "your_password"

    # 送信先の設定
    receiver_email = "recipient@example.com"

    # メールの構築
    subject = "Daily Report"
    body = "This is the daily report for today."

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # 添付ファイルの追加（オプション）
    attachment_path = "path/to/attachment_file.pdf"
    if os.path.exists(attachment_path):
        filename = os.path.basename(attachment_path)
        attachment = open(attachment_path, "rb")
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename= {filename}')
        msg.attach(part)

    # SMTPサーバに接続してメール送信
    try:
        server = smtplib.SMTP_SSL('smtp.example.com', 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        print("メールが送信されました。")
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
    finally:
        server.quit()

# メイン関数
if __name__ == "__main__":
    send_daily_report_email()
```

### 3. スクリプトの設定とカスタマイズ

- **SMTPサーバの設定**: `smtplib.SMTP_SSL('smtp.example.com', 465)` の部分を、自分のSMTPサーバの設定に合わせて変更してください。
- **送信元メールアドレスとパスワード**: `sender_email` と `sender_password` には、送信に使用するメールアカウントのメールアドレスとパスワードを設定してください。
- **送信先メールアドレス**: `receiver_email` には、日報を送信する相手のメールアドレスを設定します。
- **メールの内容**: `subject` と `body` には、送信するメールの件名と本文を設定します。
- **添付ファイルの追加**: 必要に応じて、日報に添付するファイルのパスを `attachment_path` に設定します。

### 4. スクリプトの実行

設定が完了したら、スクリプトを実行してメールが送信されることを確認します。エラーが発生した場合は、エラーメッセージを確認し、設定やコードの修正を行います。

このスクリプトを定期的に実行する場合は、タスクスケジューラやcronなどのシステムのスケジューリング機能を利用して、自動的に実行するように設定します。
