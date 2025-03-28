# 必要なライブラリをインストール
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

# 1. データの取得 (ソフトバンクグループ: 9984.T)
ticker = '9984.T'
df = yf.download(ticker, start='2020-01-01', end='2023-01-01')

# 2. 必要なデータのみ抽出
df = df[['Close']]  # 終値のみを使用

# 3. 移動平均やラグ特徴量を追加
df['MA_5'] = df['Close'].rolling(window=5).mean()  # 5日移動平均
df['Shift_1'] = df['Close'].shift(1)  # 1日前の終値

# 欠損値を除去
df = df.dropna()

# 4. データ分割
X = df[['MA_5', 'Shift_1']]  # 特徴量
y = df['Close']  # 目的変数

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# 5. 線形回帰モデルの作成
model = LinearRegression()
model.fit(X_train, y_train)

# 6. 予測
y_pred = model.predict(X_test)

# 7. 結果の可視化
plt.figure(figsize=(10,6))
plt.plot(df.index[len(X_train):], y_test, label='Actual Price', color='blue')
plt.plot(df.index[len(X_train):], y_pred, label='Predicted Price', color='red')
plt.title('SoftBank Group Stock Price Prediction')
plt.xlabel('Date')
plt.ylabel('Price (JPY)')
plt.legend()
plt.show()