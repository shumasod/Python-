import requests

def check_for_419_error(url):
    try:
        response = requests.get(url)
        if response.status_code == 419:
            print("419 Unknown エラーが検知されました。")
            # その他の処理をここに追加する
        else:
            print("リクエストは成功しました。")
    except requests.exceptions.RequestException as e:
        print("リクエスト中にエラーが発生しました:", e)

# 検知したいURLを指定して関数を呼び出す
url_to_check = "https://example.com"
check_for_419_error(url_to_check)
