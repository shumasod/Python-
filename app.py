import streamlit as st # pip install streamlit
from openai import OpenAI # pip install openai
import requests # pip install requests
import os
import re
from PIL import Image # pip install pillow
from io import BytesIO
from skimage.metrics import structural_similarity as compare_ssim # pip install scikit-image
import numpy as np # pip install numpy

from dotenv import load_dotenv # pip install python-dotenv
load_dotenv(verbose=True)

# Streamlitページの設定
st.title('DALL-E画像生成アプリ')

# 画像を保存するディレクトリの作成
os.makedirs('generated_images', exist_ok=True)

# 基準画像の読み込み
groundtruth_path = 'groundtruth.png'
if os.path.exists(groundtruth_path):
    groundtruth_img = Image.open(groundtruth_path)
    groundtruth_img = groundtruth_img.convert('L')  # グレースケールに変換
else:
    st.error('基準画像が見つかりません。')

# 生成された画像とSSIMスコアを保持するリスト
images_ssim = []

# 複数のプロンプト入力
prompts = st.text_area('複数の画像プロンプトを入力してください（行ごとに異なるプロンプト）').split('\n')

# 生成された画像を保持するリスト
images = []

# プロンプトが入力されたときに画像を生成
for prompt in prompts:
    if prompt:
        # ファイル名をプロンプトから生成
        file_name = re.sub(r'\W+', '_', prompt)[:20] + '.png'

        # OpenAI APIを使用して画像を生成
        try:
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024"
            )

            # 画像のURLを取得
            image_url = response.data[0].url

            # 画像をダウンロードして保存
            response = requests.get(image_url)
            if response.status_code == 200:
                print(file_name, "done")
                path = os.path.join('generated_images', file_name)
                with open(path, "wb") as f:
                    f.write(response.content)

                # PILを使用して画像サイズを調整
                img = Image.open(BytesIO(response.content))
                resized_img = img.resize((150, 150))  # 画像サイズを150x150に調整

                # 画像をリストに追加
                images.append(resized_img)

                img = img.convert('L')  # グレースケールに変換

                # SSIM計算
                ssim = compare_ssim(np.array(groundtruth_img), np.array(img))
                images_ssim.append(ssim)

        except:
            print(file_name, "error")

# 5個ずつ画像を並べて表示
for i in range(0, len(images), 5):
    cols = st.columns(5)
    for j in range(5):
        if i + j < len(images):
            with cols[j]:
                st.image(images[i + j], use_column_width=True, caption=f'{images_ssim[i + j]}')
