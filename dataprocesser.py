import pandas as pd
import numpy as np
from typing import Dict, List, Union, Optional
from datetime import datetime
import logging
import argparse
import json
from pathlib import Path

class DataProcessor:
    """データ処理の基本クラス"""
    
    def __init__(self, input_path: str, output_dir: str):
        """
        初期化
        
        Args:
            input_path: 入力データのパス
            output_dir: 出力ディレクトリ
        """
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # ログ設定
        self.logger = self._setup_logger()
        
        # データ読み込み
        self.df = self._load_data()
    
    def _setup_logger(self) -> logging.Logger:
        """ロガーの設定"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # ファイルハンドラー
        fh = logging.FileHandler(self.output_dir / 'process.log')
        fh.setLevel(logging.INFO)
        
        # コンソールハンドラー
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # フォーマッター
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _load_data(self) -> pd.DataFrame:
        """データの読み込み"""
        self.logger.info(f'Loading data from {self.input_path}')
        
        if self.input_path.suffix == '.csv':
            return pd.read_csv(self.input_path)
        elif self.input_path.suffix == '.xlsx':
            return pd.read_excel(self.input_path)
        elif self.input_path.suffix == '.json':
            return pd.read_json(self.input_path)
        else:
            raise ValueError(f'Unsupported file format: {self.input_path.suffix}')

    def filter_data(self, conditions: Dict[str, Union[str, int, float]]) -> pd.DataFrame:
        """
        条件に基づくデータのフィルタリング
        
        Args:
            conditions: フィルタ条件の辞書
        """
        filtered_df = self.df.copy()
        
        for column, value in conditions.items():
            filtered_df = filtered_df[filtered_df[column] == value]
        
        return filtered_df
    
    def aggregate_data(self, group_by: List[str], metrics: List[str]) -> pd.DataFrame:
        """
        データの集計
        
        Args:
            group_by: グループ化するカラム
            metrics: 集計するメトリクス
        """
        return self.df.groupby(group_by)[metrics].agg(['mean', 'sum', 'count', 'std'])
    
    def generate_report(self, report_config: Dict) -> None:
        """
        レポートの生成
        
        Args:
            report_config: レポート設定
        """
        self.logger.info('Generating report...')
        
        # 基本統計量の計算
        stats = self.df.describe()
        
        # グループごとの集計
        if 'group_by' in report_config and 'metrics' in report_config:
            agg_data = self.aggregate_data(
                report_config['group_by'],
                report_config['metrics']
            )
        else:
            agg_data = pd.DataFrame()
        
        # レポートの保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 統計情報の保存
        stats.to_csv(self.output_dir / f'stats_{timestamp}.csv')
        
        # 集計データの保存
        if not agg_data.empty:
            agg_data.to_csv(self.output_dir / f'aggregation_{timestamp}.csv')
        
        # サマリーレポートの作成
        summary = {
            'timestamp': timestamp,
            'total_records': len(self.df),
            'columns': list(self.df.columns),
            'missing_values': self.df.isnull().sum().to_dict()
        }
        
        with open(self.output_dir / f'summary_{timestamp}.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info('Report generation completed')

def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='データ処理システム')
    
    parser.add_argument('input_path', help='入力データのパス')
    parser.add_argument('output_dir', help='出力ディレクトリ')
    parser.add_argument('--filter', help='フィルタ条件（JSON形式）')
    parser.add_argument('--group_by', help='グループ化するカラム（カンマ区切り）')
    parser.add_argument('--metrics', help='集計するメトリクス（カンマ区切り）')
    
    args = parser.parse_args()
    
    # データプロセッサーの初期化
    processor = DataProcessor(args.input_path, args.output_dir)
    
    # フィルタリング条件の処理
    if args.filter:
        conditions = json.loads(args.filter)
        filtered_data = processor.filter_data(conditions)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filtered_data.to_csv(processor.output_dir / f'filtered_{timestamp}.csv', index=False)
    
    # レポート設定
    report_config = {}
    if args.group_by:
        report_config['group_by'] = args.group_by.split(',')
    if args.metrics:
        report_config['metrics'] = args.metrics.split(',')
    
    # レポート生成
    processor.generate_report(report_config)

if __name__ == '__main__':
    main()