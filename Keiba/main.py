"""
JRA競馬予測アプリケーション - メインエントリーポイント
"""

import os
import argparse
import logging
from pathlib import Path

from .app import create_app, AppConfig, Environment


def parse_arguments() -> argparse.Namespace:
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description='JRA競馬予測アプリケーション',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python -m Keiba.main --port 8000 --debug
  python -m Keiba.main --model-path ./models/jra_model.pkl
  python -m Keiba.main --base-url https://example.com/races --num-pages 20
        """
    )

    # Server settings
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='サーバーホスト (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='サーバーポート (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='デバッグモードを有効化'
    )

    # Model settings
    parser.add_argument(
        '--model-path',
        type=Path,
        help='事前学習済みモデルのパス'
    )
    parser.add_argument(
        '--no-auto-train',
        action='store_true',
        help='自動トレーニングを無効化'
    )

    # Scraping settings
    parser.add_argument(
        '--base-url',
        help='スクレイピング対象のベースURL'
    )
    parser.add_argument(
        '--num-pages',
        type=int,
        help='スクレイピングするページ数'
    )

    # Logging settings
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='ログレベル (default: INFO)'
    )
    parser.add_argument(
        '--log-dir',
        type=Path,
        help='ログディレクトリ'
    )

    # Environment
    parser.add_argument(
        '--env',
        choices=['development', 'staging', 'production', 'testing'],
        default='development',
        help='実行環境 (default: development)'
    )

    return parser.parse_args()


def create_config_from_args(args: argparse.Namespace) -> AppConfig:
    """コマンドライン引数から設定を作成"""
    # 環境変数ベースの設定をロード
    config = AppConfig.from_env()

    # コマンドライン引数で上書き
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.debug:
        config.debug = True

    if args.model_path:
        config.model_path = args.model_path
    if args.no_auto_train:
        config.auto_train = False

    if args.base_url:
        config.base_url = args.base_url
    if args.num_pages:
        config.num_pages = args.num_pages

    if args.log_level:
        config.log_level = args.log_level
    if args.log_dir:
        config.log_dir = args.log_dir

    if args.env:
        config.environment = Environment(args.env)

    return config


def main() -> None:
    """アプリケーションのメインエントリーポイント"""
    # 引数のパース
    args = parse_arguments()

    # 設定の作成
    config = create_config_from_args(args)

    # アプリケーションの作成
    app = create_app(config)

    # バナー表示
    print("=" * 60)
    print(f"  {config.app_name} v{config.version}")
    print("=" * 60)
    print(f"  環境:       {config.environment.value}")
    print(f"  URL:        http://{config.host}:{config.port}")
    print(f"  デバッグ:   {config.debug}")
    print(f"  モデル:     {config.model_path or '自動トレーニング'}")
    print("=" * 60)
    print()

    # アプリケーションの起動
    try:
        app.run(
            host=config.host,
            port=config.port,
            debug=config.debug,
            use_reloader=config.debug,
        )
    except KeyboardInterrupt:
        print("\n\nアプリケーションを停止しています...")
    except Exception as e:
        logging.getLogger(__name__).exception("アプリケーション起動エラー: %s", e)
        raise


if __name__ == '__main__':
    main()
