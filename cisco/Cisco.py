import sys
import logging
from ncclient import manager
import xml.etree.ElementTree as ET
from ncclient.operations import RPCError
from ncclient.transport.errors import SSHError
from typing import Dict, List, Optional

# ロギングの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_route_config(routes: List[Dict[str, str]]) -> str:
    """
    ルート設定のXMLペイロードを生成する
    
    :param routes: ルート情報のリスト
    :return: XML形式の設定ペイロード
    """
    root = ET.Element("config", xmlns="urn:ietf:params:xml:ns:netconf:base:1.0")
    native = ET.SubElement(root, "native", xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native")
    ip = ET.SubElement(native, "ip")
    route = ET.SubElement(ip, "route")

    for r in routes:
        route_elem = ET.SubElement(route, "ip-route-interface-forwarding-list")
        ET.SubElement(route_elem, "prefix").text = r['prefix']
        ET.SubElement(route_elem, "mask").text = r['mask']
        fwd_list = ET.SubElement(route_elem, "fwd-list")
        ET.SubElement(fwd_list, "fwd").text = r.get('fwd', '')

    return ET.tostring(root, encoding='unicode')

def connect_and_configure(host: str, port: int, username: str, password: str, routes: List[Dict[str, str]]) -> Optional[str]:
    """
    デバイスに接続し、設定を適用する
    
    :param host: デバイスのIPアドレス
    :param port: NCTCONFポート
    :param username: ユーザー名
    :param password: パスワード
    :param routes: ルート情報のリスト
    :return: 実行中の設定（XML形式）、エラーの場合はNone
    """
    try:
        with manager.connect(host=host, port=port, username=username, password=password,
                             hostkey_verify=False, device_params={'name': 'iosxe'}, timeout=30) as m:
            
            # 設定ペイロードの生成
            payload = create_route_config(routes)
            logger.info("Generated configuration payload")

            # 設定の適用
            try:
                response = m.edit_config(target='running', config=payload)
                logger.info("Configuration applied successfully")
            except RPCError as e:
                logger.error(f"Failed to apply configuration: {e}")
                return None

            # 実行中の設定の取得
            try:
                running_config = m.get_config(source='running').data_xml
                logger.info("Retrieved running configuration")
                return running_config
            except RPCError as e:
                logger.error(f"Failed to retrieve running configuration: {e}")
                return None

    except SSHError as e:
        logger.error(f"Failed to connect to the device: {e}")
        return None

def format_xml(xml_string: str) -> str:
    """
    XML文字列を整形する
    
    :param xml_string: 整形前のXML文字列
    :return: 整形後のXML文字列
    """
    root = ET.fromstring(xml_string)
    return ET.tostring(root, encoding='unicode', pretty_print=True)

if __name__ == "__main__":
    # ルート情報
    routes = [
        {"prefix": "1.1.1.1", "mask": "255.255.255.0"},
        {"prefix": "1.1.1.2", "mask": "255.255.255.255", "fwd": "Null0"},
        {"prefix": "1.1.1.3", "mask": "255.255.255.255", "fwd": "Null0"}
    ]

    # デバイス接続情報
    device_info = {
        "host": "172.16.62.151",
        "port": 830,
        "username": "cisco",
        "password": "cisco"
    }

    # 設定の適用と取得
    running_config = connect_and_configure(**device_info, routes=routes)

    if running_config:
        print('###########################################################################')
        print('### XML Formatted String')
        print('###########################################################################')
        print(format_xml(running_config))
    else:
        logger.error("Failed to retrieve the running configuration")
        sys.exit(1)
