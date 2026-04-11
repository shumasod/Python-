"""
データローダーモジュール
CSV・JSON形式の学習データ読み込みと基本的な検証を担当する
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from app.model.features import FEATURE_COLUMNS, preprocess_dataframe
from app.utils.logger import get_logger

logger = get_logger(__name__)

# デフォルトのデータディレクトリ
DATA_DIR = Path("data")


def load_training_data(
    file_path: Optional[str] = None,
    use_sample: bool = False,
) -> pd.DataFrame:
    """
    学習用データを読み込む

    Args:
        file_path: CSVファイルパス。None の場合 data/training.csv を使用
        use_sample: True の場合は自動生成サンプルデータを使用

    Returns:
        前処理済みの学習用DataFrame

    Raises:
        FileNotFoundError: 指定ファイルが存在しない場合
        ValueError: 必須カラムが不足している場合
    """
    if use_sample:
        from app.model.features import generate_sample_training_data
        logger.info("サンプルデータを使用します")
        df = generate_sample_training_data(n_races=2000)
        return preprocess_dataframe(df)

    path = Path(file_path) if file_path else DATA_DIR / "training.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"学習データが見つかりません: {path}\n"
            "use_sample=True でサンプルデータを生成できます"
        )

    logger.info(f"データを読み込んでいます: {path}")
    df = pd.read_csv(path, encoding="utf-8")

    # 必須カラムの検証
    required_cols = FEATURE_COLUMNS + ["label"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"必須カラムが不足しています: {missing}")

    logger.info(f"読み込み完了: {len(df)} 行, {len(df.columns)} 列")
    return preprocess_dataframe(df)


def save_training_data(df: pd.DataFrame, file_path: Optional[str] = None) -> None:
    """
    DataFrameをCSVに保存する

    Args:
        df: 保存するDataFrame
        file_path: 保存先パス。None の場合 data/training.csv を使用
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(file_path) if file_path else DATA_DIR / "training.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info(f"データを保存しました: {path} ({len(df)} 行)")
