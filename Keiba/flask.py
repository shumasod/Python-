# config.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    BASE_URL: str = 'YOUR_BASE_URL_HERE'
    NUM_PAGES: int = 5
    DEBUG: bool = True
    MODEL_PATH: Optional[str] = None
    
# exceptions.py
class PredictionError(Exception):
    """予測処理中のエラーを表すカスタム例外"""
    pass

class DataProcessingError(Exception):
    """データ処理中のエラーを表すカスタム例外"""
    pass

# schemas.py
from pydantic import BaseModel, Field
from typing import List

class HorseDataInput(BaseModel):
    枠番: int = Field(..., ge=1, le=8)
    馬番: int = Field(..., ge=1, le=18)
    斤量: float = Field(..., ge=45.0, le=65.0)
    人気: int = Field(..., ge=1)
    単勝: float = Field(..., ge=1.0)
    馬体重: int = Field(..., ge=300, le=600)
    増減: int = Field(..., ge=-20, le=20)
    性齢: str = Field(...)
    騎手: str = Field(...)

class PredictionResponse(BaseModel):
    prediction: int
    confidence: float

# services.py
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
from .exceptions import PredictionError, DataProcessingError

class PredictionService:
    def __init__(self, jra_app: 'JRAPredictionApp'):
        self.jra_app = jra_app
        
    def prepare_input_data(self, input_data: HorseDataInput) -> pd.DataFrame:
        try:
            base_data = {
                '枠番': [input_data.枠番],
                '馬番': [input_data.馬番],
                '斤量': [input_data.斤量],
                '人気': [input_data.人気],
                '単勝': [input_data.単勝],
                '馬体重': [input_data.馬体重],
                '増減': [input_data.増減],
            }
            
            df = pd.DataFrame(base_data)
            
            # One-hot encoding
            for col in self.jra_app.data.columns:
                if col.startswith('性齢_'):
                    df[col] = 1 if col == f'性齢_{input_data.性齢}' else 0
                elif col.startswith('騎手_'):
                    df[col] = 1 if col == f'騎手_{input_data.騎手}' else 0
                    
            return df
            
        except Exception as e:
            raise DataProcessingError(f"入力データの処理中にエラーが発生しました: {str(e)}")
            
    def make_prediction(self, df: pd.DataFrame) -> Tuple[int, float]:
        try:
            prediction = self.jra_app.predict(df)
            confidence = self.jra_app.get_prediction_confidence(df)
            return int(prediction[0]), float(confidence)
        except Exception as e:
            raise PredictionError(f"予測処理中にエラーが発生しました: {str(e)}")

# app.py
from flask import Flask, request, jsonify
from flask.logging import create_logger
import logging
from typing import Dict, Any

from .config import Config
from .schemas import HorseDataInput, PredictionResponse
from .services import PredictionService
from .exceptions import PredictionError, DataProcessingError

def create_app(config: Config = None) -> Flask:
    app = Flask(__name__)
    
    if config is None:
        config = Config()
        
    logging.basicConfig(level=logging.INFO)
    logger = create_logger(app)
    
    # JRAPredictionAppのインスタンス化と初期設定
    jra_app = JRAPredictionApp()
    if config.MODEL_PATH:
        jra_app.load_model(config.MODEL_PATH)
    else:
        jra_app.scrape_data(config.BASE_URL, config.NUM_PAGES)
        jra_app.preprocess_data()
        jra_app.train_model()
    
    prediction_service = PredictionService(jra_app)
    
    @app.route('/')
    def index():
        return render_template('index.html')
        
    @app.route('/predict', methods=['POST'])
    def predict():
        try:
            # 入力データのバリデーション
            input_data = HorseDataInput(**request.json)
            
            # データの準備と予測
            df = prediction_service.prepare_input_data(input_data)
            prediction, confidence = prediction_service.make_prediction(df)
            
            # レスポンスの作成
            response = PredictionResponse(
                prediction=prediction,
                confidence=confidence
            )
            
            return jsonify(response.dict())
            
        except (PredictionError, DataProcessingError) as e:
            logger.error(f"Prediction error: {str(e)}")
            return jsonify({'error': str(e)}), 400
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return jsonify({'error': '予期せぬエラーが発生しました'}), 500
            
    return app

# main.py
if __name__ == '__main__':
    config = Config()
    app = create_app(config)
    app.run(debug=config.DEBUG)
