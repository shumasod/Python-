import aiohttp
import asyncio
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict, Any, Optional, Set, Callable, Union
import logging
import logging.handlers
from dataclasses import dataclass, field
import os
import json
import hashlib
import aiofiles
from urllib.parse import urljoin, urlparse
import re
from pathlib import Path
import sqlite3
from contextlib import asynccontextmanager
import time
import random
from tqdm.asyncio import tqdm
import socket
import sys
from enum import Enum

# 非同期ループの最適化

if os.name == ‘nt’:
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class LogLevel(Enum):
“”“ログレベル定義”””
DEBUG = “DEBUG”
INFO = “INFO”
WARNING = “WARNING”
ERROR = “ERROR”
CRITICAL = “CRITICAL”

class CloudLogProvider(Enum):
“”“クラウドログプロバイダー”””
CLOUDWATCH = “cloudwatch”
DATADOG = “datadog”
NEW_RELIC = “newrelic”
ELASTIC = “elastic”
SPLUNK = “splunk”
CUSTOM_HTTP = “custom_http”

@dataclass
class CloudLoggingConfig:
“”“クラウドログ設定”””
provider: CloudLogProvider
enabled: bool = True

```
# 共通設定
service_name: str = "web-scraper"
environment: str = "production"
version: str = "1.0.0"

# AWS CloudWatch設定
aws_region: str = "us-east-1"
log_group: str = "/aws/application/scraper"
log_stream: str = None  # Noneの場合は自動生成
aws_access_key: str = None
aws_secret_key: str = None

# Datadog設定
datadog_api_key: str = None
datadog_site: str = "datadoghq.com"

# New Relic設定
newrelic_license_key: str = None
newrelic_app_name: str = "web-scraper"

# Elastic/ELK設定
elastic_host: str = "localhost"
elastic_port: int = 9200
elastic_index: str = "scraper-logs"
elastic_username: str = None
elastic_password: str = None

# カスタムHTTP設定
custom_endpoint: str = None
custom_headers: Dict[str, str] = field(default_factory=dict)
custom_auth_token: str = None

# バッファリング設定
buffer_size: int = 100
flush_interval: int = 30  # 秒
max_retries: int = 3
timeout: int = 10
```

class StructuredLogger:
“”“構造化ログ出力クラス”””

