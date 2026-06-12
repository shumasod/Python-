"""
データスキーマ定義
"""

from typing import Optional
from pydantic import BaseModel, Field, validator


class HorseDataInput(BaseModel):
    """競馬予測の入力データスキーマ"""

    枠番: int = Field(..., ge=1, le=8, description="枠番（1-8）")
    馬番: int = Field(..., ge=1, le=18, description="馬番（1-18）")
    斤量: float = Field(..., ge=40.0, le=65.0, description="斤量（kg）")
    人気: int = Field(..., ge=1, le=18, description="人気順位")
    単勝: float = Field(..., ge=1.0, description="単勝オッズ")
    馬体重: int = Field(..., ge=300, le=600, description="馬体重（kg）")
    増減: int = Field(..., ge=-50, le=50, description="馬体重の増減（kg）")
    性齢: str = Field(..., description="性別と年齢（例：牡3、牝4、セ5）")
    騎手: str = Field(..., min_length=1, description="騎手名")

    class Config:
        json_schema_extra = {
            "example": {
                "枠番": 3,
                "馬番": 5,
                "斤量": 55.0,
                "人気": 2,
                "単勝": 3.5,
                "馬体重": 480,
                "増減": 2,
                "性齢": "牡4",
                "騎手": "川田将雅"
            }
        }

    @validator('性齢')
    def validate_sex_age(cls, v):
        """性齢のフォーマットをバリデート"""
        if not v or len(v) < 2:
            raise ValueError('性齢は2文字以上である必要があります')

        valid_prefixes = ['牡', '牝', 'セ']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError('性齢は「牡」「牝」「セ」のいずれかで始まる必要があります')

        return v


class PredictionResponse(BaseModel):
    """予測結果のレスポンススキーマ"""

    prediction: int = Field(..., description="予測着順")
    confidence: float = Field(..., ge=0.0, le=1.0, description="予測の信頼度（0.0-1.0）")

    class Config:
        json_schema_extra = {
            "example": {
                "prediction": 3,
                "confidence": 0.85
            }
        }


class RaceDataInput(BaseModel):
    """レース全体の入力データスキーマ"""

    race_name: str = Field(..., description="レース名")
    race_date: str = Field(..., description="レース日付（YYYY-MM-DD）")
    track: str = Field(..., description="競馬場名")
    distance: int = Field(..., ge=800, le=4000, description="距離（メートル）")
    track_condition: str = Field(..., description="馬場状態（良、稍重、重、不良）")
    horses: list[HorseDataInput] = Field(..., description="出走馬のリスト")

    class Config:
        json_schema_extra = {
            "example": {
                "race_name": "天皇賞（春）",
                "race_date": "2025-05-04",
                "track": "京都",
                "distance": 3200,
                "track_condition": "良",
                "horses": []
            }
        }


class ModelInfo(BaseModel):
    """モデル情報のスキーマ"""

    model_type: str = Field(..., description="モデルのタイプ")
    version: str = Field(..., description="バージョン")
    trained_at: Optional[str] = Field(None, description="トレーニング日時")
    accuracy: Optional[float] = Field(None, description="精度")

    class Config:
        json_schema_extra = {
            "example": {
                "model_type": "RandomForestRegressor",
                "version": "1.0.0",
                "trained_at": "2025-01-01T00:00:00",
                "accuracy": 0.82
            }
        }


class HealthCheckResponse(BaseModel):
    """ヘルスチェックのレスポンススキーマ"""

    status: str = Field(..., description="ステータス（healthy/unhealthy）")
    model_loaded: bool = Field(..., description="モデルが読み込まれているか")
    version: str = Field(..., description="アプリケーションバージョン")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "model_loaded": True,
                "version": "1.0.0"
            }
        }
