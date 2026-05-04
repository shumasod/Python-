"""
予測APIルーター
POST /predict エンドポイントを定義する

機能:
  - Redisキャッシュ（CACHE_ENABLED=true 時）
  - API Key 認証（API_AUTH_ENABLED=true 時）
  - レートリミット（RATE_LIMIT_ENABLED=true 時）
  - DBへの予測ログ保存（BackgroundTask）
  - Prometheusメトリクス記録
"""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.api.auth import verify_api_key
from app.model.features import N_BOATS
from app.model.predict import predict_race
from app.utils.logger import get_logger

# オプション依存モジュール
try:
    from app.db import log_prediction
    _DB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DB_AVAILABLE = False

try:
    from app.cache import get_cached_prediction, set_cached_prediction
    _CACHE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CACHE_AVAILABLE = False

try:
    from app.api.metrics import record_predict_request
    _METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _METRICS_AVAILABLE = False

logger = get_logger(__name__)
router = APIRouter()


# ============================================================
# リクエスト / レスポンス スキーマ
# ============================================================

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

    @field_validator("race")
    @classmethod
    def validate_race(cls, v: Dict) -> Dict:
        boats = v.get("boats", [])
        if len(boats) != N_BOATS:
            raise ValueError(f"boats には{N_BOATS}艇分のデータが必要です（受け取り: {len(boats)}艇）")
        return v


class TrifectaItem(BaseModel):
    combination: List[int] = Field(..., description="艇番の順序 [1着, 2着, 3着]")
    probability: float
    rank: int


class RecommendationItem(BaseModel):
    combination: List[int]
    probability: float
    odds: float
    expected_value: float
    kelly_fraction: float
    note: str


class PredictResponse(BaseModel):
    race_id: Optional[str] = None
    win_probabilities: List[float] = Field(..., description="各艇の1着確率（1〜6号艇）")
    trifecta: List[TrifectaItem] = Field(..., description="三連単上位10点")
    recommendations: List[RecommendationItem] = Field(..., description="推奨買い目")
    cached: bool = Field(False, description="キャッシュから返した結果か")


# ============================================================
# エンドポイント
# ============================================================

@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="競艇レース予測",
    description=(
        "競艇レース情報を受け取り、各艇の1着確率・三連単推奨を返す。\n\n"
        "認証: `X-API-Key` ヘッダーに有効なキーを設定してください。"
    ),
)
async def predict_endpoint(
    request: RaceRequest,
    background_tasks: BackgroundTasks,
    _api_key: str = Depends(verify_api_key),
) -> PredictResponse:
    """
    レース予測メインエンドポイント

    処理フロー:
    1. API Key 認証
    2. Redis キャッシュ確認（ヒット時はそのまま返す）
    3. LightGBM 推論
    4. キャッシュ保存 + DB ログ記録（BackgroundTask）
    """
    start = time.monotonic()
    race_id = request.race_id

    try:
        logger.info(f"予測リクエスト受信: race_id={race_id}")

        # ---- キャッシュ確認 ----
        if _CACHE_AVAILABLE:
            cached = await get_cached_prediction(request.race, race_id)
            if cached is not None:
                latency = time.monotonic() - start
                if _METRICS_AVAILABLE:
                    record_predict_request("cache_hit", latency)
                return PredictResponse(race_id=race_id, cached=True, **cached)

        # ---- 推論 ----
        result = predict_race(request.race)
        latency = time.monotonic() - start

        if _METRICS_AVAILABLE:
            record_predict_request("success", latency)

        # ---- バックグラウンド処理（キャッシュ保存・DBログ） ----
        if _CACHE_AVAILABLE:
            background_tasks.add_task(
                set_cached_prediction, request.race, result, race_id
            )
        if _DB_AVAILABLE:
            background_tasks.add_task(
                log_prediction,
                race_id=race_id,
                request_body=request.race,
                response_body=result,
                latency_ms=int(latency * 1000),
            )

        return PredictResponse(race_id=race_id, cached=False, **result)

    except FileNotFoundError as e:
        latency = time.monotonic() - start
        if _METRICS_AVAILABLE:
            record_predict_request("model_not_found", latency)
        logger.error(f"モデルファイルエラー: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"モデルが未学習です。先にトレーニングを実行してください。詳細: {e}",
        )
    except ValueError as e:
        logger.error(f"入力値エラー: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        latency = time.monotonic() - start
        if _METRICS_AVAILABLE:
            record_predict_request("error", latency)
        logger.exception(f"予測処理中に予期しないエラー: {e}")
        raise HTTPException(status_code=500, detail="内部サーバーエラー")


@router.get("/stats", summary="予測統計情報")
async def stats_endpoint(
    days: int = 7,
    _api_key: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """過去N日間の予測API利用統計（DB接続が必要）"""
    stats: Dict[str, Any] = {}

    if _DB_AVAILABLE:
        from app.db import get_prediction_stats
        stats["db"] = await get_prediction_stats(days=days)
    else:
        stats["db"] = {"message": "asyncpg 未インストール"}

    if _CACHE_AVAILABLE:
        from app.cache import get_cache_stats
        stats["cache"] = await get_cache_stats()

    return stats


@router.delete("/cache/{race_id}", summary="キャッシュ無効化")
async def invalidate_cache_endpoint(
    race_id: str,
    _api_key: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """指定レースIDのキャッシュを削除する"""
    if not _CACHE_AVAILABLE:
        return {"message": "キャッシュが無効です"}

    from app.cache import invalidate_cache
    deleted = await invalidate_cache(race_id)
    return {"race_id": race_id, "deleted": deleted}


# ============================================================
# バッチ予測エンドポイント
# ============================================================

class BatchRaceRequest(BaseModel):
    """POST /predict/batch のリクエストボディ"""
    races: List[RaceRequest] = Field(..., min_length=1, max_length=20, description="レースリスト（最大20件）")


class BatchPredictResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[Dict[str, Any]]


@router.post(
    "/predict/batch",
    response_model=BatchPredictResponse,
    summary="バッチ予測（複数レース一括）",
    description="複数レースをまとめて予測します（最大20件）。個別のエラーは results 内に記録されます。",
)
async def predict_batch_endpoint(
    request: BatchRaceRequest,
    background_tasks: BackgroundTasks,
    _api_key: str = Depends(verify_api_key),
) -> BatchPredictResponse:
    """複数レースを一括で予測する"""
    results = []
    succeeded = 0
    failed = 0

    for race_req in request.races:
        race_id = race_req.race_id
        try:
            # キャッシュ確認
            if _CACHE_AVAILABLE:
                cached = await get_cached_prediction(race_req.race, race_id)
                if cached is not None:
                    results.append({
                        "race_id": race_id,
                        "status": "success",
                        "cached": True,
                        **cached,
                    })
                    succeeded += 1
                    continue

            # 推論
            result = predict_race(race_req.race)

            if _CACHE_AVAILABLE:
                background_tasks.add_task(
                    set_cached_prediction, race_req.race, result, race_id
                )

            results.append({
                "race_id": race_id,
                "status": "success",
                "cached": False,
                **result,
            })
            succeeded += 1

        except FileNotFoundError:
            results.append({
                "race_id": race_id,
                "status": "error",
                "error": "モデルが未学習です",
            })
            failed += 1
        except Exception as e:
            logger.error(f"バッチ予測エラー race_id={race_id}: {e}")
            results.append({
                "race_id": race_id,
                "status": "error",
                "error": str(e),
            })
            failed += 1

    logger.info(f"バッチ予測完了: {succeeded}/{len(request.races)} 成功")
    return BatchPredictResponse(
        total=len(request.races),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
