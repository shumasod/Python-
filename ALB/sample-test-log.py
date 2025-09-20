import os
import random
from datetime import datetime, timedelta
from typing import Dict, List

# Cす
TEST_LOG_FILE = 'test_alb.log'
LOG_ENTRIES = 100
IPS = [f'192.168.1.{i:03d}' for i in range(1, 11)]
PATHS = ['/api/users', '/api/products', '/api/orders', '/api/login', '/']
STATUS_CODES = [200] * 7 + [301, 404, 503]  # 70% success rate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Chrome/91.0.4472.124',
    'Safari/537.36 Edg/91.0.864.59'
]

def generate_test_log() -> None:
    """テスト用のALBログを生成"""
    try:
        with open(TEST_LOG_FILE, 'w') as f:
            start_time = datetime.now() - timedelta(hours=1)
            
            for i in range(LOG_ENTRIES):
                timestamp = (start_time + timedelta(seconds=i)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                log_line = _generate_log_line(timestamp)
                f.write(log_line)
    except IOError as e:
        print(f"ログファイル生成エラー: {e}")
        raise

def _generate_log_line(timestamp: str) -> str:
    """単一のログラインを生成"""
    return (f"{timestamp} alb/1 "
            f"{random.choice(IPS)}:12345 10.0.0.1:80 "
            f"{random.uniform(0.1, 2.0):.3f} {random.uniform(0.1, 2.0):.3f} "
            f"{random.uniform(0.1, 2.0):.3f} {random.choice(STATUS_CODES)} "
            f"{random.choice(STATUS_CODES)} {random.randint(100, 1000)} "
            f"{random.randint(1000, 10000)} "
            f"\"{random.choice(['GET', 'POST', 'PUT'])} {random.choice(PATHS)} HTTP/1.1\" "
            f"\"{random.choice(USER_AGENTS)}\" "
            f"ECDHE-RSA-AES128-GCM-SHA256 TLSv1.2\n")

def main() -> None:
    try:
        print("テストログを生成中...")
        generate_test_log()
        print(f"テストログを生成しました: {TEST_LOG_FILE}")
        
        from alb_analyzer import analyze_alb_log, print_stats
        
        print("\nログの解析を開始...")
        stats = analyze_alb_log(TEST_LOG_FILE)
        print_stats(stats)
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        if os.path.exists(TEST_LOG_FILE):
            os.remove(TEST_LOG_FILE)
            print("\nテストファイルを削除しました")

if __name__ == "__main__":
    main()
