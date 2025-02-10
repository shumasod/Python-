#!/usr/bin/env python
from typing import Optional, Dict, List
from dataclasses import dataclass
from ncclient import manager
from ncclient.operations import RPCError
import lxml.etree as ET
import logging
import sys
from pathlib import Path
import yaml
import socket
from contextlib import contextmanager
import ssl
import ipaddress

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class NetworkConfig:
    """ネットワーク設定のデータクラス"""
    host: str
    port: int = 830
    username: str = 'cisco'
    password: str = 'cisco'
    timeout: int = 30
    device_type: str = 'iosxe'
    verify_ssl: bool = False

class RouteConfig:
    """ルート設定を管理するクラス"""
    NAMESPACES = {
        'xc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
        'base': 'urn:ietf:params:xml:ns:netconf:base:1.0',
        'cisco': 'http://cisco.com/ns/yang/Cisco-IOS-XE-native'
    }

    def __init__(self, routes: List[str]):
        """
        初期化
        
        Args:
            routes: 削除するルートのリスト (CIDR形式)
        """
        self.routes = routes
        self._validate_routes()

    def _validate_routes(self) -> None:
        """ルートの妥当性を検証"""
        for route in self.routes:
            try:
                ipaddress.ip_network(route)
            except ValueError as e:
                raise ValueError(f"無効なルート形式: {route} - {str(e)}")

    def _create_route_xml(self, ip: str, mask: str) -> ET.Element:
        """
        ルート削除用のXML要素を作成
        
        Args:
            ip: IPアドレス
            mask: サブネットマスク
        Returns:
            ET.Element: XML要素
        """
        route = ET.Element(
            'ip-route-interface-forwarding-list',
            {f'{{{self.NAMESPACES["xc"]}}}operation': 'delete'}
        )
        prefix = ET.SubElement(route, 'prefix')
        prefix.text = ip
        netmask = ET.SubElement(route, 'mask')
        netmask.text = mask
        return route

    def generate_payload(self) -> str:
        """
        設定ペイロードを生成
        
        Returns:
            str: XML形式の設定ペイロード
        """
        # ルート基本構造の作成
        config = ET.Element('config', nsmap=self.NAMESPACES)
        native = ET.SubElement(config, f'{{{self.NAMESPACES["cisco"]}}}native')
        ip = ET.SubElement(native, 'ip')
        route = ET.SubElement(ip, 'route')

        # 各ルートの追加
        for route_cidr in self.routes:
            network = ipaddress.ip_network(route_cidr)
            route.append(self._create_route_xml(
                str(network.network_address),
                str(network.netmask)
            ))

        return ET.tostring(config, pretty_print=True).decode()

class NetconfManager:
    """Netconfセッションを管理するクラス"""

    def __init__(self, config: NetworkConfig):
        """
        初期化
        
        Args:
            config: ネットワーク接続設定
        """
        self.config = config
        self._validate_connection_params()

    def _validate_connection_params(self) -> None:
        """接続パラメータの妥当性を検証"""
        try:
            ipaddress.ip_address(self.config.host)
        except ValueError:
            raise ValueError(f"無効なホストアドレス: {self.config.host}")

        if not 1 <= self.config.port <= 65535:
            raise ValueError(f"無効なポート番号: {self.config.port}")

    @contextmanager
    def _connect(self):
        """Netconfセッションのコンテキストマネージャー"""
        conn = None
        try:
            conn = manager.connect(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                hostkey_verify=self.config.verify_ssl,
                device_params={'name': self.config.device_type},
                timeout=self.config.timeout
            )
            yield conn
        except (socket.error, ssl.SSLError) as e:
            raise ConnectionError(f"接続エラー: {str(e)}")
        finally:
            if conn:
                conn.close_session()

    def apply_configuration(self, payload: str) -> Dict:
        """
        設定を適用
        
        Args:
            payload: XML形式の設定ペイロード
        Returns:
            Dict: 操作結果
        """
        try:
            with self._connect() as m:
                # 設定の適用
                response = m.edit_config(target='running', config=payload)
                
                # レスポンスの解析
                xml_response = response.xml
                formatted_response = ET.tostring(
                    ET.fromstring(xml_response),
                    pretty_print=True
                ).decode()
                
                return {
                    'success': True,
                    'raw_response': xml_response,
                    'formatted_response': formatted_response
                }
                
        except RPCError as e:
            logger.error(f"RPC エラー: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'rpc'
            }
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'general'
            }

def load_config(config_path: str) -> NetworkConfig:
    """
    設定ファイルを読み込み
    
    Args:
        config_path: 設定ファイルのパス
    Returns:
        NetworkConfig: ネットワーク設定
    """
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        return NetworkConfig(**config_data)
    except Exception as e:
        raise ValueError(f"設定ファイルの読み込みエラー: {str(e)}")

def main():
    """メイン実行関数"""
    try:
        # ルート設定
        routes_to_delete = [
            '1.1.1.1/32',
            '1.1.1.2/32',
            '1.1.1.3/32'
        ]

        # 設定ファイルの読み込み（存在する場合）
        config_path = Path('netconf_config.yml')
        if config_path.exists():
            network_config = load_config(str(config_path))
        else:
            # デフォルト設定
            network_config = NetworkConfig(
                host='172.16.62.151',
                port=830,
                username='cisco',
                password='cisco'
            )

        # ルート設定の生成
        route_config = RouteConfig(routes_to_delete)
        payload = route_config.generate_payload()

        logger.info("生成された設定ペイロード:")
        logger.info(payload)

        # 設定の適用
        netconf = NetconfManager(network_config)
        result = netconf.apply_configuration(payload)

        if result['success']:
            logger.info("設定が正常に適用されました")
            logger.info("レスポンス:")
            print(result['formatted_response'])
        else:
            logger.error(f"設定の適用に失敗しました: {result['error']}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
