#!/usr/bin/env python3
"""取引明細集計スクリプト"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

class TransactionAnalyzer:
    def __init__(self, input_file: str, output_dir: str):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.df: Optional[pd.DataFrame] = None
        self._setup_logging()

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def load_data(self) -> None:
        """CSVファイルを読み込み、DataFrameに変換"""
        try:
            self.df = pd.read_csv(
                self.input_file,
                parse_dates=['取引日'],
                encoding='utf-8'
            )
            self.logger.info(f"データ読み込み完了: {len(self.df)}件")
        except Exception as e:
            self.logger.error(f"データ読み込みエラー: {e}")
            raise

    def analyze_by_category(self) -> pd.DataFrame:
        """カテゴリ別集計"""
        return self.df.groupby('カテゴリ').agg({
            '金額': ['sum', 'count', 'mean']
        }).round(0)

    def analyze_by_month(self) -> pd.DataFrame:
        """月別集計"""
        monthly = self.df.set_index('取引日').resample('M').agg({
            '金額': 'sum',
            'カテゴリ': 'count'
        })
        monthly.columns = ['合計金額', '取引件数']
        return monthly

    def generate_summary(self) -> Dict:
        """サマリー情報の生成"""
        return {
            '総取引件数': len(self.df),
            '総取引金額': self.df['金額'].sum(),
            '平均取引金額': self.df['金額'].mean(),
            '最大取引金額': self.df['金額'].max(),
            '最小取引金額': self.df['金額'].min()
        }

    def export_results(self) -> None:
        """集計結果をExcelファイルに出力"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.output_dir / f'取引集計_{timestamp}.xlsx'
            
            with pd.ExcelWriter(output_file) as writer:
                # カテゴリ別集計
                category_summary = self.analyze_by_category()
                category_summary.to_excel(writer, sheet_name='カテゴリ別集計')
                
                # 月別集計
                monthly_summary = self.analyze_by_month()
                monthly_summary.to_excel(writer, sheet_name='月別集計')
                
                # サマリー
                summary_df = pd.DataFrame.from_dict(
                    self.generate_summary(),
                    orient='index',
                    columns=['値']
                )
                summary_df.to_excel(writer, sheet_name='サマリー')
            
            self.logger.info(f"集計結果を保存: {output_file}")
            
        except Exception as e:
            self.logger.error(f"結果出力エラー: {e}")
            raise

def main():
    try:
        analyzer = TransactionAnalyzer(
            input_file='transactions.csv',
            output_dir='output'
        )
        analyzer.load_data()
        analyzer.export_results()
        
    except Exception as e:
        logging.error(f"処理エラー: {e}")
        raise

if __name__ == "__main__":
    main()
