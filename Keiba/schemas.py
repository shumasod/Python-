# schemas.py
from pydantic import BaseModel, Field, field_validator
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

    @field_validator('性齢')
    def validate_gender_age(cls, v):
        """性齢のフォーマットを検証"""
        if not re.match(r'^(牡|牝|セ)[2-9]$', v):
            raise ValueError("性齢は「牡/牝/セ」と「2-9」の組み合わせである必要があります（例: 牡3）")
        return v

    @field_validator('騎手')
    def validate_jockey(cls, v):
        """騎手名が空でないことを確認"""
        if not v.strip():
            raise ValueError("騎手名は必須です")
        return v.strip()

    model_config = {
        "json_schema_extra": {
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
    }

class PredictionResponse(BaseModel):
    """予測結果のレスポンススキーマ
    
    モデルの予測結果と信頼度を含みます。
    """
    prediction: int = Field(..., description="予測結果（着順）")
    confidence: float = Field(..., ge=0.0, le=1.0, description="予測の信頼度（0.0〜1.0）")
    details: Optional[Dict[str, Any]] = Field(None, description="予測の詳細情報（オプション）")

    model_config = {
        "json_schema_extra": {
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
    }
