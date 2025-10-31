#!/usr/bin/env python3
“””
ALB ログ解析ツールのテストスクリプト

実際のALBログ形式に準拠したテストデータを生成し、
解析ツールの動作を検証します。
“””

import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

class HTTPMethod(Enum):
“”“HTTPメソッド”””
GET = “GET”
POST = “POST”
PUT = “PUT”
DELETE = “DELETE”
PATCH = “PATCH”

class HTTPVersion(Enum):
“”“HTTPバージョン”””
HTTP_1_0 = “HTTP/1.0”
HTTP_1_1 = “HTTP/1.1”
HTTP_2_0 = “HTTP/2.0”

@dataclass
class LogGeneratorConfig:
“”“ログジェネレータの設定”””
log_file: Path = Path(‘test_alb.log’)
num_entries: int = 100
time_span_hours: int = 1

```
# IPアドレス範囲
ip_range_start: str = "192.168.1.1"
ip_range_count: int = 10

# ステータスコードの分布 (code: weight)
status_distribution: dict = None

# パス
paths: List[str] = None

# User-Agent
user_agents: List[str] = None

# レスポンスタイムの範囲（秒）
response_time_min: float = 0.01
response_time_max: float = 3.0

# 遅いリクエストを意図的に生成する割合
slow_request_rate: float = 0.1
slow_request_time_min: float = 1.5
slow_request_time_max: float = 5.0

def __post_init__(self):
    """デフォルト値の設定"""
    if self.status_distribution is None:
        self.status_distribution = {
            200: 70,  # 70%
            201: 5,   # 5%
            301: 5,   # 5%
            400: 5,   # 5%
            404: 10,  # 10%
            500: 3,   # 3%
            503: 2,   # 2%
        }
    
    if self.paths is None:
        self.paths = [
            '/api/users',
            '/api/users/{id}',
            '/api/products',
            '/api/products/{id}',
            '/api/orders',
            '/api/orders/{id}',
            '/api/login',
            '/api/logout',
            '/health',
            '/',
        ]
    
    if self.user_agents is None:
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'curl/7.68.0',
            'python-requests/2.26.0',
        ]
```

class ALBLogGenerator:
“”“ALBログのテストデータを生成するクラス”””

```
def __init__(self, config: LogGeneratorConfig):
    """
    Args:
        config: ジェネレータの設定
    """
    self.config = config
    self.ips = self._generate_ip_addresses()
    self.status_codes = self._prepare_status_codes()

def _generate_ip_addresses(self) -> List[str]:
    """IPアドレスのリストを生成"""
    base = self.config.ip_range_start.rsplit('.', 1)[0]
    start = int(self.config.ip_range_start.rsplit('.', 1)[1])
    return [f"{base}.{start + i}" for i in range(self.config.ip_range_count)]

def _prepare_status_codes(self) -> List[int]:
    """重み付けされたステータスコードのリストを生成"""
    codes = []
    for code, weight in self.config.status_distribution.items():
        codes.extend([code] * weight)
    return codes

def generate(self) -> None:
    """テストログファイルを生成"""
    try:
        with open(self.config.log_file, 'w', encoding='utf-8') as f:
            start_time = datetime.now() - timedelta(hours=self.config.time_span_hours)
            
            for i in range(self.config.num_entries):
                # 時系列でログを生成
                timestamp = self._calculate_timestamp(start_time, i)
                log_line = self._generate_log_line(timestamp)
                f.write(log_line)
                
        print(f"✓ テストログを生成しました: {self.config.log_file}")
        print(f"  エントリ数: {self.config.num_entries}")
        print(f"  ファイルサイズ: {self._get_file_size()}")
        
    except IOError as e:
        print(f"✗ ログファイル生成エラー: {e}")
        raise

def _calculate_timestamp(self, start_time: datetime, index: int) -> datetime:
    """
    ログエントリのタイムスタンプを計算
    
    Args:
        start_time: 開始時刻
        index: エントリのインデックス
        
    Returns:
        タイムスタンプ
    """
    # より現実的な分布（時間経過に伴いリクエストが増減）
    hours = self.config.time_span_hours
    seconds_per_entry = (hours * 3600) / self.config.num_entries
    offset = seconds_per_entry * index
    
    # ランダムなジッターを追加
    jitter = random.uniform(-seconds_per_entry * 0.3, seconds_per_entry * 0.3)
    
    return start_time + timedelta(seconds=offset + jitter)

def _generate_log_line(self, timestamp: datetime) -> str:
    """
    単一のログラインを生成
    
    Args:
        timestamp: タイムスタンプ
        
    Returns:
        ALBログ形式の文字列
    """
    # ALBログのフォーマット:
    # type timestamp elb client:port target:port request_processing_time 
    # target_processing_time response_processing_time elb_status_code 
    # target_status_code received_bytes sent_bytes "request" "user_agent" 
    # ssl_cipher ssl_protocol target_group_arn "trace_id" "domain_name" 
    # "chosen_cert_arn" matched_rule_priority request_creation_time 
    # "actions_executed" "redirect_url" "error_reason"
    
    client_ip = random.choice(self.ips)
    target_ip = f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}"
    
    # レスポンスタイムの生成（意図的に遅いリクエストを含める）
    is_slow = random.random() < self.config.slow_request_rate
    if is_slow:
        processing_times = [
            random.uniform(self.config.slow_request_time_min, self.config.slow_request_time_max)
            for _ in range(3)
        ]
    else:
        processing_times = [
            random.uniform(self.config.response_time_min, self.config.response_time_max)
            for _ in range(3)
        ]
    
    # ステータスコード
    elb_status = random.choice(self.status_codes)
    target_status = elb_status  # 通常は同じ
    
    # リクエスト
    method = random.choice(list(HTTPMethod)).value
    path = random.choice(self.config.paths)
    # パスのプレースホルダーを実際の値に置換
    if '{id}' in path:
        path = path.replace('{id}', str(random.randint(1, 1000)))
    http_version = random.choice(list(HTTPVersion)).value
    request = f"{method} {path} {http_version}"
    
    # その他のフィールド
    received_bytes = random.randint(100, 2000)
    sent_bytes = random.randint(500, 50000)
    user_agent = random.choice(self.config.user_agents)
    
    # ログラインの組み立て
    log_line = (
        f"http {timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z "
        f"app/my-loadbalancer/50dc6c495c0c9188 "
        f"{client_ip}:{random.randint(10000, 65535)} "
        f"{target_ip}:80 "
        f"{processing_times[0]:.6f} {processing_times[1]:.6f} {processing_times[2]:.6f} "
        f"{elb_status} {target_status} "
        f"{received_bytes} {sent_bytes} "
        f'"{request}" '
        f'"{user_agent}" '
        f"ECDHE-RSA-AES128-GCM-SHA256 TLSv1.2 "
        f"arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "
        f'"Root=1-67891233-abcdef012345678912345678" '
        f'"www.example.com" '
        f'"arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012" '
        f"0 {timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z "
        f'"forward" "-" "-" "-" "-" "-" "-"\n'
    )
    
    return log_line

def _get_file_size(self) -> str:
    """ファイルサイズを人間が読みやすい形式で取得"""
    size = self.config.log_file.stat().st_size
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"
```

