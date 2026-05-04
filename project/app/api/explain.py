"""
予測説明 (Explainability) APIルーター
POST /explain  ─ レースデータを受け取り、モデルが重視した特徴量と
                  各艇に対する寄与量をわかりやすく返す

説明手法:
  LightGBM の feature_importances_（gain ベース）を使い、
  各艇の特徴値と「レース内平均値からの偏差」を組み合わせて
  per-boat 寄与スコアを算出する。

  contribution[boat, feat] = importance_norm[feat]
                              × (x[boat, feat] - mean[feat])
                              / (std[feat] + ε)

  これにより「このレースの中でこの選手のこの特徴が際立っているか」を
  モデルの重要度で重み付けしたスコアが得られる。
"""
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import verify_api_key
from app.api.predict import RaceRequest
from app.model.features import FEATURE_COLUMNS, N_BOATS, build_features
from app.model.predict import get_model
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================================
# レスポンス スキーマ
# ============================================================

class FeatureImportanceItem(BaseModel):
    feature: str = Field(..., description="特徴量名")
    importance: float = Field(..., description="モデル全体での重要度（正規化済み、和=1）")
    rank: int = Field(..., description="重要度ランク（1=最重要）")


class BoatContribution(BaseModel):
    feature: str
    value: float = Field(..., description="この艇の特徴値")
    z_score: float = Field(..., description="レース内 z スコア（正=平均より高い）")
    contribution: float = Field(..., description="寄与スコア = importance × z_score")


class BoatExplanation(BaseModel):
    boat_number: int
    win_probability: float = Field(..., description="1着確率（/predict と同値）")
    top_factors: list[BoatContribution] = Field(
        ..., description="寄与スコア上位5特徴（正=有利・負=不利）"
    )
    summary: str = Field(..., description="日本語サマリー")


class ExplainResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    race_id: str | None = None
    model_version: str = Field(..., description="説明対象のモデル識別子")
    feature_importance: list[FeatureImportanceItem] = Field(
        ..., description="モデル全体の特徴量重要度ランキング"
    )
    boat_explanations: list[BoatExplanation] = Field(
        ..., description="各艇ごとの説明（1〜6号艇）"
    )


# ============================================================
# 特徴量ラベル（日本語）
# ============================================================

_FEAT_LABEL: dict[str, str] = {
    "win_rate":        "全体勝率",
    "motor_score":     "モータースコア",
    "course_win_rate": "コース別勝率",
    "start_timing":    "スタートタイミング",
    "weather_code":    "天候コード",
    "wind_speed":      "風速",
    "water_temp":      "水温",
    "boat_number":     "艇番",
    "racer_rank":      "選手ランク",
    "motor_2rate":     "モーター2連対率",
    "boat_2rate":      "ボート2連対率",
    "recent_3_avg":    "直近3走平均着順",
}


# ============================================================
# 説明ロジック
# ============================================================

def explain_race(race_data: dict[str, Any]) -> dict[str, Any]:
    """
    レースデータに対する予測説明を生成する

    Args:
        race_data: predict_race と同じ形式のレース情報辞書

    Returns:
        ExplainResponse 相当の辞書
    """
    model = get_model()
    feature_df = build_features(race_data)
    X = feature_df.to_numpy(dtype=float)            # (6, n_features) numpy for math ops

    # ---- 1. モデル全体の特徴量重要度（gain ベース、正規化） ----
    raw_importance = np.array(model.feature_importances_, dtype=float)
    total = raw_importance.sum()
    if total == 0:
        total = 1.0
    norm_importance = raw_importance / total        # shape: (n_features,)

    feat_importance_list = sorted(
        [
            {
                "feature": feat,
                "importance": float(imp),
                "rank": 0,  # 後で付与
            }
            for feat, imp in zip(FEATURE_COLUMNS, norm_importance, strict=True)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )
    for rank_i, item in enumerate(feat_importance_list, start=1):
        item["rank"] = rank_i

    # ---- 2. レース内の特徴量 z スコア ----
    mean_vals = X.mean(axis=0)                      # (n_features,)
    std_vals  = X.std(axis=0) + 1e-8               # 0除算を防ぐ

    # contribution[boat, feat] = importance × z_score
    z_scores   = (X - mean_vals) / std_vals         # (6, n_features)
    contribs   = norm_importance * z_scores         # (6, n_features) broadcast

    # ---- 3. 1着確率（predict と同じロジック） ----
    proba_matrix = model.predict_proba(feature_df)
    win_proba = proba_matrix[:, 0]
    win_proba = win_proba / win_proba.sum()

    # ---- 4. 艇ごとの説明 ----
    boat_explanations = []
    for boat_idx in range(N_BOATS):
        boat_contribs = [
            {
                "feature": feat,
                "value":        float(X[boat_idx, fi]),
                "z_score":      float(z_scores[boat_idx, fi]),
                "contribution": float(contribs[boat_idx, fi]),
            }
            for fi, feat in enumerate(FEATURE_COLUMNS)
        ]
        # |寄与スコア| の大きい順に並べ、上位5件を返す
        boat_contribs.sort(key=lambda c: abs(c["contribution"]), reverse=True)
        top5 = boat_contribs[:5]

        # 日本語サマリーを生成
        summary = _make_summary(boat_idx + 1, top5, float(win_proba[boat_idx]))

        boat_explanations.append({
            "boat_number":    boat_idx + 1,
            "win_probability": round(float(win_proba[boat_idx]), 4),
            "top_factors":    top5,
            "summary":        summary,
        })

    # モデルバージョン情報
    model_version = getattr(model, "_version_name", "unknown")

    return {
        "model_version":     model_version,
        "feature_importance": feat_importance_list,
        "boat_explanations": boat_explanations,
    }


def _make_summary(boat_num: int, top_factors: list[dict], win_prob: float) -> str:
    """人間が読めるサマリー文字列を生成する"""
    if not top_factors:
        return f"{boat_num}号艇: データ不足"

    top = top_factors[0]
    label = _FEAT_LABEL.get(top["feature"], top["feature"])
    direction = "高い" if top["contribution"] > 0 else "低い"
    prob_pct = f"{win_prob:.1%}"

    return (
        f"{boat_num}号艇 (1着確率 {prob_pct}): "
        f"主要因は「{label}」が{direction}こと"
    )


# ============================================================
# エンドポイント
# ============================================================

@router.post(
    "/explain",
    response_model=ExplainResponse,
    summary="予測説明（特徴量寄与分析）",
    description=(
        "レース情報を受け取り、モデルの予測根拠を特徴量重要度と\n"
        "艇ごとの寄与スコアとして返す。\n\n"
        "- `feature_importance`: モデル全体での特徴量重要度ランキング\n"
        "- `boat_explanations`: 各艇のトップ寄与特徴量と日本語サマリー\n\n"
        "認証: `X-API-Key` ヘッダーに有効なキーを設定してください。"
    ),
)
async def explain_endpoint(
    request: RaceRequest,
    _api_key: str = Depends(verify_api_key),
) -> ExplainResponse:
    """レース予測の説明を返すエンドポイント"""
    try:
        result = explain_race(request.race)
        return ExplainResponse(race_id=request.race_id, **result)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"モデルが未学習です。先にトレーニングを実行してください。詳細: {e}",
        ) from e
    except Exception as e:
        logger.exception(f"説明生成中にエラー: {e}")
        raise HTTPException(status_code=500, detail="内部サーバーエラー") from e
