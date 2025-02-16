#!/usr/bin/env python3
from __future__ import print_function
import os
import sys
import csv
from lib import logger
from lib.util import *
from models import *
from services.InvoiceService import *

class InvoiceGenerator:
    def __init__(self, config_path='config/config.yml'):
        self.logger = logger.get_logger(__name__)
        self.config = load_config(config_path)
        self.invoice_service = InvoiceService()

    def generate_invoice(self, data):
        """
        明細データから請求書を生成する
        
        Args:
            data (dict): 明細データ
                {
                    'customer_id': str,
                    'invoice_date': str,
                    'items': [
                        {
                            'item_name': str,
                            'quantity': int,
                            'unit_price': int
                        },
                        ...
                    ]
                }
        
        Returns:
            dict: 生成された請求書データ
        """
        try:
            # 顧客情報の取得
            customer = self.invoice_service.get_customer(data['customer_id'])
            if not customer:
                raise ValueError(f"Customer not found: {data['customer_id']}")

            # 明細項目の検証
            self._validate_items(data['items'])

            # 請求書番号の生成
            invoice_number = self.invoice_service.generate_invoice_number()

            # 小計、税額、合計金額の計算
            subtotal = sum(item['quantity'] * item['unit_price'] for item in data['items'])
            tax = int(subtotal * self.config['tax_rate'])
            total = subtotal + tax

            # 請求書データの作成
            invoice_data = {
                'invoice_number': invoice_number,
                'invoice_date': data['invoice_date'],
                'customer': customer,
                'items': data['items'],
                'subtotal': subtotal,
                'tax': tax,
                'total': total
            }

            # データベースに保存
            self.invoice_service.save_invoice(invoice_data)

            self.logger.info(f"Invoice generated successfully: {invoice_number}")
            return invoice_data

        except Exception as e:
            self.logger.error(f"Failed to generate invoice: {str(e)}")
            raise

    def _validate_items(self, items):
        """
        明細項目の検証を行う
        
        Args:
            items (list): 明細項目のリスト
        
        Raises:
            ValueError: 検証エラーが発生した場合
        """
        if not items:
            raise ValueError("No items provided")

        for item in items:
            if not all(k in item for k in ('item_name', 'quantity', 'unit_price')):
                raise ValueError(f"Invalid item format: {item}")
            if item['quantity'] <= 0:
                raise ValueError(f"Invalid quantity: {item['quantity']}")
            if item['unit_price'] < 0:
                raise ValueError(f"Invalid unit price: {item['unit_price']}")

def main():
    """
    メイン処理
    """
    try:
        # コマンドライン引数からCSVファイルパスを取得
        if len(sys.argv) != 2:
            print("Usage: python invoice_generator.py <csv_file>")
            sys.exit(1)

        csv_file = sys.argv[1]
        if not os.path.exists(csv_file):
            print(f"File not found: {csv_file}")
            sys.exit(1)

        # インスタンスの作成
        generator = InvoiceGenerator()

        # CSVファイルの読み込みと処理
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # CSVデータの整形
                invoice_data = {
                    'customer_id': row['customer_id'],
                    'invoice_date': row['invoice_date'],
                    'items': [
                        {
                            'item_name': row['item_name'],
                            'quantity': int(row['quantity']),
                            'unit_price': int(row['unit_price'])
                        }
                    ]
                }
                
                # 請求書の生成
                invoice = generator.generate_invoice(invoice_data)
                print(f"Generated invoice: {invoice['invoice_number']}")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
