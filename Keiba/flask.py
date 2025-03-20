# config.py
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

@dataclass
class Config:
    """アプリケーション設定クラス
    
    属性:
        BASE_URL: スクレイピング対象のベースURL
        NUM_PAGES: スクレイピングするページ数
        DEBUG: デバッグモードフラグ
        MODEL_PATH: 事前トレーニング済みモデルのパス（Noneの場合は新規トレーニング）
        LOG_LEVEL: ロギングレベル
    """
    BASE_URL: str = field(default_factory=lambda: os.environ.get('JRA_BASE_URL', 'https://example.com/jra'))
    NUM_PAGES: int = field(default_factory=lambda: int(os.environ.get('JRA_NUM_PAGES', '5')))
    DEBUG: bool = field(default_factory=lambda: os.environ.get('JRA_DEBUG', 'False').lower() == 'true')
    MODEL_PATH: Optional[str] = field(default_factory=lambda: os.environ.get('JRA_MODEL_PATH'))
    LOG_LEVEL: str = field(default_factory=lambda: os.environ.get('JRA_LOG_LEVEL', 'INFO'))
    
    def __post_init__(self):
        """設定値の型変換と検証を行う"""
        if isinstance(self.NUM_PAGES, str):
            self.NUM_PAGES = int(self.NUM_PAGES)
        
        # モデルパスが指定されている場合はディレクトリを作成
        if self.MODEL_PATH:
            model_dir = os.path.dirname(self.MODEL_PATH)
            if model_dir and not os.path.exists(model_dir):
                os.makedirs(model_dir)

# exceptions.py
class BaseJRAException(Exception):
    """JRA予測アプリの基本例外クラス"""
    pass

class PredictionError(BaseJRAException):
    """予測処理中のエラーを表すカスタム例外
    
    Args:
        message: エラーメッセージ
        details: エラーの詳細情報（オプション）
    """
    def __init__(self, message: str, details: Optional[dict] = None):
        self.details = details
        super().__init__(message)

class DataProcessingError(BaseJRAException):
    """データ処理中のエラーを表すカスタム例外
    
    Args:
        message: エラーメッセージ
        column: エラーが発生したカラム名（オプション）
    """
    def __init__(self, message: str, column: Optional[str] = None):
        self.column = column
        super().__init__(message)

class ModelError(BaseJRAException):
    """モデル関連のエラーを表すカスタム例外"""
    pass

# schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
import re

class HorseDataInput(BaseModel):
    """馬のデータ入力スキーマ
    
    競馬予測に必要な馬のデータを定義します。
    """
    枠番: int = Field(..., ge=1, le=8, description="馬の枠番（1〜8）")
    馬番: int = Field(..., ge=1, le=18, description="馬の馬番（1〜18）")
    斤量: float = Field(..., ge=45.0, le=65.0, description="馬の斤量（kg）")
    人気: int = Field(..., ge=1, description="人気順位")
    単勝: float = Field(..., ge=1.0, description="単勝オッズ")
    馬体重: int = Field(..., ge=300, le=600, description="馬の体重（kg）")
    増減: int = Field(..., ge=-20, le=20, description="前走からの体重増減（kg）")
    性齢: str = Field(..., description="馬の性別と年齢（例: 牡3）")
    騎手: str = Field(..., description="騎手名")

    @validator('性齢')
    def validate_gender_age(cls, v):
        """性齢のフォーマットを検証"""
        if not re.match(r'^(牡|牝|セ)[2-9]$', v):
            raise ValueError("性齢は「牡/牝/セ」と「2-9」の組み合わせである必要があります（例: 牡3）")
        return v

    @validator('騎手')
    def validate_jockey(cls, v):
        """騎手名が空でないことを確認"""
        if not v.strip():
            raise ValueError("騎手名は必須です")
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "枠番": 1,
                "馬番": 1,
                "斤量": 54.0,
                "人気": 3,
                "単勝": 4.5,
                "馬体重": 480,
                "増減": 2,
                "性齢": "牡3",
                "騎手": "福永祐一"
            }
        }

class PredictionResponse(BaseModel):
    """予測結果のレスポンススキーマ
    
    モデルの予測結果と信頼度を含みます。
    """
    prediction: int = Field(..., description="予測結果（着順）")
    confidence: float = Field(..., ge=0.0, le=1.0, description="予測の信頼度（0.0〜1.0）")
    details: Optional[Dict[str, Any]] = Field(None, description="予測の詳細情報（オプション）")

    class Config:
        schema_extra = {
            "example": {
                "prediction": 1,
                "confidence": 0.75,
                "details": {
                    "feature_importance": {
                        "単勝": 0.35,
                        "馬体重": 0.25
                    }
                }
            }
        }

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
