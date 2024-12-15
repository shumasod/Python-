import sys
from collections import defaultdict
from datetime import datetime

def analyze_alb_log(file_path):
    # 統計情報を保持する辞書
    stats = {
        'status_codes': defaultdict(int),
        'total_requests': 0,
        'errors': 0,
        'slow_requests': 0,
        'ips': set(),
        'paths': defaultdict(int)
    }
    
    # ログファイルを読み込む
    try:
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    # スペースで分割
                    parts = line.strip().split(' ')
                    
                    # 基本的な情報を抽出
                    status_code = int(parts[7])  # ELBのステータスコード
                    client_ip = parts[2].split(':')[0]
                    request = parts[11]
                    processing_time = float(parts[4]) + float(parts[5]) + float(parts[6])
                    
                    # 統計情報を更新
                    stats['total_requests'] += 1
                    stats['status_codes'][status_code] += 1
                    stats['ips'].add(client_ip)
                    
                    # エラーをカウント (4xx, 5xx)
                    if status_code >= 400:
                        stats['errors'] += 1
                    
                    # 遅いリクエストをカウント (1秒以上)
                    if processing_time > 1.0:
                        stats['slow_requests'] += 1
                    
                    # パスごとのカウント
                    try:
                        path = request.split(' ')[1].split('?')[0]
                        stats['paths'][path] += 1
                    except:
                        pass
                        
                except Exception as e:
                    print(f"行の解析でエラー: {e}")
                    continue
                    
        return stats
        
    except FileNotFoundError:
        print(f"ファイルが見つかりません: {file_path}")
        return None

def print_stats(stats):
    if not stats:
        return
    
    print("\n=== ALBログ解析結果 ===")
    print(f"\n総リクエスト数: {stats['total_requests']:,}")
    print(f"ユニークIP数: {len(stats['ips']):,}")
    
    print("\nステータスコード別集計:")
    for status, count in sorted(stats['status_codes'].items()):
        percentage = (count / stats['total_requests']) * 100
        print(f"  {status}: {count:,} ({percentage:.1f}%)")
    
    print(f"\nエラー数 (4xx/5xx): {stats['errors']:,}")
    print(f"遅いリクエスト (>1s): {stats['slow_requests']:,}")
    
    print("\n最もアクセスの多いパス (Top 5):")
    sorted_paths = sorted(stats['paths'].items(), key=lambda x: x[1], reverse=True)[:5]
    for path, count in sorted_paths:
        print(f"  {path}: {count:,}")

def main():
    if len(sys.argv) != 2:
        print("使用方法: python alb_analyzer.py <ログファイルのパス>")
        return
    
    log_file = sys.argv[1]
    stats = analyze_alb_log(log_file)
    if stats:
        print_stats(stats)

if __name__ == "__main__":
    main()
