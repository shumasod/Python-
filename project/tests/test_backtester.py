"""
backtester.py のテスト
バックテスト・ウォークフォワード検証の各関数を検証する
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture(scope="module")
def sample_df():
    """バックテスト用サンプルデータ（300 レース × 6 艇 = 1800 行）"""
    from app.model.features import generate_sample_training_data, preprocess_dataframe
    df = generate_sample_training_data(n_races=300)
    return preprocess_dataframe(df)


# ============================================================
# BacktestResult dataclass
# ============================================================

class TestBacktestResult:
    def test_fields_accessible(self):
        """BacktestResult の全フィールドにアクセスできること"""
        from backtester import BacktestResult
        r = BacktestResult(
            period=0, n_races=100, n_bet=60, n_win=12,
            hit_rate=0.2, total_bet=60_000.0,
            total_payout=54_000.0, roi=0.9,
            log_loss=1.5, accuracy=0.25,
        )
        assert r.roi == pytest.approx(0.9)
        assert r.hit_rate == pytest.approx(0.2)


# ============================================================
# WalkForwardStats
# ============================================================

class TestWalkForwardStats:
    def _make_stats(self, rois, hit_rates, loglosses):
        from backtester import WalkForwardStats, BacktestResult
        wf = WalkForwardStats()
        for i, (roi, hr, ll) in enumerate(zip(rois, hit_rates, loglosses)):
            wf.periods.append(BacktestResult(
                period=i, n_races=100, n_bet=50, n_win=int(50*hr),
                hit_rate=hr, total_bet=50_000.0,
                total_payout=50_000.0 * roi,
                roi=roi, log_loss=ll, accuracy=hr,
            ))
        return wf

    def test_mean_roi_correct(self):
        """mean_roi が期間 ROI の平均と一致すること"""
        wf = self._make_stats([0.8, 1.0, 1.2], [0.2]*3, [1.5]*3)
        assert wf.mean_roi == pytest.approx(1.0)

    def test_mean_hit_rate_correct(self):
        """mean_hit_rate が期間的中率の平均と一致すること"""
        wf = self._make_stats([1.0]*3, [0.1, 0.2, 0.3], [1.5]*3)
        assert wf.mean_hit_rate == pytest.approx(0.2)

    def test_mean_logloss_correct(self):
        """mean_logloss が期間 log_loss の平均と一致すること"""
        wf = self._make_stats([1.0]*3, [0.2]*3, [1.0, 2.0, 3.0])
        assert wf.mean_logloss == pytest.approx(2.0)

    def test_empty_stats_returns_zero(self):
        """期間なしのとき各指標が 0 を返すこと"""
        from backtester import WalkForwardStats
        wf = WalkForwardStats()
        assert wf.mean_roi == 0.0
        assert wf.mean_hit_rate == 0.0
        assert wf.mean_logloss == 0.0


# ============================================================
# run_simple_backtest
# ============================================================

class TestRunSimpleBacktest:
    def test_returns_backtest_result_and_dataframe(self, sample_df):
        """(BacktestResult, DataFrame) を返すこと"""
        from backtester import run_simple_backtest, BacktestResult
        result, df_out = run_simple_backtest(sample_df, train_ratio=0.8)
        assert isinstance(result, BacktestResult)
        assert isinstance(df_out, pd.DataFrame)

    def test_backtest_result_fields_sensible(self, sample_df):
        """BacktestResult のフィールドが意味のある範囲であること"""
        from backtester import run_simple_backtest
        result, _ = run_simple_backtest(sample_df, train_ratio=0.8)
        assert result.n_races > 0
        assert result.n_bet >= 0
        assert result.n_win <= result.n_bet
        assert 0.0 <= result.hit_rate <= 1.0
        assert result.log_loss > 0.0
        assert 0.0 <= result.accuracy <= 1.0

    def test_roi_formula_holds(self, sample_df):
        """ROI = total_payout / total_bet であること"""
        from backtester import run_simple_backtest
        result, _ = run_simple_backtest(sample_df, train_ratio=0.8)
        if result.total_bet > 0:
            assert result.roi == pytest.approx(
                result.total_payout / result.total_bet, abs=1e-6
            )

    def test_hit_rate_formula_holds(self, sample_df):
        """hit_rate = n_win / n_bet であること"""
        from backtester import run_simple_backtest
        result, _ = run_simple_backtest(sample_df, train_ratio=0.8)
        if result.n_bet > 0:
            assert result.hit_rate == pytest.approx(
                result.n_win / result.n_bet, abs=1e-6
            )

    def test_test_df_has_pred_column(self, sample_df):
        """テスト DataFrame に pred_proba_1st カラムが含まれること"""
        from backtester import run_simple_backtest
        _, df_out = run_simple_backtest(sample_df, train_ratio=0.8)
        assert "pred_proba_1st" in df_out.columns

    def test_high_ev_threshold_reduces_bets(self, sample_df):
        """閾値を高くすると購入数が減ること"""
        from backtester import run_simple_backtest
        r_low,  _ = run_simple_backtest(sample_df, ev_threshold=1.0)
        r_high, _ = run_simple_backtest(sample_df, ev_threshold=5.0)
        assert r_high.n_bet <= r_low.n_bet

    def test_train_ratio_affects_test_size(self, sample_df):
        """train_ratio が小さいほどテストデータが多くなること"""
        from backtester import run_simple_backtest
        r_80, _ = run_simple_backtest(sample_df, train_ratio=0.8)
        r_60, _ = run_simple_backtest(sample_df, train_ratio=0.6)
        # テスト期間が長ければレース数も多い
        assert r_60.n_races >= r_80.n_races


# ============================================================
# run_walk_forward
# ============================================================

class TestRunWalkForward:
    @pytest.fixture(scope="class")
    def large_df(self):
        """ウォークフォワードに十分なデータ（500レース）"""
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        df = generate_sample_training_data(n_races=500)
        return preprocess_dataframe(df)

    def test_returns_walk_forward_stats(self, large_df):
        """WalkForwardStats を返すこと"""
        from backtester import run_walk_forward, WalkForwardStats
        stats = run_walk_forward(
            large_df, n_periods=2, train_window=600, test_window=300
        )
        assert isinstance(stats, WalkForwardStats)

    def test_periods_created(self, large_df):
        """指定した期間数（またはそれ以下）の結果が作成されること"""
        from backtester import run_walk_forward
        stats = run_walk_forward(
            large_df, n_periods=2, train_window=600, test_window=300
        )
        assert 1 <= len(stats.periods) <= 2

    def test_each_period_has_races(self, large_df):
        """各期間のレース数が正であること"""
        from backtester import run_walk_forward
        stats = run_walk_forward(
            large_df, n_periods=2, train_window=600, test_window=300
        )
        for period in stats.periods:
            assert period.n_races > 0

    def test_mean_stats_in_range(self, large_df):
        """平均統計が有効な範囲であること"""
        from backtester import run_walk_forward
        stats = run_walk_forward(
            large_df, n_periods=2, train_window=600, test_window=300
        )
        if stats.periods:
            assert 0.0 <= stats.mean_hit_rate <= 1.0
            assert stats.mean_logloss > 0.0

    def test_insufficient_data_skips_periods(self):
        """データが少ない場合に期間をスキップすること"""
        from backtester import run_walk_forward
        from app.model.features import generate_sample_training_data, preprocess_dataframe
        tiny_df = preprocess_dataframe(generate_sample_training_data(n_races=50))
        stats = run_walk_forward(
            tiny_df, n_periods=5, train_window=5000, test_window=1000
        )
        # データが足りないので 0 期間になる
        assert len(stats.periods) == 0
