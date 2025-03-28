import os
import shutil
import psutil
import schedule
import time
import logging
import smtplib
import typing
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import socket
import ssl
from logging.handlers import RotatingFileHandler

# 定数定義
MAX_FILE_AGE_DAYS = 30
DEFAULT_THRESHOLDS = {
    'cpu': 80,
    'memory': 80,
    'disk': 90
}

@dataclass
class EmailConfig:
    """メール設定を保持するデータクラス"""
    smtp_server: str
    smtp_port: int
    sender_email: str
    sender_password: str
    use_tls: bool = True

class ConfigurationError(Exception):
    """設定エラーを示すカスタム例外"""
    pass

def setup_logging(log_file: str, max_bytes: int = 10485760, backup_count: int = 5) -> None:
    """ログ設定をセットアップする
    
    Args:
        log_file: ログファイルのパス
        max_bytes: ログファイルの最大サイズ
        backup_count: 保持する過去ログファイル数
    """
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

class FileManager:
    """ファイル管理を行うクラス"""
    
    def __init__(self, source_dir: str, archive_dir: str):
        self.source_dir = Path(source_dir)
        self.archive_dir = Path(archive_dir)
        self._validate_directories()
        
        self.file_types: Dict[str, List[str]] = {
            'documents': ['.pdf', '.doc', '.docx', '.txt'],
            'images': ['.jpg', '.jpeg', '.png', '.gif'],
            'spreadsheets': ['.xls', '.xlsx', '.csv']
        }
    
    def _validate_directories(self) -> None:
        """ディレクトリの存在と権限を検証"""
        for directory in [self.source_dir, self.archive_dir]:
            if not directory.exists():
                try:
                    directory.mkdir(parents=True)
                except PermissionError as e:
                    raise ConfigurationError(
                        f"ディレクトリ {directory} の作成権限がありません: {e}"
                    )
            if not os.access(directory, os.W_OK):
                raise ConfigurationError(
                    f"ディレクトリ {directory} への書き込み権限がありません"
                )
    
    def organize_files(self) -> None:
        """ファイルを種類別に整理し、古いファイルをアーカイブする"""
        try:
            self._create_type_directories()
            self._move_files_to_type_directories()
            self._archive_old_files()
        except Exception as e:
            logging.error(f'ファイル整理中にエラーが発生: {str(e)}')
            raise

    def _create_type_directories(self) -> None:
        """ファイルタイプごとのディレクトリを作成"""
        for type_dir in self.file_types.keys():
            (self.source_dir / type_dir).mkdir(exist_ok=True)

    def _move_files_to_type_directories(self) -> None:
        """ファイルを適切なタイプのディレクトリに移動"""
        for file_path in self.source_dir.glob('*.*'):
            if not file_path.is_file():
                continue
                
            ext = file_path.suffix.lower()
            moved = False
            
            for type_name, extensions in self.file_types.items():
                if ext in extensions:
                    destination = self.source_dir / type_name / file_path.name
                    if destination.exists():
                        new_name = self._generate_unique_filename(destination)
                        destination = destination.with_name(new_name)
                    
                    shutil.move(str(file_path), str(destination))
                    logging.info(f'ファイル {file_path.name} を {type_name} ディレクトリに移動')
                    moved = True
                    break
            
            if not moved:
                logging.warning(f'未分類のファイル: {file_path.name}')

    def _generate_unique_filename(self, file_path: Path) -> str:
        """重複しないファイル名を生成"""
        counter = 1
        stem = file_path.stem
        suffix = file_path.suffix
        
        while file_path.with_name(f"{stem}_{counter}{suffix}").exists():
            counter += 1
            
        return f"{stem}_{counter}{suffix}"

    def _archive_old_files(self) -> None:
        """指定日数以上経過したファイルをアーカイブ"""
        current_time = datetime.now().timestamp()
        archive_threshold = MAX_FILE_AGE_DAYS * 24 * 3600

        for file_path in self.source_dir.rglob('*.*'):
            if not file_path.is_file():
                continue

            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > archive_threshold:
                    archive_path = self.archive_dir / file_path.relative_to(self.source_dir)
                    archive_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    if archive_path.exists():
                        new_name = self._generate_unique_filename(archive_path)
                        archive_path = archive_path.with_name(new_name)
                    
                    shutil.move(str(file_path), str(archive_path))
                    logging.info(f'ファイル {file_path.name} をアーカイブ')
            
            except (PermissionError, OSError) as e:
                logging.error(f'ファイル {file_path} のアーカイブ中にエラー: {str(e)}')

