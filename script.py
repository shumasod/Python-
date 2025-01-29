from pathlib import Path
import logging
from typing import List, Optional
import shutil
import os
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PathOperations:
    """パス操作のユーティリティクラス"""
    
    @staticmethod
    def get_path_info(path: Path) -> None:
        """パス情報を表示する安全な方法"""
        try:
            logging.info(f"絶対パス: {path.absolute()}")
            logging.info(f"現在のディレクトリ: {Path.cwd()}")
            logging.info(f"ホームディレクトリ: {Path.home()}")
            logging.info(f"ファイル名: {path.name}")
            logging.info(f"親ディレクトリ: {path.parent}")
        except Exception as e:
            logging.error(f"パス情報の取得中にエラーが発生: {e}")

    @staticmethod
    def safe_path_operation(base_path: Path, operation: str, 
                          target: Optional[str] = None) -> Optional[Path]:
        """安全なパス操作を行う"""
        try:
            if operation == "join" and target:
                return base_path / target
            elif operation == "parent":
                return base_path.parent
            elif operation == "absolute":
                return base_path.absolute()
            else:
                logging.warning(f"未知の操作: {operation}")
                return None
        except Exception as e:
            logging.error(f"パス操作中にエラーが発生: {e}")
            return None

    @staticmethod
    def find_files(directory: Path, pattern: str) -> List[Path]:
        """指定パターンのファイルを安全に検索"""
        try:
            return list(directory.glob(pattern))
        except Exception as e:
            logging.error(f"ファイル検索中にエラーが発生: {e}")
            return []

class FileOperations:
    """ファイル操作のユーティリティクラス"""
    
    @staticmethod
    def get_file_info(file_path: Path) -> dict:
        """ファイルの詳細情報を取得"""
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"ファイルが存在しません: {file_path}")
                
            stat = file_path.stat()
            return {
                "name": file_path.name,
                "suffix": file_path.suffix,
                "stem": file_path.stem,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "permissions": oct(stat.st_mode),
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir()
            }
        except Exception as e:
            logging.error(f"ファイル情報の取得中にエラーが発生: {e}")
            return {}

    @staticmethod
    def safe_file_operation(file_path: Path, operation: str, 
                          content: Optional[str] = None,
                          mode: Optional[int] = None) -> bool:
        """安全なファイル操作を実行"""
        try:
            if operation == "write" and content is not None:
                file_path.write_text(content)
                logging.info(f"ファイルに書き込み完了: {file_path}")
                return True
                
            elif operation == "read":
                content = file_path.read_text()
                logging.info(f"ファイルから読み込み完了: {file_path}")
                return True
                
            elif operation == "chmod" and mode is not None:
                file_path.chmod(mode)
                logging.info(f"パーミッション変更完了: {file_path}")
                return True
                
            else:
                logging.warning(f"未知の操作: {operation}")
                return False
                
        except PermissionError as e:
            logging.error(f"権限エラー: {e}")
            return False
        except Exception as e:
            logging.error(f"ファイル操作中にエラーが発生: {e}")
            return False

class BackupManager:
    """ファイルバックアップ管理クラス"""
    
    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self) -> None:
        """バックアップディレクトリの存在を確認・作成"""
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.error(f"バックアップディレクトリの作成に失敗: {e}")
            raise

    def create_backup(self, file_path: Path) -> Optional[Path]:
        """ファイルのバックアップを作成"""
        if not file_path.exists():
            logging.error(f"バックアップ対象が存在しません: {file_path}")
            return None
            
        try:
            # タイムスタンプ付きのバックアップファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self.backup_dir / backup_name
            
            # ファイルをバックアップ
            shutil.copy2(file_path, backup_path)
            logging.info(f"バックアップ作成完了: {backup_path}")
            return backup_path
            
        except Exception as e:
            logging.error(f"バックアップ作成中にエラーが発生: {e}")
            return None

def main():
    """使用例の実演"""
    try:
        # パス操作の例
        path_ops = PathOperations()
        test_file = Path("test.txt")
        path_ops.get_path_info(test_file)
        
        # ファイル検索の例
        current_dir = Path.cwd()
        python_files = path_ops.find_files(current_dir, "*.py")
        logging.info(f"見つかったPythonファイル: {python_files}")
        
        # ファイル操作の例
        file_ops = FileOperations()
        
        # ファイル作成とバックアップ
        test_file.write_text("テストコンテンツ")
        file_info = file_ops.get_file_info(test_file)
        logging.info(f"ファイル情報: {file_info}")
        
        # バックアップの作成
        backup_manager = BackupManager(Path("backups"))
        backup_path = backup_manager.create_backup(test_file)
        
        if backup_path:
            logging.info(f"バックアップ完了: {backup_path}")
        
    except Exception as e:
        logging.error(f"実行中にエラーが発生: {e}")

if __name__ == "__main__":
    main()