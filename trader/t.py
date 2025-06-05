import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class StockPredictor:
    def __init__(self, ticker, start_date, end_date, prediction_days=1):
        """
        株価予測クラス
        
        Args:
            ticker (str): 銘柄コード
            start_date (str): 開始日
            end_date (str): 終了日
            prediction_days (int): 何日先を予測するか
        """
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.prediction_days = prediction_days
        self.model = LinearRegression()
        self.scaler = StandardScaler()
        self.data = None
        
    def download_data(self):
        """データの取得とエラーハンドリング"""
        try:
            print(f"Downloading data for {self.ticker}...")
            self.data = yf.download(self.ticker, start=self.start_date, end=self.end_date)
            
            if self.data.empty:
                raise ValueError(f"No data found for ticker {self.ticker}")
                
            if len(self.data) < 50:  # 最低限のデータ量チェック
                raise ValueError(f"Insufficient data: only {len(self.data)} records")
                
            print(f"Successfully downloaded {len(self.data)} records")
            return True
            
        except Exception as e:
            print(f"Error downloading data: {e}")
            return False
    
    def create_features(self):
        """適切な特徴量の作成（データリークを避ける）"""
        if self.data is None:
            raise ValueError("Data not loaded. Call download_data() first.")
        
        df = self.data.copy()
        
        # 基本的な価格情報
        df['High_Low_Pct'] = (df['High'] - df['Low']) / df['Close'] * 100
        df['Volume_MA'] = df['Volume'].rolling(window=10).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        # ラグ特徴量（過去の情報のみ使用）
        for lag in [1, 2, 3, 5]:
            df[f'Close_Lag_{lag}'] = df['Close'].shift(lag)
            df[f'Volume_Lag_{lag}'] = df['Volume'].shift(lag)
            df[f'Returns_Lag_{lag}'] = df['Close'].pct_change(lag).shift(1)
        
        # 技術指標（過去の情報のみ使用）
        df['MA_5'] = df['Close'].shift(1).rolling(window=5).mean()
        df['MA_10'] = df['Close'].shift(1).rolling(window=10).mean()
        df['MA_20'] = df['Close'].shift(1).rolling(window=20).mean()
        
        # RSI（相対力指数）
        delta = df['Close'].diff().shift(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # ボラティリティ
        df['Volatility'] = df['Close'].shift(1).rolling(window=10).std()
        
        # 価格位置（過去20日の最高値・最低値に対する位置）
        df['High_20'] = df['High'].shift(1).rolling(window=20).max()
        df['Low_20'] = df['Low'].shift(1).rolling(window=20).min()
        df['Price_Position'] = (df['Close'].shift(1) - df['Low_20']) / (df['High_20'] - df['Low_20'])
        
        # 目的変数：N日後の価格変化率
        df['Target'] = (df['Close'].shift(-self.prediction_days) / df['Close'] - 1) * 100
        
        return df
    
    def prepare_data(self):
        """データの前処理"""
        df = self.create_features()
        
        # 特徴量の選択
        feature_columns = [
            'High_Low_Pct', 'Volume_Ratio',
            'Close_Lag_1', 'Close_Lag_2', 'Close_Lag_3', 'Close_Lag_5',
            'Volume_Lag_1', 'Volume_Lag_2', 'Volume_Lag_3', 'Volume_Lag_5',
            'Returns_Lag_1', 'Returns_Lag_2', 'Returns_Lag_3', 'Returns_Lag_5',
            'MA_5', 'MA_10', 'MA_20', 'RSI', 'Volatility', 'Price_Position'
        ]
        
        # 欠損値を除去
        df = df.dropna()
        
        if len(df) < 100:
            raise ValueError(f"Insufficient data after feature engineering: {len(df)} records")
        
        X = df[feature_columns]
        y = df['Target']
        
        # 異常値の除去（目的変数の上下5%を除去）
        lower_bound = y.quantile(0.05)
        upper_bound = y.quantile(0.95)
        mask = (y >= lower_bound) & (y <= upper_bound)
        
        X = X[mask]
        y = y[mask]
        
        print(f"Final dataset size: {len(X)} records")
        print(f"Features: {list(X.columns)}")
        
        return X, y
    
    def train_model(self):
        """時系列交差検証を使ったモデル訓練"""
        X, y = self.prepare_data()
        
        # 時系列分割
        tscv = TimeSeriesSplit(n_splits=5)
        
        cv_scores = []
        cv_mse = []
        cv_mae = []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            # スケーリング
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            # モデル訓練
            self.model.fit(X_train_scaled, y_train)
            
            # 予測と評価
            y_pred = self.model.predict(X_val_scaled)
            
            r2 = r2_score(y_val, y_pred)
            mse = mean_squared_error(y_val, y_pred)
            mae = mean_absolute_error(y_val, y_pred)
            
            cv_scores.append(r2)
            cv_mse.append(mse)
            cv_mae.append(mae)
            
            print(f"Fold {fold + 1}: R² = {r2:.4f}, MSE = {mse:.4f}, MAE = {mae:.4f}")
        
        print(f"\nCross-validation results:")
        print(f"Average R² = {np.mean(cv_scores):.4f} ± {np.std(cv_scores):.4f}")
        print(f"Average MSE = {np.mean(cv_mse):.4f} ± {np.std(cv_mse):.4f}")
        print(f"Average MAE = {np.mean(cv_mae):.4f} ± {np.std(cv_mae):.4f}")
        
        # 最終モデルの訓練（全データを使用）
        train_size = int(len(X) * 0.8)
        X_train = X.iloc[:train_size]
        X_test = X.iloc[train_size:]
        y_train = y.iloc[:train_size]
        y_test = y.iloc[train_size:]
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        self.model.fit(X_train_scaled, y_train)
        
        # テストセット評価
        y_pred = self.model.predict(X_test_scaled)
        
        test_r2 = r2_score(y_test, y_pred)
        test_mse = mean_squared_error(y_test, y_pred)
        test_mae = mean_absolute_error(y_test, y_pred)
        
        print(f"\nTest set results:")
        print(f"R² = {test_r2:.4f}")
        print(f"MSE = {test_mse:.4f}")
        print(f"MAE = {test_mae:.4f}")
        
        return X_train, X_test, y_train, y_test, y_pred
    
    def plot_results(self, y_test, y_pred):
        """結果の可視化"""
        plt.figure(figsize=(15, 10))
        
        # 予測結果のプロット
        plt.subplot(2, 2, 1)
        plt.scatter(y_test, y_pred, alpha=0.6)
        plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
        plt.xlabel('Actual Returns (%)')
        plt.ylabel('Predicted Returns (%)')
        plt.title('Actual vs Predicted Returns')
        
        # 残差プロット
        plt.subplot(2, 2, 2)
        residuals = y_test - y_pred
        plt.scatter(y_pred, residuals, alpha=0.6)
        plt.axhline(y=0, color='r', linestyle='--')
        plt.xlabel('Predicted Returns (%)')
        plt.ylabel('Residuals')
        plt.title('Residual Plot')
        
        # 特徴量重要度
        plt.subplot(2, 2, 3)
        feature_importance = pd.DataFrame({
            'feature': self.prepare_data()[0].columns,
            'importance': np.abs(self.model.coef_)
        }).sort_values('importance', ascending=True)
        
        plt.barh(range(len(feature_importance)), feature_importance['importance'])
        plt.yticks(range(len(feature_importance)), feature_importance['feature'])
        plt.xlabel('Absolute Coefficient')
        plt.title('Feature Importance')
        
        # 誤差分布
        plt.subplot(2, 2, 4)
        plt.hist(residuals, bins=30, alpha=0.7, edgecolor='black')
        plt.xlabel('Residuals')
        plt.ylabel('Frequency')
        plt.title('Distribution of Residuals')
        
        plt.tight_layout()
        plt.show()
    
    def run_analysis(self):
        """完全な分析の実行"""
        if not self.download_data():
            return False
        
        try:
            X_train, X_test, y_train, y_test, y_pred = self.train_model()
            self.plot_results(y_test, y_pred)
            
            # 統計的有意性のチェック
            from scipy import stats
            _, p_value = stats.pearsonr(y_test, y_pred)
            print(f"\nCorrelation p-value: {p_value:.6f}")
            
            if p_value < 0.05:
                print("Model predictions are statistically significant!")
            else:
                print("Model predictions may not be statistically significant.")
            
            return True
            
        except Exception as e:
            print(f"Error during analysis: {e}")
            return False

# 使用例
if __name__ == "__main__":
    # トヨタ自動車の1日先価格変化率を予測
    predictor = StockPredictor(
        ticker='7203.T',
        start_date='2020-01-01',
        end_date='2024-01-01',
        prediction_days=1
    )
    
    predictor.run_analysis()
