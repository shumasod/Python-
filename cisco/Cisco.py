#!/usr/bin/env python3
"""
NETCONF プロトコルを使用してCiscoデバイスにルート設定を行うスクリプト
"""
import argparse
import getpass
import json
import logging
import os
import sys
import xml.dom.minidom
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ncclient import manager
from ncclient.operations import RPCError
from ncclient.transport.errors import SSHError, SessionCloseError
from ncclient.operations.rpc import RPCReply

# ログ設定

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
level=logging.INFO,
format=LOG_FORMAT,
handlers=[
logging.FileHandler("netconf_config.log"),
logging.StreamHandler()
]
)
logger = logging.getLogger(__name__)

# 環境変数からデフォルト値を取得

DEFAULT_HOST = os.environ.get('NETCONF_HOST', '')
DEFAULT_PORT = int(os.environ.get('NETCONF_PORT', '830'))
DEFAULT_USERNAME = os.environ.get('NETCONF_USERNAME', '')

# パスワードは環境変数から読み込まない（セキュリティ上の理由）

@dataclass
class RouteConfig:
    """ルート設定を表すデータクラス"""
    prefix: str
    mask: str
    fwd: Optional[str] = None

    def __post_init__(self):
        """バリデーション"""
        if not self.prefix or not self.mask:
            raise ValueError("prefix and mask are required")

        # 簡単なIPアドレス形式チェック
        if not self._is_valid_ip(self.prefix):
            raise ValueError(f"Invalid IP address format: {self.prefix}")

        if not self._is_valid_ip(self.mask):
            raise ValueError(f"Invalid subnet mask format: {self.mask}")

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """簡単なIPアドレス形式チェック"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False
            return True
        except (ValueError, AttributeError):
            return False

class NetconfConnectionError(Exception):
    """NETCONF接続エラー"""
    pass


class NetconfConfigurationError(Exception):
    """NETCONF設定エラー"""
    pass


class NetconfClient:
    """NETCONF プロトコルを使用してCiscoデバイスを設定するクライアント"""

    def __init__(self, host: str, port: int, username: str, password: str, timeout: int = 30):
        """
        NETCONF クライアントを初期化

        Args:
            host: ネットワークデバイスのホスト名またはIPアドレス
            port: NECTONFポート（デフォルト: 830）
            username: 認証用ユーザー名
            password: 認証用パスワード
            timeout: 接続タイムアウト（秒）
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.connection = None
        self._connected = False

    def connect(self) -> bool:
        """
        デバイスに接続

        Returns:
            bool: 接続が成功したかどうか

        Raises:
            NetconfConnectionError: 接続に失敗した場合
        """
        if self._connected:
            logger.warning("Already connected to device")
            return True

        try:
            logger.info(f"Connecting to {self.host}:{self.port}...")
            self.connection = manager.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                hostkey_verify=False,
                device_params={'name': 'iosxe'},
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False
            )
            self._connected = True
            logger.info(f"Successfully connected to {self.host}")
            return True
        except SSHError as e:
            error_msg = f"SSH connection failed to {self.host}:{self.port}: {e}"
            logger.error(error_msg)
            raise NetconfConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Connection failed to {self.host}:{self.port}: {e}"
            logger.error(error_msg)
            raise NetconfConnectionError(error_msg) from e

    def disconnect(self) -> None:
        """接続を閉じる"""
        if self.connection and self._connected:
            try:
                self.connection.close_session()
                logger.info("Session closed successfully")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self._connected = False
                self.connection = None

    def __enter__(self):
        """コンテキストマネージャー（with文）のサポート"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー（with文）のサポート"""
        self.disconnect()

    def _ensure_connected(self) -> None:
        """接続状態を確認"""
        if not self._connected or not self.connection:
            raise NetconfConnectionError("Not connected to device")

    def get_capabilities(self) -> List[str]:
        """
        デバイスの機能（capabilities）を取得

        Returns:
            List[str]: サポートされている機能のリスト
        """
        self._ensure_connected()
        return list(self.connection.server_capabilities)

    def get_running_config(self, filter_str: Optional[str] = None) -> str:
        """
        実行中の設定を取得

        Args:
            filter_str: 設定フィルター（オプション）

        Returns:
            str: 設定XML

        Raises:
            NetconfConfigurationError: 設定取得に失敗した場合
        """
        self._ensure_connected()

        try:
            if filter_str:
                logger.debug(f"Getting running config with filter: {filter_str}")
                reply = self.connection.get_config(source='running', filter=('subtree', filter_str))
            else:
                logger.debug("Getting full running config")
                reply = self.connection.get_config(source='running')

            return reply.data_xml
        except RPCError as e:
            error_msg = f"Failed to get running config: {e}"
            logger.error(error_msg)
            raise NetconfConfigurationError(error_msg) from e
        except Exception as e:
            error_msg = f"Error retrieving running config: {e}"
            logger.error(error_msg)
            raise NetconfConfigurationError(error_msg) from e

    def edit_config(self, config: str) -> RPCReply:
        """
        設定を編集

        Args:
            config: 設定XML

        Returns:
            RPCReply: レスポンス

        Raises:
            NetconfConfigurationError: 設定適用に失敗した場合
        """
        self._ensure_connected()

        try:
            logger.debug("Applying configuration changes")
            reply = self.connection.edit_config(target='running', config=config)
            logger.info("Configuration applied successfully")
            return reply
        except RPCError as e:
            error_msg = f"Failed to apply configuration: {e}"
            logger.error(error_msg)
            raise NetconfConfigurationError(error_msg) from e
        except Exception as e:
            error_msg = f"Error applying configuration: {e}"
            logger.error(error_msg)
            raise NetconfConfigurationError(error_msg) from e

    def verify_config(self, config_path: str) -> str:
        """
        設定パスが存在するか検証

        Args:
            config_path: 検証する設定パス（例: "ip/route"）

        Returns:
            str: 設定XML

        Raises:
            NetconfConfigurationError: 設定が存在しない場合
        """
        filter_xml = f"""
        <filter>
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                {config_path}
            </native>
        </filter>
        """

        result = self.get_running_config(filter_xml)
        if not result:
            raise NetconfConfigurationError(f"Configuration path '{config_path}' not found")

        return result