```
def __init__(self, name: str, config: CloudLoggingConfig):
    self.name = name
    self.config = config
    self.logger = logging.getLogger(name)
    self.logger.setLevel(logging.DEBUG)
    
    # バッファリング用
    self.log_buffer = []
    self.last_flush = time.time()
    
    # セッション情報
    self.session_id = self._generate_session_id()
    self.hostname = socket.gethostname()
    self.process_id = os.getpid()
    
    self._setup_handlers()
    
    # 定期フラッシュタスク
    if config.enabled:
        asyncio.create_task(self._periodic_flush())

def _generate_session_id(self) -> str:
    """セッションID生成"""
    timestamp = int(time.time())
    random_part = random.randint(1000, 9999)
    return f"{timestamp}_{random_part}"

def _setup_handlers(self):
    """ログハンドラー設定"""
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    self.logger.addHandler(console_handler)
    
    # ファイルハンドラー（ローテーション対応）
    file_handler = logging.handlers.RotatingFileHandler(
        f'logs/{self.name}.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    self.logger.addHandler(file_handler)

def _create_structured_log(self, level: str, message: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
    """構造化ログエントリ作成"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'level': level,
        'message': message,
        'service': self.config.service_name,
        'environment': self.config.environment,
        'version': self.config.version,
        'session_id': self.session_id,
        'hostname': self.hostname,
        'process_id': self.process_id,
        'logger_name': self.name
    }
    
    if extra:
        log_entry.update(extra)
    
    return log_entry

async def _send_to_cloud(self, log_entries: List[Dict[str, Any]]):
    """クラウドログサービスへの送信"""
    if not self.config.enabled or not log_entries:
        return
    
    try:
        if self.config.provider == CloudLogProvider.CLOUDWATCH:
            await self._send_to_cloudwatch(log_entries)
        elif self.config.provider == CloudLogProvider.DATADOG:
            await self._send_to_datadog(log_entries)
        elif self.config.provider == CloudLogProvider.NEW_RELIC:
            await self._send_to_newrelic(log_entries)
        elif self.config.provider == CloudLogProvider.ELASTIC:
            await self._send_to_elastic(log_entries)
        elif self.config.provider == CloudLogProvider.CUSTOM_HTTP:
            await self._send_to_custom_http(log_entries)
            
    except Exception as e:
        self.logger.error(f"クラウドログ送信エラー: {e}")

async def _send_to_cloudwatch(self, log_entries: List[Dict[str, Any]]):
    """AWS CloudWatch Logsへの送信"""
    try:
        import boto3
        
        client = boto3.client(
            'logs',
            region_name=self.config.aws_region,
            aws_access_key_id=self.config.aws_access_key,
            aws_secret_access_key=self.config.aws_secret_key
        )
        
        log_stream = self.config.log_stream or f"{self.hostname}-{self.session_id}"
        
        # ログストリーム作成（存在しない場合）
        try:
            client.create_log_stream(
                logGroupName=self.config.log_group,
                logStreamName=log_stream
            )
        except client.exceptions.ResourceAlreadyExistsException:
            pass
        
        # ログイベント準備
        events = []
        for entry in log_entries:
            events.append({
                'timestamp': int(datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).timestamp() * 1000),
                'message': json.dumps(entry, ensure_ascii=False)
            })
        
        # ログ送信
        client.put_log_events(
            logGroupName=self.config.log_group,
            logStreamName=log_stream,
            logEvents=events
        )
        
    except ImportError:
        self.logger.error("boto3がインストールされていません。pip install boto3を実行してください。")
    except Exception as e:
        self.logger.error(f"CloudWatch送信エラー: {e}")

async def _send_to_datadog(self, log_entries: List[Dict[str, Any]]):
    """Datadogへの送信"""
    if not self.config.datadog_api_key:
        return
    
    url = f"https://http-intake.logs.{self.config.datadog_site}/v1/input/{self.config.datadog_api_key}"
    
    async with aiohttp.ClientSession() as session:
        for entry in log_entries:
            payload = {
                'timestamp': entry['timestamp'],
                'level': entry['level'],
                'message': entry['message'],
                'service': entry['service'],
                'environment': entry['environment'],
                'version': entry['version'],
                'hostname': entry['hostname'],
                'session_id': entry['session_id']
            }
            
            async with session.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    self.logger.error(f"Datadog送信エラー: {response.status}")

async def _send_to_newrelic(self, log_entries: List[Dict[str, Any]]):
    """New Relicへの送信"""
    if not self.config.newrelic_license_key:
        return
    
    url = "https://log-api.newrelic.com/log/v1"
    headers = {
        'Content-Type': 'application/json',
        'X-License-Key': self.config.newrelic_license_key
    }
    
    async with aiohttp.ClientSession() as session:
        payload = {
            'logs': [{
                'timestamp': int(datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).timestamp() * 1000),
                'message': entry['message'],
                'logtype': entry['level'],
                'service': entry['service'],
                'environment': entry['environment'],
                'version': entry['version'],
                'hostname': entry['hostname'],
                'session_id': entry['session_id']
            } for entry in log_entries]
        }
        
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        ) as response:
            if response.status != 200:
                self.logger.error(f"New Relic送信エラー: {response.status}")

async def _send_to_elastic(self, log_entries: List[Dict[str, Any]]):
    """Elasticsearchへの送信"""
    url = f"http://{self.config.elastic_host}:{self.config.elastic_port}/{self.config.elastic_index}/_bulk"
    
    headers = {'Content-Type': 'application/x-ndjson'}
    if self.config.elastic_username and self.config.elastic_password:
        import base64
        credentials = base64.b64encode(f"{self.config.elastic_username}:{self.config.elastic_password}".encode()).decode()
        headers['Authorization'] = f"Basic {credentials}"
    
    # バルクペイロード作成
    bulk_data = []
    for entry in log_entries:
        index_action = {'index': {'_index': self.config.elastic_index}}
        bulk_data.append(json.dumps(index_action))
        bulk_data.append(json.dumps(entry))
    
    payload = '\n'.join(bulk_data) + '\n'
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        ) as response:
            if response.status not in [200, 201]:
                self.logger.error(f"Elasticsearch送信エラー: {response.status}")

async def _send_to_custom_http(self, log_entries: List[Dict[str, Any]]):
    """カスタムHTTPエンドポイントへの送信"""
    if not self.config.custom_endpoint:
        return
    
    headers = {'Content-Type': 'application/json'}
    headers.update(self.config.custom_headers)
    
    if self.config.custom_auth_token:
        headers['Authorization'] = f"Bearer {self.config.custom_auth_token}"
    
    payload = {'logs': log_entries}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            self.config.custom_endpoint,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        ) as response:
            if response.status not in [200, 201]:
                self.logger.error(f"カスタムHTTP送信エラー: {response.status}")

async def _periodic_flush(self):
    """定期的なログフラッシュ"""
    while True:
        await asyncio.sleep(self.config.flush_interval)
        await self._flush_logs()

async def _flush_logs(self):
    """ログバッファをフラッシュ"""
    if not self.log_buffer:
        return
    
    logs_to_send = self.log_buffer.copy()
    self.log_buffer.clear()
    
    await self._send_to_cloud(logs_to_send)
    self.last_flush = time.time()

def _log(self, level: LogLevel, message: str, extra: Dict[str, Any] = None):
    """内部ログ処理"""
    # 標準ログ出力
    getattr(self.logger, level.value.lower())(message, extra=extra or {})
    
    # 構造化ログをバッファに追加
    if self.config.enabled:
        structured_log = self._create_structured_log(level.value, message, extra)
        self.log_buffer.append(structured_log)
        
        # バッファサイズチェック
        if len(self.log_buffer) >= self.config.buffer_size:
            asyncio.create_task(self._flush_logs())

def debug(self, message: str, **kwargs):
    """デバッグログ"""
    self._log(LogLevel.DEBUG, message, kwargs)

def info(self, message: str, **kwargs):
    """情報ログ"""
    self._log(LogLevel.INFO, message, kwargs)

def warning(self, message: str, **kwargs):
    """警告ログ"""
    self._log(LogLevel.WARNING, message, kwargs)

def error(self, message: str, **kwargs):
    """エラーログ"""
    self._log(LogLevel.ERROR, message, kwargs)

def critical(self, message: str, **kwargs):
    """重大エラーログ"""
    self._log(LogLevel.CRITICAL, message, kwargs)

async def close(self):
    """リソース解放"""
    await self._flush_logs()
```

