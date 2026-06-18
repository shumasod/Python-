"""
予測スコアリング API
日次予測ログと実際のレース結果を突き合わせて精度を集計する

エンドポイント:
  GET /api/v1/scoring/daily          : 日付ごとの的中率
  GET /api/v1/scoring/by-venue       : 場コードごとの的中率
  GET /api/v1/scoring/race/{race_id} : 1レース分の予測 vs 結果
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import verify_api_key
from app.config import PREDICTION_LOG_DIR, RESULT_LOG_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================================
# スキーマ
# ============================================================

class RaceScore(BaseModel):
    race_id:           str
    jyo_code:          str | None = None
    race_date:         str | None = None
    race_no:           int | None = None
    predicted_winner:  int | None = None
    true_winner:       int | None = None
    is_correct:        bool | None = None
    prediction_rank:   int | None = None
    has_prediction:    bool = False
    has_result:        bool = False


class DailyScore(BaseModel):
    date:       str
    n_races:    int
    n_scored:   int   # 予測と結果の両方がある件数
    n_correct:  int
    hit_rate:   float
    avg_rank:   float


class VenueScore(BaseModel):
    jyo_code:   str
    n_races:    int
    n_scored:   int
    n_correct:  int
    hit_rate:   float
    avg_rank:   float


class ScoringOverview(BaseModel):
    n_predictions:  int
    n_results:      int
    n_scored:       int
    n_correct:      int
    hit_rate:       float
    avg_rank:       float
    by_date:        list[DailyScore]
    by_venue:       list[VenueScore]


# ============================================================
# ヘルパー
# ============================================================

def _load_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _rank_proba(proba: list, true_winner: int) -> dict[str, Any]:
    """確率ベクトルと正解艇番から予測順位情報を返す。"""
    import numpy as np
    arr   = np.array(proba)
    order = np.argsort(arr)[::-1]
    predicted_winner = int(order[0]) + 1
    is_correct       = (predicted_winner == true_winner)
    winner_idx       = true_winner - 1
    pred_rank: int | None = None
    if 0 <= winner_idx < len(arr):
        pred_rank = int(np.where(order == winner_idx)[0][0]) + 1
    return {"predicted_winner": predicted_winner, "is_correct": is_correct, "prediction_rank": pred_rank}


def _score_pair(pred: dict, result: dict) -> RaceScore:
    """予測ログと結果ログを突き合わせて RaceScore を返す。"""
    race_id = pred.get("race_id") or result.get("race_id", "unknown")

    proba       = pred.get("win_probabilities") or pred.get("proba") or []
    true_winner = result.get("true_winner")

    predicted_winner: int | None = None
    is_correct:       bool | None = None
    pred_rank:        int | None  = None

    if proba and true_winner is not None:
        ranked = _rank_proba(proba, true_winner)
        predicted_winner = ranked["predicted_winner"]
        is_correct       = ranked["is_correct"]
        pred_rank        = ranked["prediction_rank"]

    return RaceScore(
        race_id          = race_id,
        jyo_code         = pred.get("jyo_code") or result.get("jyo_code"),
        race_date        = pred.get("race_date") or result.get("race_date"),
        race_no          = pred.get("race_no")   or result.get("race_no"),
        predicted_winner = predicted_winner,
        true_winner      = true_winner,
        is_correct       = is_correct,
        prediction_rank  = pred_rank,
        has_prediction   = True,
        has_result       = True,
    )


def _collect_scores() -> list[RaceScore]:
    """全予測ログ × 全結果ログを突き合わせてスコアリストを返す。"""
    preds   = {p.stem: _load_json(p) for p in PREDICTION_LOG_DIR.glob("*.json")} \
              if PREDICTION_LOG_DIR.exists() else {}
    results = {r.stem: _load_json(r) for r in RESULT_LOG_DIR.glob("*.json")} \
              if RESULT_LOG_DIR.exists() else {}

    scores: list[RaceScore] = []
    all_ids = set(preds) | set(results)

    for race_id in sorted(all_ids):
        pred   = preds.get(race_id)
        result = results.get(race_id)

        if pred and result:
            scores.append(_score_pair(pred, result))
        elif pred:
            scores.append(RaceScore(
                race_id    = race_id,
                jyo_code   = pred.get("jyo_code"),
                race_date  = pred.get("race_date"),
                race_no    = pred.get("race_no"),
                has_prediction = True,
            ))
        elif result:
            scores.append(RaceScore(
                race_id     = race_id,
                true_winner = result.get("true_winner"),
                has_result  = True,
            ))

    return scores


def _agg(scores: list[RaceScore]) -> dict[str, Any]:
    scored   = [s for s in scores if s.has_prediction and s.has_result and s.is_correct is not None]
    n_correct = sum(1 for s in scored if s.is_correct)
    ranks     = [s.prediction_rank for s in scored if s.prediction_rank is not None]
    return {
        "n_scored":  len(scored),
        "n_correct": n_correct,
        "hit_rate":  round(n_correct / len(scored), 4) if scored else 0.0,
        "avg_rank":  round(sum(ranks) / len(ranks), 2) if ranks else 0.0,
    }


# ============================================================
# エンドポイント
# ============================================================

@router.get(
    "/scoring",
    response_model=ScoringOverview,
    summary="予測スコアリング概要",
    description="保存済み予測ログとレース結果を突き合わせ、的中率・平均予測順位を集計します。",
)
async def scoring_overview(
    _api_key: str = Depends(verify_api_key),
) -> ScoringOverview:
    """全期間の予測精度概要を返す"""
    scores = _collect_scores()
    agg    = _agg(scores)

    # 日別集計
    by_date_map: dict[str, list[RaceScore]] = defaultdict(list)
    for s in scores:
        key = (s.race_date or "unknown")
        by_date_map[key].append(s)

    by_date = []
    for dt in sorted(by_date_map):
        g   = by_date_map[dt]
        a   = _agg(g)
        by_date.append(DailyScore(
            date      = dt,
            n_races   = len(g),
            **a,
        ))

    # 場別集計
    by_venue_map: dict[str, list[RaceScore]] = defaultdict(list)
    for s in scores:
        key = (s.jyo_code or "unknown")
        by_venue_map[key].append(s)

    by_venue = []
    for jyo in sorted(by_venue_map):
        g = by_venue_map[jyo]
        a = _agg(g)
        by_venue.append(VenueScore(
            jyo_code = jyo,
            n_races  = len(g),
            **a,
        ))

    n_preds   = sum(1 for p in PREDICTION_LOG_DIR.glob("*.json")) \
                if PREDICTION_LOG_DIR.exists() else 0
    n_results = sum(1 for r in RESULT_LOG_DIR.glob("*.json")) \
                if RESULT_LOG_DIR.exists() else 0

    return ScoringOverview(
        n_predictions = n_preds,
        n_results     = n_results,
        by_date       = by_date,
        by_venue      = by_venue,
        **agg,
    )


@router.get(
    "/scoring/race/{race_id}",
    response_model=RaceScore,
    summary="1レースのスコア照合",
)
async def race_score(
    race_id: str,
    _api_key: str = Depends(verify_api_key),
) -> RaceScore:
    """指定レースの予測と結果を突き合わせて返す"""
    pred_path   = PREDICTION_LOG_DIR / f"{race_id}.json"
    result_path = RESULT_LOG_DIR     / f"{race_id}.json"

    pred   = _load_json(pred_path)   if pred_path.exists()   else None
    result = _load_json(result_path) if result_path.exists() else None

    if pred is None and result is None:
        raise HTTPException(
            status_code=404,
            detail=f"レースID {race_id} の予測も結果も見つかりません",
        )

    if pred and result:
        return _score_pair(pred, result)

    return RaceScore(
        race_id        = race_id,
        true_winner    = result.get("true_winner") if result else None,
        has_prediction = pred is not None,
        has_result     = result is not None,
    )
