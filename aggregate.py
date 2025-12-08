"""
Web Scraping Framework

非同期Webスクレイピングフレームワーク。
キャッシング、レート制限、データ品質チェック、複数エクスポート形式に対応。

Usage:
    config = ScrapingConfig(base_url="https://example.com")
    async with WebScraper(config) as scraper:
        results = await scraper.scrape(urls)
        await scraper.export()
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm

# Windows向け非同期ループ設定
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# =============================================================================
# Logging
# =============================================================================


class LogLevel(Enum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class LogConfig:
    """ロギング設定"""

    name: str = "scraper"
    level: LogLevel = LogLevel.INFO
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    def __post_init__(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)


def setup_logger(config: LogConfig) -> logging.Logger:
    """ロガーをセットアップ"""
    logger = logging.getLogger(config.name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コンソール
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, config.level.name))
    console.setFormatter(formatter)
    logger.addHandler(console)

    # ファイル
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        config.log_dir / f"{config.name}.log",
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ScrapingConfig:
    """スクレイピング設定"""

    base_url: str
    output_dir: Path = field(default_factory=lambda: Path("data"))
    cache_dir: Path = field(default_factory=lambda: Path("cache"))

    # HTTP設定
    max_concurrent: int = 10
    timeout: int = 15
    max_retries: int = 3
    delay_range: tuple[float, float] = (1.0, 3.0)

    # キャッシュ設定
    cache_enabled: bool = True
    cache_expire_hours: int = 24

    # パース設定
    parse_rules: dict[str, str] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)

    # バリデーション設定
    min_content_length: int = 50
    max_content_length: int = 50000

    # エクスポート設定
    export_formats: list[str] = field(default_factory=lambda: ["csv", "json"])

    # HTTPヘッダー
    headers: dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en;q=0.7",
    })

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.parse_rules:
            self.parse_rules = {
                "title": "h1, .title, title",
                "content": "article, .content, main",
                "date": "time, .date, .published",
                "author": ".author, .byline",
            }


# =============================================================================
# Rate Limiter
# =============================================================================


class RateLimiter:
    """レート制限"""

    def __init__(self, delay_range: tuple[float, float]) -> None:
        self._delay_range = delay_range
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """レート制限を適用"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            delay = random.uniform(*self._delay_range)

            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

            self._last_request = time.monotonic()


# =============================================================================
# Cache
# =============================================================================


class Cache:
    """SQLiteベースのURLキャッシュ"""

    def __init__(self, cache_dir: Path, expire_hours: int = 24) -> None:
        self._cache_dir = cache_dir
        self._expire_hours = expire_hours
        self._db_path = cache_dir / "cache.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    status_code INTEGER
                )
            """)

    def _hash_url(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def _cache_path(self, url_hash: str) -> Path:
        return self._cache_dir / f"{url_hash}.html"

    def _is_valid(self, cached_at: str) -> bool:
        cached_time = datetime.fromisoformat(cached_at)
        expire_time = datetime.now() - timedelta(hours=self._expire_hours)
        return cached_time > expire_time

    async def get(self, url: str) -> str | None:
        """キャッシュからコンテンツを取得"""
        url_hash = self._hash_url(url)
        cache_path = self._cache_path(url_hash)

        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT cached_at FROM cache WHERE url_hash = ?",
                (url_hash,),
            ).fetchone()

        if not row or not self._is_valid(row[0]) or not cache_path.exists():
            return None

        async with aiofiles.open(cache_path, encoding="utf-8") as f:
            return await f.read()

    async def set(self, url: str, content: str, status_code: int = 200) -> None:
        """コンテンツをキャッシュに保存"""
        url_hash = self._hash_url(url)
        cache_path = self._cache_path(url_hash)

        async with aiofiles.open(cache_path, "w", encoding="utf-8") as f:
            await f.write(content)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (url_hash, url, cached_at, status_code)
                VALUES (?, ?, ?, ?)
                """,
                (url_hash, url, datetime.now().isoformat(), status_code),
            )


