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
from typing import Dict, List, Optional, Tuple, Union

from ncclient import manager
from ncclient.operations import RPCError
from ncclient.transport.errors import SSHError, SessionCloseError
from ncclient.operations.rpc import RPCReply

# ログ設定
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
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
DEFAULT_PASSWORD = os.environ.get('NETCONF_PASSWORD', '')
# 安全なパスワード処理のため、環境変数からの直接読み込みは推奨されません
# ここでは例として示しています

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
    
    def connect(self) -> bool:
        """
        デバイスに接続
        
        Returns:
            bool: 接続が成功したかどうか
        """
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
            logger.info(f"Connected to {self.host}")
            return True
        except SSHError as e:
            logger.error(f"SSH connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """接続を閉じる"""
        if self.connection:
            try:
                self.connection.close_session()
                logger.info("Session closed")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
    
    def get_capabilities(self) -> List[str]:
        """
        デバイスの機能（capabilities）を取得
        
        Returns:
            List[str]: サポートされている機能のリスト
        """
        if not self.connection:
            logger.error("Not connected to device")
            return []
        
        return list(self.connection.server_capabilities)
    
    def get_running_config(self, filter_str: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        実行中の設定を取得
        
        Args:
            filter_str: 設定フィルター（オプション）
            
        Returns:
            Tuple[bool, Optional[str]]: (成功したかどうか, 設定XML)
        """
        if not self.connection:
            logger.error("Not connected to device")
            return False, None
        
        try:
            if filter_str:
                logger.debug(f"Getting running config with filter: {filter_str}")
                reply = self.connection.get_config(source='running', filter=('subtree', filter_str))
            else:
                logger.debug("Getting full running config")
                reply = self.connection.get_config(source='running')
            
            return True, reply.data_xml
        except RPCError as e:
            logger.error(f"Failed to get running config: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error retrieving running config: {e}")
            return False, None
    
    def edit_config(self, config: str) -> Tuple[bool, Optional[RPCReply]]:
        """
        設定を編集
        
        Args:
            config: 設定XML
            
        Returns:
            Tuple[bool, Optional[RPCReply]]: (成功したかどうか, レスポンス)
        """
        if not self.connection:
            logger.error("Not connected to device")
            return False, None
        
        try:
            logger.debug("Applying configuration changes")
            reply = self.connection.edit_config(target='running', config=config)
            logger.info("Configuration applied successfully")
            return True, reply
        except RPCError as e:
            logger.error(f"Failed to apply configuration: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error applying configuration: {e}")
            return False, None
    
    def verify_config(self, config_path: str) -> Tuple[bool, Optional[str]]:
        """
        設定パスが存在するか検証
        
        Args:
            config_path: 検証する設定パス（例: "native/ip/route"）
        
        Returns:
            Tuple[bool, Optional[str]]: (存在するかどうか, 設定XML)
        """
        filter_xml = f"""
        <filter>
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                {config_path}
            </native>
        </filter>
        """
        
        success, result = self.get_running_config(filter_xml)
        if success and result:
            # 返されたXMLに目的の設定が含まれているか確認
            return True, result
        else:
            return False, None


def create_route_config(routes: List[Dict[str, str]]) -> str:
    """
    ルート設定用のXMLペイロードを生成
    
    Args:
        routes: ルート情報のリスト [{"prefix": "x.x.x.x", "mask": "x.x.x.x", "fwd": "interface"}]
        
    Returns:
        str: XML形式の設定ペイロード
    """
    # 設定用のルート要素を生成
    root = ET.Element("config", xmlns="urn:ietf:params:xml:ns:netconf:base:1.0")
    native = ET.SubElement(root, "native", xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native")
    ip = ET.SubElement(native, "ip")
    route = ET.SubElement(ip, "route")
    
    # 各ルートを追加
    for r in routes:
        if not all(k in r for k in ['prefix', 'mask']):
            logger.warning(f"Skipping invalid route: {r} - missing required keys")
            continue
            
        route_elem = ET.SubElement(route, "ip-route-interface-forwarding-list")
        ET.SubElement(route_elem, "prefix").text = r['prefix']
        ET.SubElement(route_elem, "mask").text = r['mask']
        
        if 'fwd' in r and r['fwd']:
            fwd_list = ET.SubElement(route_elem, "fwd-list")
            ET.SubElement(fwd_list, "fwd").text = r['fwd']
    
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
        return pretty_xml
    except Exception as e:
        logger.error(f"Failed to format XML: {e}")
        return xml_string


def load_routes_from_file(file_path: str) -> List[Dict[str, str]]:
    """
    JSONファイルからルート設定をロード
    
    Args:
        file_path: ルート設定を含むJSONファイルのパス
        
    Returns:
        List[Dict[str, str]]: ロードされたルート設定データ
    """
    try:
        with open(file_path, 'r') as f:
            routes = json.load(f)
            
            # 基本的な検証
            if not isinstance(routes, list):
                logger.error(f"Invalid format in {file_path}: expected a list of routes")
                return []
                
            # 各ルートの必須フィールドを検証
            valid_routes = []
            for i, route in enumerate(routes):
                if not isinstance(route, dict):
                    logger.warning(f"Skipping invalid route at index {i}: not a dictionary")
                    continue
                    
                if not all(k in route for k in ['prefix', 'mask']):
                    logger.warning(f"Skipping invalid route at index {i}: missing required keys")
                    continue
                    
                valid_routes.append(route)
                
            return valid_routes
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load routes from {file_path}: {e}")
        return []


def parse_arguments():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description='Configure static routes on Cisco devices using NETCONF'
    )
    
    # 接続情報
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help='Network device hostname or IP address')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help='NETCONF port number (default: 830)')
    parser.add_argument('--username', default=DEFAULT_USERNAME,
                        help='Authentication username')
    parser.add_argument('--password', default=DEFAULT_PASSWORD,
                        help='Authentication password (will prompt if not provided)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Connection timeout in seconds (default: 30)')
    
    # ルート設定
    parser.add_argument('--routes-file', 
                        help='JSON file containing route configurations')
    
    # 動作モード
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate connection and show config without applying changes')
    parser.add_argument('--get-config', action='store_true',
                        help='Retrieve and display the running configuration')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    
    return parser.parse_args()


