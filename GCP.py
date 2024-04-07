import subprocess
import json
import datetime
from google.cloud import storage

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

def save_log_to_cloud_storage(bucket_name, log_data):
    """
    Cloud Storageにログを保存する関数
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    now = datetime.datetime.now()
    filename = f"log_{now.strftime('%Y%m%d%H%M%S')}.txt"
    blob = bucket.blob(filename)
    blob.upload_from_string(log_data)
    print(f"Log saved to Cloud Storage: gs://{bucket_name}/{filename}")

def delete_old_logs(bucket_name):
    """
    Cloud Storageの指定されたバケットから古いログを削除する関数
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    for blob in blobs:
        # ログが90日以上前の場合に削除
        if (datetime.datetime.now() - blob.time_created).days >= 90:
            blob.delete()
            print(f"Deleted old log: {blob.name}")

if __name__ == "__main__":
    # 以下の変数を適切な値に変更してください
    gcp_project_id = "your_gcp_project_id"
    app_engine_service_name = "your_app_engine_service_name"
    app_engine_version = "your_app_engine_version"
    cloud_storage_bucket_name = "your_cloud_storage_bucket_name"

    # App Engineエンドポイントの取得
    app_engine_endpoint = get_app_engine_endpoint(gcp_project_id, app_engine_service_name, app_engine_version)

    if app_engine_endpoint:
        print(f"App Engine Endpoint: {app_engine_endpoint}")

        # ログを保存
        log_data = f"Monitoring App Engine Endpoint: {app_engine_endpoint}"
        save_log_to_cloud_storage(cloud_storage_bucket_name, log_data)

        # 古いログの削除
        delete_old_logs(cloud_storage_bucket_name)
    else:
        print(f"Error: Unable to retrieve App Engine Endpoint for {app_engine_service_name} ({app_engine_version})")
