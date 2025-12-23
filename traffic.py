from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle
import os
from typing import Dict, List, Optional, Union
import json

# 共通モジュールのインポート
from shared.logging_utils import setup_logging
from shared.exceptions import ValidationError, AppError
from shared.config import get_config

# ログ設定
logger = setup_logging(__name__)
config = get_config()

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

    def train(self, data: Optional[pd.DataFrame] = None) -> 'CongestionPredictor':
        """
        モデルを訓練

        Args:
            data: 訓練データ（省略時はサンプルデータを生成）

        Returns:
            CongestionPredictor: 自身のインスタンス

        Raises:
            ValidationError: データが不正な場合
        """
        try:
            if data is None:
                logger.info("サンプルデータを生成中...")
                data = self.generate_sample_data(2000)

            # データの検証
            if data.empty:
                raise ValidationError("訓練データが空です", code="EMPTY_DATA")

            if not all(col in data.columns for col in self.feature_columns + ['congestion']):
                missing_cols = set(self.feature_columns + ['congestion']) - set(data.columns)
                raise ValidationError(
                    f"必要なカラムが不足しています: {missing_cols}",
                    code="MISSING_COLUMNS",
                    details={'missing_columns': list(missing_cols)}
                )

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

        except ValidationError:
            raise
        except Exception as e:
            logger.exception("モデル訓練中にエラーが発生しました")
            raise AppError(
                f"モデル訓練に失敗しました: {str(e)}",
                code="TRAINING_FAILED"
            ) from e

    def predict(
        self,
        datetime_obj: datetime,
        temperature: float = 20.0,
        weather_code: int = 0,
        is_holiday: bool = False
    ) -> Dict[str, Union[float, str, Dict]]:
        """
        混雑度を予測

        Args:
            datetime_obj: 予測対象の日時
            temperature: 気温（デフォルト: 20.0）
            weather_code: 天気コード（0:晴れ, 1:曇り, 2:雨, 3:雪）
            is_holiday: 祝日かどうか

        Returns:
            予測結果の辞書:
                - congestion_level: 混雑度（0-100）
                - confidence: 信頼度（0-100）
                - status: 混雑状況の文字列
                - features_used: 使用した特徴量

        Raises:
            ValidationError: モデルが未訓練または入力が不正な場合
        """
        if not self.is_trained:
            raise ValidationError(
                "モデルが訓練されていません",
                code="MODEL_NOT_TRAINED"
            )

        # 入力検証
        if not isinstance(datetime_obj, datetime):
            raise ValidationError(
                "datetime_objはdatetimeオブジェクトである必要があります",
                code="INVALID_DATETIME_TYPE"
            )

        if weather_code not in [0, 1, 2, 3]:
            raise ValidationError(
                f"weather_codeは0-3の範囲である必要があります: {weather_code}",
                code="INVALID_WEATHER_CODE",
                details={'value': weather_code, 'expected': '0-3'}
            )

        try:
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

        except Exception as e:
            logger.exception("予測中にエラーが発生しました")
            raise AppError(
                f"予測に失敗しました: {str(e)}",
                code="PREDICTION_FAILED"
            ) from e

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

    def predict_multiple(
        self,
        start_datetime: datetime,
        hours: int = 24,
        temperature: float = 20.0,
        weather_code: int = 0,
        is_holiday: bool = False
    ) -> List[Dict[str, Union[float, str, Dict]]]:
        """
        複数時間の予測

        Args:
            start_datetime: 開始日時
            hours: 予測する時間数（デフォルト: 24）
            temperature: 気温
            weather_code: 天気コード
            is_holiday: 祝日かどうか

        Returns:
            予測結果のリスト

        Raises:
            ValidationError: 入力が不正な場合
        """
        if hours <= 0:
            raise ValidationError(
                f"hoursは正の整数である必要があります: {hours}",
                code="INVALID_HOURS",
                details={'value': hours, 'expected': '>0'}
            )

        if hours > 168:  # 1週間以上
            logger.warning(f"長時間の予測が要求されました: {hours}時間")

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
        except ValueError as e:
            raise ValidationError(
                '日時形式が正しくありません (ISO 8601形式を使用)',
                code='INVALID_DATETIME_FORMAT',
                details={'value': datetime_str}
            ) from e

        # 予測実行
        prediction = predictor.predict(dt, temperature, weather_code, is_holiday)

        return jsonify({
            'success': True,
            'prediction': prediction,
            'requested_datetime': datetime_str
        })

    except ValidationError as e:
        logger.warning(f"検証エラー: {e}")
        return jsonify(e.to_dict()), 400

    except AppError as e:
        logger.error(f"アプリケーションエラー: {e}")
        return jsonify(e.to_dict()), 500

    except Exception as e:
        logger.exception("予期しないエラーが発生しました")
        error = AppError(
            "予測処理中に予期しないエラーが発生しました",
            code="UNEXPECTED_ERROR"
        )
        return jsonify(error.to_dict()), 500

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
        except ValueError as e:
            raise ValidationError(
                '日時形式が正しくありません (ISO 8601形式を使用)',
                code='INVALID_DATETIME_FORMAT',
                details={'value': start_datetime_str}
            ) from e

        # 複数予測実行
        predictions = predictor.predict_multiple(
            start_dt, hours, temperature, weather_code, is_holiday
        )

        return jsonify({
            'success': True,
            'predictions': predictions,
            'total_hours': hours
        })

    except ValidationError as e:
        logger.warning(f"検証エラー: {e}")
        return jsonify(e.to_dict()), 400

    except AppError as e:
        logger.error(f"アプリケーションエラー: {e}")
        return jsonify(e.to_dict()), 500

    except Exception as e:
        logger.exception("予期しないエラーが発生しました")
        error = AppError(
            "バッチ予測処理中に予期しないエラーが発生しました",
            code="UNEXPECTED_ERROR"
        )
        return jsonify(error.to_dict()), 500

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

    except ValidationError as e:
        logger.warning(f"検証エラー: {e}")
        return jsonify(e.to_dict()), 400

    except AppError as e:
        logger.error(f"再訓練エラー: {e}")
        return jsonify(e.to_dict()), 500

    except Exception as e:
        logger.exception("予期しないエラーが発生しました")
        error = AppError(
            "モデル再訓練中に予期しないエラーが発生しました",
            code="UNEXPECTED_ERROR"
        )
        return jsonify(error.to_dict()), 500

if __name__ == '__main__':
    # 開発サーバーで実行
    app.run(
        host=config.api_host,
        port=config.api_port,
        debug=config.debug
    )