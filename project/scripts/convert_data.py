"""
スクレイピングデータ → 学習用CSV 変換スクリプト

scraper.py が生成した生データ（race_results_*.csv, racer_info.csv）を
app/model/features.py の FEATURE_COLUMNS 形式に変換する

実行例:
  # デフォルト（data/scraped/ 配下を全て処理）
  python scripts/convert_data.py

  # 入力ディレクトリを指定
  python scripts/convert_data.py --input-dir data/scraped --output data/training.csv

  # サマリーのみ表示（変換しない）
  python scripts/convert_data.py --dry-run
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import DEFAULT_TRAINING_CSV, SCRAPED_DIR
from app.model.features import FEATURE_COLUMNS
from app.utils.logger import get_logger

logger = get_logger(__name__)

OUTPUT_PATH = DEFAULT_TRAINING_CSV


# ============================================================
# 読み込み
# ============================================================

def load_race_results(input_dir: Path) -> pd.DataFrame:
    """
    scraper.py が生成した race_results_*.csv を結合して読み込む

    Args:
        input_dir: スクレイピングデータのディレクトリ

    Returns:
        結合済み DataFrame（空の場合は空DataFrame）
    """
    csv_files = list(input_dir.glob("race_results_*.csv"))
    if not csv_files:
        logger.warning(f"race_results_*.csv が見つかりません: {input_dir}")
        return pd.DataFrame()

    dfs = []
    for f in sorted(csv_files):
        df = pd.read_csv(f, encoding="utf-8")
        dfs.append(df)
        logger.info(f"  読み込み: {f.name} ({len(df)} 行)")

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"レース結果: {len(combined)} 行 (ファイル数: {len(csv_files)})")
    return combined


def load_racer_info(input_dir: Path) -> pd.DataFrame:
    """
    racer_info.csv を読み込む

    Args:
        input_dir: スクレイピングデータのディレクトリ

    Returns:
        選手情報 DataFrame
    """
    path = input_dir / "racer_info.csv"
    if not path.exists():
        logger.warning(f"racer_info.csv が見つかりません: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path, encoding="utf-8")
    logger.info(f"選手情報: {len(df)} 行")
    return df


# ============================================================
# 変換・特徴量生成
# ============================================================

def build_training_rows(
    results: pd.DataFrame,
    racers: pd.DataFrame,
) -> pd.DataFrame:
    """
    レース結果 + 選手情報 を学習用の1行=1艇フォーマットに変換する

    Args:
        results: load_race_results() の出力
        racers: load_racer_info() の出力

    Returns:
        FEATURE_COLUMNS + ["label", "race_id"] を持つ DataFrame
    """
    if results.empty:
        logger.error("レース結果データが空です")
        return pd.DataFrame()

    logger.info("学習データへの変換を開始します...")

    # 選手情報をインデックス化（racer_no → dict）
    racer_map: dict = {}
    if not racers.empty and "racer_no" in racers.columns:
        racer_map = racers.set_index("racer_no").to_dict("index")

    rows = []

    # レース単位でグループ化（date + jyo_code + race_no）
    group_cols = [c for c in ["date", "jyo_code", "race_no"] if c in results.columns]
    if not group_cols:
        logger.error("グループ化に必要なカラム（date/jyo_code/race_no）が見つかりません")
        return pd.DataFrame()

    for group_key, group in results.groupby(group_cols):
        if len(group) < 6:
            continue  # 6艇揃っていないレースはスキップ

        # 1着艇番を特定（rank==1）
        winner_rows = group[group["rank"].astype(str) == "1"]
        if winner_rows.empty:
            continue
        winner_boat = int(winner_rows.iloc[0]["boat_number"])

        for _, row in group.iterrows():
            boat_num = int(row.get("boat_number", 0))
            racer_no = str(row.get("racer_no", ""))
            racer_info = racer_map.get(racer_no, {})

            # 選手ランク（racer_info になければ B1 で補完）
            rank_str = racer_info.get("rank", "B1") or "B1"

            # 勝率（racer_info にあれば使用、なければ 0）
            win_rate = float(racer_info.get("win_rate", 0.0) or 0.0)
            rate_2   = float(racer_info.get("2rate", 0.0) or 0.0)

            feature_row = {
                "win_rate":       win_rate,
                "motor_score":    50.0,       # モータースコアは別途取得が必要
                "course_win_rate": _course_win_rate(boat_num),
                "start_timing":   0.18,        # STは別途取得が必要
                "weather_code":   0,            # 天候は別途取得が必要
                "wind_speed":     0.0,
                "water_temp":     20.0,
                "boat_number":    boat_num,
                "racer_rank":     _encode_rank(rank_str),
                "motor_2rate":    35.0,
                "boat_2rate":     rate_2,
                "recent_3_avg":   3.5,
                # ラベル: 1着艇番(1始まり) → クラス(0始まり)
                "label":          winner_boat - 1,
                "race_id":        "_".join(str(k) for k in (group_key if isinstance(group_key, tuple) else [group_key])),
            }
            rows.append(feature_row)

    df = pd.DataFrame(rows)
    logger.info(f"変換完了: {len(df)} 行 ({len(df) // 6 if len(df) >= 6 else 0} レース)")
    return df


def _course_win_rate(boat_number: int) -> float:
    """枠番別のデフォルト勝率（コースアドバンテージを近似）"""
    defaults = {1: 42.0, 2: 18.0, 3: 14.0, 4: 10.0, 5: 8.5, 6: 7.5}
    return defaults.get(boat_number, 10.0)


def _encode_rank(rank: str) -> int:
    """選手ランクを数値に変換"""
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4}.get(rank.upper(), 3)


# ============================================================
# 品質チェック
# ============================================================

def validate_training_data(df: pd.DataFrame) -> dict:
    """
    学習データの品質チェックを行う

    Args:
        df: 変換後のDataFrame

    Returns:
        チェック結果辞書
    """
    issues = []

    if df.empty:
        return {"ok": False, "issues": ["データが空です"]}

    # ラベル分布チェック（極端な偏りがないか）
    label_dist = df["label"].value_counts(normalize=True)
    if label_dist.max() > 0.5:
        issues.append(f"ラベル偏り: クラス{label_dist.idxmax()} が {label_dist.max()*100:.1f}%")

    # 欠損値チェック
    missing = df[FEATURE_COLUMNS].isnull().sum()
    if missing.any():
        for col, cnt in missing[missing > 0].items():
            issues.append(f"欠損値: {col} に {cnt} 件")

    # レース数チェック
    n_races = len(df) // 6
    if n_races < 100:
        issues.append(f"レース数が少なすぎます: {n_races} レース（推奨: 1000以上）")

    return {
        "ok": len(issues) == 0,
        "n_rows": len(df),
        "n_races": n_races,
        "label_distribution": label_dist.to_dict(),
        "issues": issues,
    }


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="スクレイピングデータ→学習データ変換")
    parser.add_argument(
        "--input-dir", type=str, default=str(SCRAPED_DIR),
        help="スクレイピングデータのディレクトリ",
    )
    parser.add_argument(
        "--output", type=str, default=str(OUTPUT_PATH),
        help="出力CSVパス",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="変換せずにサマリーのみ表示",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    logger.info(f"入力ディレクトリ: {input_dir}")
    logger.info(f"出力パス: {output_path}")

    # データ読み込み
    results = load_race_results(input_dir)
    racers  = load_racer_info(input_dir)

    if results.empty:
        logger.error("レース結果データが空のため変換を中止します")
        sys.exit(1)

    # 変換
    df = build_training_rows(results, racers)

    if df.empty:
        logger.error("変換後のデータが空です")
        sys.exit(1)

    # 品質チェック
    validation = validate_training_data(df)
    print("\n【データ品質チェック】")
    print(f"  行数    : {validation['n_rows']:,}")
    print(f"  レース数: {validation['n_races']:,}")
    print(f"  ラベル分布: {validation['label_distribution']}")
    if validation["issues"]:
        print("  警告:")
        for issue in validation["issues"]:
            print(f"    ⚠ {issue}")
    else:
        print("  問題なし ✓")

    if args.dry_run:
        print("\n[DRY RUN] ファイルへの保存をスキップしました")
        return

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info(f"学習データを保存しました: {output_path} ({len(df)} 行)")
    print(f"\n保存完了: {output_path}")


if __name__ == "__main__":
    main()
