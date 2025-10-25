"""
データスキーマ定義
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class HorseDataInput(BaseModel):
    """馬データの入力スキーマ"""
    
    # 馬の基本情報
    horse_name: str = Field(..., description="馬名", min_length=1, max_length=100)
    horse_id: Optional[str] = Field(None, description="馬ID")
    age: int = Field(..., description="年齢", ge=2, le=10)
    sex: str = Field(..., description="性別 (牡/牝/セ)")
    weight: float = Field(..., description="馬体重(kg)", ge=300, le=600)
    
    # レース情報
    race_type: str = Field(..., description="レース種別 (芝/ダート/障害)")
    distance: int = Field(..., description="距離(m)", ge=1000, le=4000)
    track_condition: str = Field(..., description="馬場状態 (良/稍重/重/不良)")
    weather: str = Field(..., description="天候 (晴/曇/雨/雪)")
    
    # 騎手・厩舎情報
    jockey_name: str = Field(..., description="騎手名")
    jockey_weight: float = Field(..., description="騎手の斤量(kg)", ge=48, le=60)
    trainer_name: str = Field(..., description="調教師名")
    
    # 過去の成績
    recent_runs: Optional[int] = Field(None, description="最近の出走回数", ge=0)
    wins: Optional[int] = Field(None, description="勝利数", ge=0)
    places: Optional[int] = Field(None, description="入着数", ge=0)
    earnings: Optional[float] = Field(None, description="獲得賞金(万円)", ge=0)
    
    # オプション情報
    blinkers: bool = Field(False, description="ブリンカー装着")
    apprentice_allowance: Optional[float] = Field(None, description="見習騎手減量(kg)")
    gate_number: Optional[int] = Field(None, description="ゲート番号", ge=1, le=18)
    
    @validator('sex')
    def validate_sex(cls, v):
        """性別のバリデーション"""
        valid_sexes = ['牡', '牝', 'セ']
        if v not in valid_sexes:
            raise ValueError(f'性別は {", ".join(valid_sexes)} のいずれかである必要があります')
        return v
    
    @validator('race_type')
    def validate_race_type(cls, v):
        """レース種別のバリデーション"""
        valid_types = ['芝', 'ダート', '障害']
        if v not in valid_types:
            raise ValueError(f'レース種別は {", ".join(valid_types)} のいずれかである必要があります')
        return v
    
    @validator('track_condition')
    def validate_track_condition(cls, v):
        """馬場状態のバリデーション"""
        valid_conditions = ['良', '稍重', '重', '不良']
        if v not in valid_conditions:
            raise ValueError(f'馬場状態は {", ".join(valid_conditions)} のいずれかである必要があります')
        return v
    
    @validator('weather')
    def validate_weather(cls, v):
        """天候のバリデーション"""
        valid_weather = ['晴', '曇', '雨', '雪']
        if v not in valid_weather:
            raise ValueError(f'天候は {", ".join(valid_weather)} のいずれかである必要があります')
        return v
    
    @validator('wins', 'places')
    def validate_performance(cls, v, values, field):
        """成績のバリデーション"""
        if v is not None and 'recent_runs' in values:
            recent_runs = values.get('recent_runs')
            if recent_runs is not None and v > recent_runs:
                raise ValueError(f'{field.name}は出走回数を超えることはできません')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "horse_name": "サンプル号",
                "age": 4,
                "sex": "牡",
                "weight": 480.0,
                "race_type": "芝",
                "distance": 2000,
                "track_condition": "良",
                "weather": "晴",
                "jockey_name": "武豊",
                "jockey_weight": 57.0,
                "trainer_name": "藤沢和雄",
                "recent_runs": 10,
                "wins": 3,
                "places": 7,
                "earnings": 5000.0,
                "blinkers": False,
                "gate_number": 5
            }
        }


class PredictionResponse(BaseModel):
    """予測結果のレスポンススキーマ"""
    
    prediction: int = Field(..., description="予測着順", ge=1)
    confidence: float = Field(..., description="信頼度", ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now, description="予測時刻")
    
    class Config:
        schema_extra = {
            "example": {
                "prediction": 1,
                "confidence": 0.85,
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class BatchPredictionInput(BaseModel):
    """バッチ予測の入力スキーマ"""
    
    horses: List[HorseDataInput] = Field(..., description="馬データのリスト", min_items=1, max_items=18)
    
    @validator('horses')
    def validate_unique_horses(cls, v):
        """馬の重複チェック"""
        horse_names = [horse.horse_name for horse in v]
        if len(horse_names) != len(set(horse_names)):
            raise ValueError('馬名が重複しています')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "horses": [
                    {
                        "horse_name": "サンプル号",
                        "age": 4,
                        "sex": "牡",
                        "weight": 480.0,
                        "race_type": "芝",
                        "distance": 2000,
                        "track_condition": "良",
                        "weather": "晴",
                        "jockey_name": "武豊",
                        "jockey_weight": 57.0,
                        "trainer_name": "藤沢和雄"
                    }
                ]
            }
        }


class BatchPredictionResponse(BaseModel):
    """バッチ予測結果のレスポンススキーマ"""
    
    predictions: List[PredictionResponse] = Field(..., description="予測結果のリスト")
    total_horses: int = Field(..., description="予測対象の馬の総数")
    timestamp: datetime = Field(default_factory=datetime.now, description="予測時刻")
    
    class Config:
        schema_extra = {
            "example": {
                "predictions": [
                    {
                        "prediction": 1,
                        "confidence": 0.85,
                        "timestamp": "2024-01-01T12:00:00"
                    }
                ],
                "total_horses": 1,
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class ErrorResponse(BaseModel):
    """エラーレスポンススキーマ"""
    
    error: str = Field(..., description="エラーメッセージ")
    details: Optional[str] = Field(None, description="詳細情報")
    timestamp: datetime = Field(default_factory=datetime.now, description="エラー発生時刻")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "入力データが無効です",
                "details": "年齢は2から10の範囲である必要があります",
                "timestamp": "2024-01-01T12:00:00"
            }
        }
