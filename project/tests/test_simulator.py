"""
simulator.py のテスト
競艇回収率シミュレーターの各関数を検証する
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# expected_value
# ============================================================

class TestExpectedValue:
    def test_basic_calculation(self):
        """期待値 = 確率 × オッズ"""
        from simulator import expected_value
        assert expected_value(0.5, 2.0) == pytest.approx(1.0)

    def test_zero_probability(self):
        """確率0で期待値0"""
        from simulator import expected_value
        assert expected_value(0.0, 10.0) == pytest.approx(0.0)

    def test_favorable_bet(self):
        """期待値 > 1 の有利なベット"""
        from simulator import expected_value
        assert expected_value(0.4, 3.0) == pytest.approx(1.2)

    def test_unfavorable_bet(self):
        """期待値 < 1 の不利なベット"""
        from simulator import expected_value
        assert expected_value(0.1, 5.0) == pytest.approx(0.5)


# ============================================================
# kelly_criterion
# ============================================================

class TestKellyCriterion:
    def test_positive_edge(self):
        """有利な賭けでケリー比率が正であること"""
        from simulator import kelly_criterion
        kelly = kelly_criterion(0.6, 2.0)
        assert kelly > 0.0

    def test_negative_edge_returns_zero(self):
        """不利な賭けでケリー比率が0（見送り）であること"""
        from simulator import kelly_criterion
        kelly = kelly_criterion(0.1, 2.0)  # EV = 0.2 < 1.0
        assert kelly == 0.0

    def test_zero_probability_returns_zero(self):
        """確率0でケリー比率が0であること"""
        from simulator import kelly_criterion
        assert kelly_criterion(0.0, 5.0) == 0.0

    def test_zero_odds_returns_zero(self):
        """オッズ1以下でケリー比率が0であること"""
        from simulator import kelly_criterion
        assert kelly_criterion(0.5, 1.0) == 0.0

    def test_formula_correctness(self):
        """ケリー公式 f* = (p(b+1)-1)/b の正確性を検証"""
        from simulator import kelly_criterion
        p, odds = 0.5, 3.0
        b = odds - 1
        expected = (p * (b + 1) - 1) / b
        assert kelly_criterion(p, odds) == pytest.approx(expected)


# ============================================================
# decide_bet
# ============================================================

class TestDecideBet:
    def _uniform_proba(self):
        return [1 / 6] * 6

    def _uniform_odds(self, multiplier=1.0):
        return [6.0 * multiplier] * 6

    def test_returns_tuple(self):
        """タプルを返すこと"""
        from simulator import decide_bet
        result = decide_bet(self._uniform_proba(), self._uniform_odds(), 100_000.0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_high_ev_triggers_bet(self):
        """高期待値の場合に購入すること"""
        from simulator import decide_bet
        proba = [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
        odds  = [4.0, 5.0, 5.0, 5.0, 5.0, 5.0]  # 1号艇 EV=2.0
        boat, amount = decide_bet(proba, odds, 100_000.0, ev_threshold=1.0)
        assert boat == 1
        assert amount > 0

    def test_low_ev_skips_bet(self):
        """低期待値の場合に見送ること（boat=None, amount=0）"""
        from simulator import decide_bet
        proba = [1 / 6] * 6
        odds  = [0.5] * 6  # オッズ0.5 → 全艇 EV < 1
        boat, amount = decide_bet(proba, odds, 100_000.0, ev_threshold=1.0)
        assert boat is None
        assert amount == 0.0

    def test_bet_amount_multiple_of_100(self):
        """ベット額が100円単位であること"""
        from simulator import decide_bet
        proba = [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
        odds  = [4.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        _, amount = decide_bet(proba, odds, 100_000.0)
        assert amount % 100 == 0

    def test_bet_amount_within_max_ratio(self):
        """ベット額が資金の max_bet_ratio を超えないこと"""
        from simulator import decide_bet
        proba = [0.8, 0.04, 0.04, 0.04, 0.04, 0.04]
        odds  = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        capital = 100_000.0
        max_ratio = 0.1
        _, amount = decide_bet(proba, odds, capital, max_bet_ratio=max_ratio)
        assert amount <= capital * max_ratio + 100  # +100 で丸め誤差を許容

    def test_minimum_bet_enforced(self):
        """ケリー比率が小さくても min_bet 以上のベットをすること"""
        from simulator import decide_bet
        proba = [0.2, 0.16, 0.16, 0.16, 0.16, 0.16]
        odds  = [6.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        _, amount = decide_bet(proba, odds, 100_000.0, min_bet=100.0)
        if amount > 0:
            assert amount >= 100.0

    def test_kelly_multiplier_reduces_bet(self):
        """kelly_multiplier を下げるとベット額が減ること"""
        from simulator import decide_bet
        proba = [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
        odds  = [4.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        _, amount_half = decide_bet(proba, odds, 100_000.0, kelly_multiplier=0.25)
        _, amount_full = decide_bet(proba, odds, 100_000.0, kelly_multiplier=0.5)
        assert amount_half <= amount_full

    def test_selects_highest_ev_boat(self):
        """最高期待値の艇を選ぶこと"""
        from simulator import decide_bet
        proba = [0.1, 0.5, 0.1, 0.1, 0.1, 0.1]
        odds  = [2.0, 4.0, 2.0, 2.0, 2.0, 2.0]  # 2号艇 EV=2.0 が最高
        boat, _ = decide_bet(proba, odds, 100_000.0, ev_threshold=1.0)
        assert boat == 2


# ============================================================
# generate_sample_races
# ============================================================

class TestGenerateSampleRaces:
    def test_returns_correct_count(self):
        """指定した数のレースを返すこと"""
        from simulator import generate_sample_races
        races = generate_sample_races(n_races=50, seed=0)
        assert len(races) == 50

    def test_proba_sums_to_one(self):
        """各レースの確率の和が 1 であること"""
        from simulator import generate_sample_races
        races = generate_sample_races(n_races=20, seed=1)
        for race in races:
            assert sum(race["predicted_proba"]) == pytest.approx(1.0, abs=1e-6)

    def test_all_odds_positive(self):
        """全オッズが正であること"""
        from simulator import generate_sample_races
        races = generate_sample_races(n_races=20, seed=2)
        for race in races:
            assert all(o > 0 for o in race["odds"])

    def test_win_boat_in_range(self):
        """1着艇番が 1〜6 の範囲であること"""
        from simulator import generate_sample_races
        races = generate_sample_races(n_races=100, seed=3)
        for race in races:
            assert 1 <= race["win_boat"] <= 6

    def test_required_keys_present(self):
        """必要なキーが含まれること"""
        from simulator import generate_sample_races
        races = generate_sample_races(n_races=5, seed=4)
        for race in races:
            assert "race_id" in race
            assert "predicted_proba" in race
            assert "odds" in race
            assert "win_boat" in race

    def test_reproducible_with_same_seed(self):
        """同じシードで同じ結果が得られること"""
        from simulator import generate_sample_races
        r1 = generate_sample_races(n_races=10, seed=42)
        r2 = generate_sample_races(n_races=10, seed=42)
        for race_a, race_b in zip(r1, r2):
            assert race_a["win_boat"] == race_b["win_boat"]


# ============================================================
# run_simulation
# ============================================================

class TestRunSimulation:
    def _get_races(self, n=100):
        from simulator import generate_sample_races
        return generate_sample_races(n_races=n, seed=99)

    def test_returns_tuple_of_results_and_stats(self):
        """(List[RaceResult], SimulationStats) を返すこと"""
        from simulator import run_simulation
        races = self._get_races(50)
        results, stats = run_simulation(races)
        assert isinstance(results, list)
        assert len(results) == 50

    def test_stats_n_races_matches_input(self):
        """stats.n_races が入力レース数と一致すること"""
        from simulator import run_simulation
        races = self._get_races(30)
        _, stats = run_simulation(races)
        assert stats.n_races == 30

    def test_capital_history_length(self):
        """capital_history の長さが n_races + 1 であること（初期値含む）"""
        from simulator import run_simulation
        races = self._get_races(20)
        _, stats = run_simulation(races, initial_capital=100_000.0)
        assert len(stats.capital_history) == 21

    def test_capital_never_negative(self):
        """資金が負にならないこと"""
        from simulator import run_simulation
        races = self._get_races(100)
        _, stats = run_simulation(races)
        assert all(c >= 0.0 for c in stats.capital_history)

    def test_n_bet_le_n_races(self):
        """購入レース数 ≤ 全レース数であること"""
        from simulator import run_simulation
        races = self._get_races(100)
        _, stats = run_simulation(races)
        assert stats.n_bet <= stats.n_races

    def test_n_win_le_n_bet(self):
        """的中数 ≤ 購入数であること"""
        from simulator import run_simulation
        races = self._get_races(100)
        _, stats = run_simulation(races)
        assert stats.n_win <= stats.n_bet

    def test_high_ev_threshold_reduces_bets(self):
        """閾値を高くすると購入数が減ること"""
        from simulator import run_simulation
        races = self._get_races(200)
        _, stats_low  = run_simulation(races, ev_threshold=1.0)
        _, stats_high = run_simulation(races, ev_threshold=5.0)
        assert stats_high.n_bet <= stats_low.n_bet

    def test_roi_calculated_correctly(self):
        """ROI = total_payout / total_bet であること"""
        from simulator import run_simulation
        races = self._get_races(100)
        _, stats = run_simulation(races)
        if stats.total_bet > 0:
            assert stats.roi == pytest.approx(stats.total_payout / stats.total_bet)

    def test_no_bets_when_all_low_odds(self):
        """全オッズが非常に低い場合は一切購入しないこと"""
        from simulator import run_simulation, generate_sample_races
        races = generate_sample_races(50, seed=7)
        # オッズを全部 0.5 倍に下げて EV < 1 にする
        for r in races:
            r["odds"] = [0.5] * 6
        _, stats = run_simulation(races, ev_threshold=1.0)
        assert stats.n_bet == 0


# ============================================================
# RaceResult dataclass
# ============================================================

class TestRaceResult:
    def test_fields_accessible(self):
        """RaceResult の全フィールドにアクセスできること"""
        from simulator import RaceResult
        r = RaceResult(
            race_id=1, win_boat=1, predicted_proba=[1/6]*6,
            odds=[6.0]*6, bet_boat=1, bet_amount=1000.0,
            payout=6000.0, profit=5000.0,
            expected_value=1.0, kelly_fraction=0.1,
        )
        assert r.profit == 5000.0
        assert r.bet_boat == 1


# ============================================================
# SimulationStats dataclass
# ============================================================

class TestSimulationStats:
    def test_defaults_are_zero(self):
        """デフォルト値がすべて0であること"""
        from simulator import SimulationStats
        s = SimulationStats()
        assert s.n_races == 0
        assert s.n_bet == 0
        assert s.roi == 0.0
        assert s.capital_history == []