def create_route_config(routes: List[RouteConfig]) -> str:
    """
    ルート設定用のXMLペイロードを生成

    Args:
        routes: ルート設定のリスト

    Returns:
        str: XML形式の設定ペイロード
    """
    if not routes:
        raise ValueError("No routes provided")

    # 設定用のルート要素を生成
    root = ET.Element("config", xmlns="urn:ietf:params:xml:ns:netconf:base:1.0")
    native = ET.SubElement(root, "native", xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native")
    ip = ET.SubElement(native, "ip")
    route = ET.SubElement(ip, "route")

    # 各ルートを追加
    for route_config in routes:
        route_elem = ET.SubElement(route, "ip-route-interface-forwarding-list")
        ET.SubElement(route_elem, "prefix").text = route_config.prefix
        ET.SubElement(route_elem, "mask").text = route_config.mask

        if route_config.fwd:
            fwd_list = ET.SubElement(route_elem, "fwd-list")
            ET.SubElement(fwd_list, "fwd").text = route_config.fwd

    # XMLを文字列に変換
    xml_str = ET.tostring(root, encoding='unicode')
    logger.debug(f"Generated XML configuration: {xml_str}")
    return xml_str

def format_xml(xml_string: str) -> str:
    """
    XML文字列を整形して読みやすくする

    Args:
        xml_string: 整形前のXML文字列

    Returns:
        str: 整形後のXML文字列
    """
    try:
        dom = xml.dom.minidom.parseString(xml_string)
        pretty_xml = dom.toprettyxml(indent="  ")
        # 空行を除去
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        return '\n'.join(lines)
    except Exception as e:
        logger.error(f"Failed to format XML: {e}")
        return xml_string

def load_routes_from_file(file_path: str) -> List[RouteConfig]:
    """
    JSONファイルからルート設定をロード

    Args:
        file_path: ルート設定を含むJSONファイルのパス

    Returns:
        List[RouteConfig]: ロードされたルート設定データ

    Raises:
        FileNotFoundError: ファイルが見つからない場合
        json.JSONDecodeError: JSONの形式が不正な場合
        ValueError: ルートデータが不正な場合
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Routes file not found: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            routes_data = json.load(f)

        # 基本的な検証
        if not isinstance(routes_data, list):
            raise ValueError(f"Invalid format in {file_path}: expected a list of routes")

        # RouteConfigオブジェクトに変換
        routes = []
        for i, route_data in enumerate(routes_data):
            if not isinstance(route_data, dict):
                logger.warning(f"Skipping invalid route at index {i}: not a dictionary")
                continue

            try:
                route = RouteConfig(**route_data)
                routes.append(route)
            except (TypeError, ValueError) as e:
                logger.warning(f"Skipping invalid route at index {i}: {e}")
                continue

        if not routes:
            raise ValueError("No valid routes found in the file")

        logger.info(f"Loaded {len(routes)} routes from {file_path}")
        return routes

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {e}", e.doc, e.pos)

def parse_arguments() -> argparse.Namespace:
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description='Configure static routes on Cisco devices using NETCONF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --host 192.168.1.1 --username admin --routes-file routes.json
  %(prog)s --host 192.168.1.1 --username admin --get-config
  %(prog)s --host 192.168.1.1 --username admin --routes-file routes.json --dry-run
"""
    )

    # 接続情報
    parser.add_argument('--host', default=DEFAULT_HOST, required=not DEFAULT_HOST,
                        help='Network device hostname or IP address')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'NETCONF port number (default: {DEFAULT_PORT})')
    parser.add_argument('--username', default=DEFAULT_USERNAME, required=not DEFAULT_USERNAME,
                        help='Authentication username')
    parser.add_argument('--password', default='',
                        help='Authentication password (will prompt if not provided)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Connection timeout in seconds (default: 30)')

    # ルート設定
    parser.add_argument('--routes-file', type=str,
                        help='JSON file containing route configurations')

    # 動作モード
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate connection and show config without applying changes')
    parser.add_argument('--get-config', action='store_true',
                        help='Retrieve and display the running configuration')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')

    return parser.parse_args()

