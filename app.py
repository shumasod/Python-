import streamlit as st
from openai import OpenAI
import requests
import os
import re
from PIL import Image
from io import BytesIO
from skimage.metrics import structural_similarity as compare_ssim
import numpy as np
from dotenv import load_dotenv
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiohttp
from contextlib import asynccontextmanager

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ImageGenerationConfig:
    """画像生成の設定を保持するデータクラス"""
    model: str = "dall-e-3"
    size: str = "1024x1024"
    output_dir: str = "generated_images"
    thumbnail_size: Tuple[int, int] = (150, 150)
    groundtruth_path: str = "groundtruth.png"
    max_workers: int = 4
    request_timeout: int = 10
    chunk_size: int = 5

class ImageCache:
    """画像キャッシュ管理クラス"""
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._cache: Dict[str, Tuple[Image.Image, float]] = {}

    def get(self, key: str) -> Optional[Tuple[Image.Image, float]]:
        return self._cache.get(key)

    def set(self, key: str, value: Tuple[Image.Image, float]) -> None:
        self._cache[key] = value

class ImageProcessor:
    def __init__(self, config: ImageGenerationConfig):
        """画像処理クラスの初期化"""
        self.config = config
        self.client = self._initialize_openai_client()
        self.cache = ImageCache(config.output_dir)
        self._setup_output_directory()
        self.groundtruth_img = self._load_groundtruth()
        self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    def _initialize_openai_client(self) -> OpenAI:
        """OpenAI クライアントの初期化"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API キーが設定されていません")
        return OpenAI(api_key=api_key)

    def _setup_output_directory(self) -> None:
        """出力ディレクトリの作成"""
        os.makedirs(self.config.output_dir, exist_ok=True)

    @lru_cache(maxsize=1)
    def _load_groundtruth(self) -> Optional[Image.Image]:
        """基準画像の読み込み（キャッシュ付き）"""
        try:
            if os.path.exists(self.config.groundtruth_path):
                img = Image.open(self.config.groundtruth_path)
                return img.convert('L')
            logger.warning("基準画像が見つかりません")
            return None
        except Exception as e:
            logger.error(f"基準画像の読み込みエラー: {e}")
            return None

    @staticmethod
    def _sanitize_filename(prompt: str) -> str:
        """プロンプトからファイル名を生成"""
        return re.sub(r'\W+', '_', prompt.lower())[:20] + '.png'

    async def _download_image(self, url: str) -> Optional[bytes]:
        """画像の非同期ダウンロード"""
        try:
            async with self.session.get(url, timeout=self.config.request_timeout) as response:
                response.raise_for_status()
                return await response.read()
        except Exception as e:
            logger.error(f"画像のダウンロードエラー: {e}")
            return None

    def _save_image(self, image_data: bytes, path: str) -> Optional[Image.Image]:
        """画像の保存"""
        try:
            img = Image.open(BytesIO(image_data))
            img.save(path, optimize=True)
            return img
        except Exception as e:
            logger.error(f"画像の保存エラー: {e}")
            return None

    def _calculate_ssim(self, img: Image.Image) -> float:
        """SSIM スコアの計算"""
        if self.groundtruth_img is None:
            return 0.0
        try:
            img_gray = img.convert('L')
            img_array = np.array(img_gray)
            groundtruth_array = np.array(self.groundtruth_img)
            
            # サイズが異なる場合はリサイズ
            if img_array.shape != groundtruth_array.shape:
                img_gray = img_gray.resize(self.groundtruth_img.size)
                img_array = np.array(img_gray)
            
            return compare_ssim(groundtruth_array, img_array)
        except Exception as e:
            logger.error(f"SSIM計算エラー: {e}")
            return 0.0

    async def process_prompt(self, prompt: str) -> Tuple[Optional[Image.Image], float]:
        """プロンプトを処理して画像を生成（非同期）"""
        if not prompt.strip():
            return None, 0.0

        file_name = self._sanitize_filename(prompt)
        path = os.path.join(self.config.output_dir, file_name)

        # キャッシュチェック
        cached_result = self.cache.get(file_name)
        if cached_result:
            return cached_result

        try:
            response = await asyncio.to_thread(
                self.client.images.generate,
                model=self.config.model,
                prompt=prompt,
                size=self.config.size
            )
            
            image_url = response.data[0].url
            image_data = await self._download_image(image_url)
            
            if image_data is None:
                return None, 0.0

            img = self._save_image(image_data, path)
            if img is None:
                return None, 0.0

            thumbnail = img.resize(self.config.thumbnail_size, Image.Resampling.LANCZOS)
            ssim = self._calculate_ssim(img)
            
            # キャッシュに保存
            result = (thumbnail, ssim)
            self.cache.set(file_name, result)
            
            logger.info(f"画像生成成功: {file_name}")
            return result

        except Exception as e:
            logger.error(f"画像生成エラー: {prompt} - {str(e)}")
            return None, 0.0

async def process_prompts(processor: ImageProcessor, prompts: List[str]) -> List[Tuple[Optional[Image.Image], float]]:
    """複数のプロンプトを非同期で処理"""
    tasks = [processor.process_prompt(prompt) for prompt in prompts if prompt.strip()]
    return await asyncio.gather(*tasks)

def create_grid_layout(results: List[Tuple[Optional[Image.Image], float]], cols: int) -> None:
    """グリッドレイアウトで画像を表示"""
    for i in range(0, len(results), cols):
        columns = st.columns(cols)
        for j, col in enumerate(columns):
            if i + j < len(results):
                img, ssim = results[i + j]
                if img:
                    col.image(img, use_column_width=True, caption=f'SSIM: {ssim:.3f}')

async def main():
    st.title('DALL-E画像生成アプリ')

    config = ImageGenerationConfig()
    
    async with ImageProcessor(config) as processor:
        prompts = st.text_area(
            '複数の画像プロンプトを入力してください（行ごとに異なるプロンプト）',
            help='各行に1つのプロンプトを入力してください'
        ).split('\n')

        if st.button('生成開始'):
            with st.spinner('画像を生成中...'):
                results = await process_prompts(processor, prompts)
                create_grid_layout(
                    [r for r in results if r[0] is not None],
                    config.chunk_size
                )

if __name__ == "__main__":
    load_dotenv(verbose=True)
    asyncio.run(main())
