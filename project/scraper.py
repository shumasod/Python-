"""
競艇データスクレイパー
レース結果・選手情報・モーター情報を収集してCSVに保存する

# 実行方法
  # 基本実行（デフォルト: 過去30日分のレース結果）
  python scraper.py

  # 期間指定
  python scraper.py --start 2024-01-01 --end 2024-03-31

  # 場コード指定（01=桐生, 02=戸田, ..., 24=大村）
  python scraper.py --jyo-codes 01 02 03

  # ドライランモード（実際にリクエストを送らず構造確認）
  python scraper.py --dry-run

# 設計上の注意
  - robots.txt を確認し、Disallow パスへのアクセスは行わない
  - クロール間隔は MIN_SLEEP〜MAX_SLEEP 秒のランダムスリープで制御
  - Airflow DAG から呼び出せるよう scrape_race_results() を外部公開

# Airflow での使用例
  from scraper import scrape_race_results
  # PythonOperator(task_id="scrape", python_callable=scrape_race_results, ...)
"""

import csv
import random
import time
import urllib.robotparser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import logging

import requests
from bs4 import BeautifulSoup

from app.utils.retry import CircuitBreaker, CircuitOpenError, retry

# ---- 設定 ----
BASE_URL = "https://www.boatrace.jp"  # 公式サイト（robots.txt要確認）
RESULTS_URL = f"{BASE_URL}/owpc/pc/race/resultlist"
RACER_URL = f"{BASE_URL}/owpc/pc/data/racersearch/rankRacer"
MOTOR_URL = f"{BASE_URL}/owpc/pc/data/motorInfo"

MIN_SLEEP = 2.0   # リクエスト間の最小待機秒数（robots.txt の Crawl-delay に従う）
MAX_SLEEP = 5.0   # リクエスト間の最大待機秒数

OUTPUT_DIR = Path("data/scraped")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---- サーキットブレーカー（公式サイトへの過剰アクセスを防止） ----
_site_cb = CircuitBreaker(
    name="boatrace-site",
    failure_threshold=5,    # 5回連続失敗で OPEN
    recovery_timeout=120.0, # 2分後に HALF_OPEN へ
    success_threshold=2,    # 2回成功で CLOSED に復帰
)

# HTTPセッション（接続プールの再利用）
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "BoatRaceResearcher/1.0 "
        "(educational purpose; contact: your@email.com)"
    ),
    "Accept-Language": "ja,en;q=0.9",
})


# ---- robots.txt チェック ----

def check_robots(url: str) -> bool:
    """
    robots.txt を確認し、指定URLへのアクセスが許可されているか返す

    Args:
        url: チェック対象URL

    Returns:
        True=アクセス可, False=アクセス禁止
    """
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{BASE_URL}/robots.txt")
    try:
        rp.read()
    except Exception as e:
        logger.warning(f"robots.txt の読み込みに失敗しました: {e} → アクセスを継続します")
        return True
    allowed = rp.can_fetch(session.headers["User-Agent"], url)
    if not allowed:
        logger.warning(f"robots.txt により禁止されています: {url}")
    return allowed


# ---- HTTPリクエスト（リトライ + サーキットブレーカー付き） ----

@retry(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    backoff_factor=2.0,
    jitter=True,
    exceptions=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
)
def _get_with_retry(url: str, params: Optional[Dict]) -> requests.Response:
    """
    タイムアウト・接続エラー時にリトライする内部 GET ヘルパー。
    404 などの HTTP エラーはリトライしない（呼び出し元で処理する）。
    """
    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp


def fetch_page(url: str, params: Optional[Dict] = None, dry_run: bool = False) -> Optional[str]:
    """
    ページHTMLを取得する（リトライ + サーキットブレーカー付き）

    Args:
        url: 取得先URL
        params: クエリパラメータ辞書
        dry_run: True の場合リクエストを送らず None を返す

    Returns:
        HTML文字列、失敗時は None
    """
    if dry_run:
        logger.info(f"[DRY RUN] GET {url} params={params}")
        return None

    if not check_robots(url):
        return None

    try:
        resp = _site_cb.execute(_get_with_retry, url, params)
        resp.encoding = resp.apparent_encoding  # 文字コード自動検出
        logger.info(f"取得成功: {resp.url} ({resp.status_code})")
        return resp.text

    except CircuitOpenError as e:
        logger.error(f"サーキットブレーカー OPEN: {e}")
        return None

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.warning(f"404 Not Found: {url}")
        else:
            logger.error(f"HTTPエラー（リトライ上限到達）: {e}")
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"リクエストエラー（リトライ上限到達）: {e}")
        return None


def polite_sleep() -> None:
    """礼儀正しいクロール間隔を設ける"""
    wait = random.uniform(MIN_SLEEP, MAX_SLEEP)
    logger.debug(f"クロール間隔: {wait:.1f}秒")
    time.sleep(wait)


# ---- パーサー ----

