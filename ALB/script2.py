#!/usr/bin/env python3
“””
ALB (Application Load Balancer) ログ解析ツール

ALBのアクセスログを解析し、以下の統計情報を提供します:

- ステータスコード別の集計
- エラー率
- レスポンスタイムの分析
- アクセスパターンの可視化
  “””

import sys
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple
from enum import Enum

class LogLevel(Enum):
“”“ログレベルの定義”””
INFO = “info”
WARNING = “warning”
ERROR = “error”

@dataclass
class ALBLogStats:
“”“ALBログの統計情報を保持するデータクラス”””
status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
total_requests: int = 0
errors: int = 0
slow_requests: int = 0
ips: Set[str] = field(default_factory=set)
paths: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
response_times: List[float] = field(default_factory=list)
failed_lines: int = 0

```
@property
def error_rate(self) -> float:
    """エラー率を計算"""
    return (self.errors / self.total_requests * 100) if self.total_requests > 0 else 0.0

@property
def slow_request_rate(self) -> float:
    """遅いリクエストの割合を計算"""
    return (self.slow_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0

@property
def avg_response_time(self) -> float:
    """平均レスポンスタイムを計算"""
    return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

@property
def max_response_time(self) -> float:
    """最大レスポンスタイムを取得"""
    return max(self.response_times) if self.response_times else 0.0
```

class ALBLogParser:
“”“ALBログのパーサークラス”””

```
# ALBログのフィールドインデックス
TYPE_INDEX = 0
TIMESTAMP_INDEX = 1
CLIENT_IP_INDEX = 2
TARGET_IP_INDEX = 3
REQUEST_PROCESSING_TIME_INDEX = 4
TARGET_PROCESSING_TIME_INDEX = 5
RESPONSE_PROCESSING_TIME_INDEX = 6
ELB_STATUS_CODE_INDEX = 7
TARGET_STATUS_CODE_INDEX = 8
RECEIVED_BYTES_INDEX = 9
SENT_BYTES_INDEX = 10
REQUEST_INDEX = 11

SLOW_REQUEST_THRESHOLD = 1.0  # 秒

def __init__(self, slow_threshold: float = SLOW_REQUEST_THRESHOLD):
    """
    Args:
        slow_threshold: 遅いリクエストと判定する閾値（秒）
    """
    self.slow_threshold = slow_threshold
    self.logger = logging.getLogger(__name__)

def parse_line(self, line: str) -> Optional[Tuple[int, str, str, float]]:
    """
    ログの1行をパースする
    
    Args:
        line: ログの1行
        
    Returns:
        (ステータスコード, クライアントIP, パス, 処理時間) のタプル
        パースに失敗した場合はNone
    """
    try:
        parts = line.strip().split(' ')
        
        if len(parts) < self.REQUEST_INDEX + 1:
            self.logger.warning(f"フィールド数が不足しています: {len(parts)}個")
            return None
        
        # ステータスコード
        status_code = int(parts[self.ELB_STATUS_CODE_INDEX])
        
        # クライアントIP
        client_ip = parts[self.CLIENT_IP_INDEX].split(':')[0]
        
        # 処理時間の合計
        processing_time = (
            float(parts[self.REQUEST_PROCESSING_TIME_INDEX]) +
            float(parts[self.TARGET_PROCESSING_TIME_INDEX]) +
            float(parts[self.RESPONSE_PROCESSING_TIME_INDEX])
        )
        
        # リクエストパス
        request = parts[self.REQUEST_INDEX].strip('"')
        path = self._extract_path(request)
        
        return status_code, client_ip, path, processing_time
        
    except (ValueError, IndexError) as e:
        self.logger.error(f"行の解析エラー: {e}")
        return None

@staticmethod
def _extract_path(request: str) -> str:
    """
    HTTPリクエストからパスを抽出
    
    Args:
        request: HTTPリクエスト文字列
        
    Returns:
        パス部分
    """
    try:
        # "GET /path?query HTTP/1.1" から "/path" を抽出
        parts = request.split(' ')
        if len(parts) >= 2:
            return parts[1].split('?')[0]
    except Exception:
        pass
    return "unknown"
```

class ALBLogAnalyzer:
“”“ALBログの解析を行うクラス”””

