
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
