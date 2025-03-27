import aiohttp
import asyncio
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict, Any, Optional, Set
import logging
from dataclasses import dataclass
import os
import json
import hashlib
import aiofiles

# 非同期ループの最適化
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingConfig:
    """スクレイピングの設定を保持するデータクラス"""
    base_url: str
    output_dir: str = "data"
    max_retries: int = 3
    timeout: int = 10
    max_workers: int = 4
    chunk_size: int = 1000
    cache_dir: str = "cache"
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        os.makedirs(self.cache_dir, exist_ok=True)

class URLCache:
    """URLキャッシュ管理クラス"""
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.cached_urls: Set[str] = set()
        self._load_cached_urls()

    def _get_cache_path(self, url: str) -> str:
        """URLのキャッシュパスを取得"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.html")

    def _load_cached_urls(self) -> None:
        """キャッシュされているURLを読み込み"""
        if os.path.exists(self.cache_dir):
            for file in os.listdir(self.cache_dir):
                if file.endswith('.html'):
                    self.cached_urls.add(file[:-5])  # .html を除去

    async def get(self, url: str) -> Optional[str]:
        """キャッシュからコンテンツを取得"""
        cache_path = self._get_cache_path(url)
        if os.path.exists(cache_path):
            async with aiofiles.open(cache_path, mode='r', encoding='utf-8') as f:
                return await f.read()
        return None

    async def set(self, url: str, content: str) -> None:
        """コンテンツをキャッシュに保存"""
        cache_path = self._get_cache_path(url)
        async with aiofiles.open(cache_path, mode='w', encoding='utf-8') as f:
            await f.write(content)
        self.cached_urls.add(url)

class DataCollector:
    """データ収集クラス"""
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.cache = URLCache(config.cache_dir)
        self._setup_output_directory()
        self.session = None

    def _setup_output_directory(self) -> None:
        """出力ディレクトリの作成"""
        os.makedirs(self.config.output_dir, exist_ok=True)

    async def _init_session(self) -> None:
        """非同期セッションの初期化"""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.config.headers)

    async def _fetch_page(self, url: str) -> Optional[str]:
        """ページの非同期取得"""
        # キャッシュチェック
        cached_content = await self.cache.get(url)
        if cached_content:
            return cached_content

        # 新規取得
        await self._init_session()
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.get(url, timeout=self.config.timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        await self.cache.set(url, content)
                        return content
            except aiohttp.ClientError as e:
                logger.error(f"ページ取得エラー {url}: {str(e)}")
                if attempt == self.config.max_retries - 1:
                    return None
                await asyncio.sleep(2 ** attempt)  # 指数バックオフ
            except asyncio.TimeoutError:
                logger.error(f"タイムアウトエラー {url}")
                if attempt == self.config.max_retries - 1:
                    return None
                await asyncio.sleep(2 ** attempt)  # 指数バックオフ
            except Exception as e:
                logger.error(f"予期しないエラー {url}: {str(e)}")
                if attempt == self.config.max_retries - 1:
                    return None
                await asyncio.sleep(2 ** attempt)  # 指数バックオフ


    @staticmethod
    def _parse_page(content: str) -> Dict[str, Any]:
        """ページの解析"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            data = {
                'title': soup.find('h1').text.strip() if soup.find('h1') else None,
                'date': soup.find('time').text.strip() if soup.find('time') else None,
                'content': soup.find('article').text.strip() if soup.find('article') else None,
            }
            return {k: v for k, v in data.items() if v is not None}
        except Exception as e:
            logger.error(f"ページ解析エラー: {str(e)}")
            return {}

    async def scrape_data(self, urls: List[str]) -> List[Dict[str, Any]]:
        """複数URLからの非同期データ収集"""
        tasks = []
        for url_chunk in np.array_split(urls, len(urls) // self.config.chunk_size + 1):
            chunk_tasks = [self._process_url(url) for url in url_chunk]
            chunk_results = await asyncio.gather(*chunk_tasks)
            tasks.extend(chunk_results)
        
        return [t for t in tasks if t]

    async def _process_url(self, url: str) -> Optional[Dict[str, Any]]:
        """URLの処理"""
        content = await self._fetch_page(url)
        if content:
            data = self._parse_page(content)
            if data:
                data['url'] = url
                return data
        return None

    async def close(self):
        """リソースの解放"""
        if self.session:
            await self.session.close()

class DataAnalyzer:
    """データ分析クラス"""
    def __init__(self, data: List[Dict[str, Any]], config: ScrapingConfig):
        self.config = config
        self.df = pd.DataFrame(data)

    def prepare_data(self) -> None:
        """データの前処理"""
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
        
        self.df = self.df.dropna(subset=['title', 'content'])
        
        if 'content' in self.df.columns:
            self.df['content_length'] = self.df['content'].str.len()

    def generate_basic_stats(self) -> Dict[str, Any]:
        """基本的な統計情報の生成"""
        stats = {
            'total_articles': len(self.df),
            'unique_dates': self.df['date'].nunique() if 'date' in self.df.columns else 0,
            'avg_content_length': self.df['content_length'].mean() if 'content_length' in self.df.columns else 0,
        }
        
        if 'date' in self.df.columns:
            date_stats = self.df['date'].agg(['min', 'max'])
            stats['date_range'] = {
                'start': date_stats['min'],
                'end': date_stats['max']
            }
        
        return stats

    def plot_time_series(self, save_path: str) -> None:
        """時系列データの可視化"""
        if 'date' not in self.df.columns:
            return

        plt.figure(figsize=(12, 6))
        daily_counts = self.df.groupby(self.df['date'].dt.date).size()
        
        with plt.style.context('seaborn'):
            sns.lineplot(data=daily_counts)
            plt.title('記事数の推移')
            plt.xlabel('日付')
            plt.ylabel('記事数')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()

    def export_data(self, output_dir: str) -> None:
        """データのエクスポート"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # CSVとして保存
        csv_path = os.path.join(output_dir, f'data_{timestamp}.csv')
        self.df.to_csv(csv_path, index=False, encoding='utf-8')
        
        # 基本統計をJSONとして保存
        stats_path = os.path.join(output_dir, f'stats_{timestamp}.json')
        stats = self.generate_basic_stats()
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, default=str)
        
        # グラフの保存
        plot_path = os.path.join(output_dir, f'timeline_{timestamp}.png')
        self.plot_time_series(plot_path)

async def main():
    # 設定
    config = ScrapingConfig(
        base_url="https://example.com",
        output_dir="data",
        max_workers=os.cpu_count() or 4
    )
    
    # スクレイピング対象のURL一覧
    target_urls = [
        "https://example.com/page1",
        "https://example.com/page2",
    ]
    
    # データ収集
    collector = DataCollector(config)
    try:
        collected_data = await collector.scrape_data(target_urls)
    finally:
        await collector.close()
    
    if not collected_data:
        logger.error("データを収集できませんでした")
        return
    
    # データ分析
    analyzer = DataAnalyzer(collected_data, config)
    analyzer.prepare_data()
    analyzer.export_data(config.output_dir)
    
    logger.info("データ分析が完了しました")
    
    # 基本統計の表示
    stats = analyzer.generate_basic_stats()
    print("\n基本統計:")
    print(json.dumps(stats, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
