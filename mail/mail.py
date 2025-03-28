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
