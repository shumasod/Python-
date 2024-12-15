# deploy_appengine.py
import subprocess
import sys

def deploy_appengine(app_directory):
    # アプリケーションのデプロイコマンド
    deploy_command = f"gcloud app deploy {app_directory}/app.yaml"

    try:
        # コマンドを実行し、結果を取得
        result = subprocess.run(deploy_command, shell=True, check=True, text=True, capture_output=True)
        print("デプロイ成功:\n", result.stdout)
    except subprocess.CalledProcessError as e:
        print("デプロイに失敗しました:\n", e.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用法: python deploy_appengine.py <アプリケーションのディレクトリ>")
        sys.exit(1)

    app_directory = sys.argv[1]
    deploy_appengine(app_directory)