# =============================================================================
# Parser
# =============================================================================


@dataclass
class ParsedContent:
    """パース済みコンテンツ"""

    url: str
    title: str | None = None
    content: str | None = None
    date: str | None = None
    author: str | None = None
    meta_description: str | None = None
    word_count: int = 0
    links_count: int = 0
    images_count: int = 0
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class ContentParser:
    """HTMLコンテンツパーサー"""

    def __init__(self, parse_rules: dict[str, str]) -> None:
        self._rules = parse_rules

    def parse(self, html: str, url: str) -> ParsedContent:
        """HTMLをパース"""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 基本フィールド抽出
            fields = {}
            for name, selector in self._rules.items():
                fields[name] = self._extract(soup, selector)

            return ParsedContent(
                url=url,
                title=fields.get("title"),
                content=fields.get("content"),
                date=fields.get("date"),
                author=fields.get("author"),
                meta_description=self._get_meta(soup, "description"),
                word_count=len(html.split()),
                links_count=len(soup.find_all("a", href=True)),
                images_count=len(soup.find_all("img", src=True)),
                extra={k: v for k, v in fields.items() if k not in ["title", "content", "date", "author"]},
            )

        except Exception as e:
            return ParsedContent(url=url, error=str(e))

    def _extract(self, soup: BeautifulSoup, selector: str) -> str | None:
        """セレクタでテキストを抽出"""
        for sel in selector.split(","):
            elem = soup.select_one(sel.strip())
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        return None

    def _get_meta(self, soup: BeautifulSoup, name: str) -> str | None:
        """metaタグの内容を取得"""
        meta = soup.find("meta", {"name": name}) or soup.find("meta", {"property": f"og:{name}"})
        return meta.get("content") if meta else None


# =============================================================================
# Validator
# =============================================================================


