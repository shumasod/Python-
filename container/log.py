#!/usr/bin/env python3
import os
import re
import sys
import subprocess
import requests
import argparse
import logging
from datetime import datetime
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_clf_log(log_entry):
    """Common Log Format (CLF) のログエントリを解析する"""
    clf_pattern = r'(?P<host>[\d\.]+) - - \[(?P<timestamp>.*?)\] "(?P<request>.*?)" (?P<status>\d+) (?P<bytes_sent>\d+)'
    match = re.match(clf_pattern, log_entry)
    if match:
        data = match.groupdict()
        data['timestamp'] = datetime.strptime(data['timestamp'], '%d/%b/%Y:%H:%M:%S %z')
        return data
    else:
        return None

def find_docker_compose_path():
    """システム上のdocker-composeコマンドのパスを探す"""
    # 一般的なdocker-composeコマンド名のリスト
    possible_commands = [
        'docker-compose',
        'docker compose',  # Docker CLI統合版
    ]
    
    for cmd in possible_commands:
        try:
            # 'which' コマンドでパスを確認 (Unix/Linux/Mac)
            if ' ' not in cmd:  # 単一コマンド (docker-compose)
                result = subprocess.run(['which', cmd], 
                                     capture_output=True, text=True, check=False)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            else:  # 複合コマンド (docker compose)
                parts = cmd.split()
                result = subprocess.run(['which', parts[0]], 
                                     capture_output=True, text=True, check=False)
                if result.returncode == 0 and result.stdout.strip():
                    return cmd
        except Exception:
            continue
    
    # Windows環境の場合は単にコマンド名を返す
    if sys.platform.startswith('win'):
        return 'docker-compose'
    
    return None

def check_container_status(project_dir, container_name, compose_path):
    """指定されたコンテナの稼働状態を確認する"""
    logger.info(f"コンテナ '{container_name}' の状態を確認します...")
    
    try:
        # プロジェクトディレクトリに移動
        original_dir = os.getcwd()
        os.chdir(project_dir)
        
        # docker-compose コマンドを実行
        if ' ' in compose_path:  # 'docker compose' のような複合コマンド
            cmd_parts = compose_path.split() + ['ps', '--format', 'json']
            result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False)
        else:
            result = subprocess.run([compose_path, 'ps', '--format', 'json'], 
                                  capture_output=True, text=True, check=False)
        
        # 新しいDocker Composeバージョン (JSONフォーマット) の出力でない場合
        if result.returncode != 0 or not result.stdout.strip().startswith('['):
            # 従来のテキスト形式で再試行
            if ' ' in compose_path:
                cmd_parts = compose_path.split() + ['ps']
                result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False)
            else:
                result = subprocess.run([compose_path, 'ps'], 
                                      capture_output=True, text=True, check=False)
            
            # 各行を確認し、コンテナ名とUp状態を検索
            container_running = False
            for line in result.stdout.splitlines():
                if container_name in line and "Up" in line:
                    container_running = True
                    break
        else:
            # JSON形式の出力を解析 (新しいDocker Compose)
            import json
            containers = json.loads(result.stdout)
            container_running = any(
                c.get('Name', '').endswith(container_name) and 
                c.get('State', '') == 'running'
                for c in containers
            )
        
        # 元のディレクトリに戻る
        os.chdir(original_dir)
        
        return container_running
    
    except Exception as e:
        logger.error(f"コンテナ状態確認中にエラーが発生しました: {e}")
        # 元のディレクトリに戻る
        if 'original_dir' in locals():
            os.chdir(original_dir)
        return False

