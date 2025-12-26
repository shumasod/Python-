"""
予測サービスモジュール
"""

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
        logger.info("PredictionServiceを初期化しました")

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
            # 性齢と騎手のカテゴリカル変数を処理
            for col in self.jra_app.feature_columns:
                if col not in df.columns:
                    if col.startswith('性齢_'):
                        df[col] = 1 if col == f'性齢_{input_data.性齢}' else 0
                    elif col.startswith('騎手_'):
                        df[col] = 1 if col == f'騎手_{input_data.騎手}' else 0
                    else:
                        # その他の未知のカテゴリカル変数は0で埋める
                        df[col] = 0

            logger.debug(f"前処理完了: 特徴量数 {len(df.columns)}")
            return df

        except Exception as e:
            error_msg = f"入力データの処理中にエラーが発生しました: {str(e)}"
            logger.error(error_msg, exc_info=True)
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

            # 予測結果を整数に丸める（着順は整数値）
            predicted_rank = int(np.round(prediction[0]))

            # 着順の範囲を1-18に制限
            predicted_rank = max(1, min(18, predicted_rank))

            logger.info(
                f"予測結果: 着順 {predicted_rank}, 信頼度: {float(confidence):.4f}"
            )

            return predicted_rank, float(confidence)

        except Exception as e:
            error_msg = f"予測処理中にエラーが発生しました: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PredictionError(error_msg)

    def predict_from_input(self, input_data: HorseDataInput) -> Dict[str, Any]:
        """入力データから予測を実行する便利メソッド

        Args:
            input_data: 入力馬データ

        Returns:
            Dict[str, Any]: 予測結果を含む辞書
        """
        # データの準備
        df = self.prepare_input_data(input_data)

        # 予測の実行
        prediction, confidence = self.make_prediction(df)

        return {
            'prediction': prediction,
            'confidence': confidence,
            'input_data': input_data.dict()
        }