def main():
    """メイン実行関数"""
    args = parse_arguments()
    
    # 詳細ログを有効化
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    # 必須パラメータの検証
    if not args.host:
        print("Error: Host is required. Use --host or set NETCONF_HOST environment variable.")
        return 1
    
    if not args.username:
        print("Error: Username is required. Use --username or set NETCONF_USERNAME environment variable.")
        return 1
    
    # パスワードが指定されていない場合は入力を求める
    password = args.password
    if not password:
        password = getpass.getpass(f"Enter password for {args.username}@{args.host}: ")
    
    # ルート情報の準備
    routes = []
    if args.routes_file:
        logger.info(f"Loading routes from {args.routes_file}")
        routes = load_routes_from_file(args.routes_file)
        if not routes:
            logger.error("No valid routes found in the file")
            if not args.get_config:  # get-configだけの場合はルートが不要
                print("Error: No valid routes found in the file.")
                return 1
    elif not args.get_config:  # get-configだけの場合はデフォルトルートは不要
        # デフォルトのサンプルルート
        logger.info("Using default sample routes")
        routes = [
            {"prefix": "1.1.1.1", "mask": "255.255.255.0", "fwd": "GigabitEthernet1"},
            {"prefix": "1.1.1.2", "mask": "255.255.255.255", "fwd": "Null0"},
            {"prefix": "1.1.1.3", "mask": "255.255.255.255", "fwd": "Null0"}
        ]
    
    # NetconfClientのインスタンス化
    client = NetconfClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=password,
        timeout=args.timeout
    )
    
    # デバイスへの接続
    if not client.connect():
        logger.error("Connection failed")
        print(f"Error: Could not connect to {args.host}:{args.port}")
        return 1
    
    try:
        # デバイスの機能（capabilities）を表示
        capabilities = client.get_capabilities()
        logger.debug(f"Device capabilities: {capabilities}")
        
        # 実行中の設定を取得
        if args.get_config:
            logger.info("Retrieving running configuration")
            success, running_config = client.get_running_config()
            if success and running_config:
                formatted_config = format_xml(running_config)
                print("\n=== Running Configuration ===\n")
                print(formatted_config)
                print("\n=============================\n")
            else:
                logger.error("Failed to retrieve running configuration")
                print("Error: Could not retrieve running configuration")
                return 1
        
        # dry-runモードまたはget-configのみの場合は設定変更を行わない
        if args.dry_run or args.get_config and not routes:
            if args.dry_run:
                logger.info("Dry run mode - configuration will not be applied")
                # 生成した設定を表示
                if routes:
                    config_xml = create_route_config(routes)
                    formatted_config = format_xml(config_xml)
                    print("\n=== Configuration that would be applied ===\n")
                    print(formatted_config)
                    print("\n=========================================\n")
            return 0
        
        # 設定の適用
        if routes:
            logger.info("Applying route configuration")
            config_xml = create_route_config(routes)
            success, response = client.edit_config(config_xml)
            
            if success:
                logger.info("Route configuration applied successfully")
                print("Routes configured successfully!")
                
                # 適用後の設定を確認
                verify_success, verify_config = client.verify_config("ip/route")
                if verify_success and verify_config:
                    formatted_config = format_xml(verify_config)
                    print("\n=== Applied Route Configuration ===\n")
                    print(formatted_config)
                    print("\n==================================\n")
                return 0
            else:
                logger.error("Failed to apply route configuration")
                print("Error: Failed to apply route configuration")
                return 1
    finally:
        # 接続のクリーンアップ
        client.disconnect()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        print(f"Error: {e}")
        sys.exit(1)
