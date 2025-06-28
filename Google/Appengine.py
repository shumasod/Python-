#!/usr/bin/env python3

import logging
import os
import subprocess
import sys
from typing import Optional

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeploymentError(Exception):
    """デプロイメント関連のエラーを処理するカスタム例外クラス"""
    pass

def validate_directory(app_directory: str) -> None:
    """
    デプロイ対象ディレクトリの妥当性を検証します
    
    Args:
        app_directory: 検証するディレクトリパス
        
    Raises:
        DeploymentError: ディレクトリが存在しないか、app.yamlが見つからない場合
    """
    if not os.path.isdir(app_directory):
        raise DeploymentError(f"指定されたディレクトリが存在しません: {app_directory}")
    
    yaml_path = os.path.join(app_directory, "app.yaml")
    if not os.path.isfile(yaml_path):
        raise DeploymentError(f"app.yamlが見つかりません: {yaml_path}")

def deploy_appengine(app_directory: str) -> Optional[str]:
    """
    App Engine へのデプロイを実行します
    
    Args:
        app_directory: デプロイ対象のアプリケーションディレクトリ
        
    Returns:
        デプロイ成功時のログ出力、失敗時はNone
        
    Raises:
        DeploymentError: デプロイ処理中にエラーが発生した場合
    """
    try:
        validate_directory(app_directory)
        
        deploy_command = f"gcloud app deploy {app_directory}/app.yaml"
        logger.info(f"デプロイを開始: {deploy_command}")
        
        result = subprocess.run(
            deploy_command,
            shell=True,
            check=True,
            text=True,
            capture_output=True
        )
        
        logger.info("デプロイが正常に完了しました")
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        logger.error(f"デプロイコマンドの実行に失敗: {e.stderr}")
        raise DeploymentError(f"デプロイ処理でエラーが発生: {e.stderr}")
        
def main() -> None:
    """メイン実行関数"""
    if len(sys.argv) != 2:
        logger.error("引数が不正です")
        print("使用法: python deploy_appengine.py <アプリケーションのディレクトリ>")
        sys.exit(1)
        
    try:
        app_directory = sys.argv[1]
        output = deploy_appengine(app_directory)
        print(output)
        
    except DeploymentError as e:
        logger.error(str(e))
        sys.exit(1)
        
    except Exception as e:
        logger.exception("予期せぬエラーが発生しました")
        sys.exit(1)

if __name__ == "__main__":
    main()