def validate_arguments(args: argparse.Namespace) -> None:
    """引数の検証"""
    if not args.get_config and not args.routes_file:
        if not args.dry_run:
            raise ValueError("Either --routes-file or --get-config must be specified")

    if args.routes_file and not Path(args.routes_file).exists():
        raise FileNotFoundError(f"Routes file not found: {args.routes_file}")

def main() -> int:
    """メイン実行関数"""
    try:
        args = parse_arguments()

        # 詳細ログを有効化
        if args.verbose:
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)

        # 引数の検証
        validate_arguments(args)

        # パスワードが指定されていない場合は入力を求める
        password = args.password
        if not password:
            password = getpass.getpass(f"Enter password for {args.username}@{args.host}: ")

        # ルート情報の準備
        routes = []
        if args.routes_file:
            logger.info(f"Loading routes from {args.routes_file}")
            routes = load_routes_from_file(args.routes_file)
        elif not args.get_config:
            # デフォルトのサンプルルート
            logger.info("Using default sample routes")
            routes = [
                RouteConfig(prefix="1.1.1.1", mask="255.255.255.0", fwd="GigabitEthernet1"),
                RouteConfig(prefix="1.1.1.2", mask="255.255.255.255", fwd="Null0"),
                RouteConfig(prefix="1.1.1.3", mask="255.255.255.255", fwd="Null0")
            ]

        # デバイスへの接続（コンテキストマネージャーを使用）
        with NetconfClient(
            host=args.host,
            port=args.port,
            username=args.username,
            password=password,
            timeout=args.timeout
        ) as client:

            # デバイスの機能（capabilities）を表示
            capabilities = client.get_capabilities()
            logger.debug(f"Device capabilities: {len(capabilities)} capabilities found")

            # 実行中の設定を取得
            if args.get_config:
                logger.info("Retrieving running configuration")
                running_config = client.get_running_config()
                formatted_config = format_xml(running_config)
                print("\n=== Running Configuration ===")
                print(formatted_config)
                print("=============================\n")

            # dry-runモードまたはget-configのみの場合は設定変更を行わない
            if args.dry_run or (args.get_config and not routes):
                if args.dry_run and routes:
                    logger.info("Dry run mode - configuration will not be applied")
                    config_xml = create_route_config(routes)
                    formatted_config = format_xml(config_xml)
                    print("\n=== Configuration that would be applied ===")
                    print(formatted_config)
                    print("=========================================\n")
                return 0

            # 設定の適用
            if routes:
                logger.info(f"Applying {len(routes)} route configurations")
                config_xml = create_route_config(routes)
                client.edit_config(config_xml)

                logger.info("Route configuration applied successfully")
                print("Routes configured successfully!")

                # 適用後の設定を確認
                try:
                    verify_config = client.verify_config("ip/route")
                    formatted_config = format_xml(verify_config)
                    print("\n=== Applied Route Configuration ===")
                    print(formatted_config)
                    print("==================================\n")
                except NetconfConfigurationError as e:
                    logger.warning(f"Could not verify configuration: {e}")

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except (NetconfConnectionError, NetconfConfigurationError) as e:
        logger.error(f"NETCONF error: {e}")
        print(f"Error: {e}")
        return 1
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Input error: {e}")
        print(f"Error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        print(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())