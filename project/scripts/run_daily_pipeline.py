"""
日次予測パイプライン
毎日実行し、対象場・レースの予測を行い結果を記録・通知する

実行例:
  # 今日の桐生 全12レースをサンプルデータで予測
  python scripts/run_daily_pipeline.py --jyo 01 --dry-run

  # 指定日・複数場を実際のオッズで予測してSlack通知
  python scripts/run_daily_pipeline.py --jyo 01 02 06 --date 20260420

  # 予測ログだけ保存（通知なし）
  python scripts/run_daily_pipeline.py --jyo 01 --dry-run --no-notify
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import PREDICTION_LOG_DIR
from app.model.predict import predict_race
from app.utils.logger import get_logger
from app.utils.notification import notify_sync

logger = get_logger(__name__)

# 全競艇場コード（01=桐生 … 24=若松）
ALL_JYO_CODES = [f"{i:02d}" for i in range(1, 25)]


# ============================================================
# サンプルレースデータ生成
# ============================================================

def build_sample_race_data(
    jyo_code: str,
    race_no: int,
    win_odds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    実データがない場合のサンプルレース情報を組み立てる。
    win_odds があればそのオッズを埋め込む。
    """
    rng = numpy_rng(jyo_code, race_no)

    boats = []
    for boat_no in range(1, 7):
        boats.append({
            "boat_number": boat_no,
            "racer_rank":  ["A1", "A2", "B1", "B2"][rng.integers(0, 4)],
            "win_rate":    float(rng.uniform(10, 35)),
            "motor_score": float(rng.uniform(40, 65)),
            "course_win_rate": float(rng.uniform(5, 45)),
            "start_timing":    float(rng.uniform(0.10, 0.25)),
            "motor_2rate":     float(rng.uniform(20, 55)),
            "boat_2rate":      float(rng.uniform(20, 50)),
            "recent_3_avg":    float(rng.uniform(1.5, 5.5)),
        })

    race: Dict[str, Any] = {
        "boats":   boats,
        "weather": {
            "condition":  "晴",
            "wind_speed":  float(rng.uniform(0, 6)),
            "water_temp":  float(rng.uniform(15, 30)),
        },
    }
    if win_odds:
        race["odds"] = win_odds
    return race


def numpy_rng(jyo_code: str, race_no: int):
    """再現可能な乱数生成器（場コード×レース番号をシードに使用）"""
    import numpy as np
    seed = int(jyo_code) * 100 + race_no
    return np.random.default_rng(seed)


# ============================================================
# 単レース予測
# ============================================================

def run_race_prediction(
    jyo_code: str,
    race_date: str,
    race_no: int,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    1レースの予測を実行し、結果dictを返す。
    失敗した場合は None を返す（パイプライン全体は止めない）。
    """
    race_id = f"{race_date}_{jyo_code}_R{race_no:02d}"

    # オッズ取得
    win_odds: Optional[Dict[str, float]] = None
    if not dry_run:
        try:
            from scripts.fetch_odds import fetch_win_odds
            win_odds = fetch_win_odds(jyo_code, race_date, race_no)
        except Exception as exc:
            logger.warning(f"オッズ取得失敗 {race_id}: {exc}")

    # レースデータ組み立て
    race_data = build_sample_race_data(jyo_code, race_no, win_odds)
    race_data["race_id"] = race_id

    # 予測
    try:
        result = predict_race(race_data)
    except FileNotFoundError:
        logger.error("モデルが未学習です。先に scripts/train_model.py を実行してください。")
        return None
    except Exception as exc:
        logger.error(f"予測失敗 {race_id}: {exc}")
        return None

    prediction_log = {
        "race_id":          race_id,
        "jyo_code":         jyo_code,
        "race_date":        race_date,
        "race_no":          race_no,
        "predicted_at":     datetime.now(timezone.utc).isoformat(),
        "win_probabilities": result["win_probabilities"],
        "top1_boat":        int(result["win_probabilities"].index(
                                max(result["win_probabilities"]))) + 1,
        "trifecta_top3":    [t["combination"] for t in result["trifecta"][:3]],
        "win_odds":         win_odds or {},
        "dry_run":          dry_run,
    }
    return prediction_log


# ============================================================
# 予測ログ保存
# ============================================================

def save_prediction_log(log: Dict[str, Any]) -> Path:
    """予測ログを JSON ファイルに保存する。ファイルパスを返す。"""
    PREDICTION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = PREDICTION_LOG_DIR / f"{log['race_id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return path


# ============================================================
# 通知サマリー構築
# ============================================================

def build_daily_summary(
    results: List[Dict[str, Any]],
    jyo_codes: List[str],
    race_date: str,
) -> str:
    """当日の全予測をまとめた通知メッセージを組み立てる。"""
    n_total  = len(results)
    n_failed = sum(1 for r in results if r is None)
    valid    = [r for r in results if r is not None]

    lines = [
        f"🏁 競艇予想AI 日次レポート ({race_date})",
        f"場コード: {', '.join(jyo_codes)}",
        f"予測レース: {n_total}  成功: {n_total - n_failed}  失敗: {n_failed}",
        "",
    ]

    for log in valid[:5]:  # 先頭5レースのみ詳細表示
        proba = log["win_probabilities"]
        lines.append(
            f"  {log['race_id']} → 1位予測: {log['top1_boat']}号艇 "
            f"({proba[log['top1_boat'] - 1] * 100:.1f}%)"
        )

    if len(valid) > 5:
        lines.append(f"  ... 他 {len(valid) - 5} レース")

    return "\n".join(lines)


# ============================================================
# メイン
# ============================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="競艇予想 日次パイプライン")
    p.add_argument(
        "--jyo", nargs="+", default=["01"],
        metavar="JYO_CODE",
        help="場コード（スペース区切りで複数指定可 例: 01 06 24）",
    )
    p.add_argument(
        "--date",
        default=date.today().strftime("%Y%m%d"),
        help="開催日 YYYYMMDD（省略時: 今日）",
    )
    p.add_argument(
        "--races", nargs="+", type=int,
        default=list(range(1, 13)),
        help="レース番号（省略時: 全12レース）",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="HTTP リクエストなし・サンプルデータで動作確認",
    )
    p.add_argument(
        "--no-notify", action="store_true",
        help="Slack/LINE 通知を送らない",
    )
    p.add_argument(
        "--no-save", action="store_true",
        help="予測ログを保存しない",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(f"=== 日次予測パイプライン開始: {args.date} 場={args.jyo} ===")

    all_results: List[Optional[Dict[str, Any]]] = []

    for jyo_code in args.jyo:
        for race_no in args.races:
            log = run_race_prediction(
                jyo_code=jyo_code,
                race_date=args.date,
                race_no=race_no,
                dry_run=args.dry_run,
            )
            all_results.append(log)

            if log and not args.no_save:
                path = save_prediction_log(log)
                logger.debug(f"保存: {path}")

    # 集計
    n_ok   = sum(1 for r in all_results if r is not None)
    n_fail = len(all_results) - n_ok
    print(f"\n予測完了: {n_ok}/{len(all_results)} 成功  失敗: {n_fail}")

    # 通知
    if not args.no_notify and n_ok > 0:
        msg = build_daily_summary(all_results, args.jyo, args.date)
        notify_sync(msg)
        logger.info("通知を送信しました")

    logger.info("=== 日次予測パイプライン完了 ===")


if __name__ == "__main__":
    main()
