"""
JRA競馬予測アプリケーション - Flaskアプリファクトリ
"""

import os
import logging
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, render_template

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
    
    # 設定の初期化
    if config is None:
        config = Config()
    
    # Flaskアプリケーションに設定を追加
    app.config.from_object(config)
    
    # ロギング設定
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log') if hasattr(config, 'LOG_FILE') else logging.NullHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # JRAPredictionAppのインスタンス化と初期設定
    logger.info("=" * 50)
    logger.info("アプリケーションの初期化を開始")
    logger.info("=" * 50)
    
    jra_app = JRAPredictionApp()
    
    try:
        # モデルの読み込みまたはトレーニング
        if config.MODEL_PATH and os.path.exists(config.MODEL_PATH):
            logger.info(f"既存モデルを読み込み中: {config.MODEL_PATH}")
            jra_app.load_model(config.MODEL_PATH)
            logger.info("モデルの読み込みが完了しました")
        else:
            logger.info("新しいモデルをトレーニング中")
            logger.info(f"データスクレイピング: {config.BASE_URL} (ページ数: {config.NUM_PAGES})")
            
            # データのスクレイピング
            jra_app.scrape_data(config.BASE_URL, config.NUM_PAGES)
            logger.info("データのスクレイピングが完了しました")
            
            # データの前処理
            logger.info("データの前処理を開始")
            jra_app.preprocess_data()
            logger.info("データの前処理が完了しました")
            
            # モデルのトレーニング
            logger.info("モデルのトレーニングを開始")
            jra_app.train_model()
            logger.info("モデルのトレーニングが完了しました")
            
            # モデルの保存
            if config.MODEL_PATH:
                logger.info(f"モデルを保存中: {config.MODEL_PATH}")
                # 保存先ディレクトリが存在しない場合は作成
                os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
                jra_app.save_model(config.MODEL_PATH)
                logger.info("モデルの保存が完了しました")
        
        logger.info("=" * 50)
        logger.info("モデルの初期化が完了しました")
        logger.info("=" * 50)
        
    except FileNotFoundError as e:
        logger.error(f"ファイルが見つかりません: {str(e)}")
        raise
    except PermissionError as e:
        logger.error(f"ファイルへのアクセス権限がありません: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"モデル初期化中にエラーが発生: {str(e)}", exc_info=True)
        raise
    
    # PredictionServiceの初期化
    prediction_service = PredictionService(jra_app)
    
    @app.route('/')
    def index():
        """ホームページを表示する
        
        Returns:
            HTML: インデックスページ
        """
        try:
            return render_template('index.html')
        except Exception as e:
            logger.error(f"ホームページ表示中にエラーが発生: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'ページの表示中にエラーが発生しました',
                'message': 'テンプレートファイルが見つからない可能性があります'
            }), 500
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """ヘルスチェックエンドポイント
        
        Returns:
            JSON: アプリケーションの状態
        """
        try:
            return jsonify({
                'status': 'healthy',
                'model_loaded': jra_app.model is not None,
                'version': getattr(config, 'VERSION', '1.0.0')
            }), 200
        except Exception as e:
            logger.error(f"ヘルスチェック中にエラー: {str(e)}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500
    
    @app.route('/predict', methods=['POST'])
    def predict():
        """予測APIエンドポイント
        
        JSONリクエストから馬データを受け取り、予測結果を返します。
        
        Request Body:
            JSON形式の馬データ（HorseDataInputスキーマに準拠）
        
        Returns:
            JSON: 予測結果と信頼度
            
        Status Codes:
            200: 予測成功
            400: リクエストエラー（不正なデータ形式など）
            500: サーバーエラー
        """
        try:
            # リクエストデータの検証
            if not request.is_json:
                logger.warning("JSON形式でないリクエストを受信")
                return jsonify({
                    'error': 'リクエストはJSON形式である必要があります',
                    'received_content_type': request.content_type
                }), 400
            
            # リクエストボディが空でないことを確認
            if not request.json:
                logger.warning("空のリクエストボディを受信")
                return jsonify({
                    'error': 'リクエストボディが空です'
                }), 400
            
            logger.info(f"予測リクエストを受信: {request.json}")
            
            # 入力データのバリデーション
            try:
                input_data = HorseDataInput(**request.json)
            except ValueError as e:
                logger.warning(f"入力データのバリデーションエラー: {str(e)}")
                return jsonify({
                    'error': '入力データが無効です',
                    'details': str(e)
                }), 400
            except Exception as e:
                logger.error(f"入力データの解析中にエラー: {str(e)}")
                return jsonify({
                    'error': '入力データの解析に失敗しました',
                    'details': str(e)
                }), 400
            
            # データの準備
            logger.debug("入力データを準備中")
            df = prediction_service.prepare_input_data(input_data)
            
            # 予測の実行
            logger.debug("予測を実行中")
            prediction, confidence = prediction_service.make_prediction(df)
            
            # レスポンスの作成
            response = PredictionResponse(
                prediction=prediction,
                confidence=confidence
            )
            
            logger.info(f"予測成功: {prediction} (信頼度: {confidence:.2f})")
            return jsonify(response.dict()), 200
            
        except PredictionError as e:
            logger.error(f"予測エラー: {str(e)}")
            return jsonify({
                'error': '予測の実行中にエラーが発生しました',
                'details': str(e)
            }), 400
            
        except DataProcessingError as e:
            logger.error(f"データ処理エラー: {str(e)}")
            return jsonify({
                'error': 'データ処理中にエラーが発生しました',
                'details': str(e)
            }), 400
            
        except ModelError as e:
            logger.error(f"モデルエラー: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'モデルエラーが発生しました',
                'message': '管理者に連絡してください'
            }), 500
            
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}", exc_info=True)
            # 本番環境では詳細なエラーメッセージを露出しない
            if app.debug:
                return jsonify({
                    'error': '予期せぬエラーが発生しました',
                    'details': str(e)
                }), 500
            else:
                return jsonify({
                    'error': '予期せぬエラーが発生しました',
                    'message': '管理者に連絡してください'
                }), 500
    
    @app.route('/api/info', methods=['GET'])
    def api_info():
        """API情報を返すエンドポイント
        
        Returns:
            JSON: API情報
        """
        return jsonify({
            'api_version': getattr(config, 'VERSION', '1.0.0'),
            'endpoints': {
                '/': 'ホームページ',
                '/health': 'ヘルスチェック',
                '/predict': '予測API (POST)',
                '/api/info': 'API情報'
            },
            'model_info': {
                'loaded': jra_app.model is not None,
                'type': type(jra_app.model).__name__ if jra_app.model else None
            }
        }), 200
    
    @app.errorhandler(404)
    def not_found(error):
        """404エラーハンドラー"""
        return jsonify({
            'error': 'ページが見つかりません',
            'requested_url': request.url
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """405エラーハンドラー"""
        return jsonify({
            'error': '許可されていないHTTPメソッドです',
            'method': request.method,
            'allowed_methods': error.valid_methods if hasattr(error, 'valid_methods') else []
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        """500エラーハンドラー"""
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        return jsonify({
            'error': 'サーバー内部エラーが発生しました',
            'message': '管理者に連絡してください'
        }), 500
    
    return app


def main():
    """アプリケーションのエントリーポイント"""
    config = Config()
    app = create_app(config)
    
    # デバッグモードの設定
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # ホストとポートの設定
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    
    print("=" * 50)
    print("JRA競馬予測アプリケーション")
    print("=" * 50)
    print(f"ホスト: {host}")
    print(f"ポート: {port}")
    print(f"デバッグモード: {debug_mode}")
    print("=" * 50)
    
    app.run(
        host=host,
        port=port,
        debug=debug_mode
    )


if __name__ == '__main__':
    main()
