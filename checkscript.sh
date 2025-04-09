#!/usr/bin/env python3
import os
import subprocess
import requests

# Docker Composeプロジェクトのディレクトリに移動
os.chdir('/home/ec2-user/batch')

# Docker Composeを使用してコンテナが起動しているかチェック
try:
    result = subprocess.run(['/usr/local/bin/docker-compose', 'ps'], 
                          capture_output=True, text=True, check=True)
    
    # 各行を確認し、"Up" と "container_name" の両方が同じ行に含まれているか確認
    container_running = False
    for line in result.stdout.splitlines():
        if "Up" in line and "container_name" in line:
            container_running = True
            break
    
    if container_running:
        # コンテナが起動している場合の処理
        print("コンテナは正常に稼働しています")
    else:
        # コンテナが起動していない場合の処理
        print("コンテナが起動していないため、再起動を試みます")
        
        # Docker Composeを使用してコンテナを再起動
        restart_result = subprocess.run(['/usr/local/bin/docker-compose', 'restart'], 
                                      capture_output=True, text=True, check=False)
        
        if restart_result.returncode == 0:
            # コンテナの再起動が成功した場合の処理
            print("コンテナの再起動が成功しました")
        else:
            # コンテナの再起動が失敗した場合の処理
            print("コンテナの再起動に失敗しました")
            
            # Slackに通知
            slack_webhook_url = ""  # ここにSlack WebhookのURLを設定
            message = "コンテナの再起動に失敗しました"
            
            if slack_webhook_url:  # URLが設定されている場合のみ送信
                requests.post(
                    slack_webhook_url,
                    json={"text": message}
                )

except Exception as e:
    print(f"エラーが発生しました: {e}")