# ログ設定

def setup_cloud_logger(name: str, cloud_config: CloudLoggingConfig = None) -> StructuredLogger:
“”“クラウド対応ロガーのセットアップ”””
if cloud_config is None:
cloud_config = CloudLoggingConfig(
provider=CloudLogProvider.CUSTOM_HTTP,
enabled=False  # デフォルトは無効
)

```
# ログディレクトリ作成
Path('logs').mkdir(exist_ok=True)

return StructuredLogger(name, cloud_config)
```

# メインのロガーインスタンス

logger = setup_cloud_logger(**name**)

@dataclass
class ScrapingConfig:
“”“スクレイピング設定の拡張版”””
base_url: str
output_dir: str = “data”
cache_dir: str = “cache”
log_dir: str = “logs”

```
# リクエスト設定
max_retries: int = 3
timeout: int = 15
delay_range: tuple = (1, 3)  # レート制限用の遅延範囲
max_concurrent: int = 10
chunk_size: int = 50

# キャッシュ設定
cache_expire_hours: int = 24
use_cache: bool = True

# 解析設定
parse_rules: Dict[str, str] = field(default_factory=dict)
required_fields: List[str] = field(default_factory=list)

# データ品質設定
min_content_length: int = 50
max_content_length: int = 50000

# エクスポート設定
export_formats: List[str] = field(default_factory=lambda: ['csv', 'json', 'excel'])

# クラウドログ設定
cloud_logging: CloudLoggingConfig = field(default_factory=lambda: CloudLoggingConfig(
    provider=CloudLogProvider.CUSTOM_HTTP,
    enabled=False
))

headers: Dict[str, str] = field(default_factory=lambda: {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})

def __post_init__(self):
    # ディレクトリ作成
    for directory in [self.output_dir, self.cache_dir, self.log_dir]:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # デフォルトの解析ルール
    if not self.parse_rules:
        self.parse_rules = {
            'title': 'h1, .title, .headline, title',
            'content': 'article, .content, .post-content, .article-body, main',
            'date': 'time, .date, .published, .post-date',
            'author': '.author, .byline, .writer',
            'tags': '.tags, .categories, .keywords'
        }
```

