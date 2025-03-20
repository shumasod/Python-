import time
import requests
from bs4 import BeautifulSoup
import logging
import os
import argparse
import sys
from typing import Optional, Tuple
import hashlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("site_monitor.log")
    ]
)

logger = logging.getLogger(__name__)

class SiteMonitor:
    """
    指定されたウェブサイトの特定要素を監視するクラス。
    変更があったときに通知します。
    """
    
    def __init__(self, url: str, selector: str, file_path: str, interval: int = 20, 
                 timeout: int = 10, max_retries: int = 3):
        """
        モニターを初期化します。
        
        Args:
            url: 監視するウェブサイトのURL
            selector: 監視するHTML要素のCSSセレクタ
            file_path: 以前の要素の状態を保存するファイルパス
            interval: チェック間隔（秒）
            timeout: リクエストタイムアウト（秒）
            max_retries: リクエスト失敗時の最大再試行回数
        """
        self.url = url
        self.selector = selector
        self.file_path = file_path
        self.interval = interval
        self.timeout = timeout
        
        # 再試行設定でセッションを作成
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,  # 再試行間の待機時間を指数関数的に増加
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # ユーザーエージェントを設定してボットと識別されにくくする
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def _get_stored_content(self) -> Tuple[str, str]:
        """
        保存されている以前の要素の内容とそのハッシュを取得します。
        
        Returns:
            Tuple[str, str]: 保存された内容とそのSHA-256ハッシュ
        """
        try:
            if os.path.exists(self.file_path) and os.path.getsize(self.file_path) > 0:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    logger.info(f'保存された内容を取得しました ({len(content)} 文字, ハッシュ: {content_hash[:8]}...)')
                return content, content_hash
            else:
                logger.info('以前の内容が見つからないか、ファイルが空です')
                return '', ''
        except Exception as e:
            logger.error(f"ファイル {self.file_path} の読み込みエラー: {e}")
            return '', ''

    def _fetch_current_content(self) -> Tuple[Optional[str], Optional[str]]:
        """
        ウェブサイトから現在の要素の内容を取得します。
        
        Returns:
            Tuple[Optional[str], Optional[str]]: 取得した内容とそのSHA-256ハッシュ、または失敗時はNone
        """
        try:
            response = self.session.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            
            response.encoding = response.apparent_encoding
            bs = BeautifulSoup(response.text, 'html.parser')
            elements = bs.select(self.selector)
            
            if not elements:
                logger.warning(f"セレクタに一致する要素が見つかりません: {self.selector}")
                return None, None
                
            content = str(elements)
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            logger.info(f'現在の内容を取得しました ({len(content)} 文字, ハッシュ: {content_hash[:8]}...)')
            return content, content_hash
        except requests.RequestException as e:
            logger.error(f"リクエストエラー: {e}")
            return None, None
        except Exception as e:
            logger.error(f"要素取得エラー: {e}")
            return None, None

    def _update_stored_content(self, content: str) -> bool:
        """
        新しい内容をファイルに保存します。
        
        Args:
            content: 保存する内容
            
        Returns:
            bool: 保存が成功したかどうか
        """
        try:
            # バックアップを作成
            if os.path.exists(self.file_path):
                backup_path = f"{self.file_path}.bak"
                try:
                    os.replace(self.file_path, backup_path)
                    logger.info(f"バックアップを作成しました: {backup_path}")
                except Exception as e:
                    logger.warning(f"バックアップの作成に失敗しました: {e}")
            
            # 新しい内容を書き込み
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"新しい内容を {self.file_path} に保存しました")
            return True
        except Exception as e:
            logger.error(f"ファイル {self.file_path} の更新エラー: {e}")
            return False

    def check_for_changes(self) -> bool:
        """
        現在の内容と保存された内容を比較して変更を検出します。
        
        Returns:
            bool: 変更が検出されたかどうか
        """
        logger.info(f"{self.url} の変更をチェックします (セレクタ: {self.selector})")
        
        # 以前の内容を取得
        old_content, old_hash = self._get_stored_content()
        
        # 現在の内容を取得
        new_content, new_hash = self._fetch_current_content()
        
        # 取得に失敗した場合
        if new_content is None:
            logger.warning("取得エラーのため比較をスキップします")
            return False
            
        # 変更を検出
        if old_hash != new_hash:
            logger.info(f"変更を検出しました! (旧ハッシュ: {old_hash[:8]}..., 新ハッシュ: {new_hash[:8]}...)")
            self._update_stored_content(new_content)
            return True
        else:
            logger.info("変更は検出されませんでした")
            return False

    def start_monitoring(self):
        """
        モニタリングループを開始します。
        """
        logger.info(f"{self.url} のウェブサイト変更監視を開始します")
        logger.info(f"{self.interval}秒ごとにチェックします")
        logger.info(f"停止するには Ctrl+C を押してください")
        
        try:
            while True:
                logger.info("=" * 50)
                self.check_for_changes()
                logger.info(f"次のチェックまで {self.interval} 秒待機します...")
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("ユーザーによって監視が停止されました")
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            logger.exception("詳細なエラー情報:")


def parse_arguments():
    """
    コマンドライン引数を解析します。
    
    Returns:
        argparse.Namespace: パース済みの引数
    """
    parser = argparse.ArgumentParser(description="ウェブサイトの要素変更を監視します")
    parser.add_argument("-u", "--url", default="https://example.com", 
                        help="監視するURL (デフォルト: https://example.com)")
    parser.add_argument("-s", "--selector", 
                        default="div.newUserPageProfile_info_body.newUserPageProfile_description", 
                        help="監視する要素のCSSセレクタ")
    parser.add_argument("-f", "--file", default="elems_text.txt", 
                        help="以前の状態を保存するファイル (デフォルト: elems_text.txt)")
    parser.add_argument("-i", "--interval", type=int, default=20, 
                        help="チェック間隔（秒） (デフォルト: 20)")
    parser.add_argument("-t", "--timeout", type=int, default=10, 
                        help="リクエストタイムアウト（秒） (デフォルト: 10)")
    parser.add_argument("-r", "--retries", type=int, default=3, 
                        help="リクエスト失敗時の最大再試行回数 (デフォルト: 3)")
    parser.add_argument("-l", "--log-level", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        default="INFO", help="ログレベル (デフォルト: INFO)")
    return parser.parse_args()


def main():
    """
    メイン関数。コマンドライン引数を解析し、モニタリングを開始します。
    """
    args = parse_arguments()
    
    # ログレベルを設定
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # モニターを作成して開始
    monitor = SiteMonitor(
        url=args.url,
        selector=args.selector,
        file_path=args.file,
        interval=args.interval,
        timeout=args.timeout,
        max_retries=args.retries
    )
    monitor.start_monitoring()


if __name__ == '__main__':
    main()
