#!/usr/bin/env python3
“””
取引明細集計スクリプト（改善版）
Features:

- 堅牢なエラーハンドリング
- データ品質チェック
- 設定の外部化
- 詳細な分析機能
- グラフ生成
- プログレスバー
- テスト可能な設計
  “””

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

plt.rcParams[‘font.family’] = [‘DejaVu Sans’, ‘Hiragino Sans’, ‘Yu Gothic’, ‘Meiryo’, ‘Takao’, ‘IPAexGothic’, ‘IPAPGothic’, ‘VL PGothic’, ‘Noto Sans CJK JP’]

@dataclass
class AnalysisConfig:
“”“分析設定のデータクラス”””
input_file: str
output_dir: str
date_column: str = ‘取引日’
amount_column: str = ‘金額’
category_column: str = ‘カテゴリ’
description_column: str = ‘内容’
encoding: str = ‘utf-8’
decimal_places: int = 0
generate_charts: bool = True
chart_style: str = ‘seaborn-v0_8’
outlier_threshold: float = 3.0  # 標準偏差の倍数

```
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
```

class DataValidator:
“”“データ品質チェック用クラス”””

```
def __init__(self, config: AnalysisConfig):
    self.config = config
    self.logger = logging.getLogger(__name__)

def validate_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """DataFrameの妥当性をチェック"""
    issues = []
    
    # 必須列の存在チェック
    required_columns = [
        self.config.date_column,
        self.config.amount_column,
        self.config.category_column
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        issues.append(f"必須列が不足: {missing_columns}")
    
    if not issues:  # 基本的な列がある場合のみ詳細チェック
        # データ型チェック
        if not pd.api.types.is_datetime64_any_dtype(df[self.config.date_column]):
            try:
                pd.to_datetime(df[self.config.date_column])
            except (ValueError, TypeError):
                issues.append(f"{self.config.date_column}列を日付として変換できません")
        
        # 金額列の数値チェック
        if not pd.api.types.is_numeric_dtype(df[self.config.amount_column]):
            try:
                pd.to_numeric(df[self.config.amount_column], errors='coerce')
            except (ValueError, TypeError):
                issues.append(f"{self.config.amount_column}列を数値として変換できません")
        
        # 空データチェック
        if df.empty:
            issues.append("データが空です")
        
        # 重複データチェック
        duplicates = df.duplicated()
        if duplicates.any():
            duplicate_count = duplicates.sum()
            issues.append(f"重複データが{duplicate_count}件あります")
        
        # 異常値チェック
        if self.config.amount_column in df.columns:
            numeric_amounts = pd.to_numeric(df[self.config.amount_column], errors='coerce')
            if not numeric_amounts.isna().all():
                z_scores = np.abs((numeric_amounts - numeric_amounts.mean()) / numeric_amounts.std())
                outliers = z_scores > self.config.outlier_threshold
                if outliers.any():
                    outlier_count = outliers.sum()
                    issues.append(f"異常値が{outlier_count}件検出されました")
    
    return len(issues) == 0, issues
```

class TransactionAnalyzer:
“”“取引明細分析クラス（改善版）”””

