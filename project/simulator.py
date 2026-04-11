"""
競艇回収率シミュレーター
モデル予測確率・オッズを入力として期待値・ケリー基準で買い目を決定し
長期回収率を可視化する

# 実行例
  python simulator.py                    # サンプルデータでシミュレーション
  python simulator.py --n-races 500      # レース数を指定
  python simulator.py --ev-threshold 1.2 # 期待値閾値を引き上げて厳選
  python simulator.py --kelly-frac 0.25  # ケリー比率に係数を掛けてリスク軽減
  python simulator.py --no-plot          # グラフを表示しない
"""

import argparse
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["font.family"] = ["IPAGothic", "Noto Sans CJK JP", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


# ---- データ構造 ----

@dataclass
class RaceResult:
    """1レースのシミュレーション結果"""
    race_id: int
    win_boat: int                          # 実際の1着艇番（1〜6）
    predicted_proba: List[float]           # モデルが出した各艇の確率
    odds: List[float]                      # 各艇のオッズ
    bet_boat: Optional[int]               # 購入した艇番（None=見送り）
    bet_amount: float                      # 購入金額（円）
    payout: float                          # 払戻金額（円）
    profit: float                          # 損益（= payout - bet_amount）
    expected_value: float                  # 購入時の期待値
    kelly_fraction: float                  # ケリー比率


@dataclass
class SimulationStats:
    """シミュレーション全体の統計"""
    n_races: int = 0
    n_bet: int = 0                        # 購入したレース数
    n_win: int = 0                        # 的中レース数
    total_bet: float = 0.0                # 総投資額
    total_payout: float = 0.0            # 総払戻額
    roi: float = 0.0                      # 回収率（= total_payout / total_bet）
    capital_history: List[float] = field(default_factory=list)  # 資金推移


# ---- 期待値・ケリー計算 ----

def expected_value(probability: float, odds: float) -> float:
    """
    期待値 = 確率 × オッズ

    Args:
        probability: 勝利確率（0〜1）
        odds: 配当倍率

    Returns:
        期待値（1.0を超えると収益期待）
    """
    return probability * odds


def kelly_criterion(probability: float, odds: float) -> float:
    """
    ケリー基準による最適ベット比率

    f* = (p*(b+1) - 1) / b  (b = 純利益倍率 = odds - 1)

    Args:
        probability: 勝利確率
        odds: 配当倍率

    Returns:
        総資金に対するベット比率（0以下は見送り）
    """
    b = odds - 1.0
    if b <= 0 or probability <= 0:
        return 0.0
    kelly = (probability * (b + 1.0) - 1.0) / b
    return max(0.0, kelly)


# ---- 購入判断 ----

def decide_bet(
    predicted_proba: List[float],
    odds: List[float],
    capital: float,
    ev_threshold: float = 1.0,
    kelly_multiplier: float = 0.5,
    min_bet: float = 100.0,
    max_bet_ratio: float = 0.1,
) -> Tuple[Optional[int], float]:
    """
    購入する艇番と金額を決定する

    戦略:
    1. 全艇の期待値を計算
    2. 期待値 > ev_threshold の艇のみ対象
    3. 最高期待値の艇に対してケリー基準でベット額を決定
    4. ケリー比率に kelly_multiplier を掛けてリスクを調整（フラクショナルケリー）

    Args:
        predicted_proba: 各艇の予測確率リスト（長さ6）
        odds: 各艇のオッズリスト（長さ6）
        capital: 現在の資金（円）
        ev_threshold: 購入する最低期待値
        kelly_multiplier: ケリー比率への係数（0.5 = ハーフケリー）
        min_bet: 最低ベット額
        max_bet_ratio: 最大ベット額の資金比率（リスク上限）

    Returns:
        (購入艇番 or None, ベット額)
    """
    best_boat = None
    best_ev = ev_threshold
    best_kelly = 0.0
    best_odds = 1.0

    for i, (prob, odd) in enumerate(zip(predicted_proba, odds)):
        ev = expected_value(prob, odd)
        if ev > best_ev:
            best_ev = ev
            best_boat = i + 1  # 1始まり艇番
            best_kelly = kelly_criterion(prob, odd)
            best_odds = odd

    if best_boat is None:
        return None, 0.0  # 見送り

    # フラクショナルケリーでベット額を計算
    kelly_adjusted = best_kelly * kelly_multiplier
    bet_amount = capital * kelly_adjusted

    # 上下限クリッピング
    bet_amount = max(min_bet, min(bet_amount, capital * max_bet_ratio))

    # 100円単位に切り捨て（舟券の最低単位）
    bet_amount = int(bet_amount / 100) * 100
    if bet_amount < min_bet:
        bet_amount = min_bet

    return best_boat, float(bet_amount)


# ---- サンプルデータ生成 ----

def generate_sample_races(n_races: int = 200, seed: int = 42) -> List[dict]:
    """
    シミュレーション用サンプルレースデータを生成する

    Args:
        n_races: 生成するレース数
        seed: 乱数シード

    Returns:
        レースデータ辞書のリスト
    """
    rng = np.random.default_rng(seed)
    races = []

    for i in range(n_races):
        # 1着確率（内側コースが有利）
        raw_proba = rng.exponential(scale=[0.30, 0.22, 0.18, 0.14, 0.10, 0.06])
        proba = (raw_proba / raw_proba.sum()).tolist()

        # オッズ（確率の逆数に誤差を加える。控除率 = 25%を模倣）
        base_odds = [0.75 / p for p in proba]
        odds = [max(1.1, o * rng.uniform(0.85, 1.20)) for o in base_odds]

        # 実際の1着（確率に従ってサンプリング）
        win_boat = int(rng.choice(6, p=proba)) + 1  # 1始まり

        races.append({
            "race_id": i + 1,
            "predicted_proba": proba,
            "odds": odds,
            "win_boat": win_boat,
        })

    return races


# ---- シミュレーション本体 ----

def run_simulation(
    races: List[dict],
    initial_capital: float = 100_000.0,
    ev_threshold: float = 1.0,
    kelly_multiplier: float = 0.5,
) -> Tuple[List[RaceResult], SimulationStats]:
    """
    レースリストに対してシミュレーションを実行する

    Args:
        races: generate_sample_races() で生成したレースデータリスト
        initial_capital: 初期資金（円）
        ev_threshold: 購入する最低期待値
        kelly_multiplier: フラクショナルケリー係数

    Returns:
        (RaceResult のリスト, SimulationStats)
    """
    capital = initial_capital
    results: List[RaceResult] = []
    stats = SimulationStats()
    stats.capital_history.append(capital)

    for race_data in races:
        stats.n_races += 1
        proba = race_data["predicted_proba"]
        odds = race_data["odds"]
        win_boat = race_data["win_boat"]

        bet_boat, bet_amount = decide_bet(
            proba, odds, capital,
            ev_threshold=ev_threshold,
            kelly_multiplier=kelly_multiplier,
        )

        if bet_boat is None:
            # 見送り
            result = RaceResult(
                race_id=race_data["race_id"],
                win_boat=win_boat,
                predicted_proba=proba,
                odds=odds,
                bet_boat=None,
                bet_amount=0.0,
                payout=0.0,
                profit=0.0,
                expected_value=0.0,
                kelly_fraction=0.0,
            )
        else:
            is_win = (bet_boat == win_boat)
            payout = bet_amount * odds[bet_boat - 1] if is_win else 0.0
            profit = payout - bet_amount
            capital = max(0.0, capital + profit)

            ev = expected_value(proba[bet_boat - 1], odds[bet_boat - 1])
            kelly = kelly_criterion(proba[bet_boat - 1], odds[bet_boat - 1])

            result = RaceResult(
                race_id=race_data["race_id"],
                win_boat=win_boat,
                predicted_proba=proba,
                odds=odds,
                bet_boat=bet_boat,
                bet_amount=bet_amount,
                payout=payout,
                profit=profit,
                expected_value=ev,
                kelly_fraction=kelly,
            )

            stats.n_bet += 1
            if is_win:
                stats.n_win += 1
            stats.total_bet += bet_amount
            stats.total_payout += payout

        results.append(result)
        stats.capital_history.append(capital)

    stats.n_races = len(races)
    stats.roi = (stats.total_payout / stats.total_bet) if stats.total_bet > 0 else 0.0

    return results, stats


# ---- 可視化 ----

def plot_results(
    results: List[RaceResult],
    stats: SimulationStats,
    initial_capital: float,
    save_path: Optional[str] = None,
) -> None:
    """
    シミュレーション結果を4パネルグラフで可視化する

    Args:
        results: run_simulation() の出力
        stats: SimulationStats
        initial_capital: 初期資金
        save_path: 画像保存パス（None の場合は画面表示）
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("競艇回収率シミュレーション結果", fontsize=16, fontweight="bold")

    # ---- パネル1: 資金推移 ----
    ax1 = axes[0, 0]
    ax1.plot(stats.capital_history, color="steelblue", linewidth=1.5, label="資金")
    ax1.axhline(y=initial_capital, color="red", linestyle="--", alpha=0.6, label="初期資金")
    ax1.set_title("資金推移")
    ax1.set_xlabel("レース数")
    ax1.set_ylabel("資金 (円)")
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # ---- パネル2: レース毎損益 ----
    ax2 = axes[0, 1]
    profits = [r.profit for r in results if r.bet_boat is not None]
    races_bet = [r.race_id for r in results if r.bet_boat is not None]
    colors = ["green" if p >= 0 else "red" for p in profits]
    ax2.bar(range(len(profits)), profits, color=colors, alpha=0.7)
    ax2.axhline(y=0, color="black", linewidth=0.8)
    ax2.set_title("レース毎損益")
    ax2.set_xlabel("購入レース番号")
    ax2.set_ylabel("損益 (円)")
    ax2.grid(True, alpha=0.3, axis="y")

    # ---- パネル3: 期待値分布 ----
    ax3 = axes[1, 0]
    evs = [r.expected_value for r in results if r.bet_boat is not None]
    ax3.hist(evs, bins=30, color="orange", alpha=0.8, edgecolor="black")
    ax3.axvline(x=1.0, color="red", linestyle="--", label="期待値=1.0（元返し）")
    ax3.set_title("購入時の期待値分布")
    ax3.set_xlabel("期待値")
    ax3.set_ylabel("頻度")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # ---- パネル4: 統計サマリー ----
    ax4 = axes[1, 1]
    ax4.axis("off")
    hit_rate = (stats.n_win / stats.n_bet * 100) if stats.n_bet > 0 else 0
    final_capital = stats.capital_history[-1]
    total_return = (final_capital - initial_capital) / initial_capital * 100

    summary = [
        ["項目", "値"],
        ["総レース数", f"{stats.n_races:,}"],
        ["購入レース数", f"{stats.n_bet:,} ({stats.n_bet/stats.n_races*100:.1f}%)"],
        ["的中数", f"{stats.n_win:,}"],
        ["的中率", f"{hit_rate:.1f}%"],
        ["総投資額", f"¥{stats.total_bet:,.0f}"],
        ["総払戻額", f"¥{stats.total_payout:,.0f}"],
        ["回収率", f"{stats.roi*100:.1f}%"],
        ["最終資金", f"¥{final_capital:,.0f}"],
        ["総収益率", f"{total_return:+.1f}%"],
    ]

    table = ax4.table(
        cellText=summary[1:],
        colLabels=summary[0],
        cellLoc="center",
        loc="center",
        bbox=[0.0, 0.0, 1.0, 1.0],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    # ヘッダー行の色付け
    for j in range(2):
        table[0, j].set_facecolor("#4472C4")
        table[0, j].set_text_props(color="white", fontweight="bold")
    # 回収率行を強調
    for j in range(2):
        table[8, j].set_facecolor("#FFD700")

    ax4.set_title("シミュレーション統計")

    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"グラフを保存しました: {save_path}")
    else:
        plt.show()

    plt.close()


# ---- CLI エントリーポイント ----

def main() -> None:
    parser = argparse.ArgumentParser(description="競艇回収率シミュレーター")
    parser.add_argument("--n-races", type=int, default=200, help="シミュレーションするレース数")
    parser.add_argument("--capital", type=float, default=100_000, help="初期資金 (円)")
    parser.add_argument(
        "--ev-threshold", type=float, default=1.0,
        help="購入する最低期待値（例: 1.2 = 期待値1.2以上のみ購入）"
    )
    parser.add_argument(
        "--kelly-frac", type=float, default=0.5,
        help="フラクショナルケリー係数（0.5 = ハーフケリー）"
    )
    parser.add_argument("--no-plot", action="store_true", help="グラフを表示しない")
    parser.add_argument("--save-plot", type=str, default=None, help="グラフ保存パス")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f" 競艇回収率シミュレーター")
    print(f"{'='*50}")
    print(f" レース数     : {args.n_races:,}")
    print(f" 初期資金     : ¥{args.capital:,.0f}")
    print(f" 期待値閾値   : {args.ev_threshold}")
    print(f" ケリー係数   : {args.kelly_frac}")
    print(f"{'='*50}\n")

    # サンプルデータ生成
    races = generate_sample_races(n_races=args.n_races)

    # シミュレーション実行
    results, stats = run_simulation(
        races,
        initial_capital=args.capital,
        ev_threshold=args.ev_threshold,
        kelly_multiplier=args.kelly_frac,
    )

    # 結果表示
    hit_rate = (stats.n_win / stats.n_bet * 100) if stats.n_bet > 0 else 0
    final_capital = stats.capital_history[-1]
    total_return = (final_capital - args.capital) / args.capital * 100

    print(f"【結果サマリー】")
    print(f" 購入レース数 : {stats.n_bet:,} / {stats.n_races:,}")
    print(f" 的中率       : {hit_rate:.1f}%")
    print(f" 回収率       : {stats.roi*100:.1f}%")
    print(f" 最終資金     : ¥{final_capital:,.0f} ({total_return:+.1f}%)\n")

    # グラフ表示
    if not args.no_plot:
        plot_results(
            results, stats, args.capital,
            save_path=args.save_plot,
        )


if __name__ == "__main__":
    main()