class RateLimiter:
“”“レート制限管理クラス”””
def **init**(self, delay_range: tuple = (1, 3), logger_instance: StructuredLogger = None):
self.delay_range = delay_range
self.last_request = 0
self.logger = logger_instance or logger

```
async def wait(self):
    """適切な間隔での待機"""
    now = time.time()
    elapsed = now - self.last_request
    delay = random.uniform(*self.delay_range)
    
    if elapsed < delay:
        wait_time = delay - elapsed
        self.logger.debug(f"レート制限待機中", wait_time=wait_time, elapsed=elapsed, target_delay=delay)
        await asyncio.sleep(wait_time)
    
    self.last_request = time.time()
```

class EnhancedURLCache:
“”“拡張URLキャッシュ管理クラス”””
def **init**(self, cache_dir: str, expire_hours: int = 24, logger_instance: StructuredLogger = None):
self.cache_dir = Path(cache_dir)
self.expire_hours = expire_hours
self.db_path = self.cache_dir / “cache_metadata.db”
self.logger = logger_instance or logger
self._init_db()

```
def _init_db(self):
    """キャッシュメタデータDB初期化"""
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                url_hash TEXT PRIMARY KEY,
                url TEXT,
                cached_at TIMESTAMP,
                file_path TEXT,
                content_type TEXT,
                status_code INTEGER
            )
        """)
    self.logger.info("キャッシュデータベース初期化完了", db_path=str(self.db_path))

def _get_cache_path(self, url: str) -> tuple:
    """URLのキャッシュパスとハッシュを取得"""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    cache_file = self.cache_dir / f"{url_hash}.html"
    return cache_file, url_hash

def _is_cache_valid(self, cached_at: str) -> bool:
    """キャッシュの有効性確認"""
    cached_time = datetime.fromisoformat(cached_at)
    expire_time = datetime.now() - timedelta(hours=self.expire_hours)
    return cached_time > expire_time

async def get(self, url: str) -> Optional[str]:
    """キャッシュからコンテンツを取得"""
    cache_file, url_hash = self._get_cache_path(url)
    
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute(
            "SELECT cached_at, file_path FROM cache_metadata WHERE url_hash = ?",
            (url_hash,)
        )
        result = cursor.fetchone()
    
    if result and self._is_cache_valid(result[0]) and cache_file.exists():
        async with aiofiles.open(cache_file, mode='r', encoding='utf-8') as f:
            content = await f.read()
            self.logger.debug("キャッシュヒット", url=url, cache_file=str(cache_file))
            return content
    
    self.logger.debug("キャッシュミス", url=url)
    return None

async def set(self, url: str, content: str, status_code: int = 200):
    """コンテンツをキャッシュに保存"""
    cache_file, url_hash = self._get_cache_path(url)
    
    async with aiofiles.open(cache_file, mode='w', encoding='utf-8') as f:
        await f.write(content)
    
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO cache_metadata 
            (url_hash, url, cached_at, file_path, content_type, status_code)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (url_hash, url, datetime.now().isoformat(), str(cache_file), 'text/html', status_code))
    
    self.logger.debug("キャッシュ保存", url=url, status_code=status_code, content_length=len(content))
```

class ContentParser:
“”“コンテンツ解析クラス”””
def **init**(self, parse_rules: Dict[str, str], logger_instance: StructuredLogger = None):
self.parse_rules = parse_rules
self.logger = logger_instance or logger