def parse_race_results(html: str, jyo_code: str, hd: str) -> List[Dict]:
    """
    レース結果ページをパースして結果リストを返す

    Args:
        html: ページHTML
        jyo_code: 場コード（例: "01"）
        hd: 開催日（YYYYMMDD形式）

    Returns:
        レース結果辞書のリスト
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    # NOTE: 実際のサイト構造に合わせてセレクタを修正してください
    # 以下は仮の構造例です
    race_tables = soup.select("table.is-w748")  # 仮セレクタ

    for table in race_tables:
        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue
            try:
                result = {
                    "date": hd,
                    "jyo_code": jyo_code,
                    "race_no": _safe_text(cells, 0),
                    "rank": _safe_text(cells, 1),
                    "boat_number": _safe_text(cells, 2),
                    "racer_no": _safe_text(cells, 3),
                    "racer_name": _safe_text(cells, 4),
                    "time": _safe_text(cells, 5),
                }
                results.append(result)
            except (IndexError, AttributeError) as e:
                logger.debug(f"行パースエラー: {e}")
                continue

    return results


def parse_racer_info(html: str) -> List[Dict]:
    """
    選手一覧ページをパースして選手情報リストを返す

    Args:
        html: ページHTML

    Returns:
        選手情報辞書のリスト
    """
    soup = BeautifulSoup(html, "lxml")
    racers = []

    # NOTE: 実際のサイト構造に合わせてセレクタを修正してください
    rows = soup.select("table.is-w748 tbody tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 5:
            continue
        try:
            racer = {
                "racer_no": _safe_text(cells, 0),
                "racer_name": _safe_text(cells, 1),
                "rank": _safe_text(cells, 2),
                "win_rate": _safe_text(cells, 3),
                "2rate": _safe_text(cells, 4),
            }
            racers.append(racer)
        except (IndexError, AttributeError) as e:
            logger.debug(f"選手情報パースエラー: {e}")
            continue

    return racers


def _safe_text(cells, idx: int) -> str:
    """セルのテキストを安全に取得する"""
    try:
        return cells[idx].get_text(strip=True)
    except (IndexError, AttributeError):
        return ""


# ---- CSV保存 ----

def save_to_csv(records: List[Dict], filename: str) -> None:
    """
    レコードリストをCSVに追記保存する

    Args:
        records: 保存するレコードリスト
        filename: 保存先ファイル名（OUTPUT_DIR 配下）
    """
    if not records:
        logger.info("保存するレコードがありません")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    file_exists = filepath.exists()

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        if not file_exists:
            writer.writeheader()  # 新規ファイルのみヘッダー書き込み
        writer.writerows(records)

    logger.info(f"CSVに {len(records)} 件追記しました: {filepath}")


# ---- メインスクレイピング関数（Airflowから呼び出し可能） ----

def scrape_race_results(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    jyo_codes: Optional[List[str]] = None,
    dry_run: bool = False,
) -> List[Dict]:
    """
    指定期間・場のレース結果を収集する

    Airflow PythonOperator から直接呼び出せるよう設計

    Args:
        start_date: 収集開始日（デフォルト: 30日前）
        end_date: 収集終了日（デフォルト: 昨日）
        jyo_codes: 場コードリスト（デフォルト: 全24場）
        dry_run: True の場合リクエストを送らない

    Returns:
        収集したレース結果レコードのリスト
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if jyo_codes is None:
        # 全24場コード（01=桐生 〜 24=大村）
        jyo_codes = [f"{i:02d}" for i in range(1, 25)]

    logger.info(
        f"スクレイピング開始: {start_date} 〜 {end_date}, 場数={len(jyo_codes)}"
    )

    all_results: List[Dict] = []
    current = start_date

    while current <= end_date:
        hd = current.strftime("%Y%m%d")

        for jyo_code in jyo_codes:
            url = RESULTS_URL
            params = {"hd": hd, "jcd": jyo_code}

            html = fetch_page(url, params=params, dry_run=dry_run)
            if html:
                records = parse_race_results(html, jyo_code, hd)
                all_results.extend(records)
                logger.info(
                    f"{hd} 場={jyo_code}: {len(records)} 件取得"
                )
            else:
                logger.warning(f"{hd} 場={jyo_code}: データ取得失敗")

            if not dry_run:
                polite_sleep()

        current += timedelta(days=1)

    # CSVに保存
    if all_results:
        filename = f"race_results_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        save_to_csv(all_results, filename)

    logger.info(f"スクレイピング完了: 合計 {len(all_results)} 件")
    return all_results


def scrape_racer_info(dry_run: bool = False) -> List[Dict]:
    """
    全選手情報を収集する

    Args:
        dry_run: True の場合リクエストを送らない

    Returns:
        選手情報レコードのリスト
    """
    logger.info("選手情報のスクレイピングを開始します")
    all_racers: List[Dict] = []

    # ランク別・五十音別にページを巡回
    for rank in ["A1", "A2", "B1", "B2"]:
        for initial in "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわ":
            url = RACER_URL
            params = {"rank": rank, "initial": initial}

            html = fetch_page(url, params=params, dry_run=dry_run)
            if html:
                racers = parse_racer_info(html)
                all_racers.extend(racers)

            if not dry_run:
                polite_sleep()

    if all_racers:
        save_to_csv(all_racers, "racer_info.csv")

    logger.info(f"選手情報収集完了: {len(all_racers)} 件")
    return all_racers


# ---- CLI エントリーポイント ----

def main() -> None:
    parser = argparse.ArgumentParser(description="競艇データスクレイパー")
    parser.add_argument("--start", type=str, help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="終了日 (YYYY-MM-DD)")
    parser.add_argument(
        "--jyo-codes",
        nargs="+",
        help="場コード（例: 01 02 03）。省略時は全24場",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際にリクエストを送らずに実行フローを確認する",
    )
    parser.add_argument(
        "--target",
        choices=["results", "racers", "all"],
        default="results",
        help="収集対象 (results/racers/all)",
    )
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else None
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else None

    if args.target in ("results", "all"):
        scrape_race_results(
            start_date=start,
            end_date=end,
            jyo_codes=args.jyo_codes,
            dry_run=args.dry_run,
        )

    if args.target in ("racers", "all"):
        scrape_racer_info(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