@dataclass
class ValidationResult:
    """バリデーション結果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ContentValidator:
    """コンテンツバリデーター"""

    def __init__(
        self,
        required_fields: list[str],
        min_length: int = 50,
        max_length: int = 50000,
    ) -> None:
        self._required = required_fields
        self._min_length = min_length
        self._max_length = max_length

    def validate(self, content: ParsedContent) -> ValidationResult:
        """コンテンツをバリデート"""
        errors = []
        warnings = []

        # 必須フィールドチェック
        for field_name in self._required:
            value = getattr(content, field_name, None) or content.extra.get(field_name)
            if not value:
                errors.append(f"必須フィールド '{field_name}' が不足")

        # コンテンツ長チェック
        if content.content:
            length = len(content.content)
            if length < self._min_length:
                warnings.append(f"コンテンツが短すぎます ({length}文字)")
            elif length > self._max_length:
                warnings.append(f"コンテンツが長すぎます ({length}文字)")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )


# =============================================================================
# Exporter
# =============================================================================


class Exporter(ABC):
    """エクスポーターの基底クラス"""

    @abstractmethod
    async def export(self, data: list[ParsedContent], path: Path) -> None:
        """データをエクスポート"""


class JsonExporter(Exporter):
    async def export(self, data: list[ParsedContent], path: Path) -> None:
        output = path.with_suffix(".json")
        records = [self._to_dict(item) for item in data]

        async with aiofiles.open(output, "w", encoding="utf-8") as f:
            await f.write(json.dumps(records, ensure_ascii=False, indent=2))

    def _to_dict(self, item: ParsedContent) -> dict[str, Any]:
        return {
            "url": item.url,
            "title": item.title,
            "content": item.content,
            "date": item.date,
            "author": item.author,
            "meta_description": item.meta_description,
            "word_count": item.word_count,
            "links_count": item.links_count,
            "images_count": item.images_count,
            "parsed_at": item.parsed_at,
            **item.extra,
        }


class CsvExporter(Exporter):
    async def export(self, data: list[ParsedContent], path: Path) -> None:
        import csv

        output = path.with_suffix(".csv")
        if not data:
            return

        fieldnames = [
            "url", "title", "content", "date", "author",
            "meta_description", "word_count", "links_count",
            "images_count", "parsed_at",
        ]

        rows = []
        for item in data:
            rows.append({
                "url": item.url,
                "title": item.title,
                "content": item.content[:500] if item.content else None,  # 切り詰め
                "date": item.date,
                "author": item.author,
                "meta_description": item.meta_description,
                "word_count": item.word_count,
                "links_count": item.links_count,
                "images_count": item.images_count,
                "parsed_at": item.parsed_at,
            })

        async with aiofiles.open(output, "w", encoding="utf-8", newline="") as f:
            # aiofilesはcsv.writerと直接使えないため、文字列として書き込み
            import io
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            await f.write(buffer.getvalue())


def get_exporter(format_name: str) -> Exporter:
    """フォーマット名からエクスポーターを取得"""
    exporters = {
        "json": JsonExporter(),
        "csv": CsvExporter(),
    }
    if format_name not in exporters:
        raise ValueError(f"未対応のフォーマット: {format_name}")
    return exporters[format_name]


# =============================================================================
# HTTP Client
# =============================================================================


@dataclass
class FetchResult:
    """フェッチ結果"""

    url: str
    content: str | None = None
    status_code: int = 0
    error: str | None = None
    from_cache: bool = False


class HttpClient:
    """非同期HTTPクライアント"""

    def __init__(
        self,
        config: ScrapingConfig,
        cache: Cache | None,
        rate_limiter: RateLimiter,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._logger = logger
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> HttpClient:
        connector = aiohttp.TCPConnector(limit=self._config.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=self._config.timeout)
        self._session = aiohttp.ClientSession(
            headers=self._config.headers,
            connector=connector,
            timeout=timeout,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._session:
            await self._session.close()

    async def fetch(self, url: str) -> FetchResult:
        """URLからコンテンツを取得"""
        # キャッシュチェック
        if self._cache:
            cached = await self._cache.get(url)
            if cached:
                self._logger.debug("キャッシュヒット: %s", url)
                return FetchResult(url=url, content=cached, status_code=200, from_cache=True)

        # レート制限
        await self._rate_limiter.acquire()

        # リトライ付きフェッチ
        for attempt in range(self._config.max_retries):
            try:
                async with self._session.get(url) as response:
                    content = await response.text()

                    if response.status == 200:
                        if self._cache:
                            await self._cache.set(url, content, response.status)
                        return FetchResult(url=url, content=content, status_code=response.status)

                    self._logger.warning("HTTPエラー %d: %s", response.status, url)
                    return FetchResult(url=url, status_code=response.status, error=f"HTTP {response.status}")

            except asyncio.TimeoutError:
                self._logger.warning("タイムアウト (試行 %d/%d): %s", attempt + 1, self._config.max_retries, url)
            except aiohttp.ClientError as e:
                self._logger.warning("接続エラー (試行 %d/%d): %s - %s", attempt + 1, self._config.max_retries, url, e)

            if attempt < self._config.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        return FetchResult(url=url, error="最大リトライ回数超過")


# =============================================================================
# Main Scraper
# =============================================================================


@dataclass
class ScrapingStats:
    """スクレイピング統計"""

    total: int = 0
    successful: int = 0
    failed: int = 0
    cached: int = 0
    valid: int = 0
    invalid: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def duration(self) -> timedelta | None:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "cached": self.cached,
            "valid": self.valid,
            "invalid": self.invalid,
            "duration_seconds": self.duration.total_seconds() if self.duration else None,
        }


class WebScraper:
    """Webスクレイパー"""

    def __init__(self, config: ScrapingConfig, log_config: LogConfig | None = None) -> None:
        self._config = config
        self._logger = setup_logger(log_config or LogConfig())

        self._cache = Cache(config.cache_dir, config.cache_expire_hours) if config.cache_enabled else None
        self._rate_limiter = RateLimiter(config.delay_range)
        self._parser = ContentParser(config.parse_rules)
        self._validator = ContentValidator(
            config.required_fields,
            config.min_content_length,
            config.max_content_length,
        )

        self._client: HttpClient | None = None
        self._results: list[ParsedContent] = []
        self._stats = ScrapingStats()

    async def __aenter__(self) -> WebScraper:
        self._client = HttpClient(
            self._config,
            self._cache,
            self._rate_limiter,
            self._logger,
        )
        await self._client.__aenter__()
        self._stats.start_time = datetime.now()
        self._logger.info("スクレイピング開始: %s", self._config.base_url)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.__aexit__(*_)
        self._stats.end_time = datetime.now()
        self._logger.info("スクレイピング完了: %s", self._stats.to_dict())

    async def scrape(self, urls: list[str], show_progress: bool = True) -> list[ParsedContent]:
        """URLリストをスクレイプ"""
        self._stats.total = len(urls)
        self._results = []

        tasks = [self._process_url(url) for url in urls]

        if show_progress:
            results = await tqdm.gather(*tasks, desc="スクレイピング中")
        else:
            results = await asyncio.gather(*tasks)

        self._results = [r for r in results if r is not None]
        return self._results

    async def _process_url(self, url: str) -> ParsedContent | None:
        """単一URLを処理"""
        # フェッチ
        result = await self._client.fetch(url)

        if result.from_cache:
            self._stats.cached += 1

        if result.error or not result.content:
            self._stats.failed += 1
            self._logger.error("取得失敗: %s - %s", url, result.error)
            return ParsedContent(url=url, error=result.error)

        self._stats.successful += 1

        # パース
        parsed = self._parser.parse(result.content, url)

        if parsed.error:
            self._logger.warning("パースエラー: %s - %s", url, parsed.error)
            return parsed

        # バリデーション
        validation = self._validator.validate(parsed)

        if validation.is_valid:
            self._stats.valid += 1
        else:
            self._stats.invalid += 1
            self._logger.warning("バリデーション失敗: %s - %s", url, validation.errors)

        return parsed

    async def export(self, filename: str = "scraped_data") -> list[Path]:
        """結果をエクスポート"""
        if not self._results:
            self._logger.warning("エクスポートするデータがありません")
            return []

        output_path = self._config.output_dir / filename
        exported = []

        for fmt in self._config.export_formats:
            try:
                exporter = get_exporter(fmt)
                await exporter.export(self._results, output_path)
                exported.append(output_path.with_suffix(f".{fmt}"))
                self._logger.info("エクスポート完了: %s", output_path.with_suffix(f".{fmt}"))
            except Exception as e:
                self._logger.error("エクスポートエラー (%s): %s", fmt, e)

        return exported

    @property
    def stats(self) -> ScrapingStats:
        return self._stats

    @property
    def results(self) -> list[ParsedContent]:
        return self._results


# =============================================================================
# Entry Point
# =============================================================================


async def main() -> None:
    """使用例"""
    config = ScrapingConfig(
        base_url="https://example.com",
        max_concurrent=5,
        delay_range=(1.0, 2.0),
        required_fields=["title"],
        export_formats=["json", "csv"],
    )

    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3",
    ]

    async with WebScraper(config) as scraper:
        results = await scraper.scrape(urls)

        print(f"\n=== 統計 ===")
        print(f"成功: {scraper.stats.successful}/{scraper.stats.total}")
        print(f"キャッシュ: {scraper.stats.cached}")
        print(f"有効: {scraper.stats.valid}")

        await scraper.export("example_output")


if __name__ == "__main__":
    asyncio.run(main())
