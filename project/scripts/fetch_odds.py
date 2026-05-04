"""
オッズ取得スクリプト
レース直前のオッズデータを取得し、予測APIに渡す形式に変換して
JSON ファイルへ保存する

# 実行例
  # 特定レースのオッズを取得して保存
  python scripts/fetch_odds.py --jyo 01 --date 20240415 --race 1

  # 全レース一括取得（1日分）
  python scripts/fetch_odds.py --jyo 01 --date 20240415 --all-races

  # 取得したオッズを使って予測APIを呼ぶ
  python scripts/fetch_odds.py --jyo 01 --date 20240415 --race 1 --predict

# オッズファイルフォーマット
  data/odds/{YYYYMMDD}/{jyo_code}_race{no}.json
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import ODDS_DIR
from app.utils.logger import get_logger
from app.utils.retry import CircuitBreaker, CircuitOpenError, retry

logger = get_logger(__name__)

BASE_URL     = "https://www.boatrace.jp"
ODDS_URL     = f"{BASE_URL}/owpc/pc/race/oddstf"   # 3連単オッズページ
WIN_ODDS_URL = f"{BASE_URL}/owpc/pc/race/odds1tk"  # 単勝オッズページ
OUTPUT_DIR   = ODDS_DIR

_session = requests.Session()
_session.headers.update({
    "User-Agent": "BoatRaceResearcher/1.0 (educational; contact: your@email.com)",
    "Accept-Language": "ja,en;q=0.9",
})

# ---- サーキットブレーカー（オッズサイトへの過剰アクセスを防止） ----
_odds_cb = CircuitBreaker(
    name="boatrace-odds",
    failure_threshold=5,    # 5回連続失敗で OPEN
    recovery_timeout=120.0, # 2分後に HALF_OPEN へ
    success_threshold=2,    # 2回成功で CLOSED に復帰
)


# ============================================================
# 内部 HTTP ヘルパー（リトライ付き）
# ============================================================

@retry(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    backoff_factor=2.0,
    jitter=True,
    exceptions=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
)
def _get_with_retry(url: str, params: dict) -> requests.Response:
    """
    タイムアウト・接続エラー時にリトライする内部 GET ヘルパー。
    HTTPError (例: 404) はリトライしない。
    """
    resp = _session.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp


def _fetch_html(url: str, params: dict) -> str | None:
    """
    サーキットブレーカー経由で HTML を取得する共通ヘルパー。

    Returns:
        HTML 文字列、取得失敗時は None
    """
    try:
        resp = _odds_cb.execute(_get_with_retry, url, params)
        resp.encoding = resp.apparent_encoding
        return resp.text
    except CircuitOpenError as e:
        logger.error(f"サーキットブレーカー OPEN (オッズ取得スキップ): {e}")
        return None
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        logger.warning(f"HTTP {code} エラー: {url} params={params}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"リクエストエラー（リトライ上限到達）: {e}")
        return None


# ============================================================
# オッズ取得・パース
# ============================================================

def fetch_win_odds(
    jyo_code: str,
    race_date: str,
    race_no: int,
    dry_run: bool = False,
) -> dict[str, float]:
    """
    単勝オッズ（各艇の1着配当倍率）を取得する

    Args:
        jyo_code: 場コード（例: "01"）
        race_date: 開催日 YYYYMMDD形式
        race_no: レース番号（1〜12）
        dry_run: True の場合ダミーデータを返す

    Returns:
        艇番→オッズのdict（例: {"1": 2.3, "2": 5.8, ...}）
    """
    if dry_run:
        # ダミーオッズ（内側コースが低オッズ）
        logger.info(f"[DRY RUN] 単勝オッズ取得: 場={jyo_code}, 日={race_date}, R{race_no}")
        return {
            "1": 2.3, "2": 4.5, "3": 7.2,
            "4": 12.0, "5": 18.5, "6": 35.0,
        }

    params = {"hd": race_date, "jcd": jyo_code, "rno": race_no}
    html = _fetch_html(WIN_ODDS_URL, params)
    if html is None:
        return {}
    return _parse_win_odds(html)


def _parse_win_odds(html: str) -> dict[str, float]:
    """
    単勝オッズページをパースする

    NOTE: 実際のサイト構造に合わせてセレクタを修正してください
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    odds: dict[str, float] = {}

    # 仮のセレクタ（実際のHTML構造に合わせて修正が必要）
    rows = soup.select("table.is-w238 tbody tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) >= 2:
            try:
                boat_num = cells[0].get_text(strip=True)
                odds_val = float(cells[1].get_text(strip=True).replace("−", "0"))
                if boat_num.isdigit() and 1 <= int(boat_num) <= 6:
                    odds[boat_num] = odds_val
            except (ValueError, IndexError):
                continue

    return odds


def fetch_trifecta_odds(
    jyo_code: str,
    race_date: str,
    race_no: int,
    dry_run: bool = False,
) -> dict[str, float]:
    """
    三連単オッズを取得する（120通り）

    Args:
        jyo_code: 場コード
        race_date: 開催日 YYYYMMDD形式
        race_no: レース番号

    Returns:
        "1-2-3" 形式のキー→オッズのdict
    """
    if dry_run:
        logger.info(f"[DRY RUN] 三連単オッズ取得: 場={jyo_code}, 日={race_date}, R{race_no}")
        # ダミー三連単オッズを生成
        import random
        from itertools import permutations
        rng = random.Random(42)
        return {
            f"{a}-{b}-{c}": round(rng.uniform(5.0, 500.0), 1)
            for a, b, c in permutations(range(1, 7), 3)
        }

    params = {"hd": race_date, "jcd": jyo_code, "rno": race_no}
    html = _fetch_html(ODDS_URL, params)
    if html is None:
        return {}
    return _parse_trifecta_odds(html)


def _parse_trifecta_odds(html: str) -> dict[str, float]:
    """
    三連単オッズページをパースする

    NOTE: 実際のサイト構造に合わせてセレクタを修正してください
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    odds: dict[str, float] = {}

    # 仮のセレクタ
    cells = soup.select("td.oddsPoint")
    combos = soup.select("td.combi")

    for combo_cell, odds_cell in zip(combos, cells, strict=False):
        try:
            combo = combo_cell.get_text(strip=True).replace("=", "-")
            val_str = odds_cell.get_text(strip=True)
            if val_str and val_str != "−":
                odds[combo] = float(val_str)
        except (ValueError, AttributeError):
            continue

    return odds


# ============================================================
# 保存・読み込み
# ============================================================

def save_odds(
    odds_data: dict,
    jyo_code: str,
    race_date: str,
    race_no: int,
) -> Path:
    """
    オッズデータを JSON ファイルに保存する

    Args:
        odds_data: 保存するオッズ辞書
        jyo_code: 場コード
        race_date: 開催日
        race_no: レース番号

    Returns:
        保存したファイルのパス
    """
    out_dir = OUTPUT_DIR / race_date
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{jyo_code}_race{race_no:02d}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(odds_data, f, ensure_ascii=False, indent=2)

    logger.info(f"オッズを保存しました: {path}")
    return path


def load_odds(jyo_code: str, race_date: str, race_no: int) -> dict | None:
    """
    保存済みオッズを読み込む

    Args:
        jyo_code: 場コード
        race_date: 開催日
        race_no: レース番号

    Returns:
        オッズ辞書、ファイルが存在しない場合は None
    """
    path = OUTPUT_DIR / race_date / f"{jyo_code}_race{race_no:02d}.json"
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# API 連携
# ============================================================

def predict_with_odds(
    race_data: dict,
    win_odds: dict[str, float],
    api_url: str = "http://localhost:8000/api/v1/predict",
    api_key: str = "",
) -> dict | None:
    """
    オッズ情報を付加してAPIに予測を依頼する

    Args:
        race_data: レース情報辞書（boats/weather を含む）
        win_odds: 艇番→単勝オッズのdict
        api_url: 予測APIのURL
        api_key: API Key

    Returns:
        APIレスポンスのdict、失敗時は None
    """
    # オッズを race_data に埋め込む
    race_data["odds"] = win_odds

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        resp = requests.post(
            api_url,
            json={"race": race_data},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"API呼び出しに失敗しました: {e}")
        return None


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="競艇オッズ取得スクリプト")
    parser.add_argument("--jyo", type=str, required=True, help="場コード (例: 01)")
    parser.add_argument(
        "--date", type=str,
        default=date.today().strftime("%Y%m%d"),
        help="開催日 YYYYMMDD（デフォルト: 今日）",
    )
    parser.add_argument("--race", type=int, default=1, help="レース番号 (1〜12)")
    parser.add_argument("--all-races", action="store_true", help="全12レース取得")
    parser.add_argument("--dry-run", action="store_true", help="ダミーデータで動作確認")
    parser.add_argument("--predict", action="store_true", help="取得後にAPIへ予測依頼")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000/api/v1/predict")
    parser.add_argument("--api-key", type=str, default="", help="X-API-Key ヘッダー値")
    args = parser.parse_args()

    race_nos = list(range(1, 13)) if args.all_races else [args.race]

    for race_no in race_nos:
        logger.info(f"=== 場={args.jyo} 日={args.date} R{race_no} ===")

        # 単勝・三連単オッズを取得
        win_odds      = fetch_win_odds(args.jyo, args.date, race_no, dry_run=args.dry_run)
        trifecta_odds = fetch_trifecta_odds(args.jyo, args.date, race_no, dry_run=args.dry_run)

        odds_data = {
            "jyo_code": args.jyo,
            "race_date": args.date,
            "race_no": race_no,
            "win_odds": win_odds,
            "trifecta_odds": trifecta_odds,
        }

        # 保存
        path = save_odds(odds_data, args.jyo, args.date, race_no)
        print(f"保存: {path}")

        if win_odds:
            print("単勝オッズ:")
            for boat, odd in sorted(win_odds.items()):
                print(f"  {boat}号艇: {odd:.1f}倍")

        # API 予測（--predict フラグ時）
        if args.predict:
            # サンプルのレースデータ（実際は別途取得が必要）
            sample_race = {
                "boats": [
                    {
                        "boat_number": i,
                        "racer_rank": "B1",
                        "win_rate": 20.0,
                        "motor_score": 50.0,
                        "course_win_rate": 20.0,
                        "start_timing": 0.18,
                        "motor_2rate": 35.0,
                        "boat_2rate": 32.0,
                        "recent_3_avg": 3.5,
                    }
                    for i in range(1, 7)
                ],
                "weather": {"condition": "晴", "wind_speed": 2.0, "water_temp": 22.0},
            }
            result = predict_with_odds(sample_race, win_odds, args.api_url, args.api_key)
            if result:
                print("\n予測結果（推奨買い目）:")
                for rec in result.get("recommendations", []):
                    combo = "-".join(map(str, rec["combination"]))
                    print(
                        f"  {combo} | 確率={rec['probability']:.3f} "
                        f"| オッズ={rec['odds']:.1f} | EV={rec['expected_value']:.2f}"
                    )

        if not args.dry_run and len(race_nos) > 1:
            time.sleep(2)  # 礼儀正しいクロール間隔


if __name__ == "__main__":
    main()
