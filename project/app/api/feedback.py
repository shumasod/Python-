"""
レース結果フィードバック API
予測後に実際のレース結果を記録し、
A/B テスト・シャドウモードの精度追跡に使用する

エンドポイント:
  POST /api/v1/result/{race_id}  : レース結果を記録
  GET  /api/v1/result/{race_id}  : 記録済み結果を取得
  GET  /api/v1/result/summary    : 直近の的中率サマリー
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import verify_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# ログ保存先（テストで monkeypatch 可能なモジュール変数）
RESULT_LOG_DIR     = Path("data/race_results")
PREDICTION_LOG_DIR = Path("data/prediction_logs")
RESULT_LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# スキーマ
# ============================================================

class RaceResultRequest(BaseModel):
    """POST /result/{race_id} のリクエストボディ"""
    true_winner: int = Field(..., ge=1, le=6, description="実際の1着艇番（1〜6）")
    second_place: Optional[int] = Field(None, ge=1, le=6, description="2着艇番")
    third_place: Optional[int] = Field(None, ge=1, le=6, description="3着艇番")
    official_odds: Optional[Dict[str, float]] = Field(
        None, description="公式オッズ {'trifecta': 25.0, 'win': 3.5}"
    )
    note: Optional[str] = Field(None, description="備考")


class RaceResultResponse(BaseModel):
    race_id: str
    true_winner: int
    second_place: Optional[int] = None
    third_place: Optional[int] = None
    recorded_at: str
    # 予測との比較（predict が記録済みの場合のみ）
    predicted_winner: Optional[int] = None
    is_correct: Optional[bool] = None
    prediction_rank: Optional[int] = None  # 正解艇の予測順位（1〜6）


class ResultSummary(BaseModel):
    n_results: int
    hit_rate: float           # 1着的中率
    top3_hit_rate: float      # 予測3位以内に正解が入った率
    avg_prediction_rank: float


# ============================================================
# ヘルパー
# ============================================================

def _result_path(race_id: str) -> Path:
    return RESULT_LOG_DIR / f"{race_id}.json"


def _load_prediction_log(race_id: str) -> Optional[Dict]:
    """
    予測ログを読み込む。

    検索順:
    1. data/prediction_logs/{race_id}.json  (run_daily_pipeline が保存)
    2. data/ab_test_logs/*.jsonl            (ab_test ルーターが保存)
    """
    # 1. 予測ログディレクトリ（run_daily_pipeline.py の出力）
    pred_log_path = PREDICTION_LOG_DIR / f"{race_id}.json"
    if pred_log_path.exists():
        try:
            with open(pred_log_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # 2. A/B テストログ（フォールバック）
    ab_log_dir = Path("data/ab_test_logs")
    for log_file in ab_log_dir.glob("*.jsonl"):
        try:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("race_id") == race_id:
                            return entry
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return None


def _compare_prediction(
    result: RaceResultRequest,
    race_id: str,
) -> Dict[str, Any]:
    """予測記録と実結果を比較する"""
    comparison: Dict[str, Any] = {
        "predicted_winner": None,
        "is_correct": None,
        "prediction_rank": None,
    }

    pred_log = _load_prediction_log(race_id)
    if pred_log is None:
        return comparison

    # run_daily_pipeline → "win_probabilities",  ab_test → "proba"
    proba = pred_log.get("win_probabilities") or pred_log.get("proba", [])
    if not proba:
        return comparison

    import numpy as np
    proba_arr = np.array(proba)
    ranks = np.argsort(proba_arr)[::-1]  # 確率降順のインデックス

    # 予測1位（0始まり → 1始まり）
    predicted_winner = int(ranks[0]) + 1
    comparison["predicted_winner"] = predicted_winner
    comparison["is_correct"] = (predicted_winner == result.true_winner)

    # 正解艇の予測順位
    winner_idx = result.true_winner - 1
    if 0 <= winner_idx < len(proba_arr):
        rank_pos = int(np.where(ranks == winner_idx)[0][0]) + 1
        comparison["prediction_rank"] = rank_pos

    return comparison


# ============================================================
# エンドポイント
# ============================================================

@router.post(
    "/result/{race_id}",
    response_model=RaceResultResponse,
    summary="レース結果を記録",
    description="実際の1着艇番をシステムに登録し、予測精度の追跡に使用します。",
)
async def record_result(
    race_id: str,
    body: RaceResultRequest,
    _api_key: str = Depends(verify_api_key),
) -> RaceResultResponse:
    """レース結果を記録する"""
    path = _result_path(race_id)
    if path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"レースID {race_id} の結果は既に記録されています",
        )

    recorded_at = datetime.now(timezone.utc).isoformat()
    comparison = _compare_prediction(body, race_id)

    record = {
        "race_id": race_id,
        "true_winner": body.true_winner,
        "second_place": body.second_place,
        "third_place": body.third_place,
        "official_odds": body.official_odds,
        "note": body.note,
        "recorded_at": recorded_at,
        **comparison,
    }

    # ---- JSON 保存 ----
    RESULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # ---- A/B テストに結果を通知（ルーターが存在すれば） ----
    try:
        from app.model.ab_test import _global_router  # type: ignore[attr-defined]
        _global_router.record_result(race_id=race_id, true_winner=body.true_winner)
    except (ImportError, AttributeError):
        pass

    logger.info(
        f"結果記録: race_id={race_id} winner={body.true_winner} "
        f"correct={comparison['is_correct']}"
    )

    return RaceResultResponse(
        race_id=race_id,
        true_winner=body.true_winner,
        second_place=body.second_place,
        third_place=body.third_place,
        recorded_at=recorded_at,
        **comparison,
    )


@router.get(
    "/result/summary",
    response_model=ResultSummary,
    summary="予測精度サマリー",
    description="記録済み全レースの的中率・平均予測順位を返します。",
)
async def get_result_summary(
    _api_key: str = Depends(verify_api_key),
) -> ResultSummary:
    """全レース結果の集計サマリーを返す"""
    files = list(RESULT_LOG_DIR.glob("*.json"))

    if not files:
        return ResultSummary(
            n_results=0,
            hit_rate=0.0,
            top3_hit_rate=0.0,
            avg_prediction_rank=0.0,
        )

    n_total = 0
    n_correct = 0
    n_top3 = 0
    rank_sum = 0.0
    n_with_rank = 0

    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        n_total += 1
        if rec.get("is_correct"):
            n_correct += 1

        pred_rank = rec.get("prediction_rank")
        if pred_rank is not None:
            rank_sum += pred_rank
            n_with_rank += 1
            if pred_rank <= 3:
                n_top3 += 1

    return ResultSummary(
        n_results=n_total,
        hit_rate=round(n_correct / n_total, 4) if n_total else 0.0,
        top3_hit_rate=round(n_top3 / n_with_rank, 4) if n_with_rank else 0.0,
        avg_prediction_rank=round(rank_sum / n_with_rank, 2) if n_with_rank else 0.0,
    )


@router.get(
    "/result/{race_id}",
    response_model=RaceResultResponse,
    summary="記録済みレース結果を取得",
)
async def get_result(
    race_id: str,
    _api_key: str = Depends(verify_api_key),
) -> RaceResultResponse:
    """記録済みのレース結果を返す"""
    path = _result_path(race_id)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"レースID {race_id} の結果が見つかりません",
        )

    with open(path, encoding="utf-8") as f:
        record = json.load(f)

    return RaceResultResponse(**record)
