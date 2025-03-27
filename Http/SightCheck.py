import time
import requests
from bs4 import BeautifulSoup
import logging
import os
import json
from typing import Optional, Dict, Any, Tuple
import argparse
from dataclasses import dataclass
from pathlib import Path

# データクラスを使用して設定を整理
@dataclass
class Config:
    """ウェブサイト監視の設定を保持するクラス"""
    url: str
    selector: str
    output_file: Path
    check_interval: int
    max_retries: int
    retry_delay: int

    @classmethod
    def from_json(cls, json_file: str) -> 'Config':
        """JSONファイルから設定を読み込む"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(
                url=config_data.get('url', 'https://example.com'),
                selector=config_data.get('selector', 'div.content'),
                output_file=Path(config_data.get('output_file', 'elems_text.txt')),
                check_interval=config_data.get('check_interval', 20),
                max_retries=config_data.get('max_retries', 3),
                retry_delay=config_data.get('retry_delay', 5)
            )
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"設定ファイル読み込みエラー: {e}")
            # デフォルト設定を返す
            return cls(
                url='https://example.com',
                selector='div.content',
                output_file=Path('elems_text.txt'),
                check_interval=20,
                max_retries=3,
                retry_delay=5
            )

def setup_logging() -> None:
    """ロギングの設定"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"sightcheck_{time.strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def get_stored_content(file_path: Path) -> str:
    """保存されている以前の要素を取得します
    
    Args:
        file_path: 保存ファイルのパス
        
    Returns:
        str: 保存されていた内容（ファイルが存在しない場合は空文字列）
    """
    try:
        if file_path.exists() and file_path.stat().st_size > 0:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logging.info(f'保存内容: {content[:50]}...' if len(content) > 50 else f'保存内容: {content}')
            return content
        else:
            logging.info('保存されている内容が見つかりませんでした')
            return ''
    except Exception as e:
        logging.error(f"ファイル読み込みエラー: {e}")
        return ''

def fetch_website_content(config: Config) -> Optional[str]:
    """ウェブサイトから要素を取得します
    
    Args:
        config: 監視設定
        
    Returns:
        Optional[str]: 取得した要素のテキスト。エラー時はNone
    """
    for attempt in range(config.max_retries):
        try:
            logging.info(f"ウェブサイト取得試行 {attempt + 1}/{config.max_retries}")
            response = requests.get(config.url, timeout=10)
            response.raise_for_status()
            
            response.encoding = response.apparent_encoding
            bs = BeautifulSoup(response.text, 'html.parser')
            elements = bs.select(config.selector)
            
            if not elements:
                logging.warning(f"指定されたセレクタに一致する要素が見つかりません: {config.selector}")
                return ""
                
            content = elements[0].get_text(strip=True) if len(elements) > 0 else ""
            logging.info(f'取得内容: {content[:50]}...' if len(content) > 50 else f'取得内容: {content}')
            return content
            
        except requests.RequestException as e:
            logging.error(f"リクエストエラー: {e}")
            if attempt < config.max_retries - 1:
                logging.info(f"{config.retry_delay}秒後に再試行します...")
                time.sleep(config.retry_delay)
            else:
                logging.error("最大試行回数に達しました。処理を続行します。")
                return None
        except Exception as e:
            logging.error(f"要素取得エラー: {e}")
            return None

def content_changed(old_content: str, new_content: str) -> bool:
    """コンテンツが変更されたかどうかを確認します
    
    Args:
        old_content: 以前のコンテンツ
        new_content: 新しいコンテンツ
        
    Returns:
        bool: 変更があった場合はTrue、なければFalse
    """
    # 空白やタブ、改行を正規化して比較
    old_normalized = ' '.join(old_content.split())
    new_normalized = ' '.join(new_content.split())
    
    return old_normalized != new_normalized

def update_stored_content(file_path: Path, content: str) -> None:
    """ファイルに新しい内容を保存します
    
    Args:
        file_path: 保存先ファイルパス
        content: 保存する内容
    """
    try:
        # ディレクトリが存在しない場合は作成
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info("変更を検出しました。ファイルを更新しました。")
    except IOError as e:
        logging.error(f"ファイル書き込みエラー: {e}")

def check_for_changes(config: Config) -> Tuple[bool, Optional[str]]:
    """ウェブサイトの変更を確認します
    
    Args:
        config: 監視設定
        
    Returns:
        Tuple[bool, Optional[str]]: 
            - 変更があったかどうか
            - 新しい内容（エラー時はNone）
    """
    logging.info("=" * 50)
    logging.info(f"ウェブサイト {config.url} をチェック中...")
    
    new_content = fetch_website_content(config)
    if new_content is None:
        return False, None
        
    old_content = get_stored_content(config.output_file)
    
    if content_changed(old_content, new_content):
        update_stored_content(config.output_file, new_content)
        return True, new_content
    else:
        logging.info("変更は検出されませんでした")
        return False, new_content

def parse_arguments() -> argparse.Namespace:
    """コマンドライン引数をパースします"""
    parser = argparse.ArgumentParser(description='ウェブサイトの変更を監視します')
    parser.add_argument('--config', '-c', type=str, default='config.json',
                        help='設定ファイルのパス (デフォルト: config.json)')
    parser.add_argument('--url', '-u', type=str,
                        help='監視するウェブサイトのURL')
    parser.add_argument('--selector', '-s', type=str,
                        help='監視するHTML要素のCSS3セレクタ')
    parser.add_argument('--interval', '-i', type=int,
                        help='確認間隔（秒）')
    parser.add_argument('--output', '-o', type=str,
                        help='出力ファイルパス')
    return parser.parse_args()

def main() -> None:
    """メイン処理ループ"""
    setup_logging()
    logging.info("ウェブサイト変更監視を開始します...")
    
    args = parse_arguments()
    
    # 設定読み込み
    config = Config.from_json(args.config)
    
    # コマンドライン引数で上書き
    if args.url:
        config.url = args.url
    if args.selector:
        config.selector = args.selector
    if args.interval:
        config.check_interval = args.interval
    if args.output:
        config.output_file = Path(args.output)
    
    logging.info(f"設定: URL={config.url}, セレクタ={config.selector}, "
                 f"確認間隔={config.check_interval}秒, 出力ファイル={config.output_file}")
    
    try:
        while True:
            changed, _ = check_for_changes(config)
            # 変更があった場合は追加の処理をここに実装できます
            
            logging.info(f"{config.check_interval}秒後に次の確認を行います...")
            time.sleep(config.check_interval)
    except KeyboardInterrupt:
        logging.info("ユーザーによって監視が停止されました")
    except Exception as e:
        logging.error(f"予期しないエラー: {e}")
        raise

if __name__ == '__main__':
    main()
