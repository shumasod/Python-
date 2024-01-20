import subprocess
import json

def get_app_engine_endpoint(project_id, service_name, version):
    """
    App Engineのエンドポイントを取得する関数
    """
    try:
        # gcloudコマンドを使用してApp Engineのサービス情報を取得
        command = ['gcloud', 'app', 'services', 'describe', '--project', project_id, service_name]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        service_info = json.loads(result.stdout)

        # サービスのバージョン情報を取得
        for v in service_info.get('versions', []):
            if v.get('id') == version:
                return v.get('versionUrl')

        return None
    except subprocess.CalledProcessError as e:
        print(f"Error while getting App Engine endpoint: {e}")
        return None

if __name__ == "__main__":
    # 以下の変数を適切な値に変更してください
    gcp_project_id = "your_gcp_project_id"
    app_engine_service_name = "your_app_engine_service_name"
    app_engine_version = "your_app_engine_version"

    # App Engineエンドポイントの取得
    app_engine_endpoint = get_app_engine_endpoint(gcp_project_id, app_engine_service_name, app_engine_version)

    if app_engine_endpoint:
        print(f"App Engine Endpoint: {app_engine_endpoint}")
    else:
        print(f"Error: Unable to retrieve App Engine Endpoint for {app_engine_service_name} ({app_engine_version})")
