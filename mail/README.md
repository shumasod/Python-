# 日報メール自動送信スクリプト

日報メールを自動送信するPythonスクリプトの作成・設定方法を説明します。

## 必要要件

- Python 3.6以上
- 送信用メールアカウント（Gmail、Outlook等）

## 1. 必要なライブラリ

基本的な機能は標準ライブラリのみで実装可能ですが、追加機能用のライブラリをインストールすることもできます。

```bash
# 環境変数管理用（推奨）
pip install python-dotenv

# スケジュール実行用（オプション）
pip install schedule
```

## 2. 環境変数の設定

セキュリティのため、認証情報は環境変数で管理します。

### .envファイルの作成

```bash
# .env
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=recipient@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

**重要**: `.env`ファイルは必ず`.gitignore`に追加してください。

## 3. メインスクリプト

### daily_report.py

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

def create_daily_report_content():
    """日報の内容を生成"""
    today = datetime.now().strftime("%Y年%m月%d日")
    
    report_content = f"""
    【日報】 {today}
    
    ■ 本日の業務内容
    1. プロジェクトA: 設計書の作成（進捗率: 80%）
    2. プロジェクトB: コードレビュー対応
    3. 定例ミーティング参加（14:00-15:00）
    
    ■ 完了タスク
    - 機能Xの実装完了
    - バグ#123の修正
    
    ■ 明日の予定
    - プロジェクトA: 設計書の完成
    - テストケースの作成
    
    ■ 課題・相談事項
    - 特になし
    
    以上、よろしくお願いいたします。
    """
    
    return report_content

def send_daily_report_email():
    """日報メールを送信"""
    
    # 環境変数から設定を取得
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    receiver_email = os.getenv('RECEIVER_EMAIL')
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    
    # 設定の検証
    if not all([sender_email, sender_password, receiver_email]):
        raise ValueError("必要な環境変数が設定されていません")
    
    # 日付を含む件名
    today = datetime.now().strftime("%Y/%m/%d")
    subject = f"【日報】{today} - {sender_email.split('@')[0]}"
    
    # メールの作成
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    
    # 本文の追加
    body = create_daily_report_content()
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # 添付ファイルの追加（オプション）
    attachment_path = "reports/daily_report.pdf"
    if os.path.exists(attachment_path):
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            filename = os.path.basename(attachment_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )
            msg.attach(part)
    
    # メール送信
    server = None
    try:
        # SMTPサーバーへの接続
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # TLS暗号化を開始
        server.login(sender_email, sender_password)
        
        # メール送信
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        
        print(f"✅ 日報メールを送信しました: {receiver_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ 認証エラー: メールアドレスまたはパスワードが正しくありません")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP エラー: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラー: {str(e)}")
        return False
    finally:
        if server:
            server.quit()

if __name__ == "__main__":
    send_daily_report_email()
```

## 4. 主要メールプロバイダーの設定

### Gmail
```python
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
# アプリパスワードの生成が必要
# https://myaccount.google.com/apppasswords
```

### Outlook/Hotmail
```python
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
```

### Yahoo Mail
```python
SMTP_SERVER=smtp.mail.yahoo.co.jp
SMTP_PORT=587
```

## 5. 自動実行の設定

### Linuxの場合（crontab）

```bash
# crontabを編集
crontab -e

# 毎日18:00に実行
0 18 * * * /usr/bin/python3 /path/to/daily_report.py
```

### Windowsの場合（タスクスケジューラ）

1. タスクスケジューラを開く
2. 「基本タスクの作成」を選択
3. トリガーで「毎日」を選択し、時刻を設定
4. 操作で「プログラムの開始」を選択
5. Pythonスクリプトのパスを指定

### Pythonでスケジュール実行

```python
# scheduler.py
import schedule
import time
from daily_report import send_daily_report_email

def job():
    send_daily_report_email()

# 毎日18:00に実行
schedule.every().day.at("18:00").do(job)

print("スケジューラーを開始しました...")
while True:
    schedule.run_pending()
    time.sleep(60)
```

## 6. セキュリティに関する注意事項

1. **パスワード管理**
   - 直接コードにパスワードを記載しない
   - 環境変数またはシークレット管理ツールを使用

2. **アプリパスワード**
   - Gmailなど2段階認証を使用している場合は、アプリ専用パスワードを生成

3. **アクセス制限**
   - `.env`ファイルのアクセス権限を適切に設定
   - `chmod 600 .env`（Linuxの場合）

## 7. トラブルシューティング

### よくあるエラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| SMTPAuthenticationError | 認証失敗 | アプリパスワードの確認、2段階認証の設定 |
| Connection refused | ポート番号が間違っている | SMTP設定の確認 |
| SSL/TLS Error | 暗号化設定の問題 | starttls()の使用、ポート番号の確認 |

### デバッグモード

```python
import logging

# デバッグログを有効化
logging.basicConfig(level=logging.DEBUG)
smtplib.set_debuglevel(1)
```

## 8. 拡張機能のアイデア

- HTMLメールの送信（MIMEText with 'html'）
- 複数の宛先への送信（CC、BCC）
- テンプレートエンジンの使用（Jinja2）
- データベースからの情報取得
- Slack/Teams通知との連携

