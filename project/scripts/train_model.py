"""
モデル学習スクリプト
実行例:
  # サンプルデータで学習
  python scripts/train_model.py --use-sample

  # 実データ（CSVファイル）で学習
  python scripts/train_model.py --data-path data/training.csv

  # レース数を指定してサンプルデータ生成
  python scripts/train_model.py --use-sample --n-races 5000
"""
import argparse
import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加（project/ ディレクトリから実行する想定）
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.loader import load_training_data
from app.model.train import train_model
from app.utils.logger import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="競艇予想AIモデル学習スクリプト")
    parser.add_argument(
        "--use-sample",
        action="store_true",
        help="自動生成サンプルデータで学習する",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="学習CSVファイルのパス（省略時は data/training.csv）",
    )
    parser.add_argument(
        "--n-races",
        type=int,
        default=2000,
        help="サンプルデータのレース数（--use-sample 時のみ有効）",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="boat_race_model",
        help="保存するモデル名（拡張子なし）",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Cross Validation の分割数",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("=== 競艇予想AIモデル学習開始 ===")

    # --- データ読み込み ---
    if args.use_sample:
        logger.info(f"サンプルデータを生成します（レース数: {args.n_races}）")
        # generate_sample_training_data は load_training_data 内で呼ばれる
        # n_races を渡すには features.py を直接呼ぶ
        from app.model.features import generate_sample_training_data
        from app.model.features import preprocess_dataframe
        df = preprocess_dataframe(generate_sample_training_data(n_races=args.n_races))
    else:
        df = load_training_data(file_path=args.data_path)

    logger.info(f"学習データ: {len(df)} 行, クラス分布: {df['label'].value_counts().to_dict()}")

    # --- モデル学習 ---
    model, metrics = train_model(
        df,
        model_name=args.model_name,
        n_splits=args.n_splits,
    )

    # --- 結果表示 ---
    logger.info("=== 学習完了 ===")
    logger.info(f"CV Log Loss : {metrics['cv_logloss_mean']:.4f} ± {metrics['cv_logloss_std']:.4f}")
    logger.info(f"CV Accuracy : {metrics['cv_accuracy_mean']:.4f} ± {metrics['cv_accuracy_std']:.4f}")
    logger.info(f"モデルは models/{args.model_name}.pkl に保存されました")

    # メトリクスをコンソール出力
    print("\n" + "=" * 50)
    print("学習メトリクス")
    print("=" * 50)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
