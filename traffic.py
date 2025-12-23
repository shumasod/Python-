from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle
import os
import logging
from typing import Dict, List, Optional
import json

# ログ設定

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class CongestionPredictor:
    """混雑予測クラス"""

    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_columns = [
            'hour', 'day_of_week', 'is_weekend', 'is_holiday',
            'temperature', 'weather_code', 'month', 'is_rush_hour'
        ]

    def create_features(self, datetime_obj: datetime,
                       temperature: float = 20.0,
                       weather_code: int = 0,
                       is_holiday: bool = False) -> Dict:
        """特徴量を作成"""
        features = {
            'hour': datetime_obj.hour,
            'day_of_week': datetime_obj.weekday(),
            'is_weekend': 1 if datetime_obj.weekday() >= 5 else 0,
            'is_holiday': 1 if is_holiday else 0,
            'temperature': temperature,
            'weather_code': weather_code,  # 0:晴れ, 1:曇り, 2:雨, 3:雪
            'month': datetime_obj.month,
            'is_rush_hour': 1 if datetime_obj.hour in [7, 8, 9, 17, 18, 19] else 0
        }
        return features

    def generate_sample_data(self, n_samples: int = 1000) -> pd.DataFrame:
        """サンプルデータを生成（実際の運用では実データを使用）"""
        np.random.seed(42)
        data = []

        base_date = datetime(2023, 1, 1)
        for i in range(n_samples):
            dt = base_date + timedelta(hours=i)

            # 基本的な混雑パターンを設定
            base_congestion = 30  # 基本混雑度

            # 時間帯による影響
            if dt.hour in [7, 8, 9]:  # 朝のラッシュ
                base_congestion += 40
            elif dt.hour in [17, 18, 19]:  # 夕方のラッシュ
                base_congestion += 50
            elif dt.hour in [12, 13]:  # 昼休み
                base_congestion += 20
            elif dt.hour in [0, 1, 2, 3, 4, 5]:  # 深夜早朝
                base_congestion -= 20

            # 曜日による影響
            if dt.weekday() >= 5:  # 週末
                base_congestion -= 10

            # 月による影響（季節性）
            if dt.month in [7, 8]:  # 夏休み
                base_congestion += 15
            elif dt.month in [12, 1]:  # 年末年始
                base_congestion += 10

            # ランダムノイズ
            base_congestion += np.random.normal(0, 10)

            # 0-100の範囲に制限
            congestion = max(0, min(100, base_congestion))

            # 特徴量作成
            temperature = 20 + np.random.normal(0, 10)
            weather_code = np.random.choice([0, 1, 2, 3], p=[0.5, 0.3, 0.15, 0.05])
            is_holiday = np.random.choice([True, False], p=[0.1, 0.9])

            features = self.create_features(dt, temperature, weather_code, is_holiday)
            features['congestion'] = congestion

            data.append(features)

        return pd.DataFrame(data)

    def train(self, data: pd.DataFrame = None):
        """モデルを訓練"""
        if data is None:
            logger.info("サンプルデータを生成中...")
            data = self.generate_sample_data(2000)

        X = data[self.feature_columns]
        y = data['congestion']

        # データの標準化
        X_scaled = self.scaler.fit_transform(X)

        # モデル訓練
        logger.info("モデルを訓練中...")
        self.model.fit(X_scaled, y)
        self.is_trained = True

        logger.info("訓練完了!")
        return self

    def predict(self, datetime_obj: datetime,
                temperature: float = 20.0,
                weather_code: int = 0,
                is_holiday: bool = False) -> Dict:
        """混雑度を予測"""
        if not self.is_trained:
            raise ValueError("モデルが訓練されていません")

        features = self.create_features(datetime_obj, temperature, weather_code, is_holiday)
        X = pd.DataFrame([features])[self.feature_columns]
        X_scaled = self.scaler.transform(X)

        prediction = self.model.predict(X_scaled)[0]
        prediction = max(0, min(100, prediction))  # 0-100の範囲に制限

        # 信頼区間の推定（簡易版）
        confidence = max(0, min(100, 100 - abs(prediction - 50) * 0.5))

        return {
            'congestion_level': round(prediction, 1),
            'confidence': round(confidence, 1),
            'status': self._get_congestion_status(prediction),
            'features_used': features
        }

    def _get_congestion_status(self, level: float) -> str:
        """混雑レベルを文字列で表現"""
        if level < 20:
            return "空いている"
        elif level < 40:
            return "やや空いている"
        elif level < 60:
            return "普通"
        elif level < 80:
            return "やや混雑"
        else:
            return "混雑"

    def predict_multiple(self, start_datetime: datetime,
                        hours: int = 24,
                        temperature: float = 20.0,
                        weather_code: int = 0,
                        is_holiday: bool = False) -> List[Dict]:
        """複数時間の予測"""
        predictions = []
        for i in range(hours):
            dt = start_datetime + timedelta(hours=i)
            pred = self.predict(dt, temperature, weather_code, is_holiday)
            pred['datetime'] = dt.isoformat()
            predictions.append(pred)
        return predictions

