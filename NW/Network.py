import requests
import json

def get_router_ip():
    # ルーターのデフォルトゲートウェイを取得
    gateway = requests.get("https://ifconfig.co/").json()["gateway"]

    # ルーターのIPアドレスを取得
    router_ip = gateway.split("/")[0]

    return router_ip

def login_router(router_ip, username, password):
    # ルーターの設定画面にアクセス
    url = "http://" + router_ip + "/admin"
    payload = {"username": username, "password": password}
    response = requests.post(url, data=payload)

    # ログインに成功したか確認
    if response.status_code == 200:
        return True
    else:
        return False

def change_router_setting(router_ip, setting_name, setting_value):
    # ルーターの設定画面にアクセス
    url = "http://" + router_ip + "/admin/settings/" + setting_name
    payload = {"setting_value": setting_value}
    response = requests.post(url, data=payload)

    # 設定の変更に成功したか確認
    if response.status_code == 200:
        return True
    else:
        return False

if __name__ == "__main__":
    # ルーターのIPアドレスを取得
    router_ip = get_router_ip()

    # ログイン
    login_success = login_router(router_ip, "admin", "password")
    if login_success:
        # 設定を変更
        change_router_setting(router_ip, "wifi_ssid", "My_WiFi_SSID")
        change_router_setting(router_ip, "wifi_password", "My_WiFi_Password")
    else:
        print("ログインに失敗しました。")
