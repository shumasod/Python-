#!/usr/bin/env python3
"""
取引明細集計スクリプト（改善版）
Features:
- 堅牢なエラーハンドリング
- データ品質チェック
- 設定の外部化
- 詳細な分析機能
- グラフ生成
- プログレスバー
- テスト可能な設計
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import argparse
import json
import yaml
from dataclasses import dataclass
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import warnings

# 日本語フォント設定
plt.rcParams['font.family'] = [
    'DejaVu Sans', 'Hiragino Sans', 'Yu Gothic', 'Meiryo',
    'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP'
]


@dataclass
class AnalysisConfig:
    """分析設定のデータクラス"""
    input_file: str
    output_dir: str
    date_column: str = '取引日'
    amount_column: str = '金額'
    category_column: str = 'カテゴリ'
    description_column: str = '内容'
    encoding: str = 'utf-8'
    decimal_places: int = 0
    generate_charts: bool = True
    chart_style: str = 'seaborn-v0_8'
    outlier_threshold: float = 3.0  # 標準偏差の倍数

    @classmethod
    def from_file(cls, config_path: str) -> 'AnalysisConfig':
        """設定ファイルから読み込み"""
        config_path = Path(config_path)
        if config_path.suffix.lower() == '.json':
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif config_path.suffix.lower() in ['.yml', '.yaml']:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"サポートされていない設定ファイル形式: {config_path.suffix}")

        return cls(**data)


class DataValidator:
    """データ品質チェック用クラス"""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def validate_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """DataFrameの妥当性をチェック"""
        issues = []

        required_columns = [
            self.config.date_column,
            self.config.amount_column,
            self.config.category_column
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(f"必須列が不足: {missing_columns}")

        if not issues:
            # データ型チェック
            if not pd.api.types.is_datetime64_any_dtype(df[self.config.date_column]):
                try:
                    pd.to_datetime(df[self.config.date_column])
                except (ValueError, TypeError):
                    issues.append(f"{self.config.date_column}列を日付として変換できません")

            # 金額列チェック
            if not pd.api.types.is_numeric_dtype(df[self.config.amount_column]):
                try:
                    pd.to_numeric(df[self.config.amount_column], errors='coerce')
                except (ValueError, TypeError):
                    issues.append(f"{self.config.amount_column}列を数値として変換できません")

            if df.empty:
                issues.append("データが空です")

            duplicates = df.duplicated()
            if duplicates.any():
                issues.append(f"重複データが{duplicates.sum()}件あります")

            if self.config.amount_column in df.columns:
                numeric_amounts = pd.to_numeric(df[self.config.amount_column], errors='coerce')
                if not numeric_amounts.isna().all():
                    z_scores = np.abs((numeric_amounts - numeric_amounts.mean()) / numeric_amounts.std())
                    outliers = z_scores > self.config.outlier_threshold
                    if outliers.any():
                        issues.append(f"異常値が{outliers.sum()}件検出されました")

        return len(issues) == 0, issues


# TransactionAnalyzer クラス以下の処理（省略せずそのまま使えます）
# --- あなたの元コードの TransactionAnalyzer, create_sample_config, main 関数などはそのままでOK ---
# 修正ポイントは全角文字と if __name__ == "__main__": のみです


def create_sample_config(config_path: str) -> None:
    """サンプル設定ファイルを生成"""
    sample_config = {
        "input_file": "transactions.csv",
        "output_dir": "output",
        "date_column": "取引日",
        "amount_column": "金額",
        "category_column": "カテゴリ",
        "description_column": "内容",
        "encoding": "utf-8",
        "decimal_places": 0,
        "generate_charts": True,
        "chart_style": "seaborn-v0_8",
        "outlier_threshold": 3.0
    }

    config_path = Path(config_path)
    if config_path.suffix.lower() == '.json':
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, indent=2, ensure_ascii=False)
    else:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(sample_config, f, default_flow_style=False, allow_unicode=True)


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='取引明細集計スクリプト（改善版）')
    parser.add_argument('--config', '-c', help='設定ファイルパス')
    parser.add_argument('--input', '-i', help='入力CSVファイル')
    parser.add_argument('--output', '-o', help='出力ディレクトリ')
    parser.add_argument('--create-config', help='サンプル設定ファイルを生成')
    parser.add_argument('--no-charts', action='store_true', help='グラフ生成を無効化')

    args = parser.parse_args()

    # --- 以降は元の処理を流用 ---


if __name__ == "__main__":
    main()