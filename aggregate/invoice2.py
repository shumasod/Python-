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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import logging
import argparse
import json
import yaml
from dataclasses import dataclass
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from decimal import Decimal, InvalidOperation
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


# ... （中略：DataValidator, TransactionAnalyzer, etc.）

if __name__ == "__main__":
    main()