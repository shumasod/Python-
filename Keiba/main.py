# main.py
import os
import argparse
import logging
from .config import Config
from .app import create_app

def parse_arguments():
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(description='JRA予測アプリケーション')
    parser.add_argument('--base-url', help='スクレイピング対象のベースURL')
    parser.add_argument('--num-pages', type=int, help='スクレイピングするページ数')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument('--model-path', help='モデルファイルのパス')
    parser.add_argument('--log-level', default='INFO', 
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      help='ロギングレベル')
    parser.add_argument('--port', type=int, default=5000, help='サーバーのポート番号')
    return parser.parse_args()

if __name__ == '__main__':
    # コマンドライン引数の解析
    args = parse_arguments()
    
    # 設定の初期化
    config = Config()
    
    # コマンドライン引数で設定を上書き
    if args.base_url:
        config.BASE_URL = args.base_url
    if args.num_pages:
        config.NUM_PAGES = args.num_pages
    if args.debug:
        config.DEBUG = True
    if args.model_path:
        config.MODEL_PATH = args.model_path
    if args.log_level:
        config.LOG_LEVEL = args.log_level
    
    # アプリケーションの作成と実行
    app = create_app(config)
    app.run(host='0.0.0.0', port=args.port, debug=config.DEBUG)