def restart_container(project_dir, compose_path):
    """Docker Composeプロジェクトを再起動する"""
    logger.info("コンテナの再起動を試みます...")
    
    try:
        # プロジェクトディレクトリに移動
        original_dir = os.getcwd()
        os.chdir(project_dir)
        
        # docker-compose restart コマンドを実行
        if ' ' in compose_path:  # 'docker compose' のような複合コマンド
            cmd_parts = compose_path.split() + ['restart']
            result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False)
        else:
            result = subprocess.run([compose_path, 'restart'], 
                                  capture_output=True, text=True, check=False)
        
        # 元のディレクトリに戻る
        os.chdir(original_dir)
        
        if result.returncode == 0:
            logger.info("コンテナの再起動が成功しました")
            return True
        else:
            logger.error(f"コンテナの再起動に失敗しました: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"コンテナ再起動中にエラーが発生しました: {e}")
        # 元のディレクトリに戻る
        if 'original_dir' in locals():
            os.chdir(original_dir)
        return False

def send_slack_notification(webhook_url, message):
    """Slackに通知を送信する"""
    if not webhook_url:
        logger.warning("Slack Webhook URLが設定されていないため、通知は送信されません")
        return False
    
    try:
        response = requests.post(
            webhook_url,
            json={"text": message}
        )
        if response.status_code == 200:
            logger.info("Slack通知を送信しました")
            return True
        else:
            logger.error(f"Slack通知の送信に失敗しました: {response.status_code} {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Slack通知の送信中にエラーが発生しました: {e}")
        return False

def check_container_logs(project_dir, container_name, compose_path, lines=10):
    """コンテナのログを取得して解析する"""
    logger.info(f"コンテナ '{container_name}' のログを解析します...")
    
    try:
        # プロジェクトディレクトリに移動
        original_dir = os.getcwd()
        os.chdir(project_dir)
        
        # docker-compose logs コマンドを実行
        if ' ' in compose_path:  # 'docker compose' のような複合コマンド
            cmd_parts = compose_path.split() + ['logs', '--tail', str(lines), container_name]
            result = subprocess.run(cmd_parts, capture_output=True, text=True, check=False)
        else:
            result = subprocess.run([compose_path, 'logs', '--tail', str(lines), container_name], 
                                  capture_output=True, text=True, check=False)
        
        # 元のディレクトリに戻る
        os.chdir(original_dir)
        
        if result.returncode == 0:
            log_lines = result.stdout.splitlines()
            parsed_logs = []
            
            for line in log_lines:
                # 一般的なCLFログ形式を検出
                if re.search(r'\d+\.\d+\.\d+\.\d+ - - \[\d+/\w+/\d+:\d+:\d+:\d+ \+\d+\]', line):
                    parsed_log = parse_clf_log(line)
                    if parsed_log:
                        parsed_logs.append(parsed_log)
            
            return parsed_logs
        else:
            logger.error(f"ログの取得に失敗しました: {result.stderr}")
            return []
    
    except Exception as e:
        logger.error(f"ログ解析中にエラーが発生しました: {e}")
        # 元のディレクトリに戻る
        if 'original_dir' in locals():
            os.chdir(original_dir)
        return []

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Dockerコンテナの稼働状態を監視するスクリプト')
    parser.add_argument('--dir', '-d', 
                      default=os.getcwd(),
                      help='Docker Composeプロジェクトのディレクトリ (デフォルト: カレントディレクトリ)')
    parser.add_argument('--container', '-c', 
                      default='package_batch',
                      help='監視対象のコンテナ名 (デフォルト: package_batch)')
    parser.add_argument('--slack-url', '-s',
                      default='',
                      help='Slack Webhook URL (省略可)')
    parser.add_argument('--analyze-logs', '-a',
                      action='store_true',
                      help='コンテナのログを解析する')
    parser.add_argument('--log-lines', '-l',
                      type=int, 
                      default=10,
                      help='解析するログの行数 (デフォルト: 10)')
    parser.add_argument('--verbose', '-v',
                      action='store_true',
                      help='詳細なログ出力')
    
    args = parser.parse_args()
    
    # 詳細ログの設定
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # プロジェクトディレクトリの絶対パスを取得
    project_dir = os.path.abspath(args.dir)
    logger.debug(f"Docker Composeプロジェクトディレクトリ: {project_dir}")
    
    # docker-composeコマンドのパスを探す
    compose_path = find_docker_compose_path()
    if not compose_path:
        logger.error("docker-composeコマンドが見つかりません")
        return 1
    
    logger.debug(f"Docker Composeコマンド: {compose_path}")
    
    # コンテナの状態を確認
    container_running = check_container_status(project_dir, args.container, compose_path)
    
    if container_running:
        logger.info(f"コンテナ '{args.container}' は正常に稼働しています")
        
        # ログ解析が要求されている場合
        if args.analyze_logs:
            logs = check_container_logs(project_dir, args.container, compose_path, args.log_lines)
            if logs:
                logger.info(f"{len(logs)}件のログエントリを解析しました:")
                for log in logs:
                    logger.info(f"  - {log['host']} [{log['timestamp']}] \"{log['request']}\" {log['status']} {log['bytes_sent']}")
            else:
                logger.info("解析可能なログエントリは見つかりませんでした")
    else:
        logger.warning(f"コンテナ '{args.container}' が起動していないため、再起動を試みます")
        
        # コンテナを再起動
        restart_success = restart_container(project_dir, compose_path)
        
        if not restart_success:
            # 再起動に失敗した場合、Slackに通知
            message = f"コンテナ '{args.container}' の再起動に失敗しました"
            if args.slack_url:
                send_slack_notification(args.slack_url, message)
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
