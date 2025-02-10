#!/usr/bin/env python3
"""SQLを使用した取引明細集計スクリプト"""

import pandas as pd
import sqlalchemy as sa
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Optional

class TransactionAnalyzer:
    QUERIES = {
        'category_summary': """
            SELECT 
                category AS カテゴリ,
                COUNT(*) AS 取引件数,
                SUM(amount) AS 合計金額,
                AVG(amount) AS 平均金額,
                MAX(amount) AS 最大金額,
                MIN(amount) AS 最小金額
            FROM transactions
            GROUP BY category
            ORDER BY SUM(amount) DESC;
        """,
        
        'monthly_summary': """
            SELECT 
                DATE_TRUNC('month', transaction_date) AS 取引月,
                COUNT(*) AS 取引件数,
                SUM(amount) AS 合計金額,
                AVG(amount) AS 平均金額
            FROM transactions
            GROUP BY DATE_TRUNC('month', transaction_date)
            ORDER BY 取引月;
        """,
        
        'daily_summary': """
            SELECT 
                transaction_date AS 取引日,
                category AS カテゴリ,
                COUNT(*) AS 取引件数,
                SUM(amount) AS 合計金額
            FROM transactions
            GROUP BY transaction_date, category
            ORDER BY transaction_date DESC;
        """,
        
        'top_transactions': """
            SELECT 
                transaction_date AS 取引日,
                category AS カテゴリ,
                description AS 説明,
                amount AS 金額
            FROM transactions
            ORDER BY amount DESC
            LIMIT 10;
        """
    }

    def __init__(self, db_url: str, output_dir: str):
        self.engine = sa.create_engine(db_url)
        self.output_dir = Path(output_dir)
        self._setup_logging()

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def execute_query(self, query_name: str) -> pd.DataFrame:
        """SQLクエリを実行しDataFrameを返す"""
        try:
            query = self.QUERIES.get(query_name)
            if not query:
                raise ValueError(f"不明なクエリ名: {query_name}")
                
            return pd.read_sql_query(query, self.engine)
            
        except Exception as e:
            self.logger.error(f"クエリ実行エラー ({query_name}): {e}")
            raise

    def generate_custom_report(self, start_date: str, end_date: str) -> pd.DataFrame:
        """期間を指定したカスタムレポートの生成"""
        query = """
            SELECT 
                category AS カテゴリ,
                COUNT(*) AS 取引件数,
                SUM(amount) AS 合計金額
            FROM transactions
            WHERE transaction_date BETWEEN :start_date AND :end_date
            GROUP BY category
            ORDER BY SUM(amount) DESC;
        """
        params = {'start_date': start_date, 'end_date': end_date}
        return pd.read_sql_query(query, self.engine, params=params)

    def export_results(self) -> None:
        """集計結果をExcelファイルに出力"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.output_dir / f'取引集計_{timestamp}.xlsx'
            
            with pd.ExcelWriter(output_file) as writer:
                # 各クエリの結果を別シートに出力
                for query_name in self.QUERIES.keys():
                    df = self.execute_query(query_name)
                    sheet_name = query_name.replace('_', ' ').title()
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # カスタムレポート
                custom_df = self.generate_custom_report(
                    start_date='2024-01-01',
                    end_date='2024-12-31'
                )
                custom_df.to_excel(writer, sheet_name='カスタムレポート', index=False)
            
            self.logger.info(f"集計結果を保存: {output_file}")
            
        except Exception as e:
            self.logger.error(f"結果出力エラー: {e}")
            raise

def main():
    try:
        # PostgreSQL接続設定の例
        db_url = 'postgresql://username:password@localhost:5432/dbname'
        
        analyzer = TransactionAnalyzer(
            db_url=db_url,
            output_dir='output'
        )
        analyzer.export_results()
        
    except Exception as e:
        logging.error(f"処理エラー: {e}")
        raise

if __name__ == "__main__":
    main()
