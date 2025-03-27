# models.py（新規作成）
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import joblib
import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from .exceptions import ModelError, DataProcessingError

logger = logging.getLogger(__name__)

class JRAPredictionApp:
    """JRA競馬予測アプリケーションのメインクラス
    
    このクラスはデータのスクレイピング、前処理、モデルトレーニング、
    予測の実行など、競馬予測の中核機能を提供します。
    """
    
    def __init__(self):
        """初期化メソッド"""
        self.data = None
        self.model = None
        self.scaler = None
        self.feature_columns = None
        
    def scrape_data(self, base_url: str, num_pages: int) -> pd.DataFrame:
        """指定URLから競馬データをスクレイピングする
        
        Args:
            base_url: スクレイピング対象のベースURL
            num_pages: スクレイピングするページ数
            
        Returns:
            DataFrame: スクレイピングしたデータ
        """
        try:
            logger.info(f"データスクレイピングを開始: {base_url}, ページ数: {num_pages}")
            
            # 実際のスクレイピングロジックを実装
            # TODO: 本番環境では実際のスクレイピングロジックを実装する
            
            # サンプルデータを生成（実際の実装では置き換える）
            sample_data = []
            for _ in range(100):
                sample_data.append({
                    '枠番': np.random.randint(1, 9),
                    '馬番': np.random.randint(1, 19),
                    '斤量': np.random.uniform(50.0, 58.0),
                    '人気': np.random.randint(1, 19),
                    '単勝': np.random.uniform(1.1, 50.0),
                    '馬体重': np.random.randint(400, 550),
                    '増減': np.random.randint(-10, 11),
                    '性齢': np.random.choice(['牡2', '牡3', '牡4', '牡5', '牝2', '牝3', '牝4', 'セ3', 'セ4', 'セ5']),
                    '騎手': np.random.choice(['福永祐一', '川田将雅', 'デムーロ', '武豊', '戸崎圭太']),
                    '着順': np.random.randint(1, 19)
                })
            
            self.data = pd.DataFrame(sample_data)
            logger.info(f"スクレイピング完了: {len(self.data)}件のデータを取得")
            return self.data
            
        except Exception as e:
            logger.error(f"スクレイピング中にエラーが発生: {str(e)}")
            raise DataProcessingError(f"スクレイピング中にエラーが発生: {str(e)}")
            
    def preprocess_data(self) -> pd.DataFrame:
        """スクレイピングしたデータを前処理する
        
        Returns:
            DataFrame: 前処理後のデータ
        """
        if self.data is None:
            raise ValueError("データがありません。先にscrape_dataを実行してください。")
            
        try:
            logger.info("データ前処理を開始")
            
            # カテゴリ変数のOne-hotエンコーディング
            df = self.data.copy()
            
            # カテゴリカルデータのエンコーディング
            for col in ['性齢', '騎手']:
                dummies = pd.get_dummies(df[col], prefix=col)
                df = pd.concat([df, dummies], axis=1)
                df.drop(col, axis=1, inplace=True)
                
            # 特徴量として使用する列を保存
            self.feature_columns = [c for c in df.columns if c != '着順']
            
            self.data = df
            logger.info(f"前処理完了: 特徴量数 {len(self.feature_columns)}")
            return self.data
            
        except Exception as e:
            logger.error(f"データ前処理中にエラーが発生: {str(e)}")
            raise DataProcessingError(f"データ前処理中にエラーが発生: {str(e)}")
            
    def train_model(self) -> RandomForestRegressor:
        """モデルをトレーニングする
        
        Returns:
            RandomForestRegressor: トレーニング済みのモデル
        """
        if self.data is None or self.feature_columns is None:
            raise ValueError("前処理されたデータがありません。先にpreprocess_dataを実行してください。")
            
        try:
            logger.info("モデルトレーニングを開始")
            
            X = self.data[self.feature_columns]
            y = self.data['着順']
            
            # トレーニングデータとテストデータに分割
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # 特徴量のスケーリング
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # ランダムフォレストモデルのトレーニング
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.model.fit(X_train_scaled, y_train)
            
            # モデルの評価
            train_score = self.model.score(X_train_scaled, y_train)
            test_score = self.model.score(X_test_scaled, y_test)
            
            logger.info(f"モデルトレーニング完了: トレーニングスコア {train_score:.4f}, テストスコア {test_score:.4f}")
            return self.model
            
        except Exception as e:
            logger.error(f"モデルトレーニング中にエラーが発生: {str(e)}")
            raise ModelError(f"モデルトレーニング中にエラーが発生: {str(e)}")
            
    def predict(self, input_df: pd.DataFrame) -> np.ndarray:
        """入力データに基づいて予測を行う
        
        Args:
            input_df: 入力データ（前処理済み）
            
        Returns:
            ndarray: 予測結果（着順）
        """
        if self.model is None:
            raise ValueError("モデルがトレーニングされていません。")
            
        try:
            # 入力データの特徴量を調整
            missing_columns = set(self.feature_columns) - set(input_df.columns)
            if missing_columns:
                for col in missing_columns:
                    input_df[col] = 0
                    
            # 特徴量の順序を調整
            input_df = input_df[self.feature_columns]
            
            # スケーリング
            if self.scaler:
                input_scaled = self.scaler.transform(input_df)
            else:
                input_scaled = input_df
                
            # 予測
            prediction = self.model.predict(input_scaled)
            
            return prediction
            
        except Exception as e:
            logger.error(f"予測中にエラーが発生: {str(e)}")
            raise PredictionError(f"予測中にエラーが発生: {str(e)}")
            
    def get_prediction_confidence(self, input_df: pd.DataFrame) -> float:
        """予測の信頼度を計算する
        
        Args:
            input_df: 入力データ（前処理済み）
            
        Returns:
            float: 予測の信頼度（0.0〜1.0）
        """
        if self.model is None:
            raise ValueError("モデルがトレーニングされていません。")
            
        try:
            # 入力データの特徴量を調整
            missing_columns = set(self.feature_columns) - set(input_df.columns)
            if missing_columns:
                for col in missing_columns:
                    input_df[col] = 0
                    
            # 特徴量の順序を調整
            input_df = input_df[self.feature_columns]
            
            # スケーリング
            if self.scaler:
                input_scaled = self.scaler.transform(input_df)
            else:
                input_scaled = input_df
            
            # 各木の予測値を取得して標準偏差を計算
            predictions = [tree.predict(input_scaled)[0] for tree in self.model.estimators_]
            std_dev = np.std(predictions)
            
            # 信頼度の計算（標準偏差が小さいほど信頼度が高い）
            max_std_dev = 5.0  # 標準偏差の最大想定値
            confidence = max(0.0, min(1.0, 1.0 - (std_dev / max_std_dev)))
            
            return confidence
            
        except Exception as e:
            logger.error(f"信頼度計算中にエラーが発生: {str(e)}")
            raise PredictionError(f"信頼度計算中にエラーが発生: {str(e)}")
            
    def save_model(self, model_path: str) -> None:
        """モデルを保存する
        
        Args:
            model_path: モデルを保存するパス
        """
        if self.model is None:
            raise ValueError("保存するモデルがありません。")
            
        try:
            # 保存するディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            
            # モデル関連データを保存
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_columns': self.feature_columns
            }
            
            joblib.dump(model_data, model_path)
            logger.info(f"モデルを保存しました: {model_path}")
            
        except Exception as e:
            logger.error(f"モデル保存中にエラーが発生: {str(e)}")
            raise ModelError(f"モデル保存中にエラーが発生: {str(e)}")
            
    def load_model(self, model_path: str) -> None:
        """保存されたモデルを読み込む
        
        Args:
            model_path: モデルファイルのパス
        """
        try:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")
                
            # モデルデータの読み込み
            model_data = joblib.load(model_path)
            
            self.model = model_data.get('model')
            self.scaler = model_data.get('scaler')
            self.feature_columns = model_data.get('feature_columns')
            
            if self.model is None:
                raise ValueError("無効なモデルファイルです")
                
            logger.info(f"モデルを読み込みました: {model_path}")
            
        except Exception as e:
            logger.error(f"モデル読み込み中にエラーが発生: {str(e)}")
            raise ModelError(f"モデル読み込み中にエラーが発生: {str(e)}")
