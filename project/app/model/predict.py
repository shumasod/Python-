"""
推論モジュール
学習済みLightGBMモデルを使った競艇1着確率の予測・三連単生成を担当する
"""
from itertools import permutations
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from app.model.features import N_BOATS, build_features
from app.model.train import load_model
from app.utils.logger import get_logger

logger = get_logger(__name__)

# シングルトンとしてモデルをキャッシュ（起動時に1回だけロード）
_cached_model = None


def get_model():
    """モデルのシングルトンを取得する（初回のみファイル読み込み）"""
    global _cached_model
    if _cached_model is None:
        _cached_model = load_model()
    return _cached_model


def predict_race(race_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    レースデータから各艇の勝利確率・三連単推奨を返す

    Args:
        race_data: APIリクエスト由来のレース情報辞書
            - boats: 6艇分の選手・機材情報リスト
            - weather: 天候情報辞書
            - race_id: レースID（任意）

    Returns:
        予測結果辞書:
            - win_probabilities: 各艇の1着確率リスト（順番: 1号艇〜6号艇）
            - trifecta: 三連単上位10点 [{"combination": [1,2,3], "probability": 0.05}, ...]
            - recommendations: 買い目推奨リスト（期待値 > 1 の組み合わせ）
    """
    logger.info(f"予測開始: race_id={race_data.get('race_id', 'unknown')}")

    # 特徴量行列を構築（shape: 6 × n_features）
    feature_df = build_features(race_data)
    model = get_model()

    # 各艇の1着確率を取得（shape: 6 × 6、各行が1艇の予測分布）
    proba_matrix = model.predict_proba(feature_df)

    # 1着確率: 各艇について「クラス0（1着）」の確率を取り出す
    # ※ マルチクラスモデルなので predict_proba は (n_boats, n_classes) を返す
    win_proba = proba_matrix[:, 0].tolist()  # クラス0 = 1着

    # 正規化（合計が1になるよう調整）
    win_proba_arr = np.array(win_proba)
    win_proba_arr = win_proba_arr / win_proba_arr.sum()
    win_proba = win_proba_arr.tolist()

    # 三連単の確率計算（上位10点を返す）
    trifecta = _calc_trifecta(win_proba_arr, top_n=10)

    # 買い目推奨（期待値 > 1.0、かつ上位確率の組み合わせ）
    recommendations = _build_recommendations(trifecta, race_data)

    result = {
        "win_probabilities": [round(p, 4) for p in win_proba],
        "trifecta": trifecta,
        "recommendations": recommendations,
    }

    logger.info(
        f"予測完了: 1着最有力 = {int(np.argmax(win_proba_arr)) + 1}号艇 "
        f"(確率: {max(win_proba):.2%})"
    )
    return result


def _calc_trifecta(
    win_proba: np.ndarray, top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    三連単（1〜3着の順序付き組み合わせ）の確率を計算する

    Args:
        win_proba: 各艇の1着確率配列（長さ6）
        top_n: 返す組み合わせ数

    Returns:
        確率上位 top_n 点のリスト
        [{"combination": [1, 2, 3], "probability": 0.05, "rank": 1}, ...]
    """
    results = []

    for perm in permutations(range(N_BOATS), 3):
        first, second, third = perm
        # 独立性を仮定した簡易計算
        # P(1着=first) × P(2着=second | 1着=first) × P(3着=third | 1,2着確定)
        p1 = win_proba[first]
        # 1着が決まった後の残り5艇の条件付き確率（正規化）
        remaining_after_1 = np.delete(win_proba, first)
        remaining_after_1 = remaining_after_1 / remaining_after_1.sum()
        second_idx = second if second < first else second - 1
        p2 = remaining_after_1[second_idx]
        # 2着が決まった後の残り4艇
        remaining_after_2 = np.delete(remaining_after_1, second_idx)
        remaining_after_2 = remaining_after_2 / remaining_after_2.sum()
        third_idx_candidates = [i for i in range(N_BOATS) if i != first and i != second]
        third_pos = third_idx_candidates.index(third)
        p3 = remaining_after_2[third_pos]

        prob = float(p1 * p2 * p3)
        results.append({
            "combination": [first + 1, second + 1, third + 1],  # 1始まり艇番に変換
            "probability": round(prob, 6),
        })

    # 確率降順でソートして上位 top_n 件を返す
    results.sort(key=lambda x: x["probability"], reverse=True)
    for i, item in enumerate(results[:top_n]):
        item["rank"] = i + 1

    return results[:top_n]


def _build_recommendations(
    trifecta: List[Dict],
    race_data: Dict[str, Any],
    ev_threshold: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    期待値を考慮した買い目推奨を生成する

    Args:
        trifecta: _calc_trifecta の出力
        race_data: レース情報（odds情報があれば活用）
        ev_threshold: 推奨する最低期待値（デフォルト1.0 = 元返し以上）

    Returns:
        推奨買い目リスト
    """
    odds_map: Dict[str, float] = race_data.get("odds", {})
    recommendations = []

    for item in trifecta[:5]:  # 上位5点を対象に評価
        combo_key = "-".join(map(str, item["combination"]))
        odds = odds_map.get(combo_key, 100.0)  # オッズ未提供時は仮値100倍

        # 期待値 = 確率 × オッズ
        ev = item["probability"] * odds

        if ev >= ev_threshold:
            recommendations.append({
                "combination": item["combination"],
                "probability": item["probability"],
                "odds": odds,
                "expected_value": round(ev, 3),
                "kelly_fraction": round(_kelly_criterion(item["probability"], odds), 4),
                "note": f"期待値 {ev:.2f} | ケリー {_kelly_criterion(item['probability'], odds):.1%}",
            })

    if not recommendations:
        # 閾値を下げてトップ1点だけ返す
        top = trifecta[0]
        odds = odds_map.get("-".join(map(str, top["combination"])), 100.0)
        recommendations.append({
            "combination": top["combination"],
            "probability": top["probability"],
            "odds": odds,
            "expected_value": round(top["probability"] * odds, 3),
            "kelly_fraction": round(_kelly_criterion(top["probability"], odds), 4),
            "note": "期待値閾値未達のため確率最上位点のみ推奨",
        })

    return recommendations


def _kelly_criterion(probability: float, odds: float) -> float:
    """
    ケリー基準による最適ベット比率を計算する

    Args:
        probability: 勝利確率（0〜1）
        odds: 配当倍率

    Returns:
        総資金に対するベット比率（負の場合は見送り）
    """
    # ケリー公式: f* = (p*(b+1) - 1) / b  (b = 純利益倍率 = odds - 1)
    b = odds - 1
    if b <= 0:
        return 0.0
    kelly = (probability * (b + 1) - 1) / b
    return max(0.0, kelly)
