import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import matplotlib.pyplot as plt

# 1. データの取得 (トヨタ自動車: 7203.T)
ticker = '7203.T'
df = yf.download(ticker, start='2020-01-01', end='2023-01-01')

# 2. 必要なデータのみ抽出
df = df[['Close']]  # 終値のみを使用

# 3. 特徴量エンジニアリング
df['MA_5'] = df['Close'].rolling(window=5).mean()  # 5日移動平均
df['MA_20'] = df['Close'].rolling(window=20).mean()  # 20日移動平均
df['Shift_1'] = df['Close'].shift(1)  # 1日前の終値
df['Returns'] = df['Close'].pct_change()  # 日次リターン

# 欠損値を除去
df = df.dropna()

# 4. データ分割
X = df[['MA_5', 'MA_20', 'Shift_1', 'Returns']]  # 特徴量
y = df['Close']  # 目的変数

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# 5. 線形回帰モデルの作成
model = LinearRegression()
model.fit(X_train, y_train)

# 6. 予測
y_pred = model.predict(X_test)

# 7. モデル評価
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"Mean Squared Error: {mse}")
print(f"R-squared Score: {r2}")

# 8. 結果の可視化
plt.figure(figsize=(12,6))
plt.plot(df.index[-len(y_test):], y_test, label='Actual Price', color='blue')
plt.plot(df.index[-len(y_test):], y_pred, label='Predicted Price', color='red')
plt.title('Toyota Motor Corporation (7203.T) Stock Price Prediction')
plt.xlabel('Date')
plt.ylabel('Price (JPY)')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# 9. 特徴量の重要度
feature_importance = pd.DataFrame({'feature': X.columns, 'importance': model.coef_})
print("\nFeature Importance:")
print(feature_importance.sort_values('importance', ascending=False))