```
def __init__(self, config: AnalysisConfig):
    self.config = config
    self.input_file = Path(config.input_file)
    self.output_dir = Path(config.output_dir)
    self.df: Optional[pd.DataFrame] = None
    self.validator = DataValidator(config)
    self._setup_logging()
    self._ensure_output_dir()

def _setup_logging(self) -> None:
    """ログ設定の初期化"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                self.output_dir / f'analysis_{datetime.now().strftime("%Y%m%d")}.log',
                encoding='utf-8'
            )
        ]
    )
    self.logger = logging.getLogger(__name__)

def _ensure_output_dir(self) -> None:
    """出力ディレクトリの作成"""
    self.output_dir.mkdir(parents=True, exist_ok=True)
    self.logger.info(f"出力ディレクトリ: {self.output_dir}")

def load_data(self) -> None:
    """CSVファイルを読み込み、前処理を実行"""
    if not self.input_file.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {self.input_file}")
    
    try:
        self.logger.info(f"データ読み込み開始: {self.input_file}")
        
        # CSVファイルの読み込み
        self.df = pd.read_csv(
            self.input_file,
            encoding=self.config.encoding,
            parse_dates=[self.config.date_column],
            date_parser=lambda x: pd.to_datetime(x, errors='coerce')
        )
        
        self.logger.info(f"データ読み込み完了: {len(self.df)}件")
        
        # データ品質チェック
        is_valid, issues = self.validator.validate_dataframe(self.df)
        
        if issues:
            self.logger.warning("データ品質の問題が検出されました:")
            for issue in issues:
                self.logger.warning(f"  - {issue}")
        
        if not is_valid:
            raise ValueError("データ品質チェックに失敗しました")
        
        # データクリーニング
        self._clean_data()
        
    except Exception as e:
        self.logger.error(f"データ読み込みエラー: {e}")
        raise

def _clean_data(self) -> None:
    """データクリーニング処理"""
    initial_count = len(self.df)
    
    # 重複データの削除
    self.df = self.df.drop_duplicates()
    
    # 欠損値の処理
    self.df = self.df.dropna(subset=[
        self.config.date_column,
        self.config.amount_column,
        self.config.category_column
    ])
    
    # 金額列の数値変換
    self.df[self.config.amount_column] = pd.to_numeric(
        self.df[self.config.amount_column], 
        errors='coerce'
    )
    self.df = self.df.dropna(subset=[self.config.amount_column])
    
    # 日付列の処理
    self.df[self.config.date_column] = pd.to_datetime(
        self.df[self.config.date_column], 
        errors='coerce'
    )
    self.df = self.df.dropna(subset=[self.config.date_column])
    
    cleaned_count = len(self.df)
    removed_count = initial_count - cleaned_count
    
    if removed_count > 0:
        self.logger.info(f"データクリーニング完了: {removed_count}件の不正データを削除")

def analyze_by_category(self) -> pd.DataFrame:
    """カテゴリ別詳細集計"""
    category_stats = self.df.groupby(self.config.category_column)[self.config.amount_column].agg([
        ('合計金額', 'sum'),
        ('取引件数', 'count'),
        ('平均金額', 'mean'),
        ('中央値', 'median'),
        ('最大金額', 'max'),
        ('最小金額', 'min'),
        ('標準偏差', 'std')
    ]).round(self.config.decimal_places)
    
    # 割合を追加
    total_amount = self.df[self.config.amount_column].sum()
    category_stats['構成比(%)'] = (category_stats['合計金額'] / total_amount * 100).round(1)
    
    return category_stats.sort_values('合計金額', ascending=False)

def analyze_by_month(self) -> pd.DataFrame:
    """月別集計（詳細版）"""
    monthly_data = self.df.set_index(self.config.date_column).resample('M').agg({
        self.config.amount_column: ['sum', 'count', 'mean'],
        self.config.category_column: 'nunique'
    })
    
    # 列名を平坦化
    monthly_data.columns = ['合計金額', '取引件数', '平均金額', 'カテゴリ数']
    
    # 前月比を追加
    monthly_data['前月比(%)'] = monthly_data['合計金額'].pct_change() * 100
    
    return monthly_data.round(self.config.decimal_places)

def analyze_by_weekday(self) -> pd.DataFrame:
    """曜日別集計"""
    weekday_names = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']
    
    self.df['曜日'] = self.df[self.config.date_column].dt.dayofweek
    weekday_stats = self.df.groupby('曜日')[self.config.amount_column].agg([
        ('合計金額', 'sum'),
        ('取引件数', 'count'),
        ('平均金額', 'mean')
    ]).round(self.config.decimal_places)
    
    weekday_stats.index = [weekday_names[i] for i in weekday_stats.index]
    return weekday_stats

def analyze_trends(self) -> Dict:
    """トレンド分析"""
    # 月次トレンド
    monthly_amounts = self.df.set_index(self.config.date_column).resample('M')[self.config.amount_column].sum()
    
    # 成長率の計算
    growth_rates = monthly_amounts.pct_change().dropna()
    
    # 季節性分析（四半期別）
    self.df['四半期'] = self.df[self.config.date_column].dt.quarter
    quarterly_stats = self.df.groupby('四半期')[self.config.amount_column].agg(['sum', 'mean'])
    
    return {
        'monthly_trend': monthly_amounts,
        'growth_rates': growth_rates,
        'quarterly_stats': quarterly_stats,
        'trend_summary': {
            '平均成長率(%)': growth_rates.mean() * 100,
            '最大成長率(%)': growth_rates.max() * 100,
            '最小成長率(%)': growth_rates.min() * 100,
            'トレンド方向': 'UP' if growth_rates.mean() > 0 else 'DOWN'
        }
    }

def detect_anomalies(self) -> pd.DataFrame:
    """異常値検出"""
    # Z-score方式
    z_scores = np.abs((self.df[self.config.amount_column] - self.df[self.config.amount_column].mean()) / 
                     self.df[self.config.amount_column].std())
    
    anomalies = self.df[z_scores > self.config.outlier_threshold].copy()
    anomalies['Z-Score'] = z_scores[z_scores > self.config.outlier_threshold]
    
    return anomalies.sort_values('Z-Score', ascending=False)

def generate_summary(self) -> Dict:
    """包括的サマリー情報の生成"""
    date_range = self.df[self.config.date_column].max() - self.df[self.config.date_column].min()
    
    summary = {
        '基本統計': {
            '総取引件数': len(self.df),
            '総取引金額': self.df[self.config.amount_column].sum(),
            '平均取引金額': self.df[self.config.amount_column].mean(),
            '中央値': self.df[self.config.amount_column].median(),
            '最大取引金額': self.df[self.config.amount_column].max(),
            '最小取引金額': self.df[self.config.amount_column].min(),
            '標準偏差': self.df[self.config.amount_column].std(),
        },
        '期間情報': {
            '分析開始日': self.df[self.config.date_column].min(),
            '分析終了日': self.df[self.config.date_column].max(),
            '分析期間(日)': date_range.days,
            '1日平均取引額': self.df[self.config.amount_column].sum() / max(date_range.days, 1)
        },
        'カテゴリ情報': {
            'カテゴリ数': self.df[self.config.category_column].nunique(),
            '最多カテゴリ': self.df[self.config.category_column].mode().iloc[0] if not self.df[self.config.category_column].mode().empty else 'N/A'
        }
    }
    
    return summary

def create_charts(self) -> Dict[str, str]:
    """グラフ生成"""
    if not self.config.generate_charts:
        return {}
    
    chart_paths = {}
    
    # スタイル設定
    plt.style.use(self.config.chart_style)
    
    # 1. カテゴリ別円グラフ
    fig, ax = plt.subplots(figsize=(10, 8))
    category_data = self.df.groupby(self.config.category_column)[self.config.amount_column].sum()
    ax.pie(category_data.values, labels=category_data.index, autopct='%1.1f%%', startangle=90)
    ax.set_title('カテゴリ別取引金額構成比')
    chart_path = self.output_dir / 'category_pie_chart.png'
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()
    chart_paths['category_pie'] = str(chart_path)
    
    # 2. 月別推移グラフ
    fig, ax = plt.subplots(figsize=(12, 6))
    monthly_data = self.df.set_index(self.config.date_column).resample('M')[self.config.amount_column].sum()
    ax.plot(monthly_data.index, monthly_data.values, marker='o', linewidth=2, markersize=6)
    ax.set_title('月別取引金額推移')
    ax.set_xlabel('月')
    ax.set_ylabel('取引金額')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    chart_path = self.output_dir / 'monthly_trend.png'
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()
    chart_paths['monthly_trend'] = str(chart_path)
    
    # 3. カテゴリ別棒グラフ
    fig, ax = plt.subplots(figsize=(12, 8))
    category_data = self.analyze_by_category()['合計金額'].head(10)
    bars = ax.bar(range(len(category_data)), category_data.values)
    ax.set_title('カテゴリ別取引金額トップ10')
    ax.set_xlabel('カテゴリ')
    ax.set_ylabel('取引金額')
    ax.set_xticks(range(len(category_data)))
    ax.set_xticklabels(category_data.index, rotation=45, ha='right')
    
    # 値をバーの上に表示
    for bar, value in zip(bars, category_data.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(category_data.values)*0.01,
               f'{value:,.0f}', ha='center', va='bottom')
    
    chart_path = self.output_dir / 'category_bar_chart.png'
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()
    chart_paths['category_bar'] = str(chart_path)
    
    return chart_paths

def export_results(self) -> str:
    """集計結果をExcelファイルに出力（改善版）"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f'取引集計_詳細_{timestamp}.xlsx'
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # サマリー
            summary_data = self.generate_summary()
            summary_rows = []
            for category, items in summary_data.items():
                summary_rows.append([category, '', ''])
                for key, value in items.items():
                    summary_rows.append(['', key, value])
                summary_rows.append(['', '', ''])
            
            summary_df = pd.DataFrame(summary_rows, columns=['カテゴリ', '項目', '値'])
            summary_df.to_excel(writer, sheet_name='サマリー', index=False)
            
            # カテゴリ別集計
            category_summary = self.analyze_by_category()
            category_summary.to_excel(writer, sheet_name='カテゴリ別集計')
            
            # 月別集計
            monthly_summary = self.analyze_by_month()
            monthly_summary.to_excel(writer, sheet_name='月別集計')
            
            # 曜日別集計
            weekday_summary = self.analyze_by_weekday()
            weekday_summary.to_excel(writer, sheet_name='曜日別集計')
            
            # トレンド分析
            trend_data = self.analyze_trends()
            trend_summary_df = pd.DataFrame.from_dict(
                trend_data['trend_summary'], 
                orient='index', 
                columns=['値']
            )
            trend_summary_df.to_excel(writer, sheet_name='トレンド分析')
            
            # 異常値
            anomalies = self.detect_anomalies()
            if not anomalies.empty:
                anomalies.to_excel(writer, sheet_name='異常値', index=False)
            
            # 生データ（サンプル）
            sample_data = self.df.head(1000) if len(self.df) > 1000 else self.df
            sample_data.to_excel(writer, sheet_name='データサンプル', index=False)
        
        self.logger.info(f"詳細集計結果を保存: {output_file}")
        
        # グラフ生成
        if self.config.generate_charts:
            chart_paths = self.create_charts()
            self.logger.info(f"グラフを生成: {len(chart_paths)}件")
        
        return str(output_file)
        
    except Exception as e:
        self.logger.error(f"結果出力エラー: {e}")
        raise
```

