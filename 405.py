import requests

def check_for_405_error(api_url, http_method):
    try:
        response = requests.request(http_method, api_url)
        if response.status_code == 405:
            print("405 Unknown エラーが検知されました。")
            # その他の処理をここに追加する
        else:
            print("リクエストは成功しました。")
    except requests.exceptions.RequestException as e:
        print("リクエスト中にエラーが発生しました:", e)

# 検知したいLaravel APIのエンドポイントとHTTPメソッドを指定して関数を呼び出す
api_url_to_check = "https://example.com/api/endpoint"
http_method_to_check = "GET"  # 検証したいHTTPメソッドを指定
check_for_405_error(api_url_to_check, http_method_to_check)