class SystemMonitor:
    """システムリソースを監視するクラス"""
    
    def __init__(self, 
                 threshold_cpu: int = DEFAULT_THRESHOLDS['cpu'],
                 threshold_memory: int = DEFAULT_THRESHOLDS['memory'],
                 threshold_disk: int = DEFAULT_THRESHOLDS['disk']):
        self._validate_thresholds(threshold_cpu, threshold_memory, threshold_disk)
        self.threshold_cpu = threshold_cpu
        self.threshold_memory = threshold_memory
        self.threshold_disk = threshold_disk
    
    @staticmethod
    def _validate_thresholds(*thresholds: int) -> None:
        """閾値の妥当性を検証"""
        for threshold in thresholds:
            if not 0 <= threshold <= 100:
                raise ValueError(f"閾値は0から100の間である必要があります: {threshold}")
    
    def check_resources(self) -> Optional[Dict[str, Any]]:
        """システムリソースを監視し、状態を返す"""
        try:
            cpu_percent = self._check_cpu()
            memory_stats = self._check_memory()
            disk_stats = self._check_disk()
            
            return {
                'cpu': cpu_percent,
                'memory': memory_stats,
                'disk': disk_stats
            }
        
        except Exception as e:
            logging.error(f'リソース監視中にエラーが発生: {str(e)}')
            return None
    
    def _check_cpu(self) -> float:
        """CPU使用率をチェック"""
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > self.threshold_cpu:
            logging.warning(f'高CPU使用率: {cpu_percent}%')
        return cpu_percent
    
    def _check_memory(self) -> Dict[str, float]:
        """メモリ使用状況をチェック"""
        memory = psutil.virtual_memory()
        if memory.percent > self.threshold_memory:
            logging.warning(f'高メモリ使用率: {memory.percent}%')
        
        return {
            'total': memory.total / (1024 ** 3),  # GB
            'available': memory.available / (1024 ** 3),  # GB
            'percent': memory.percent
        }
    
    def _check_disk(self) -> Dict[str, Dict[str, float]]:
        """ディスク使用状況をチェック"""
        disk_stats = {}
        for partition in psutil.disk_partitions(all=False):
            try:
                if not partition.mountpoint or partition.mountpoint.startswith('/dev'):
                    continue
                    
                usage = psutil.disk_usage(partition.mountpoint)
                if usage.percent > self.threshold_disk:
                    logging.warning(
                        f'高ディスク使用率 {partition.mountpoint}: {usage.percent}%'
                    )
                
                disk_stats[partition.mountpoint] = {
                    'total': usage.total / (1024 ** 3),  # GB
                    'used': usage.used / (1024 ** 3),  # GB
                    'free': usage.free / (1024 ** 3),  # GB
                    'percent': usage.percent
                }
            
            except PermissionError:
                logging.warning(
                    f'パーティション {partition.mountpoint} へのアクセス権限がありません'
                )
                continue
        
        return disk_stats

class ReportGenerator:
    """システムレポートを生成し送信するクラス"""
    
    def __init__(self, email_config: EmailConfig):
        self.email_config = email_config
        self._validate_email_config()
    
    def _validate_email_config(self) -> None:
        """メール設定の妥当性を検証"""
        try:
            socket.gethostbyname(self.email_config.smtp_server)
        except socket.gaierror as e:
            raise ConfigurationError(f"SMTPサーバーの名前解決に失敗: {e}")
    
    def generate_system_report(self, system_stats: Optional[Dict[str, Any]]) -> str:
        """システム状態レポートを生成"""
        if not system_stats:
            return "システム統計を取得できませんでした。"
        
        report_lines = [
            "システムリソース使用状況レポート",
            f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"CPU使用率: {system_stats['cpu']:.1f}%\n",
            "メモリ使用状況:",
            f"  総容量: {system_stats['memory']['total']:.1f} GB",
            f"  使用可能: {system_stats['memory']['available']:.1f} GB",
            f"  使用率: {system_stats['memory']['percent']:.1f}%\n",
            "ディスク使用状況:"
        ]
        
        for mount_point, stats in system_stats['disk'].items():
            report_lines.extend([
                f"  マウントポイント: {mount_point}",
                f"    総容量: {stats['total']:.1f} GB",
                f"    使用中: {stats['used']:.1f} GB",
                f"    空き容量: {stats['free']:.1f} GB",
                f"    使用率: {stats['percent']:.1f}%\n"
            ])
        
        return "\n".join(report_lines)
    
    def send_report(self, recipient_email: str, report_content: str) -> None:
        """レポートをメール送信"""
        if not self._is_valid_email(recipient_email):
            raise ValueError(f"不正なメールアドレス: {recipient_email}")
        
        msg = self._create_email_message(recipient_email, report_content)
        
        try:
            self._send_email(msg)
            logging.info(f'レポートを {recipient_email} に送信しました')
        
        except Exception as e:
            logging.error(f'レポート送信中にエラーが発生: {str(e)}')
            raise
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """メールアドレスの簡易バリデーション"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _create_email_message(self, recipient_email: str, report_content: str) -> MIMEMultipart:
        """メールメッセージを作成"""
        msg = MIMEMultipart()
        msg['From'] = self.email_config.sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f'システム状態レポート - {datetime.now().strftime("%Y-%m-%d")}'
        msg.attach(MIMEText(report_content, 'plain'))
        return msg
    
    def _send_email(self, msg: MIMEMultipart) -> None:
        """SMTPを使用してメールを送信"""
        context = ssl.create_default_context()
        
        with smtplib.SMTP(
            self.email_config.smtp_server,
            self.email_config.smtp_port
        ) as server:
            if self.email_config.use_tls:
                server.starttls(context=context)
            server.login(
                self.email_config.sender_email,
                self.