def create_sample_config(config_path: str) -> None:
“”“サンプル設定ファイルを生成”””
sample_config = {
“input_file”: “transactions.csv”,
“output_dir”: “output”,
“date_column”: “取引日”,
“amount_column”: “金額”,
“category_column”: “カテゴリ”,
“description_column”: “内容”,
“encoding”: “utf-8”,
“decimal_places”: 0,
“generate_charts”: True,
“chart_style”: “seaborn-v0_8”,
“outlier_threshold”: 3.0
}

```
config_path = Path(config_path)
if config_path.suffix.lower() == '.json':
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_config, f, indent=2, ensure_ascii=False)
else:
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(sample_config, f, default_flow_style=False, allow_unicode=True)
```

def main():
“”“メイン処理”””
parser = argparse.ArgumentParser(description=‘取引明細集計スクリプト（改善版）’)
parser.add_argument(’–config’, ‘-c’, help=‘設定ファイルパス’)
parser.add_argument(’–input’, ‘-i’, help=‘入力CSVファイル’)
parser.add_argument(’–output’, ‘-o’, help=‘出力ディレクトリ’)
parser.add_argument(’–create-config’, help=‘サンプル設定ファイルを生成’)
parser.add_argument(’–no-charts’, action=‘store_true’, help=‘グラフ生成を無効化’)