# グローバルな予測器インスタンス

predictor = CongestionPredictor()

@app.before_first_request
def initialize():
    """アプリケーション初期化時にモデルを訓練"""
    logger.info("混雑予測APIを初期化中…")
    predictor.train()
    logger.info("初期化完了!")

# API エンドポイント

@app.route('/', methods=['GET'])
def health_check():
    """ヘルスチェック"""
    return jsonify({
        'status': 'healthy',
        'service': 'congestion-prediction-api',
        'model_trained': predictor.is_trained
    })

@app.route('/predict', methods=['POST'])
def predict_congestion():
    """混雑予測API"""
    try:
        data = request.get_json()

        # 必須パラメータのチェック
        if 'datetime' not in data:
            return jsonify({'error': 'datetimeパラメータが必要です'}), 400

        # パラメータの取得
        datetime_str = data['datetime']
        temperature = data.get('temperature', 20.0)
        weather_code = data.get('weather_code', 0)
        is_holiday = data.get('is_holiday', False)

        # 日時の解析
        try:
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': '日時形式が正しくありません (ISO 8601形式を使用)'}), 400

        # 予測実行
        prediction = predictor.predict(dt, temperature, weather_code, is_holiday)

        return jsonify({
            'success': True,
            'prediction': prediction,
            'requested_datetime': datetime_str
        })

    except Exception as e:
        logger.error(f"予測エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/predict/batch', methods=['POST'])
def predict_congestion_batch():
    """複数時間の混雑予測API"""
    try:
        data = request.get_json()

        # 必須パラメータのチェック
        if 'start_datetime' not in data:
            return jsonify({'error': 'start_datetimeパラメータが必要です'}), 400

        # パラメータの取得
        start_datetime_str = data['start_datetime']
        hours = data.get('hours', 24)
        temperature = data.get('temperature', 20.0)
        weather_code = data.get('weather_code', 0)
        is_holiday = data.get('is_holiday', False)

        # 日時の解析
        try:
            start_dt = datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': '日時形式が正しくありません (ISO 8601形式を使用)'}), 400

        # 複数予測実行
        predictions = predictor.predict_multiple(
            start_dt, hours, temperature, weather_code, is_holiday
        )

        return jsonify({
            'success': True,
            'predictions': predictions,
            'total_hours': hours
        })

    except Exception as e:
        logger.error(f"バッチ予測エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/model/info', methods=['GET'])
def model_info():
    """モデル情報取得API"""
    return jsonify({
        'model_type': 'RandomForestRegressor',
        'features': predictor.feature_columns,
        'trained': predictor.is_trained,
        'weather_codes': {
            0: '晴れ',
            1: '曇り',
            2: '雨',
            3: '雪'
        }
    })

@app.route('/retrain', methods=['POST'])
def retrain_model():
    """モデル再訓練API（管理用）"""
    try:
        logger.info("モデルを再訓練中…")
        predictor.train()
        return jsonify({
            'success': True,
            'message': 'モデルの再訓練が完了しました'
        })
    except Exception as e:
        logger.error(f"再訓練エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 開発サーバーで実行
    app.run(host='0.0.0.0', port=5000, debug=True)