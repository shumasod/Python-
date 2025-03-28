import pandas as pd
import json
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
from typing import List, Dict

class ALBLogAnalyzer:
    def __init__(self, log_file: str):
        """
        ALBログを分析するクラス
        Args:
            log_file: ALBログファイルのパス
        """
        self.log_file = log_file
        self.logs = []
        self.df = None

    def parse_log_line(self, line: str) -> dict:
        """単一のログ行をパースする"""
        fields = line.strip().split(' ')
        try:
            return {
                'timestamp': fields[0],
                'elb': fields[1],
                'client_ip': fields[2].split(':')[0],
                'target_ip': fields[3].split(':')[0],
                'request_processing_time': float(fields[4]),
                'target_processing_time': float(fields[5]),
                'response_processing_time': float(fields[6]),
                'elb_status_code': int(fields[7]),
                'target_status_code': int(fields[8]),
                'received_bytes': int(fields[9]),
                'sent_bytes': int(fields[10]),
                'request': fields[11],
                'user_agent': ' '.join(fields[12:-2]),
                'ssl_cipher': fields[-2],
                'ssl_protocol': fields[-1]
            }
        except Exception as e:
            print(f"Error parsing line: {e}")
            return None

    def load_logs(self):
        """ログファイルを読み込みDataFrameに変換"""
        with open(self.log_file, 'r') as f:
            self.logs = [self.parse_log_line(line) for line in f if line.strip()]
        self.logs = [log for log in self.logs if log is not None]
        self.df = pd.DataFrame(self.logs)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])

    def get_error_summary(self) -> Dict:
        """エラーの概要を取得"""
        error_summary = {
            'total_requests': len(self.df),
            'error_requests': len(self.df[self.df['elb_status_code'] >= 400]),
            'error_rates': {}
        }
        
        status_counts = self.df['elb_status_code'].value_counts()
        for status, count in status_counts.items():
            if status >= 400:
                error_summary['error_rates'][status] = {
                    'count': count,
                    'percentage': (count / len(self.df)) * 100
                }
        
        return error_summary

    def get_slow_requests(self, threshold: float = 1.0) -> pd.DataFrame:
        """遅いリクエストを抽出"""
        total_time = (
            self.df['request_processing_time'] +
            self.df['target_processing_time'] +
            self.df['response_processing_time']
        )
        return self.df[total_time > threshold].sort_values(
            by=['target_processing_time'], ascending=False
        )

    def get_traffic_pattern(self, interval: str = '1min') -> pd.DataFrame:
        """時間帯ごとのトラフィックパターンを分析"""
        return self.df.resample(interval, on='timestamp').size()

    def analyze(self) -> Dict:
        """主要な分析結果をまとめて返す"""
        analysis = {
            'error_summary': self.get_error_summary(),
            'slow_requests': len(self.get_slow_requests()),
            'traffic_stats': {
                'total_requests': len(self.df),
                'unique_ips': len(self.df['client_ip'].unique()),
                'avg_response_time': self.df['target_processing_time'].mean(),
                'p95_response_time': self.df['target_processing_time'].quantile(0.95),
                'p99_response_time': self.df['target_processing_time'].quantile(0.99)
            }
        }
        return analysis

    def plot_traffic_pattern(self):
        """トラフィックパターンを可視化"""
        traffic = self.get_traffic_pattern()
        plt.figure(figsize=(15, 5))
        traffic.plot()
        plt.title('Traffic Pattern Over Time')
        plt.xlabel('Time')
        plt.ylabel('Number of Requests')
        plt.grid(True)
        plt.show()

def main():
    """使用例"""
    analyzer = ALBLogAnalyzer('alb.log')
    analyzer.load_logs()
    
    # 分析実行
    analysis = analyzer.analyze()
    
    # 結果表示
    print("=== ALB Log Analysis ===")
    print(f"\nTotal Requests: {analysis['traffic_stats']['total_requests']}")
    print(f"Unique IPs: {analysis['traffic_stats']['unique_ips']}")
    print(f"\nError Summary:")
    for status, data in analysis['error_summary']['error_rates'].items():
        print(f"Status {status}: {data['count']} requests ({data['percentage']:.2f}%)")
    
    print(f"\nPerformance Metrics:")
    print(f"Average Response Time: {analysis['traffic_stats']['avg_response_time']:.3f}s")
    print(f"95th Percentile: {analysis['traffic_stats']['p95_response_time']:.3f}s")
    print(f"99th Percentile: {analysis['traffic_stats']['p99_response_time']:.3f}s")
    
    # トラフィックパターンの可視化
    analyzer.plot_traffic_pattern()

if __name__ == "__main__":
    main()