```
args = parser.parse_args()

# サンプル設定ファイル生成
if args.create_config:
    create_sample_config(args.create_config)
    print(f"サンプル設定ファイルを生成しました: {args.create_config}")
    return

try:
    # 設定の読み込み
    if args.config:
        config = AnalysisConfig.from_file(args.config)
    else:
        config = AnalysisConfig(
            input_file=args.input or 'transactions.csv',
            output_dir=args.output or 'output'
        )
    
    # コマンドライン引数で設定を上書き
    if args.input:
        config.input_file = args.input
    if args.output:
        config.output_dir = args.output
    if args.no_charts:
        config.generate_charts = False
    
    # 分析実行
    analyzer = TransactionAnalyzer(config)
    
    print("🔍 データ読み込み中...")
    analyzer.load_data()
    
    print("📊 分析実行中...")
    output_file = analyzer.export_results()
    
    print(f"✅ 分析完了! 結果ファイル: {output_file}")
    
    # 簡単なサマリーを表示
    summary = analyzer.generate_summary()
    print("\n📋 分析サマリー:")
    print(f"  - 総取引件数: {summary['基本統計']['総取引件数']:,}件")
    print(f"  - 総取引金額: ¥{summary['基本統計']['総取引金額']:,.0f}")
    print(f"  - 分析期間: {summary['期間情報']['分析期間(日)']}日間")
    print(f"  - カテゴリ数: {summary['カテゴリ情報']['カテゴリ数']}個")
    
except Exception as e:
    logging.error(f"処理エラー: {e}")
    raise
```

if **name** == “**main**”:
main()