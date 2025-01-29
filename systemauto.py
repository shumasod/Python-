import os
import shutil
import psutil
import schedule
import time
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# ログ設定
logging.basicConfig(
    filename='system_automation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class FileManager:
    def __init__(self, source_dir, archive_dir):
        self.source_dir = Path(source_dir)
        self.archive_dir = Path(archive_dir)
        
    def organize_files(self):
        """ファイルを種類別に整理し、古いファイルをアーカイブする"""
        try:
            # ファイルタイプごとのディレクトリを作成
            file_types = {
                'documents': ['.pdf', '.doc', '.docx', '.txt'],
                'images': ['.jpg', '.jpeg', '.png', '.gif'],
                'spreadsheets': ['.xls', '.xlsx', '.csv']
            }
            
            for type_dir in file_types.keys():
                (self.source_dir / type_dir).mkdir(exist_ok=True)
            
            # ファイルの振り分け
            for file_path in self.source_dir.glob('*.*'):
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    for type_name, extensions in file_types.items():
                        if ext in extensions:
                            destination = self.source_dir / type_name / file_path.name
                            shutil.move(str(file_path), str(destination))
                            logging.info(f'Moved {file_path.name} to {type_name} directory')
                            
            self._archive_old_files()
            
        except Exception as e:
            logging.error(f'Error in organize_files: {str(e)}')

    def _archive_old_files(self):
        """30日以上前のファイルをアーカイブする"""
        try:
            current_time = datetime.now().timestamp()
            archive_threshold = 30 * 24 * 3600  # 30日

            for file_path in self.source_dir.rglob('*.*'):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > archive_threshold:
                        archive_path = self.archive_dir / file_path.relative_to(self.source_dir)
                        archive_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(file_path), str(archive_path))
                        logging.info(f'Archived {file_path.name}')
                        
        except Exception as e:
            logging.error(f'Error in archive_old_files: {str(e)}')

class SystemMonitor:
    def __init__(self, threshold_cpu=80, threshold_memory=80, threshold_disk=90):
        self.threshold_cpu = threshold_cpu
        self.threshold_memory = threshold_memory
        self.threshold_disk = threshold_disk
        
    def check_resources(self):
        """システムリソースを監視し、閾値を超えた場合に警告を記録"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.threshold_cpu:
                logging.warning(f'High CPU usage: {cpu_percent}%')
                
            # メモリ使用率
            memory = psutil.virtual_memory()
            if memory.percent > self.threshold_memory:
                logging.warning(f'High memory usage: {memory.percent}%')
                
            # ディスク使用率
            for partition in psutil.disk_partitions():
                try:
                    disk_usage = psutil.disk_usage(partition.mountpoint)
                    if disk_usage.percent > self.threshold_disk:
                        logging.warning(f'High disk usage on {partition.mountpoint}: {disk_usage.percent}%')
                except PermissionError:
                    continue
                    
            return {
                'cpu': cpu_percent,
                'memory': memory.percent,
                'disk': {partition.mountpoint: psutil.disk_usage(partition.mountpoint).percent
                        for partition in psutil.disk_partitions()
                        if not partition.mountpoint.startswith('/dev')}
            }
            
        except Exception as e:
            logging.error(f'Error in check_resources: {str(e)}')
            return None

class ReportGenerator:
    def __init__(self, smtp_server, smtp_port, sender_email, sender_password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        
    def generate_system_report(self, system_stats):
        """システム状態レポートを生成"""
        if not system_stats:
            return "システム統計を取得できませんでした。"
            
        report = []
        report.append("システムリソース使用状況レポート")
        report.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        report.append(f"CPU使用率: {system_stats['cpu']}%")
        report.append(f"メモリ使用率: {system_stats['memory']}%")
        
        report.append("\nディスク使用率:")
        for mount_point, usage in system_stats['disk'].items():
            report.append(f"  {mount_point}: {usage}%")
            
        return "\n".join(report)
        
    def send_report(self, recipient_email, report_content):
        """レポートをメール送信"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f'システム状態レポート - {datetime.now().strftime("%Y-%m-%d")}'
            
            msg.attach(MIMEText(report_content, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            logging.info('Report sent successfully')
            
        except Exception as e:
            logging.error(f'Error sending report: {str(e)}')

def main():
    # 設定
    SOURCE_DIR = '/path/to/source'
    ARCHIVE_DIR = '/path/to/archive'
    SMTP_SERVER = 'smtp.example.com'
    SMTP_PORT = 587
    SENDER_EMAIL = 'sender@example.com'
    SENDER_PASSWORD = 'your_password'
    RECIPIENT_EMAIL = 'recipient@example.com'
    
    # インスタンス作成
    file_manager = FileManager(SOURCE_DIR, ARCHIVE_DIR)
    system_monitor = SystemMonitor()
    report_generator = ReportGenerator(SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD)
    
    def daily_tasks():
        """毎日実行するタスク"""
        # ファイル整理
        file_manager.organize_files()
        
        # システムリソース確認とレポート送信
        stats = system_monitor.check_resources()
        if stats:
            report = report_generator.generate_system_report(stats)
            report_generator.send_report(RECIPIENT_EMAIL, report)
    
    # スケジュール設定
    schedule.every().day.at("00:00").do(daily_tasks)
    
    # メインループ
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Process terminated by user")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")