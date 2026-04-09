"""
予測APIルーター
POST /predict エンドポイントを定義する
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator

from app.model.predict import predict_race
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ---- リクエストスキーマ ----

class BoatInfo(BaseModel):
    """1艇分の選手・機材情報"""
    boat_number: int = Field(..., ge=1, le=6, description="艇番（1〜6）")
    racer_name: Optional[str] = Field(None, description="選手名")
    racer_rank: str = Field("B1", description="選手ランク (A1/A2/B1/B2)")
    win_rate: float = Field(0.0, ge=0.0, le=100.0, description="全体勝率 (%)")
    motor_score: float = Field(50.0, description="モーター性能スコア")
    course_win_rate: float = Field(0.0, ge=0.0, le=100.0, description="コース別勝率 (%)")
    start_timing: float = Field(0.18, ge=0.0, le=1.0, description="スタートタイミング (秒)")
    motor_2rate: float = Field(30.0, ge=0.0, le=100.0, description="モーター2連対率 (%)")
    boat_2rate: float = Field(30.0, ge=0.0, le=100.0, description="ボート2連対率 (%)")
    recent_3_avg: float = Field(3.5, ge=1.0, le=6.0, description="直近3レース平均着順")


class WeatherInfo(BaseModel):
    """レース時の気象情報"""
    condition: str = Field("晴", description="天候 (晴/曇/雨)")
    wind_speed: float = Field(0.0, ge=0.0, description="風速 (m/s)")
    water_temp: float = Field(20.0, description="水温 (℃)")


class RaceRequest(BaseModel):
    """POST /predict のリクエストボディ"""
    race_id: Optional[str] = Field(None, description="レースID（任意）")
    race: Dict[str, Any] = Field(..., description="レース情報")

    @validator("race")
    def validate_race(cls, v: Dict) -> Dict:
        boats = v.get("boats", [])
        if len(boats) != 6:
            raise ValueError(f"boats には6艇分のデータが必要です（受け取り: {len(boats)}艇）")
        return v


# ---- レスポンススキーマ ----

class TrifectaItem(BaseModel):
    """三連単1点の情報"""
    combination: List[int] = Field(..., description="艇番の順序 [1着, 2着, 3着]")
    probability: float = Field(..., description="推定確率")
    rank: int = Field(..., description="確率順位")


class RecommendationItem(BaseModel):
    """買い目推奨1点の情報"""
    combination: List[int]
    probability: float
    odds: float
    expected_value: float
    kelly_fraction: float
    note: str


class PredictResponse(BaseModel):
    """POST /predict のレスポンスボディ"""
    race_id: Optional[str] = None
    win_probabilities: List[float] = Field(
        ..., description="各艇の1着確率（1号艇〜6号艇の順）"
    )
    trifecta: List[TrifectaItem] = Field(..., description="三連単上位10点")
    recommendations: List[RecommendationItem] = Field(..., description="推奨買い目")


# ---- エンドポイント ----

@router.post("/predict", response_model=PredictResponse, summary="競艇レース予測")
async def predict_endpoint(request: RaceRequest) -> PredictResponse:
    """
    競艇レース情報を受け取り、各艇の1着確率・三連単推奨を返す

    - **win_probabilities**: 1号艇〜6号艇の順に1着確率を並べたリスト
    - **trifecta**: モデルが計算した三連単上位10点（確率降順）
    - **recommendations**: 期待値フィルタを通過した買い目推奨
    """
    try:
        logger.info(f"予測リクエスト受信: race_id={request.race_id}")
        result = predict_race(request.race)
        return PredictResponse(
            race_id=request.race_id,
            **result,
        )
    except FileNotFoundError as e:
        # モデルファイルが見つからない場合
        logger.error(f"モデルファイルエラー: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"モデルが未学習です。先にトレーニングを実行してください。詳細: {e}",
        )
    except ValueError as e:
        logger.error(f"入力値エラー: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"予測処理中に予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="内部サーバーエラー")
