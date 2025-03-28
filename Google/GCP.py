#!/usr/bin/env python3

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional, Dict

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GCPError(Exception):
    """GCP操作関連のエラー用カスタム例外"""
    pass

class GCPMonitor:
    def __init__(self, project_id: str, service_name: str, version: str, bucket_name: str):
        self.project_id = project_id
        self.service_name = service_name
        self.version = version
        self.bucket_name = bucket_name
        self.storage_client = storage.Client()

    def get_app_engine_endpoint(self) -> Optional[str]:
        """
        App Engineのエンドポイントを取得
        
        Returns:
            str: エンドポイントURL
            
        Raises:
            GCPError: GCPコマンド実行エラー時
        """
        try:
            command = [
                'gcloud', 'app', 'services', 'describe',
                self.service_name,
                '--project', self.project_id,
                '--format', 'json'
            ]
            
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            service_info = json.loads(result.stdout)
            
            for version in service_info.get('versions', []):
                if version.get('id') == self.version:
                    return version.get('versionUrl')
                    
            logger.warning(f"Version {self.version} not found")
            return None
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            raise GCPError(f"エンドポイント取得エラー: {str(e)}")

    def save_log(self, log_data: str) -> str:
        """
        ログをCloud Storageに保存
        
        Args:
            log_data: 保存するログデータ
            
        Returns:
            str: 保存したファイルのパス
            
        Raises:
            GCPError: ストレージ操作エラー時
        """
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            filename = f"log_{timestamp}.txt"
            
            blob = bucket.blob(filename)
            blob.upload_from_string(log_data)
            
            logger.info(f"ログを保存: gs://{self.bucket_name}/{filename}")
            return filename
            
        except GoogleCloudError as e:
            raise GCPError(f"ログ保存エラー: {str(e)}")

    def cleanup_old_logs(self, days: int = 90) -> None:
        """
        古いログを削除
        
        Args:
            days: 保持する日数
            
        Raises:
            GCPError: ストレージ操作エラー時
        """
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            cutoff = datetime.now(timezone.utc)
            
            for blob in bucket.list_blobs():
                age = (cutoff - blob.time_created).days
                if age >= days:
                    blob.delete()
                    logger.info(f"古いログを削除: {blob.name}")
                    
        except GoogleCloudError as e:
            raise GCPError(f"ログ削除エラー: {str(e)}")

def main() -> None:
    """メイン実行関数"""
    # 設定値（本番環境では環境変数やConfigから読み込む）
    config = {
        'project_id': 'your_gcp_project_id',
        'service_name': 'your_app_engine_service_name',
        'version': 'your_app_engine_version',
        'bucket_name': 'your_cloud_storage_bucket_name'
    }

    try:
        monitor = GCPMonitor(**config)
        endpoint = monitor.get_app_engine_endpoint()
        
        if not endpoint:
            logger.error("エンドポイントが取得できません")
            sys.exit(1)
            
        logger.info(f"App Engine エンドポイント: {endpoint}")
        
        log_data = f"Monitoring App Engine Endpoint: {endpoint}"
        monitor.save_log(log_data)
        monitor.cleanup_old_logs()
        
    except GCPError as e:
        logger.error(str(e))
        sys.exit(1)
        
    except Exception as e:
        logger.exception("予期せぬエラーが発生")
        sys.exit(1)

if __name__ == "__main__":
    main()
