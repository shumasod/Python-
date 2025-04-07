"""
DALL-E画像生成アプリ

複数のプロンプトから画像を生成し、基準画像との類似度を計算して表示するStreamlitアプリ
"""
import asyncio
import logging
import os
import pickle
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, TypedDict, cast

import aiohttp
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from openai import AsyncOpenAI
from PIL import Image
from skimage.metrics import structural_similarity as compare_ssim

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ]
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
    """画像キャッシュ管理クラス"""
    
    def __init__(self, cache_dir: str, cache_file: str, max_size: int = 100) -> None:
        """
        キャッシュ管理クラスの初期化
        
        Args:
            cache_dir: キャッシュディレクトリのパス
            cache_file: キャッシュファイルの名前
            max_size: キャッシュに保存する最大アイテム数
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / cache_file
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Image.Image, float]] = {}
        self._load_cache()
        
    def get(self, key: str) -> Optional[Tuple[Image.Image, float]]:
        """
        キーに対応するキャッシュエントリを取得
        
        Args:
            key: キャッシュのキー
            
        Returns:
            キャッシュされたサムネイルと類似度のタプル、またはNone
        """
        return self._cache.get(key)
        
    def set(self, key: str, value: Tuple[Image.Image, float]) -> None:
        """
        キャッシュにエントリを追加
        
        Args:
            key: キャッシュのキー
            value: キャッシュする値（サムネイルと類似度のタプル）
        """
        # キャッシュサイズ制限を適用
        if len(self._cache) >= self.max_size:
            # 最初のキーを削除（より洗練された方法では、LRUなどの戦略を適用可能）
            old_key = next(iter(self._cache))
            del self._cache[old_key]
            
        self._cache[key] = value
        self._save_cache()
        
    def _load_cache(self) -> None:
        """キャッシュファイルから読み込み"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    # 型チェックして安全に読み込む
                    if isinstance(cached_data, dict):
                        self._cache = cached_data
                    logger.info(f"{len(self._cache)}個のアイテムをキャッシュから読み込みました")
        except (IOError, pickle.PickleError) as e:
            logger.error(f"キャッシュの読み込みに失敗しました: {e}")
            # キャッシュに問題がある場合は新規作成
            self._cache = {}
            
    def _save_cache(self) -> None:
        """キャッシュをファイルに保存"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self._cache, f)
        except (IOError, pickle.PickleError) as e:
            logger.error(f"キャッシュの保存に失敗しました: {e}")


class ImageProcessor:
    """DALL-E画像生成と処理を行うクラス"""
    
    def __init__(self, config: ImageGenerationConfig) -> None:
        """
        画像処理クラスの初期化
        
        Args:
            config: 画像生成の設定
        """
        self.config = config
        self.client = self._initialize_openai_client()
        self.cache = ImageCache(
            config.output_dir, 
            config.cache_file,
            config.max_cache_size
        )
        self._setup_output_directory()
        self.groundtruth_img = self._load_groundtruth()
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def setup(self) -> 'ImageProcessor':
        """非同期初期化処理を行い、自身を返す"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
        )
        return self
        
    async def cleanup(self) -> None:
        """リソースのクリーンアップ処理"""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def __aenter__(self) -> 'ImageProcessor':
        """非同期コンテキストマネージャのエントリーポイント"""
        return await self.setup()
        
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャの終了処理"""
        await self.cleanup()

    def _initialize_openai_client(self) -> AsyncOpenAI:
        """OpenAI クライアントの初期化"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API キーが設定されていません。.env ファイルを確認してください。")
        return AsyncOpenAI(api_key=api_key)

    def _setup_output_directory(self) -> None:
        """出力ディレクトリの作成"""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    def _load_groundtruth(self) -> Optional[Image.Image]:
        """基準画像の読み込み"""
        try:
            groundtruth_path = Path(self.config.groundtruth_path)
            if groundtruth_path.exists():
                img = Image.open(groundtruth_path)
                return img.convert('L')
            logger.warning(f"基準画像が見つかりません: {groundtruth_path}")
            return None
        except Exception as e:
            logger.error(f"基準画像の読み込みエラー: {e}")
            return None

    @staticmethod
    def _sanitize_filename(prompt: str) -> str:
        """プロンプトからファイル名を生成（安全な文字のみ使用）"""
        # 先頭の英数字以外の文字を削除し、空白と特殊文字をアンダースコアに置換
        sanitized = re.sub(r'\W+', '_', prompt.lower())
        # 長さを制限して拡張子を追加
        return sanitized[:40] + '.png'

    async def _download_image(self, url: str) -> Optional[bytes]:
        """画像の非同期ダウンロード"""
        if not self.session:
            logger.error("HTTP セッションが初期化されていません")
            return None
            
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"画像ダウンロードエラー: HTTP {response.status}")
                    return None
                return await response.read()
        except aiohttp.ClientError as e:
            logger.error(f"画像のダウンロードエラー: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error(f"画像ダウンロードがタイムアウトしました: {url}")
            return None
        except Exception as e:
            logger.error(f"画像ダウンロード中に予期しないエラー: {e}")
            return None

    def _save_image(self, image_data: bytes, path: str) -> Optional[Image.Image]:
        """画像の保存とオブジェクトの返却"""
        try:
            img = Image.open(BytesIO(image_data))
            img.save(path, optimize=True)
            return img
        except Exception as e:
            logger.error(f"画像の保存エラー: {e}")
            return None

    def _calculate_ssim(self, img: Image.Image) -> float:
        """基準画像とのSSIM（構造的類似性）スコアの計算"""
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
            
            ssim = compare_ssim(groundtruth_array, img_array)
            return float(ssim)  # numpy.float64 から Python の float に変換
        except Exception as e:
            logger.error(f"SSIM計算エラー: {e}")
            return 0.0

    async def process_prompt(self, prompt: str) -> Tuple[Optional[Image.Image], float]:
        """
        プロンプトを処理して画像を生成（非同期）
        
        Args:
            prompt: 画像生成のプロンプト
            
        Returns:
            生成された画像のサムネイルとSSIMスコアのタプル
        """
        if not prompt.strip():
            logger.warning("空のプロンプトはスキップします")
            return None, 0.0

        # ファイル名の生成
        file_name = self._sanitize_filename(prompt)
        path = os.path.join(self.config.output_dir, file_name)

        # キャッシュチェック
        cached_result = self.cache.get(file_name)
        if cached_result:
            logger.info(f"キャッシュから画像を返却: {file_name}")
            return cached_result

        try:
            # OpenAI APIを使用して画像を非同期生成
            response = await self.client.images.generate(
                model=self.config.model,
                prompt=prompt,
                size=self.config.size,
                quality=self.config.quality,
                n=1
            )
            
            # レスポンスから画像URLを取得
            image_url = response.data[0].url
            
            # 画像をダウンロード
            image_data = await self._download_image(image_url)
            if image_data is None:
                logger.error(f"画像データの取得に失敗: {prompt}")
                return None, 0.0

            # 画像を保存
            img = self._save_image(image_data, path)
            if img is None:
                logger.error(f"画像の保存に失敗: {path}")
                return None, 0.0

            # サムネイルを生成し、SSIMスコアを計算
            thumbnail = img.resize(self.config.thumbnail_size, Image.Resampling.LANCZOS)
            ssim = self._calculate_ssim(img)
            
            # 結果をキャッシュに保存
            result = (thumbnail, ssim)
            self.cache.set(file_name, result)
            
            logger.info(f"画像生成成功: {file_name}, SSIM: {ssim:.3f}")
            return result

        except Exception as e:
            logger.error(f"画像生成エラー: {prompt} - {str(e)}")
            return None, 0.0


async def process_prompts(processor: ImageProcessor, prompts: List[str]) -> List[Tuple[Optional[Image.Image], float]]:
    """
    複数のプロンプトを非同期で処理
    
    Args:
        processor: 画像処理クラスのインスタンス
        prompts: 処理するプロンプトのリスト
        
    Returns:
        生成された画像とSSIMスコアのリスト
    """
    valid_prompts = [prompt for prompt in prompts if prompt.strip()]
    if not valid_prompts:
        return []
        
    # すべてのプロンプトを並列処理
    tasks = [processor.process_prompt(prompt) for prompt in valid_prompts]
    return await asyncio.gather(*tasks)


def create_grid_layout(results: List[Tuple[Optional[Image.Image], float]], cols: int) -> None:
    """
    グリッドレイアウトで画像を表示
    
    Args:
        results: 表示する画像とスコアのリスト
        cols: 1行あたりのカラム数
    """
    # 結果が空の場合は何も表示しない
    if not results:
        st.warning("表示する画像がありません。プロンプトを入力してください。")
        return
        
    # 有効な結果のみフィルタリング
    valid_results = [(img, ssim) for img, ssim in results if img is not None]
    if not valid_results:
        st.error("画像の生成に失敗しました。ログを確認してください。")
        return
    
    # 結果をSSIMスコアで降順ソート
    sorted_results = sorted(valid_results, key=lambda x: x[1], reverse=True)
    
    # グリッドレイアウトで表示
    for i in range(0, len(sorted_results), cols):
        columns = st.columns(cols)
        for j, col in enumerate(columns):
            if i + j < len(sorted_results):
                img, ssim = sorted_results[i + j]
                if img:
                    col.image(img, use_column_width=True, caption=f'類似度: {ssim:.3f}')


async def main() -> None:
    """アプリケーションのメインエントリーポイント"""
    st.set_page_config(
        page_title="DALL-E画像生成アプリ",
        page_icon="🖼️",
        layout="wide"
    )
    
    st.title('DALL-E画像生成アプリ')
    st.write("複数のプロンプトから画像を生成し、基準画像との類似度を計算します。")

    # 設定
    with st.sidebar:
        st.header("設定")
        model = st.selectbox(
            "モデル",
            ["dall-e-3", "dall-e-2"],
            index=0
        )
        
        size = st.selectbox(
            "画像サイズ",
            ["1024x1024", "512x512", "256x256"],
            index=0
        )
        
        quality = st.selectbox(
            "画質",
            ["standard", "hd"],
            index=0
        )
        
        cols = st.slider(
            "表示カラム数",
            min_value=1,
            max_value=5,
            value=3
        )

    # 設定オブジェクトの作成
    config = ImageGenerationConfig(
        model=model,
        size=size,
        quality=quality,
        chunk_size=cols
    )
    
    # プロンプト入力UI
    prompts = st.text_area(
        '複数の画像プロンプトを入力してください（行ごとに異なるプロンプト）',
        help='各行に1つのプロンプトを入力してください。空行は無視されます。',
        height=150
    ).split('\n')

    # 生成ボタン
    if st.button('画像を生成', type="primary"):
        if not prompts or not any(p.strip() for p in prompts):
            st.error("少なくとも1つのプロンプトを入力してください。")
            return
            
        with st.spinner('画像を生成中...'):
            # 非同期コンテキストマネージャを使用
            async with ImageProcessor(config) as processor:
                results = await process_prompts(processor, prompts)
                create_grid_layout(results, config.chunk_size)


if __name__ == "__main__":
    # 環境変数のロード
    load_dotenv(verbose=True)
    
    # 非同期メインループの実行
    asyncio.run(main())
