# services.py
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
import logging
from .exceptions import PredictionError, DataProcessingError
from .schemas import HorseDataInput
from .models import JRAPredictionApp

logger = logging.getLogger(__name__)

class PredictionService:
    """予測サービスクラス
    
    馬データの処理と予測を行うサービスを提供します。
    """
    
    def __init__(self, jra_app: JRAPredictionApp):
        """初期化メソッド
        
        Args:
            jra_app: JRAPredictionAppのインスタンス
        """
        self.jra_app = jra_app
        
    def prepare_input_data(self, input_data: HorseDataInput) -> pd.DataFrame:
        """入力データを前処理する
        
        Args:
            input_data: 入力馬データ
            
        Returns:
            DataFrame: 前処理済みの入力データ
            
        Raises:
            DataProcessingError: データ処理中にエラーが発生した場合
        """
        try:
            logger.debug(f"入力データの処理: {input_data.dict()}")
            
            # 基本データの準備
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
            
            # モデルの特徴量情報を確認
            if not hasattr(self.jra_app, 'feature_columns') or not self.jra_app.feature_columns:
                raise ValueError("モデルの特徴量情報がありません")
                
            # One-hot encoding
            for col in self.jra_app.feature_columns:
                if col.startswith('性齢_'):
                    df[col] = 1 if col == f'性齢_{input_data.性齢}' else 0
                elif col.startswith('騎手_'):
                    df[col] = 1 if col == f'騎手_{input_data.騎手}' else 0
                    
            logger.debug(f"前処理完了: 特徴量数 {len(df.columns)}")
            return df
            
        except Exception as e:
            error_msg = f"入力データの処理中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            raise DataProcessingError(error_msg)
            
    def make_prediction(self, df: pd.DataFrame) -> Tuple[int, float]:
        """予測を実行する
        
        Args:
            df: 前処理済みの入力データ
            
        Returns:
            Tuple[int, float]: (予測結果, 信頼度)
            
        Raises:
            PredictionError: 予測処理中にエラーが発生した場合
        """
        try:
            # 予測実行
            prediction = self.jra_app.predict(df)
            confidence = self.jra_app.get_prediction_confidence(df)
            
            logger.info(f"予測結果: {int(prediction[0])}, 信頼度: {float(confidence):.4f}")
            return int(prediction[0]), float(confidence)
            
        except Exception as e:
            error_msg = f"予測処理中にエラーが発生しました: {str(e)}"
            logger.error(error_msg)
            raise PredictionError(error_msg)

# app.py
from flask import Flask, request, jsonify, render_template
import logging
from typing import Dict, Any, Optional

from .config import Config
from .schemas import HorseDataInput, PredictionResponse
from .services import PredictionService
from .models import JRAPredictionApp
from .exceptions import PredictionError, DataProcessingError, ModelError

def create_app(config: Optional[Config] = None) -> Flask:
    """Flaskアプリケーションを作成する
    
    Args:
        config: アプリケーション設定（Noneの場合はデフォルト設定を使用）
        
    Returns:
        Flask: 設定済みのFlaskアプリケーション
    """
    app = Flask(__name__)
    
    if config is None:
        config = Config()
        
    # ロギング設定
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # JRAPredictionAppのインスタンス化と初期設定
    logger.info("アプリケーションの初期化を開始")
    jra_app = JRAPredictionApp()
    
    try:
        if config.MODEL_PATH and os.path.exists(config.MODEL_PATH):
            logger.info(f"既存モデルを読み込み中: {config.MODEL_PATH}")
            jra_app.load_model(config.MODEL_PATH)
        else:
            logger.info("新しいモデルをトレーニング中")
            jra_app.scrape_data(config.BASE_URL, config.NUM_PAGES)
            jra_app.preprocess_data()
            jra_app.train_model()
            
            # モデルを保存
            if config.MODEL_PATH:
                logger.info(f"モデルを保存中: {config.MODEL_PATH}")
                jra_app.save_model(config.MODEL_PATH)
                
        logger.info("モデルの初期化が完了しました")
    except Exception as e:
        logger.error(f"モデル初期化中にエラーが発生: {str(e)}")
    
    prediction_service = PredictionService(jra_app)
    
    @app.route('/')
    def index():
        """ホームページを表示する"""
        try:
            return render_template('index.html')
        except Exception as e:
            logger.error(f"ホームページ表示中にエラーが発生: {str(e)}")
            return jsonify({'error': 'ページの表示中にエラーが発生しました'}), 500
        
    @app.route('/predict', methods=['POST'])
    def predict():
        """予測APIエンドポイント
        
        JSONリクエストから馬データを受け取り、予測結果を返します。
        
        Returns:
            JSON: 予測結果と信頼度
        """
        try:
            # リクエストデータの検証
            if not request.is_json:
                return jsonify({'error': 'リクエストはJSON形式である必要があります'}), 400
                
            # 入力データのバリデーション
            try:
                input_data = HorseDataInput(**request.json)
            except Exception as e:
                return jsonify({'error': f'入力データが無効です: {str(e)}'}), 400
            
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
            logger.error(f"予測エラー: {str(e)}")
            return jsonify({'error': str(e)}), 400
            
        except ModelError as e:
            logger.error(f"モデルエラー: {str(e)}")
            return jsonify({'error': 'モデルエラーが発生しました。管理者に連絡してください。'}), 500
            
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}")
            # 本番環境では詳細なエラーメッセージを露出しない
            return jsonify({'error': '予期せぬエラーが発生しました'}), 500
            
    return app

# main.py
import os
import argparse
import logging
from .config import Config
from .app import create_app

def parse_arguments():
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(description='JRA予測アプリケーション')
    parser.add_argument('--base-url', help='スクレイピング対象のベースURL')
    parser.add_argument('--num-pages', type=int, help='スクレイピングするページ数')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument('--model-path', help='モデルファイルのパス')
    parser.add_argument('--log-level', default='INFO', 
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      help='ロギングレベル')
    parser.add_argument('--port', type=int, default=5000, help='サーバーのポート番号')
    return parser.parse_args()

if __name__ == '__main__':
    # コマンドライン引数の解析
    args = parse_arguments()
    
    # 設定の初期化
    config = Config()
    
    # コマンドライン引数で設定を上書き
    if args.base_url:
        config.BASE_URL = args.base_url
    if args.num_pages:
        config.NUM_PAGES = args.num_pages
    if args.debug:
        config.DEBUG = True
    if args.model_path:
        config.MODEL_PATH = args.model_path
    if args.log_level:
        config.LOG_LEVEL = args.log_level
    
    # アプリケーションの作成と実行
    app = create_app(config)
    app.run(host='0.0.0.0', port=args.port, debug=config.DEBUG)
