import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

# サンプルデータの生成
np.random.seed(42)
n_samples = 100
X = np.random.rand(n_samples, 3)  # 3つの特徴量（面積、築年数、最寄り駅までの距離）
y = 5 * X[:, 0] - 3 * X[:, 1] + 2 * X[:, 2] + np.random.randn(n_samples) * 0.1

# データフレームの作成
df = pd.DataFrame(X, columns=['面積', '築年数', '最寄り駅までの距離'])
df['価格'] = y

# データの分割
X_train, X_test, y_train, y_test = train_test_split(df[['面積', '築年数', '最寄り駅までの距離']], df['価格'], test_size=0.2, random_state=42)

# モデルの作成と学習
model = LinearRegression()
model.fit(X_train, y_train)

# 予測
y_pred = model.predict(X_test)

# モデルの評価
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f'平均二乗誤差: {mse:.4f}')
print(f'決定係数: {r2:.4f}')

# 新しいデータに対する予測
new_data = np.array([[100, 5, 0.5]])  # 面積:100㎡, 築年数:5年, 最寄り駅までの距離:0.5km
predicted_price = model.predict(new_data)
print(f'予測価格: {predicted_price[0]:.2f}万円')