class TestRunner:
“”“テストの実行を管理するクラス”””

```
def __init__(self, log_file: Path):
    """
    Args:
        log_file: テスト対象のログファイル
    """
    self.log_file = log_file

def run(self) -> int:
    """
    テストを実行
    
    Returns:
        終了コード (0: 成功, 1: 失敗)
    """
    try:
        print("\n" + "=" * 60)
        print("ALB ログ解析ツール - テスト実行")
        print("=" * 60)
        
        # 解析ツールをインポート
        from alb_analyzer import ALBLogParser, ALBLogAnalyzer, StatsReporter
        
        print("\nログの解析を開始...")
        
        # 解析実行
        parser = ALBLogParser(slow_threshold=1.0)
        analyzer = ALBLogAnalyzer(parser)
        stats = analyzer.analyze(self.log_file)
        
        if stats is None:
            print("✗ 解析に失敗しました")
            return 1
        
        # レポート出力
        reporter = StatsReporter(top_n=5)
        reporter.print_report(stats)
        
        # 基本的な検証
        self._validate_results(stats)
        
        print("\n✓ テストが完了しました")
        return 0
        
    except ImportError as e:
        print(f"✗ モジュールのインポートエラー: {e}")
        print("  alb_analyzer.py が同じディレクトリにあることを確認してください")
        return 1
    except Exception as e:
        print(f"✗ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1

def _validate_results(self, stats) -> None:
    """結果の妥当性を検証"""
    print("\n【検証】")
    
    checks = [
        ("総リクエスト数 > 0", stats.total_requests > 0),
        ("ユニークIP数 > 0", len(stats.ips) > 0),
        ("ステータスコード集計あり", len(stats.status_codes) > 0),
        ("パス集計あり", len(stats.paths) > 0),
        ("レスポンスタイム記録あり", len(stats.response_times) > 0),
    ]
    
    all_passed = True
    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False
    
    if not all_passed:
        print("\n⚠️  一部の検証が失敗しました")
```

def cleanup(log_file: Path) -> None:
“”“テストファイルをクリーンアップ”””
try:
if log_file.exists():
log_file.unlink()
print(f”\n✓ テストファイルを削除しました: {log_file}”)
except Exception as e:
print(f”\n⚠️  テストファイルの削除に失敗しました: {e}”)

def main() -> int:
“”“メイン処理”””
# 設定
config = LogGeneratorConfig(
log_file=Path(‘test_alb.log’),
num_entries=100,
time_span_hours=1,
)

```
try:
    # ログ生成
    print("テストログを生成中...")
    generator = ALBLogGenerator(config)
    generator.generate()
    
    # テスト実行
    runner = TestRunner(config.log_file)
    return runner.run()
    
except KeyboardInterrupt:
    print("\n\n中断されました")
    return 1
except Exception as e:
    print(f"\n✗ エラーが発生しました: {e}")
    return 1
finally:
    # クリーンアップ
    cleanup(config.log_file)
```

if **name** == “**main**”:
sys.exit(main())