#!/usr/bin/env python3
"""

"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 定数 ---
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; sightcheck/1.0; +https://example.com)"
DEFAULT_TIMEOUT = 10  # 秒
MIN_INTERVAL = 5  # 秒

# --- データクラス ---
@dataclass
class Config:
    url: str = "https://example.com"
    selector: str = "div.content"
    output_file: Path = Path("elems_text.txt")
    check_interval: int = 20
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_json(cls, json_file: str | Path) -> "Config":
        """JSONファイルから設定を読み込み、Config を返す（見つからない/解析失敗時はデフォルトを返す）"""
        try:
            json_path = Path(json_file)
            if not json_path.exists():
                logging.info(f"設定ファイルが見つかりません: {json_file}（デフォルト設定を使用）")
                return cls()
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                url=str(data.get("url", cls.url)),
                selector=str(data.get("selector", cls.selector)),
                output_file=Path(data.get("output_file", str(cls.output_file))),
                check_interval=int(data.get("check_interval", cls.check_interval)),
                max_retries=int(data.get("max_retries", cls.max_retries)),
                retry_delay=int(data.get("retry_delay", cls.retry_delay)),
                timeout=int(data.get("timeout", cls.timeout)),
                user_agent=str(data.get("user_agent", cls.user_agent)),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"設定ファイルの読み込みに失敗しました（JSONエラー）: {e}。デフォルト設定を使用します。")
            return cls()
        except Exception as e:
            logging.exception(f"設定ファイル読み込み中に予期しないエラー: {e}。デフォルト設定を使用します。")
            return cls()

# --- ロギングセットアップ ---
def setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"sightcheck_{time.strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

# --- HTTP セッション作成（リトライ対応） ---
def create_session(config: Config) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": config.user_agent})
    retries = Retry(
        total=max(0, config.max_retries - 1),
        backoff_factor=max(0.1, config.retry_delay / 10.0),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# --- ファイル読込/書込 ---
def get_stored_content(file_path: Path) -> str:
    try:
        if file_path.exists() and file_path.stat().st_size > 0:
            text = file_path.read_text(encoding="utf-8")
            logging.info("既存ファイル読み込み: %s", str(file_path))
            return text
        logging.info("保存されている内容がありません: %s", str(file_path))
        return ""
    except Exception:
        logging.exception("既存ファイルの読み込みに失敗しました")
        return ""

def atomic_write(file_path: Path, content: str) -> None:
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # 一時ファイル経由でアトミックに書き込む
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(file_path.parent)) as tmp:
            tmp.write(content)
            tmp_name = tmp.name
        os.replace(tmp_name, str(file_path))
        logging.info("ファイルを安全に更新しました: %s", str(file_path))
    except Exception:
        logging.exception("ファイル書き込み中にエラーが発生しました")

# --- ウェブ取得と解析 ---
def fetch_website_content(session: requests.Session, config: Config) -> Optional[str]:
    """
    指定された URL を取得し、CSSセレクタにマッチした要素のテキストを返す。
    マッチする複数要素がある場合は結合して返す（間は改行）。
    None を返す場合は致命的なエラー（リクエスト失敗等）。
    空文字列を返す場合はセレクタにマッチしなかったケース。
    """
    try:
        logging.info("GET %s", config.url)
        resp = session.get(config.url, timeout=config.timeout)
        # HTTPエラーはここで扱う（ステータスによっては content を取得するが注意）
        if resp.status_code >= 400:
            logging.warning("HTTP ステータスコード %s を受け取りました。", resp.status_code)
            # 4xx/5xx はエラー扱いとする
            return None
        # 文字コードを推定して設定
        resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        elems = soup.select(config.selector)
        if not elems:
            logging.warning("セレクタに一致する要素が見つかりません: %s", config.selector)
            return ""
        # 各要素のテキストを改行で結合（必要ならここを加工）
        texts = [e.get_text(separator=" ", strip=True) for e in elems]
        combined = "\n".join(t for t in texts if t)
        logging.info("取得テキスト（先頭100文字）: %s", combined[:100].replace("\n", " ") + ("..." if len(combined) > 100 else ""))
        return combined
    except requests.RequestException:
        logging.exception("ウェブ取得中にリクエスト例外が発生しました")
        return None
    except Exception:
        logging.exception("HTML解析中に予期しないエラーが発生しました")
        return None

# --- 変更判定 ---
def content_changed(old_content: str, new_content: str) -> bool:
    # 正規化して比較（空白/改行をまとめる）
    old_norm = " ".join(old_content.split()) if old_content else ""
    new_norm = " ".join(new_content.split()) if new_content else ""
    return old_norm != new_norm

# --- 監視ロジック ---
def check_for_changes(session: requests.Session, config: Config) -> Tuple[bool, Optional[str]]:
    logging.info("チェック開始: %s", config.url)
    new_content = fetch_website_content(session, config)
    if new_content is None:
        logging.error("コンテンツ取得に失敗しました（None）。今回のチェックはスキップします。")
        return False, None
    old_content = get_stored_content(config.output_file)
    if content_changed(old_content, new_content):
        logging.info("コンテンツの変更を検出しました")
        atomic_write(config.output_file, new_content)
        return True, new_content
    logging.info("変更は検出されませんでした")
    return False, new_content

# --- 引数パース ---
def parse_arguments() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ウェブサイトの要素変更を監視し、変更時にファイルへ書き出します")
    p.add_argument("--config", "-c", type=str, default=DEFAULT_CONFIG_PATH, help="設定ファイル (JSON)")
    p.add_argument("--url", "-u", type=str, help="監視対象の URL (設定ファイルより優先)")
    p.add_argument("--selector", "-s", type=str, help="CSS セレクタ (設定ファイルより優先)")
    p.add_argument("--interval", "-i", type=int, help=f"チェック間隔（秒、最小 {MIN_INTERVAL}）")
    p.add_argument("--output", "-o", type=str, help="出力ファイルパス")
    p.add_argument("--max-retries", type=int, help="内部 HTTP リトライ回数（Session の retry を構成）")
    p.add_argument("--retry-delay", type=int, help="リトライのバックオフ係数（秒）")
    p.add_argument("--timeout", type=int, help="HTTP タイムアウト（秒）")
    return p.parse_args()

# --- メイン ---
def main() -> None:
    setup_logging()
    logging.info("サイト変更監視を開始します")
    args = parse_arguments()

    config = Config.from_json(args.config)

    # CLI 引数で上書き
    if args.url:
        config.url = args.url
    if args.selector:
        config.selector = args.selector
    if args.interval:
        config.check_interval = max(MIN_INTERVAL, args.interval)
    if args.output:
        config.output_file = Path(args.output)
    if args.max_retries is not None:
        config.max_retries = max(0, args.max_retries)
    if args.retry_delay is not None:
        config.retry_delay = max(0, args.retry_delay)
    if args.timeout is not None:
        config.timeout = max(1, args.timeout)

    logging.info("設定: url=%s selector=%s output=%s interval=%s max_retries=%s retry_delay=%s timeout=%s",
                 config.url, config.selector, str(config.output_file), config.check_interval,
                 config.max_retries, config.retry_delay, config.timeout)

    session = create_session(config)

    try:
        while True:
            changed, _ = check_for_changes(session, config)
            # 変更発生時の拡張ポイント：通知（メール/Slack等）をここに追加可能
            logging.info("次回チェックは %s 秒後です", config.check_interval)
            time.sleep(config.check_interval)
    except KeyboardInterrupt:
        logging.info("ユーザーによって監視が中断されました。")
    except Exception:
        logging.exception("致命的なエラーが発生しました。")
        raise

if __name__ == "__main__":
    main()
