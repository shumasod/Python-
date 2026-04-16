"""
バックテストモジュール
過去のレースデータに学習済みモデルを適用し、
予測精度・回収率を時系列で評価する

# 実行例
  python backtester.py --n-races 500
  python backtester.py --data-path data/training.csv --ev-threshold 1.1
  python backtester.py --walk-forward  # ウォークフォワード検証モード

# ウォークフォワード検証とは
  時系列データを「学習期間」と「テスト期間」に分割し、
  学習→予測→学習期間を1期間ずらす を繰り返す手法。
  未来データのリークを防ぎ、実運用に近い精度評価ができる。
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd

matplotlib.rcParams["font.family"] = ["IPAGothic", "Noto Sans CJK JP", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, str(Path(__file__).parent))

from app.model.features import FEATURE_COLUMNS, generate_sample_training_data
from app.model.train import train_model, LGBM_PARAMS
from app.utils.logger import get_logger
from simulator import expected_value, kelly_criterion, decide_bet

logger = get_logger(__name__)


# ============================================================
# データ構造
# ============================================================

@dataclass
class BacktestResult:
    """バックテスト1期間の結果"""
    period: int            # 期間インデックス
    n_races: int           # テスト期間のレース数
    n_bet: int             # 購入レース数
    n_win: int             # 的中数
    hit_rate: float        # 的中率
    total_bet: float       # 総投資額
    total_payout: float    # 総払戻額
    roi: float             # 回収率
    log_loss: float        # モデルの Log Loss
    accuracy: float        # 的中精度（モデル評価）


@dataclass
class WalkForwardStats:
    """ウォークフォワード全期間の統計"""
    periods: List[BacktestResult] = field(default_factory=list)

    @property
    def mean_roi(self) -> float:
        if not self.periods:
            return 0.0
        return float(np.mean([p.roi for p in self.periods]))

    @property
    def mean_hit_rate(self) -> float:
        if not self.periods:
            return 0.0
        return float(np.mean([p.hit_rate for p in self.periods]))

    @property
    def mean_logloss(self) -> float:
        if not self.periods:
            return 0.0
        return float(np.mean([p.log_loss for p in self.periods]))


# ============================================================
# バックテスト本体
# ============================================================

def run_simple_backtest(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
    ev_threshold: float = 1.0,
    kelly_multiplier: float = 0.5,
    initial_capital: float = 100_000.0,
) -> Tuple[BacktestResult, pd.DataFrame]:
    """
    シンプルな学習/テスト分割によるバックテスト

    Args:
        df: 全期間の DataFrame（FEATURE_COLUMNS + "label" 必須）
        train_ratio: 学習データの割合
        ev_threshold: 購入判断の期待値閾値
        kelly_multiplier: フラクショナルケリー係数
        initial_capital: 初期資金

    Returns:
        (BacktestResult, テスト期間の予測DataFrame)
    """
    from sklearn.metrics import log_loss, accuracy_score
    import lightgbm as lgb

    n_total = len(df)
    n_train = int(n_total * train_ratio)

    train_df = df.iloc[:n_train]
    test_df  = df.iloc[n_train:]

    logger.info(f"学習: {len(train_df)} 件, テスト: {len(test_df)} 件")

    # モデル学習
    X_train = train_df[FEATURE_COLUMNS].values
    y_train = train_df["label"].values.astype(int)

    import lightgbm as lgb
    model = lgb.LGBMClassifier(**{**LGBM_PARAMS, "n_estimators": 200})
    model.fit(X_train, y_train)

    # テストデータで予測
    X_test = test_df[FEATURE_COLUMNS].values
    y_test  = test_df["label"].values.astype(int)

    proba_matrix = model.predict_proba(X_test)
    y_pred = model.predict(X_test)

    ll = log_loss(y_test, proba_matrix, labels=list(range(6)))
    acc = accuracy_score(y_test, y_pred)

    # レース単位（6艇ずつ）で購入判断
    test_df = test_df.copy()
    test_df["pred_proba_1st"] = proba_matrix[:, 0]  # 1着確率

    # race_id 列があればそれを使用、なければ行インデックスから生成
    if "race_id" not in test_df.columns:
        test_df["race_id"] = (test_df.index // 6)

    n_bet = 0
    n_win = 0
    total_bet = 0.0
    total_payout = 0.0
    capital = initial_capital

    for race_id, group in test_df.groupby("race_id"):
        if len(group) != 6:
            continue

        proba = group["pred_proba_1st"].tolist()
        # サンプルオッズ（実際のオッズがなければ逆数で近似）
        proba_arr = np.array(proba)
        proba_arr = proba_arr / proba_arr.sum()
        odds = [max(1.1, 0.75 / p) for p in proba_arr]

        bet_boat, bet_amount = decide_bet(
            proba_arr.tolist(), odds, capital,
            ev_threshold=ev_threshold,
            kelly_multiplier=kelly_multiplier,
        )

        if bet_boat is None:
            continue

        actual_winner = int(group["label"].iloc[0]) + 1  # 1始まり艇番
        is_win = (bet_boat == actual_winner)
        payout = bet_amount * odds[bet_boat - 1] if is_win else 0.0
        capital = max(0.0, capital + payout - bet_amount)

        n_bet += 1
        total_bet += bet_amount
        total_payout += payout
        if is_win:
            n_win += 1

    n_races = len(test_df["race_id"].unique())
    roi = total_payout / total_bet if total_bet > 0 else 0.0
    hit_rate = n_win / n_bet if n_bet > 0 else 0.0

    result = BacktestResult(
        period=0,
        n_races=n_races,
        n_bet=n_bet,
        n_win=n_win,
        hit_rate=hit_rate,
        total_bet=total_bet,
        total_payout=total_payout,
        roi=roi,
        log_loss=ll,
        accuracy=acc,
    )

    return result, test_df


def run_walk_forward(
    df: pd.DataFrame,
    n_periods: int = 5,
    train_window: int = 800,   # 学習に使うレース数（6行 = 1レース）
    test_window: int = 200,
    ev_threshold: float = 1.0,
    kelly_multiplier: float = 0.5,
) -> WalkForwardStats:
    """
    ウォークフォワード検証

    [←train_window→|←test→] →1ステップ→ [←train_window→|←test→] ...

    Args:
        df: 全データ DataFrame
        n_periods: 検証期間数
        train_window: 1期間の学習レース行数
        test_window: 1期間のテストレース行数
        ev_threshold: 期待値閾値
        kelly_multiplier: ケリー係数

    Returns:
        WalkForwardStats
    """
    from sklearn.metrics import log_loss, accuracy_score
    import lightgbm as lgb

    stats = WalkForwardStats()
    step = test_window

    for period in range(n_periods):
        train_start = period * step
        train_end   = train_start + train_window
        test_end    = train_end + test_window

        if test_end > len(df):
            logger.info(f"データ不足のため期間 {period + 1} をスキップします")
            break

        train_df = df.iloc[train_start:train_end]
        test_df  = df.iloc[train_end:test_end]

        logger.info(
            f"期間 {period + 1}/{n_periods}: "
            f"学習[{train_start}:{train_end}] テスト[{train_end}:{test_end}]"
        )

        # 学習
        X_train = train_df[FEATURE_COLUMNS].values
        y_train = train_df["label"].values.astype(int)
        model = lgb.LGBMClassifier(**{**LGBM_PARAMS, "n_estimators": 150})
        model.fit(X_train, y_train)

        # テスト
        X_test = test_df[FEATURE_COLUMNS].values
        y_test  = test_df["label"].values.astype(int)
        proba_matrix = model.predict_proba(X_test)
        y_pred = model.predict(X_test)

        ll  = log_loss(y_test, proba_matrix, labels=list(range(6)))
        acc = accuracy_score(y_test, y_pred)

        # 購入シミュレーション（レース単位）
        test_copy = test_df.copy()
        test_copy["race_id"] = (np.arange(len(test_copy)) // 6) + period * (test_window // 6)
        test_copy["pred_1st"] = proba_matrix[:, 0]

        n_bet = 0; n_win = 0; total_bet = 0.0; total_payout = 0.0
        capital = 100_000.0

        for _, group in test_copy.groupby("race_id"):
            if len(group) != 6:
                continue
            proba_arr = np.array(group["pred_1st"].tolist())
            proba_arr = proba_arr / proba_arr.sum()
            odds = [max(1.1, 0.75 / p) for p in proba_arr]

            bet_boat, bet_amount = decide_bet(
                proba_arr.tolist(), odds, capital,
                ev_threshold=ev_threshold,
                kelly_multiplier=kelly_multiplier,
            )
            if bet_boat is None:
                continue

            actual = int(group["label"].iloc[0]) + 1
            is_win = (bet_boat == actual)
            payout = bet_amount * odds[bet_boat - 1] if is_win else 0.0
            capital = max(0.0, capital + payout - bet_amount)
            n_bet += 1
            total_bet += bet_amount
            total_payout += payout
            if is_win:
                n_win += 1

        n_races = len(test_copy["race_id"].unique())
        roi = total_payout / total_bet if total_bet > 0 else 0.0
        hit_rate = n_win / n_bet if n_bet > 0 else 0.0

        stats.periods.append(BacktestResult(
            period=period + 1,
            n_races=n_races,
            n_bet=n_bet,
            n_win=n_win,
            hit_rate=hit_rate,
            total_bet=total_bet,
            total_payout=total_payout,
            roi=roi,
            log_loss=ll,
            accuracy=acc,
        ))
        logger.info(
            f"  → ROI={roi*100:.1f}%, 的中率={hit_rate*100:.1f}%, LogLoss={ll:.4f}"
        )

    return stats


# ============================================================
# 可視化
# ============================================================

def plot_backtest(stats: WalkForwardStats, save_path: Optional[str] = None) -> None:
    """
    ウォークフォワード結果を3パネルグラフで表示

    Args:
        stats: WalkForwardStats
        save_path: 画像保存パス（None なら画面表示）
    """
    periods = [p.period for p in stats.periods]
    rois    = [p.roi * 100 for p in stats.periods]
    hits    = [p.hit_rate * 100 for p in stats.periods]
    losses  = [p.log_loss for p in stats.periods]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("ウォークフォワード バックテスト結果", fontsize=14, fontweight="bold")

    # ROI
    axes[0].bar(periods, rois, color=["green" if r >= 100 else "red" for r in rois], alpha=0.8)
    axes[0].axhline(y=100, color="black", linestyle="--", linewidth=1, label="元返し")
    axes[0].set_title("回収率 (%)")
    axes[0].set_xlabel("期間")
    axes[0].set_ylabel("%")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3, axis="y")

    # 的中率
    axes[1].plot(periods, hits, marker="o", color="steelblue", linewidth=2)
    axes[1].set_title("的中率 (%)")
    axes[1].set_xlabel("期間")
    axes[1].set_ylabel("%")
    axes[1].grid(True, alpha=0.3)

    # Log Loss
    axes[2].plot(periods, losses, marker="s", color="orange", linewidth=2)
    axes[2].set_title("Log Loss（低いほど良い）")
    axes[2].set_xlabel("期間")
    axes[2].set_ylabel("Log Loss")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"グラフ保存: {save_path}")
    else:
        plt.show()
    plt.close()


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="競艇予想AI バックテスト")
    parser.add_argument("--n-races", type=int, default=500, help="サンプルレース数")
    parser.add_argument("--data-path", type=str, default=None, help="学習データCSVパス")
    parser.add_argument(
        "--walk-forward", action="store_true",
        help="ウォークフォワード検証モード（通常は train/test 分割）"
    )
    parser.add_argument("--n-periods", type=int, default=5, help="ウォークフォワード期間数")
    parser.add_argument("--ev-threshold", type=float, default=1.0, help="期待値閾値")
    parser.add_argument("--kelly-frac", type=float, default=0.5, help="ケリー係数")
    parser.add_argument("--save-plot", type=str, default=None, help="グラフ保存パス")
    parser.add_argument("--no-plot", action="store_true", help="グラフを表示しない")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f" 競艇予想AI バックテスト")
    print(f" モード: {'ウォークフォワード' if args.walk_forward else '単純分割'}")
    print(f"{'='*55}\n")

    # データ準備
    if args.data_path:
        from app.data.loader import load_training_data
        df = load_training_data(file_path=args.data_path)
    else:
        logger.info(f"サンプルデータを生成します（{args.n_races} レース）")
        from app.model.features import preprocess_dataframe
        df = preprocess_dataframe(generate_sample_training_data(n_races=args.n_races))

    if args.walk_forward:
        # ---- ウォークフォワード ----
        stats = run_walk_forward(
            df,
            n_periods=args.n_periods,
            ev_threshold=args.ev_threshold,
            kelly_multiplier=args.kelly_frac,
        )

        print("\n【ウォークフォワード結果サマリー】")
        print(f"{'期間':>4} {'レース':>6} {'購入':>5} {'的中':>5} {'的中率':>7} {'ROI':>7} {'LogLoss':>9}")
        print("-" * 50)
        for p in stats.periods:
            print(
                f"{p.period:>4} {p.n_races:>6} {p.n_bet:>5} {p.n_win:>5} "
                f"{p.hit_rate*100:>6.1f}% {p.roi*100:>6.1f}% {p.log_loss:>9.4f}"
            )
        print("-" * 50)
        print(f"平均ROI: {stats.mean_roi*100:.1f}%  |  "
              f"平均的中率: {stats.mean_hit_rate*100:.1f}%  |  "
              f"平均LogLoss: {stats.mean_logloss:.4f}")

        if not args.no_plot:
            plot_backtest(stats, save_path=args.save_plot)

    else:
        # ---- 単純バックテスト ----
        result, _ = run_simple_backtest(
            df,
            ev_threshold=args.ev_threshold,
            kelly_multiplier=args.kelly_frac,
        )

        print("\n【バックテスト結果】")
        print(f" テストレース数  : {result.n_races:,}")
        print(f" 購入レース数    : {result.n_bet:,}")
        print(f" 的中数          : {result.n_win:,}")
        print(f" 的中率          : {result.hit_rate*100:.1f}%")
        print(f" 回収率 (ROI)    : {result.roi*100:.1f}%")
        print(f" モデル精度      : accuracy={result.accuracy*100:.1f}%, log_loss={result.log_loss:.4f}")


if __name__ == "__main__":
    main()
