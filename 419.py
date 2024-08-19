import os
import requests
from requests.auth import HTTPBasicAuth

def check_for_419_error(url, client_id, client_secret):
    try:
        # Passportクライアントを使用して認証を行う
        auth = HTTPBasicAuth(client_id, client_secret)
        response = requests.post(url + '/oauth/token', auth=auth, data={'grant_type': 'client_credentials', 'scope': '*'})

        if response.status_code == 200:
            access_token = response.json()['access_token']
            headers = {'Authorization': 'Bearer ' + access_token}
            response = requests.get(url + '/api/user', headers=headers)

            if response.status_code == 419:
                print("419 Unknown エラーが検知されました。")
                # アクセストークンを更新する
                updated_access_token = update_access_token(url, client_id, client_secret)
                if updated_access_token:
                    print("アクセストークンを更新しました。再度リクエストを送信します。")
                    headers = {'Authorization': 'Bearer ' + updated_access_token}
                    response = requests.get(url + '/api/user', headers=headers)
                    if response.status_code == 200:
                        print("リクエストは成功しました。")
                    else:
                        print("リクエストが再度失敗しました。")
                else:
                    print("アクセストークンの更新に失敗しました。")
            else:
                print("リクエストは成功しました。")
        else:
            print("認証に失敗しました。")

    except requests.exceptions.RequestException as e:
        print("リクエスト中にエラーが発生しました:", e)

def update_access_token(url, client_id, client_secret):
    try:
        # Passportクライアントを使用して認証を行う
        auth = HTTPBasicAuth(client_id, client_secret)
        response = requests.post(url + '/oauth/token', auth=auth, data={'grant_type': 'client_credentials', 'scope': '*'})

        if response.status_code == 200:
            access_token = response.json()['access_token']
            return access_token
        else:
            print("アクセストークンの取得に失敗しました。")
            return None

    except requests.exceptions.RequestException as e:
        print("リクエスト中にエラーが発生しました:", e)
        return None

if __name__ == "__main__":
    # 環境変数から値を取得する
    url_to_check = os.environ.get("URL_TO_CHECK")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")

    # 値が設定されていることを確認する
    if url_to_check and client_id and client_secret:
        check_for_419_error(url_to_check, client_id, client_secret)
    else:
        print("環境変数が正しく設定されていません。")