```
def parse(self, content: str, url: str) -> Dict[str, Any]:
    """ページの詳細解析"""
    start_time = time.time()
    try:
        soup = BeautifulSoup(content, 'html.parser')
        data = {'url': url, 'parsed_at': datetime.now().isoformat()}
        
        for field, selector in self.parse_rules.items():
            data[field] = self._extract_field(soup, selector)
        
        # 追加メタデータ
        data.update({
            'content_length': len(content),
            'word_count': len(content.split()) if content else 0,
            'meta_description': self._get_meta_content(soup, 'description'),
            'meta_keywords': self._get_meta_content(soup, 'keywords'),
            'lang': soup.get('lang') or soup.find('html', {'lang': True}),
            'links_count': len(soup.find_all('a', href=True)),
            'images_count': len(soup.find_all('img', src=True))
        })
        
        processing_time = time.time() - start_time
        self.logger.info("ページ解析完了", 
                       url=url, 
                       processing_time=processing_time,
                       content_length=data['content_length'],
                       word_count=data['word_count'])
        
        return data
        
    except Exception as e:
        self.logger.error("ページ解析エラー", url=url, error=str(e), error_type=type(e).__name__)
        return {'url': url, 'error': str(e)}

def _extract_field(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
    """フィールドの抽出"""
    try:
        for sel in selector.split(','):
            element = soup.select_one(sel.strip())
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None
    except Exception:
        return None

def _get_meta_content(self, soup: BeautifulSoup, name: str) -> Optional[str]:
    """メタタグの内容を取得"""
    meta = soup.find('meta', {'name': name}) or soup.find('meta', {'property': f'og:{name}'})
    return meta.get('content') if meta else None
```

class DataQualityChecker:
“”“データ品質チェッククラス”””
def **init**(self, config: ScrapingConfig, logger_instance: StructuredLogger = None):
self.config = config
self.logger = logger_instance or logger

```
def validate_record(self, record: Dict[str, Any]) -> tuple:
    """レコードの品質チェック"""
    errors = []
    warnings = []
    
    # 必須フィールドチェック
    for field in self.config.required_fields:
        if field not in record or not record[field]:
            errors.append(f"必須フィールド '{field}' が不足")
    
    # コンテンツ長チェック
    if 'content' in record and record['content']:
        content_len = len(record['content'])
        if content_len < self.config.min_content_length:
            warnings.append(f"コンテンツが短すぎます ({content_len}文字)")
        elif content_len > self.config.max_content_length:
            warnings.append(f"コンテンツが長すぎます ({content_len}文字)")
    
    # 日付形式チェック
    if 'date' in record and record['date']:
        try:
            pd.to_datetime(record['date'])
        except:
            warnings.append("日付形式が不正です")
    
    is_valid = len(errors) == 0
    
    if not is_valid:
        self.logger.warning("データ品質チェック失敗", 
                          url=record.get('url', 'unknown'),
                          errors=errors,
                          warnings=warnings)
    
    return is_valid, errors, warnings
```

class EnhancedDataCollector:
“”“拡張データ収集クラス”””
def **init**(self, config: ScrapingConfig):
self.config = config
self.logger = setup_cloud_logger(f”{**name**}.collector”, config.cloud_logging)
self.cache = EnhancedURLCache(config.cache_dir, config.cache_expire_hours, self.logger)
self.parser = ContentParser(config.parse_rules, self.logger)
self.quality_checker = DataQualityChecker(config, self.logger)
self.rate_limiter = RateLimiter(config.delay_range, self.logger)
self.session: Optional[aiohttp.ClientSession] = None
self.stats = {
‘total_urls’: 0,
‘successful’: 0,
‘failed’: 0,
‘cached’: 0,
‘quality_passed’: 0,
‘quality_failed’: 0,
‘start_time’: None,
‘end_time’: None
}

```
async def __aenter__(self):
    """非同期コンテキストマネージャー"""
    connector = aiohttp.TCPConnector(limit=self.config.max_concurrent)
    timeout = aiohttp.ClientTimeout(total=self.config.timeout)
    self.session = aiohttp.ClientSession(
        headers=self.config.headers,
        connector=connector,
        timeout=timeout
    )
    self.stats['start_time'] = datetime.now().isoformat()
    self.logger.info("データ収集セッション開始", config=self.config.__dict__)
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    """リソースの解放"""
    if self.session:
        await self.session.close()
    
    self.stats['end_time'] = datetime.now
```