```
def __init__(self, parser: ALBLogParser):
    """
    Args:
        parser: ALBLogParserのインスタンス
    """
    self.parser = parser
    self.logger = logging.getLogger(__name__)

def analyze(self, file_path: Path) -> Optional[ALBLogStats]:
    """
    ログファイルを解析する
    
    Args:
        file_path: ログファイルのパス
        
    Returns:
        統計情報、失敗時はNone
    """
    if not file_path.exists():
        self.logger.error(f"ファイルが見つかりません: {file_path}")
        return None
    
    stats = ALBLogStats()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                parsed = self.parser.parse_line(line)
                
                if parsed is None:
                    stats.failed_lines += 1
                    continue
                
                status_code, client_ip, path, processing_time = parsed
                
                # 統計情報を更新
                self._update_stats(stats, status_code, client_ip, path, processing_time)
                
    except IOError as e:
        self.logger.error(f"ファイル読み込みエラー: {e}")
        return None
    
    self.logger.info(f"解析完了: {stats.total_requests}行処理、{stats.failed_lines}行失敗")
    return stats

def _update_stats(
    self, 
    stats: ALBLogStats, 
    status_code: int, 
    client_ip: str, 
    path: str, 
    processing_time: float
) -> None:
    """統計情報を更新"""
    stats.total_requests += 1
    stats.status_codes[status_code] += 1
    stats.ips.add(client_ip)
    stats.paths[path] += 1
    stats.response_times.append(processing_time)
    
    # エラー判定 (4xx, 5xx)
    if status_code >= 400:
        stats.errors += 1
    
    # 遅いリクエスト判定
    if processing_time > self.parser.slow_threshold:
        stats.slow_requests += 1
```

class StatsReporter:
“”“統計情報をレポート形式で出力するクラス”””

```
def __init__(self, top_n: int = 5):
    """
    Args:
        top_n: Top N件を表示する数
    """
    self.top_n = top_n

def print_report(self, stats: ALBLogStats) -> None:
    """
    統計レポートを出力
    
    Args:
        stats: 統計情報
    """
    if stats.total_requests == 0:
        print("解析対象のリクエストがありません")
        return
    
    print("\n" + "=" * 60)
    print("ALB ログ解析レポート")
    print("=" * 60)
    
    self._print_summary(stats)
    self._print_status_codes(stats)
    self._print_performance_metrics(stats)
    self._print_top_paths(stats)
    
    if stats.failed_lines > 0:
        print(f"\n⚠️  解析失敗行数: {stats.failed_lines:,}")

def _print_summary(self, stats: ALBLogStats) -> None:
    """サマリー情報を出力"""
    print("\n【概要】")
    print(f"  総リクエスト数    : {stats.total_requests:>12,}")
    print(f"  ユニークIP数      : {len(stats.ips):>12,}")
    print(f"  エラー数 (4xx/5xx): {stats.errors:>12,} ({stats.error_rate:>5.1f}%)")

def _print_status_codes(self, stats: ALBLogStats) -> None:
    """ステータスコード別の集計を出力"""
    print("\n【ステータスコード別集計】")
    for status, count in sorted(stats.status_codes.items()):
        percentage = (count / stats.total_requests) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {status}: {count:>8,} ({percentage:>5.1f}%) {bar}")

def _print_performance_metrics(self, stats: ALBLogStats) -> None:
    """パフォーマンスメトリクスを出力"""
    print("\n【パフォーマンス】")
    print(f"  平均レスポンスタイム: {stats.avg_response_time:>8.3f}秒")
    print(f"  最大レスポンスタイム: {stats.max_response_time:>8.3f}秒")
    print(f"  遅いリクエスト (>1s): {stats.slow_requests:>8,} ({stats.slow_request_rate:>5.1f}%)")

def _print_top_paths(self, stats: ALBLogStats) -> None:
    """アクセスの多いパスを出力"""
    print(f"\n【最もアクセスの多いパス Top {self.top_n}】")
    sorted_paths = sorted(
        stats.paths.items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:self.top_n]
    
    for i, (path, count) in enumerate(sorted_paths, 1):
        percentage = (count / stats.total_requests) * 100
        print(f"  {i}. {path}")
        print(f"     {count:,}回 ({percentage:.1f}%)")
```

def setup_logging(level: str = “INFO”) -> None:
“”“ロギングの設定”””
logging.basicConfig(
level=getattr(logging, level.upper()),
format=’%(levelname)s: %(message)s’
)

def main() -> int:
“”“メイン処理”””
setup_logging()

```
if len(sys.argv) != 2:
    print("使用方法: python alb_analyzer.py <ログファイルのパス>")
    print("\n例:")
    print("  python alb_analyzer.py /path/to/alb.log")
    return 1

log_file = Path(sys.argv[1])

# 解析実行
parser = ALBLogParser(slow_threshold=1.0)
analyzer = ALBLogAnalyzer(parser)
stats = analyzer.analyze(log_file)

if stats is None:
    return 1

# レポート出力
reporter = StatsReporter(top_n=5)
reporter.print_report(stats)

return 0
```

if **name** == “**main**”:
sys.exit(main())