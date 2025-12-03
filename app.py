"""
DALL-E画像生成アプリ（修正版）

複数のプロンプトから画像を生成し、基準画像との類似度を計算して表示するStreamlitアプリ。
"""
import asyncio
import logging
import os
import pickle
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, TypedDict

import aiohttp
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from openai import AsyncOpenAI  # SDK により名前が違う場合は適宜変更してください
from PIL import Image
from skimage.metrics import structural_similarity as compare_ssim

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)
logger = logging.getLogger(__name__)


class ImageResponse(TypedDict):
    """OpenAI APIから返される画像レスポンスの型定義"""
    url: str


class ImageResult(TypedDict):
    """画像処理結果の型定義"""
    image: Optional[Image.Image]
    thumbnail: Optional[Image.Image]
    ssim: float
    path: str


@dataclass(frozen=True)
class ImageGenerationConfig:
    """画像生成の設定を保持するデータクラス"""
    model: str = "dall-e-3"
    size: str = "1024x1024"
    output_dir: str = "generated_images"
    cache_file: str = "image_cache.pkl"
    thumbnail_size: Tuple[int, int] = (150, 150)
    groundtruth_path: str = "groundtruth.png"
    max_workers: int = 4
    request_timeout: int = 30
    chunk_size: int = 5
    max_cache_size: int = 100
    quality: str = "standard"  # standard または hd


class ImageCache:
    """
    キャッシュは pickle に保存可能な構造（バイト列, ssim）で保持します。
    key -> (thumbnail_bytes: bytes, ssim: float)
    """

    def __init__(self, cache_dir: str, cache_file: str, max_size: int = 100) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_file = Path(cache_dir) / cache_file
        self.max_size = max_size
        self._cache: Dict[str, Tuple[bytes, float]] = {}
        self._load_cache()

    def get(self, key: str) -> Optional[Tuple[bytes, float]]:
        return self._cache.get(key)

    def set(self, key: str, value: Tuple[bytes, float]) -> None:
        if len(self._cache) >= self.max_size:
            # 単純な先入れ削除（LRU にするなら OrderedDict 等を使う）
            old_key = next(iter(self._cache))
            del self._cache[old_key]
        self._cache[key] = value
        self._save_cache()

    def _load_cache(self) -> None:
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "rb") as f:
                    cached_data = pickle.load(f)
                    if isinstance(cached_data, dict):
                        # バリデーション: 値は (bytes, float) であることを期待
                        filtered: Dict[str, Tuple[bytes, float]] = {}
                        for k, v in cached_data.items():
                            if (
                                isinstance(k, str)
                                and isinstance(v, tuple)
                                and len(v) == 2
                                and isinstance(v[0], (bytes, bytearray))
                                and isinstance(v[1], float)
                            ):
                                filtered[k] = (bytes(v[0]), float(v[1]))
                        self._cache = filtered
                logger.info(f"{len(self._cache)} items loaded from cache")
        except (IOError, pickle.PickleError) as e:
            logger.error(f"Failed to load cache: {e}")
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "wb") as f:
                pickle.dump(self._cache, f)
        except (IOError, pickle.PickleError) as e:
            logger.error(f"Failed to save cache: {e}")


class ImageProcessor:
    """DALL-E画像生成と処理を行うクラス"""

    def __init__(self, config: ImageGenerationConfig) -> None:
        self.config = config
        # OpenAI クライアントはここで作成（API キーは env から取得）
        self.client = self._initialize_openai_client()
        self.cache = ImageCache(config.output_dir, config.cache_file, config.max_cache_size)
        self._setup_output_directory()
        self.groundtruth_img = self._load_groundtruth()
        # session は非同期コンテキストで作成する（ここでは None）
        self.session: Optional[aiohttp.ClientSession] = None

    def _initialize_openai_client(self) -> AsyncOpenAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API キーが設定されていません。.env を確認してください。")
        # SDK に合わせて引数名は調整してください
        return AsyncOpenAI(api_key=api_key)

    def _setup_output_directory(self) -> None:
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)

    def _load_groundtruth(self) -> Optional[Image.Image]:
        try:
            p = Path(self.config.groundtruth_path)
            if p.exists():
                img = Image.open(p)
                return img.convert("L")
            logger.warning(f"Groundtruth not found: {p}")
            return None
        except Exception as e:
            logger.error(f"Failed to load groundtruth: {e}")
            return None

    @staticmethod
    def _sanitize_filename(prompt: str) -> str:
        sanitized = re.sub(r"\W+", "_", prompt.strip().lower())
        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
        if len(sanitized) == 0:
            sanitized = "prompt"
        return sanitized[:40] + ".png"

    async def _download_image(self, url: str) -> Optional[bytes]:
        if not self.session:
            logger.error("HTTP session not initialized")
            return None
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to download image: HTTP {resp.status}")
                    return None
                return await resp.read()
        except asyncio.TimeoutError:
            logger.error(f"Timeout while downloading {url}")
            return None
        except aiohttp.ClientError as e:
            log
