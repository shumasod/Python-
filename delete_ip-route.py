#!/usr/bin/python
import requests
import sys
import json
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

# SSL/TLS証明書の警告を無効化
disable_warnings(InsecureRequestWarning)

# デバイス接続の設定
class DeviceConfig:
    HOST = 'IP'  # ネットワークデバイスのIPアドレスまたはホスト名
    USER = 'cisco'  # ユーザー名
    PASS = 'cisco'  # パスワード
    PORT = 443  # HTTPSポート
    BASE_URL = f"https://{HOST}:{PORT}/restconf"  # ベースURL

def delete_route(ip_address='1.1.1.1', subnet_mask='255.255.255.255'):
    """
    RESTCONFを使用して特定のルートを削除する関数
    
    Args:
        ip_address (str): 削除するルートのIPアドレス
        subnet_mask (str): サブネットマスク
    
    Returns:
        requests.Response: API応答オブジェクト
    
    Raises:
        requests.exceptions.RequestException: API呼び出しに失敗した場合
    """
    try:
        # RESTCONFエンドポイントURL
        url = f"{DeviceConfig.BASE_URL}/data/Cisco-IOS-XE-native:native/ip/route/ip-route-interface-forwarding-list={ip_address},{subnet_mask}"
        
        # RESTCONFヘッダー
        headers = {
            'Content-Type': 'application/yang-data+json',
            'Accept': 'application/yang-data+json'
        }
        
        # DELETEリクエストの実行
        response = requests.delete(
            url,
            auth=(DeviceConfig.USER, DeviceConfig.PASS),
            headers=headers,
            verify=False
        )
        
        # レスポンスコードの確認
        response.raise_for_status()
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"エラーが発生しました: {str(e)}")
        raise

def main():
    """
    メイン関数 - ルート削除を実行し結果を表示
    """
    try:
        response = delete_route()
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {response.text}")
        return 0
    except Exception as e:
        print(f"スクリプトの実行に失敗しました: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
