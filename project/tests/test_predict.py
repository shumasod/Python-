"""
推論モジュール・シミュレーターのユニットテスト
モデルファイルなしでもテストできるようモックを使用
"""
import pytest
import numpy as np
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.predict import (
    _calc_trifecta,
    _kelly_criterion,
    _build_recommendations,
)
from simulator import (
    expected_value,
    kelly_criterion,
    decide_bet,
    generate_sample_races,
    run_simulation,
)


# ============================================================
# predict.py テスト
# ============================================================

class TestCalcTrifecta:
    def test_returns_top_n(self):
        """top_n 件の三連単を返すことを確認"""
        proba = np.array([0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        result = _calc_trifecta(proba, top_n=10)
        assert len(result) == 10

    def test_sorted_by_probability(self):
        """確率降順でソートされていることを確認"""
        proba = np.array([0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        result = _calc_trifecta(proba, top_n=10)
        probs = [r["probability"] for r in result]
        assert probs == sorted(probs, reverse=True)

    def test_combination_is_3_boats(self):
        """各組み合わせが3艇であることを確認"""
        proba = np.array([0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        result = _calc_trifecta(proba, top_n=5)
        for item in result:
            assert len(item["combination"]) == 3

    def test_boat_numbers_1_to_6(self):
        """艇番が 1〜6 の範囲であることを確認"""
        proba = np.array([0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        result = _calc_trifecta(proba, top_n=10)
        for item in result:
            for boat in item["combination"]:
                assert 1 <= boat <= 6

    def test_no_duplicate_boats_in_combination(self):
        """三連単の組み合わせに重複艇番がないことを確認"""
        proba = np.array([0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        result = _calc_trifecta(proba, top_n=10)
        for item in result:
            assert len(set(item["combination"])) == 3

    def test_rank_field(self):
        """rank フィールドが 1 始まりで連番であることを確認"""
        proba = np.array([0.35, 0.25, 0.15, 0.12, 0.08, 0.05])
        result = _calc_trifecta(proba, top_n=5)
        for i, item in enumerate(result):
            assert item["rank"] == i + 1


class TestKellyCriterion:
    def test_positive_ev(self):
        """期待値>1の場合、正のケリー比率を返すことを確認"""
        # p=0.5, odds=3.0 → EV=1.5
        k = _kelly_criterion(0.5, 3.0)
        assert k > 0

    def test_negative_ev(self):
        """期待値<1（負の期待値）の場合、0を返すことを確認"""
        # p=0.1, odds=2.0 → EV=0.2
        k = _kelly_criterion(0.1, 2.0)
        assert k == 0.0

    def test_zero_odds(self):
        """オッズ0以下の場合、0を返すことを確認"""
        assert _kelly_criterion(0.5, 0.0) == 0.0
        assert _kelly_criterion(0.5, -1.0) == 0.0


# ============================================================
# simulator.py テスト
# ============================================================

class TestSimulatorFunctions:
    def test_expected_value(self):
        """期待値の計算が正確であることを確認"""
        assert expected_value(0.5, 3.0) == pytest.approx(1.5)
        assert expected_value(0.1, 10.0) == pytest.approx(1.0)

    def test_kelly_positive(self):
        """正の期待値でケリー比率>0 を確認"""
        k = kelly_criterion(0.5, 3.0)
        assert k > 0

    def test_kelly_zero_probability(self):
        assert kelly_criterion(0.0, 5.0) == 0.0

    def test_decide_bet_skip_low_ev(self):
        """期待値が閾値を下回ったら見送ること"""
        # 全艇の期待値が 1.0 未満になるようオッズを低く設定
        proba = [1/6] * 6
        odds = [1.5] * 6  # EV = 1/6 * 1.5 ≈ 0.25
        boat, amount = decide_bet(proba, odds, capital=100_000, ev_threshold=1.0)
        assert boat is None
        assert amount == 0.0

    def test_decide_bet_selects_best(self):
        """最高期待値の艇を選択することを確認"""
        proba = [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
        odds = [4.0, 2.0, 2.0, 2.0, 2.0, 2.0]  # 1号艇 EV=2.0 が最高
        boat, amount = decide_bet(proba, odds, capital=100_000)
        assert boat == 1  # 1号艇

    def test_decide_bet_max_ratio(self):
        """最大ベット比率を超えないことを確認"""
        proba = [0.9, 0.02, 0.02, 0.02, 0.02, 0.02]
        odds = [10.0] * 6
        capital = 100_000
        _, amount = decide_bet(
            proba, odds, capital=capital,
            max_bet_ratio=0.1,
        )
        assert amount <= capital * 0.1 + 100  # 100円の丸め誤差を許容


class TestRunSimulation:
    def test_stats_consistency(self):
        """統計値の整合性チェック"""
        races = generate_sample_races(n_races=50)
        results, stats = run_simulation(races, initial_capital=100_000)

        # n_bet <= n_races
        assert stats.n_bet <= stats.n_races
        # n_win <= n_bet
        assert stats.n_win <= stats.n_bet
        # 資金履歴の長さ = レース数 + 1（初期値含む）
        assert len(stats.capital_history) == stats.n_races + 1

    def test_roi_calculation(self):
        """回収率の計算が正しいことを確認"""
        races = generate_sample_races(n_races=100)
        _, stats = run_simulation(races, initial_capital=100_000)

        if stats.total_bet > 0:
            expected_roi = stats.total_payout / stats.total_bet
            assert stats.roi == pytest.approx(expected_roi, rel=1e-6)

    def test_capital_non_negative(self):
        """資金がマイナスにならないことを確認"""
        races = generate_sample_races(n_races=100)
        _, stats = run_simulation(races, initial_capital=10_000)
        assert all(c >= 0 for c in stats.capital_history)

    def test_generate_sample_races(self):
        """サンプルデータの構造チェック"""
        races = generate_sample_races(n_races=10)
        assert len(races) == 10
        for race in races:
            assert len(race["predicted_proba"]) == 6
            assert len(race["odds"]) == 6
            assert 1 <= race["win_boat"] <= 6
            assert abs(sum(race["predicted_proba"]) - 1.0) < 1e-6  # 確率の合計=1
