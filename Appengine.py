# deploy_appengine.py
import subprocess

def deploy_appengine():
    # デプロイするアプリケーションのディレクトリ
    app_directory = "your_nodejs_app_directory"

    # アプリケーションのデプロイ
    deploy_command = f"gcloud app deploy {app_directory}/app.yaml"
    subprocess.run(deploy_command, shell=True)

if __name__ == "__main__":
    deploy_appengine()

改修予定
