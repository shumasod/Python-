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

# 非同期ループの最適化
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ログ設定の改善
def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """カスタムロガーのセットアップ"""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger(__name__, 'scraping.log')

@dataclass
class ScrapingConfig:
    """スクレイピング設定の拡張版"""
    base_url: str
    output_dir: str = "data"
    cache_dir: str = "cache"
    log_dir: str = "logs"
    
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

class RateLimiter:
    """レート制限管理クラス"""
    def __init__(self, delay_range: tuple = (1, 3)):
        self.delay_range = delay_range
        self.last_request = 0
    
    async def wait(self):
        """適切な間隔での待機"""
        now = time.time()
        elapsed = now - self.last_request
        delay = random.uniform(*self.delay_range)
        
        if elapsed < delay:
            wait_time = delay - elapsed
            await asyncio.sleep(wait_time)
        
        self.last_request = time.time()

class EnhancedURLCache:
    """拡張URLキャッシュ管理クラス"""
    def __init__(self, cache_dir: str, expire_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.expire_hours = expire_hours
        self.db_path = self.cache_dir / "cache_metadata.db"
        self._init_db()
    
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
                return await f.read()
        
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

class ContentParser:
    """コンテンツ解析クラス"""
    def __init__(self, parse_rules: Dict[str, str]):
        self.parse_rules = parse_rules
    
    def parse(self, content: str, url: str) -> Dict[str, Any]:
        """ページの詳細解析"""
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
            
            return data
            
        except Exception as e:
            logger.error(f"ページ解析エラー {url}: {str(e)}")
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

class DataQualityChecker:
    """データ品質チェッククラス"""
    def __init__(self, config: ScrapingConfig):
        self.config = config
    
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
        return is_valid, errors, warnings

class EnhancedDataCollector:
    """拡張データ収集クラス"""
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.cache = EnhancedURLCache(config.cache_dir, config.cache_expire_hours)
        self.parser = ContentParser(config.parse_rules)
        self.quality_checker = DataQualityChecker(config)
        self.rate_limiter = RateLimiter(config.delay_range)
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            'total_urls': 0,
            'successful': 0,
            'failed': 0,
            'cached': 0,
            'quality_passed': 0,
            'quality_failed': 0
        }
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー"""
        connector = aiohttp.TCPConnector(limit=self.config.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self.session = aiohttp.ClientSession(
            headers=self.config.headers,
            connector=connector,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """リソースの解放"""
        if self.session:
            await self.session.close()
    
    async def _fetch_page(self, url: str) -> Optional[tuple]:
        """ページの取得（コンテンツとステータスコードを返す）"""
        # キャッシュチェック
        if self.config.use_cache:
            cached_content = await self.cache.get(url)
            if cached_content:
                self.stats['cached'] += 1
                return cached_content, 200
        
        # レート制限
        await self.rate_limiter.wait()
        
        # ページ取得
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.get(url) as response:
                    content = await response.text()
                    
                    if response.status == 200:
                        # キャッシュに保存
                        if self.config.use_cache:
                            await self.cache.set(url, content, response.status)
                        return content, response.status
                    else:
                        logger.warning(f"HTTP {response.status}: {url}")
                        return None, response.status
                        
            except asyncio.TimeoutError:
                logger.warning(f"タイムアウト (試行{attempt + 1}/{self.config.max_retries}): {url}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    
            except Exception as e:
                logger.error(f"取得エラー (試行{attempt + 1}/{self.config.max_retries}) {url}: {str(e)}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return None, 0
    
    async def _process_url(self, url: str) -> Optional[Dict[str, Any]]:
        """URL処理"""
        try:
            result = await self._fetch_page(url)
            if result[0] is None:
                self.stats['failed'] += 1
                return None
            
            content, status_code = result
            
            # コンテンツ解析
            parsed_data = self.parser.parse(content, url)
            parsed_data['status_code'] = status_code
            
            # 品質チェック
            is_valid, errors, warnings = self.quality_checker.validate_record(parsed_data)
            parsed_data['quality_errors'] = errors
            parsed_data['quality_warnings'] = warnings
            
            if is_valid:
                self.stats['quality_passed'] += 1
            else:
                self.stats['quality_failed'] += 1
                logger.warning(f"品質チェック失敗 {url}: {errors}")
            
            self.stats['successful'] += 1
            return parsed_data
            
        except Exception as e:
            logger.error(f"URL処理エラー {url}: {str(e)}")
            self.stats['failed'] += 1
            return None
    
    async def scrape_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """非同期URL収集（プログレスバー付き）"""
        self.stats['total_urls'] = len(urls)
        
        # セマフォでの同時実行制限
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def process_with_semaphore(url):
            async with semaphore:
                return await self._process_url(url)
        
        # プログレスバー付きで実行
        tasks = [process_with_semaphore(url) for url in urls]
        results = []
        
        for coro in tqdm.as_completed(tasks, desc="スクレイピング進行中"):
            result = await coro
            if result:
                results.append(result)
        
        logger.info(f"スクレイピング完了: {self.stats}")
        return results

class AdvancedDataAnalyzer:
    """高度なデータ分析クラス"""
    def __init__(self, data: List[Dict[str, Any]], config: ScrapingConfig):
        self.config = config
        self.raw_data = data
        self.df = pd.DataFrame(data) if data else pd.DataFrame()
        self.cleaned_df = None
    
    def clean_data(self) -> pd.DataFrame:
        """データクリーニング"""
        if self.df.empty:
            self.cleaned_df = self.df
            return self.cleaned_df
        
        df = self.df.copy()
        
        # 日付の正規化
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # 重複削除
        if 'url' in df.columns:
            df = df.drop_duplicates(subset=['url'])
        
        # 品質フィルタリング
        if 'quality_errors' in df.columns:
            # エラーのないレコードのみ保持
            df = df[df['quality_errors'].apply(lambda x: len(x) == 0 if isinstance(x, list) else True)]
        
        # 数値データの正規化
        numeric_columns = ['content_length', 'word_count', 'links_count', 'images_count']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        self.cleaned_df = df
        return df
    
    def generate_comprehensive_stats(self) -> Dict[str, Any]:
        """包括的統計情報の生成"""
        if self.cleaned_df is None:
            self.clean_data()
        
        df = self.cleaned_df
        stats = {
            'data_overview': {
                'total_records': len(df),
                'columns': list(df.columns),
                'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
            }
        }
        
        # 基本統計
        if not df.empty:
            # 日付統計
            if 'date' in df.columns and df['date'].notna().any():
                stats['date_analysis'] = {
                    'date_range': {
                        'start': df['date'].min(),
                        'end': df['date'].max()
                    },
                    'records_by_month': df.groupby(df['date'].dt.to_period('M')).size().to_dict(),
                    'records_by_weekday': df.groupby(df['date'].dt.day_name()).size().to_dict()
                }
            
            # コンテンツ統計
            if 'content_length' in df.columns:
                stats['content_analysis'] = {
                    'avg_length': df['content_length'].mean(),
                    'median_length': df['content_length'].median(),
                    'length_distribution': df['content_length'].describe().to_dict()
                }
            
            # 品質統計
            if 'quality_warnings' in df.columns:
                warning_counts = df['quality_warnings'].apply(len)
                stats['quality_analysis'] = {
                    'records_with_warnings': (warning_counts > 0).sum(),
                    'avg_warnings_per_record': warning_counts.mean(),
                    'common_warnings': self._get_common_warnings(df['quality_warnings'])
                }
        
        return stats
    
    def _get_common_warnings(self, warnings_series) -> Dict[str, int]:
        """共通の警告を集計"""
        warning_counts = {}
        for warnings in warnings_series:
            if isinstance(warnings, list):
                for warning in warnings:
                    warning_counts[warning] = warning_counts.get(warning, 0) + 1
        return dict(sorted(warning_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    
    def create_visualizations(self, output_dir: str) -> List[str]:
        """可視化の作成"""
        if self.cleaned_df is None or self.cleaned_df.empty:
            return []
        
        output_dir = Path(output_dir)
        plots = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        
        # 1. 時系列プロット
        if 'date' in self.cleaned_df.columns:
            fig, ax = plt.subplots(figsize=(12, 6))
            daily_counts = self.cleaned_df.groupby(self.cleaned_df['date'].dt.date).size()
            daily_counts.plot(kind='line', ax=ax)
            ax.set_title('記事数の時系列変化')
            ax.set_xlabel('日付')
            ax.set_ylabel('記事数')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            plot_path = output_dir / f'timeline_{timestamp}.png'
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            plots.append(str(plot_path))
        
        # 2. コンテンツ長分布
        if 'content_length' in self.cleaned_df.columns:
            fig, ax = plt.subplots(figsize=(10, 6))
            self.cleaned_df['content_length'].hist(bins=50, ax=ax)
            ax.set_title('コンテンツ長の分布')
            ax.set_xlabel('文字数')
            ax.set_ylabel('頻度')
            plt.tight_layout()
            
            plot_path = output_dir / f'content_length_dist_{timestamp}.png'
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            plots.append(str(plot_path))
        
        # 3. 相関マトリックス
        numeric_cols = self.cleaned_df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            fig, ax = plt.subplots(figsize=(10, 8))
            correlation_matrix = self.cleaned_df[numeric_cols].corr()
            sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0, ax=ax)
            ax.set_title('数値変数間の相関関係')
            plt.tight_layout()
            
            plot_path = output_dir / f'correlation_matrix_{timestamp}.png'
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            plots.append(str(plot_path))
        
        return plots
    
    def export_data(self, output_dir: str) -> Dict[str, str]:
        """複数形式でのデータエクスポート"""
        if self.cleaned_df is None:
            self.clean_data()
        
        output_dir = Path(output_dir)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        exported_files = {}
        
        # CSV出力
        if 'csv' in self.config.export_formats:
            csv_path = output_dir / f'scraped_data_{timestamp}.csv'
            self.cleaned_df.to_csv(csv_path, index=False, encoding='utf-8')
            exported_files['csv'] = str(csv_path)
        
        # Excel出力
        if 'excel' in self.config.export_formats:
            excel_path = output_dir / f'scraped_data_{timestamp}.xlsx'
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                self.cleaned_df.to_excel(writer, sheet_name='Data', index=False)
                
                # 統計情報も別シートで保存
                stats_df = pd.DataFrame.from_dict(
                    self.generate_comprehensive_stats(), 
                    orient='index'
                )
                stats_df.to_excel(writer, sheet_name='Statistics')
            
            exported_files['excel'] = str(excel_path)
        
        # JSON出力
        if 'json' in self.config.export_formats:
            json_path = output_dir / f'scraped_data_{timestamp}.json'
            self.cleaned_df.to_json(json_path, orient='records', indent=2, ensure_ascii=False)
            exported_files['json'] = str(json_path)
        
        # 統計情報をJSON出力
        stats_path = output_dir / f'statistics_{timestamp}.json'
        stats = self.generate_comprehensive_stats()
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, default=str, ensure_ascii=False)
        exported_files['statistics'] = str(stats_path)
        
        # 可視化作成
        plot_files = self.create_visualizations(output_dir)
        exported_files['visualizations'] = plot_files
        
        return exported_files

async def main():
    """メイン実行関数"""
    # 設定
    config = ScrapingConfig(
        base_url="https://example.com",
        output_dir="data",
        max_concurrent=5,
        chunk_size=20,
        required_fields=['title', 'content'],
        export_formats=['csv', 'json', 'excel'],
        delay_range=(1, 2)
    )
    
    # サンプルURL（実際の使用時は適切なURLリストに変更）
    target_urls = [
        "https://example.com/article1",
        "https://example.com/article2",
        "https://example.com/article3",
    ]
    
    logger.info("スクレイピング開始")
    start_time = time.time()
    
    # データ収集
    async with EnhancedDataCollector(config) as collector:
        collected_data = await collector.scrape_urls(target_urls)
    
    if not collected_data:
        logger.error("データを収集できませんでした")
        return
    
    logger.info(f"データ収集完了: {len(collected_data)}件")
    
    # データ分析
    analyzer = AdvancedDataAnalyzer(collected_data, config)
    
    # データクリーニング
    cleaned_data = analyzer.clean_data()
    logger.info(f"データクリーニング完了: {len(cleaned_data)}件")
    
    # エクスポート
    exported_files = analyzer.export_data(config.output_dir)
    logger.info(f"データエクスポート完了: {list(exported_files.keys())}")
    
    # 統計表示
    stats = analyzer.generate_comprehensive_stats()
    print("\n" + "="*50)
    print("スクレイピング結果統計")
    print("="*50)
    print(json.dumps(stats, indent=2, default=str, ensure_ascii=False))
    
    elapsed_time = time.time() - start_time
    print(f"\n処理時間: {elapsed_time:.2f}秒")

if __name__ == "__main__":
    asyncio.run(main())
