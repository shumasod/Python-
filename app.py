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
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ImageGenerationConfig:
    """画像生成の設定を保持するデータクラス"""
    model: str = "dall-e-3"
    size: str = "1024x1024"
    output_dir: str = "generated_images"
    thumbnail_size: Tuple[int, int] = (150, 150)
    groundtruth_path: str = "groundtruth.png"

class ImageProcessor:
    def __init__(self, config: ImageGenerationConfig):
        """
        画像処理クラスの初期化
        
        Args:
            config: 画像生成の設定
        """
        self.config = config
        self.client = self._initialize_openai_client()
        self._setup_output_directory()
        self.groundtruth_img = self._load_groundtruth()

    def _initialize_openai_client(self) -> OpenAI:
        """OpenAI クライアントの初期化"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API キーが設定されていません")
        return OpenAI(api_key=api_key)

    def _setup_output_directory(self) -> None:
        """出力ディレクトリの作成"""
        os.makedirs(self.config.output_dir, exist_ok=True)

    def _load_groundtruth(self) -> Optional[Image.Image]:
        """基準画像の読み込み"""
        try:
            if os.path.exists(self.config.groundtruth_path):
                img = Image.open(self.config.groundtruth_path)
                return img.convert('L')  # グレースケール変換
            logger.warning("基準画像が見つかりません")
            return None
        except Exception as e:
            logger.error(f"基準画像の読み込みエラー: {e}")
            return None

    def _sanitize_filename(self, prompt: str) -> str:
        """プロンプトからファイル名を生成"""
        return re.sub(r'\W+', '_', prompt)[:20] + '.png'

    def _download_and_save_image(self, url: str, path: str) -> Optional[Image.Image]:
        """画像のダウンロードと保存"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            with open(path, "wb") as f:
                f.write(response.content)
            
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            logger.error(f"画像のダウンロードエラー: {e}")
            return None
        except Exception as e:
            logger.error(f"画像の保存エラー: {e}")
            return None

    def _calculate_ssim(self, img: Image.Image) -> float:
        """SSIM スコアの計算"""
        if self.groundtruth_img is None:
            return 0.0
        try:
            img_gray = img.convert('L')
            return compare_ssim(np.array(self.groundtruth_img), np.array(img_gray))
        except Exception as e:
            logger.error(f"SSIM計算エラー: {e}")
            return 0.0

    def process_prompt(self, prompt: str) -> Tuple[Optional[Image.Image], float]:
        """
        プロンプトを処理して画像を生成
        
        Args:
            prompt: 画像生成プロンプト
            
        Returns:
            生成された画像とSSIMスコアのタプル
        """
        if not prompt.strip():
            return None, 0.0

        file_name = self._sanitize_filename(prompt)
        path = os.path.join(self.config.output_dir, file_name)

        try:
            response = self.client.images.generate(
                model=self.config.model,
                prompt=prompt,
                size=self.config.size
            )
            
            image_url = response.data[0].url
            img = self._download_and_save_image(image_url, path)
            
            if img is None:
                return None, 0.0

            thumbnail = img.resize(self.config.thumbnail_size)
            ssim = self._calculate_ssim(img)
            
            logger.info(f"画像生成成功: {file_name}")
            return thumbnail, ssim

        except Exception as e:
            logger.error(f"画像生成エラー: {prompt} - {str(e)}")
            return None, 0.0

def main():
    st.title('DALL-E画像生成アプリ')

    config = ImageGenerationConfig()
    processor = ImageProcessor(config)

    # プロンプト入力
    prompts = st.text_area(
        '複数の画像プロンプトを入力してください（行ごとに異なるプロンプト）',
        help='各行に1つのプロンプトを入力してください'
    ).split('\n')

    # 生成された画像とスコアを保持
    results: List[Tuple[Optional[Image.Image], float]] = []
    
    # プロンプトの処理
    with st.spinner('画像を生成中...'):
        for prompt in prompts:
            if prompt.strip():
                thumbnail, ssim = processor.process_prompt(prompt)
                if thumbnail:
                    results.append((thumbnail, ssim))

    # 画像の表示
    for i in range(0, len(results), 5):
        cols = st.columns(5)
        for j in range(5):
            if i + j < len(results):
                with cols[j]:
                    img, ssim = results[i + j]
                    st.image(img, use_column_width=True, caption=f'SSIM: {ssim:.3f}')

if __name__ == "__main__":
    load_dotenv(verbose=True)
    main()
