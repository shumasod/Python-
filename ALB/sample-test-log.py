# test_alb_analyzer.py

import random
from datetime import datetime, timedelta
import os

def generate_test_log():
    """テスト用のALBログを生成"""
    
    # テストデータのパラメータ
    ips = ['192.168.1.' + str(i) for i in range(1, 11)]
    paths = ['/api/users', '/api/products', '/api/orders', '/api/login', '/']
    status_codes = [200, 200, 200, 200, 301, 404, 500]  # 200が多めになるように
    user_agents = ['Mozilla/5.0', 'Chrome/91.0', 'Safari/537.36']
    
    # テストログファイル作成
    with open('test_alb.log', 'w') as f:
        start_time = datetime.now() - timedelta(hours=1)
        
        for i in range(100):  # 100行のログを生成
            timestamp = (start_time + timedelta(seconds=i)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            client_ip = f"{random.choice(ips)}:12345"
            target_ip = "10.0.0.1:80"
            request_time = round(random.uniform(0.1, 2.0), 3)
            target_time = round(random.uniform(0.1, 2.0), 3)
            response_time = round(random.uniform(0.1, 2.0), 3)
            status = random.choice(status_codes)
            target_status = status
            received_bytes = random.randint(100, 1000)
            sent_bytes = random.randint(1000, 10000)
            method = random.choice(['GET', 'POST', 'PUT'])
            path = random.choice(paths)
            request = f'"{method} {path} HTTP/1.1"'
            user_agent = f'"{random.choice(user_agents)}"'
            ssl_cipher = "ECDHE-RSA-AES128-GCM-SHA256"
            ssl_protocol = "TLSv1.2"
            
            log_line = f"{timestamp} alb/1 {client_ip} {target_ip} {request_time} {target_time} {response_time} {status} {target_status} {received_bytes} {sent_bytes} {request} {user_agent} {ssl_cipher} {ssl_protocol}\n"
            f.write(log_line)

def main():
    # テストログ生成
    print("テストログを生成中...")
    generate_test_log()
    print("テストログを生成しました: test_alb.log")
    
    # 解析スクリプトのインポートと実行
    from alb_analyzer import analyze_alb_log, print_stats
    
    print("\nログの解析を開始...")
    stats = analyze_alb_log('test_alb.log')
    print_stats(stats)
    
    # テストファイルの削除
    print("\nテストファイルを削除中...")
    os.remove('test_alb.log')
    print("テスト完了")

if __name__ == "__main__":
    main()
