import requests
import json
import socket
import logging
import sys
import os
from getpass import getpass
from requests.exceptions import RequestException, Timeout, ConnectionError

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("router_config.log"),
        logging.StreamHandler()
    ]
)

def get_default_gateway():
    """
    デフォルトゲートウェイ（ルーターのIPアドレス）を取得する
    """
    try:
        # Windowsの場合
        if sys.platform.startswith('win'):
            import subprocess
            output = subprocess.check_output("ipconfig", universal_newlines=True)
            for line in output.split('\n'):
                if "Default Gateway" in line:
                    gateway = line.split(':')[-1].strip()
                    if gateway and gateway != '':
                        return gateway
        # Linux/Macの場合
        else:
            with open('/proc/net/route') as f:
                for line in f:
                    fields = line.strip().split()
                    if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                        continue
                    return socket.inet_ntoa(bytes.fromhex(fields[2].zfill(8))[::-1])
        
        # 上記の方法で取得できなかった場合は手動で入力を求める
        return input("ルーターのIPアドレスを入力してください: ")
    except Exception as e:
        logging.error(f"デフォルトゲートウェイの取得に失敗しました: {e}")
        return input("ルーターのIPアドレスを入力してください: ")

def login_router(router_ip, username, password, max_retries=3):
    """
    ルーターの管理画面にログインする
    
    Args:
        router_ip (str): ルーターのIPアドレス
        username (str): ログインユーザー名
        password (str): ログインパスワード
        max_retries (int): 最大リトライ回数
    
    Returns:
        tuple: (成功したかどうか, セッションオブジェクト)
    """
    session = requests.Session()
    url = f"http://{router_ip}/admin"
    payload = {"username": username, "password": password}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_retries):
        try:
            logging.info(f"ログイン試行中... ({attempt+1}/{max_retries})")
            response = session.post(url, json=payload, headers=headers, timeout=10)
            
            # 実際のルーターによってはステータスコードが異なる場合があるため、
            # レスポンスの内容も確認する
            if response.status_code == 200:
                if "error" not in response.text.lower() and "fail" not in response.text.lower():
                    logging.info("ログイン成功")
                    return True, session
            
            logging.warning(f"ログイン失敗 (ステータスコード: {response.status_code})")
            
            # リトライする前に少し待機
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
                
        except Timeout:
            logging.error(f"接続タイムアウト (試行 {attempt+1}/{max_retries})")
        except ConnectionError:
            logging.error(f"接続エラー: '{url}'にアクセスできません (試行 {attempt+1}/{max_retries})")
        except RequestException as e:
            logging.error(f"リクエストエラー: {e} (試行 {attempt+1}/{max_retries})")
    
    return False, None

def change_router_setting(session, router_ip, setting_name, setting_value):
    """
    ルーターの設定を変更する
    
    Args:
        session (requests.Session): ログイン済みのセッション
        router_ip (str): ルーターのIPアドレス
        setting_name (str): 変更する設定の名前
        setting_value (str): 設定の新しい値
    
    Returns:
        bool: 設定変更が成功したかどうか
    """
    try:
        url = f"http://{router_ip}/admin/settings/{setting_name}"
        payload = {"setting_value": setting_value}
        headers = {"Content-Type": "application/json"}
        
        logging.info(f"設定変更中: {setting_name}")
        response = session.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logging.info(f"設定 '{setting_name}' を '{setting_value}' に変更しました")
            return True
        else:
            logging.error(f"設定変更失敗: ステータスコード {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"設定変更中にエラーが発生しました: {e}")
        return False

def confirm_changes():
    """
    設定変更の確認を求める
    
    Returns:
        bool: ユーザーが変更を確認したかどうか
    """
    confirmation = input("これらの設定を変更してもよろしいですか？ (y/n): ")
    return confirmation.lower() in ['y', 'yes']

def main():
    try:
        # ルーターのIPアドレスを取得
        router_ip = get_default_gateway()
        logging.info(f"ルーターのIPアドレス: {router_ip}")
        
        # ログイン情報の取得（セキュリティのため入力を促す）
        username = input("ルーターのユーザー名を入力してください [admin]: ") or "admin"
        password = getpass("ルーターのパスワードを入力してください: ")
        
        # ログイン
        login_success, session = login_router(router_ip, username, password)
        
        if login_success and session:
            # 変更する設定を取得
            wifi_ssid = input("新しいWi-Fi SSID（ネットワーク名）を入力してください: ")
            wifi_password = getpass("新しいWi-Fiパスワードを入力してください: ")
            
            # 設定内容の確認
            print("\n変更予定の設定:")
            print(f"Wi-Fi SSID: {wifi_ssid}")
            print(f"Wi-Fiパスワード: {'*' * len(wifi_password)}")
            
            # 確認
            if confirm_changes():
                # 設定を変更
                ssid_changed = change_router_setting(session, router_ip, "wifi_ssid", wifi_ssid)
                password_changed = change_router_setting(session, router_ip, "wifi_password", wifi_password)
                
                if ssid_changed and password_changed:
                    logging.info("すべての設定変更が完了しました")
                    print("\n設定変更が完了しました。新しい設定でWi-Fiが再起動する場合があります。")
                else:
                    logging.warning("一部の設定変更が失敗しました")
                    print("\n一部の設定変更が失敗しました。ルーターの設定マニュアルを確認してください。")
            else:
                print("設定変更がキャンセルされました。")
        else:
            logging.error("ログインに失敗しました")
            print("ルーターへのログインに失敗しました。以下を確認してください：")
            print("1. ルーターのIPアドレスが正しいか")
            print("2. ユーザー名とパスワードが正しいか")
            print("3. ルーターが正常に動作しているか")
    except KeyboardInterrupt:
        print("\nプログラムが中断されました。")
    except Exception as e:
        logging.error(f"予期しないエラーが発生しました: {e}")
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
