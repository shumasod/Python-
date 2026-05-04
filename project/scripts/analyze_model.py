"""
モデル分析スクリプト
学習済みモデルの特徴量重要度・SHAP値・精度レポートを出力する

実行例:
  python scripts/analyze_model.py
  python scripts/analyze_model.py --save-dir output/analysis
"""
import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.rcParams["font.family"] = ["IPAGothic", "Noto Sans CJK JP", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.features import (  # noqa: E402
    FEATURE_COLUMNS,
    generate_sample_training_data,
    preprocess_dataframe,
)
from app.model.train import load_model  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def plot_feature_importance(model, save_dir: Path) -> None:
    """
    特徴量重要度を棒グラフで可視化する

    Args:
        model: 学習済み LGBMClassifier
        save_dir: 保存ディレクトリ
    """
    importance = model.feature_importances_
    indices = np.argsort(importance)[::-1]
    sorted_features = [FEATURE_COLUMNS[i] for i in indices]
    sorted_importance = importance[indices]

    # 正規化（最大を100とする）
    normalized = sorted_importance / sorted_importance.max() * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(sorted_features[::-1], normalized[::-1], color="steelblue", alpha=0.8)
    ax.set_xlabel("重要度スコア（最大=100）")
    ax.set_title("LightGBM 特徴量重要度（gain ベース）")
    ax.grid(True, alpha=0.3, axis="x")

    # スコア値をバーの右に表示
    for bar, val in zip(bars, normalized[::-1], strict=False):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}",
            va="center", fontsize=9,
        )

    plt.tight_layout()
    save_path = save_dir / "feature_importance.png"
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"特徴量重要度グラフを保存しました: {save_path}")

    # CSVでも保存
    df_imp = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "importance": importance,
        "normalized": importance / importance.max() * 100,
    }).sort_values("importance", ascending=False)
    df_imp.to_csv(save_dir / "feature_importance.csv", index=False)
    print("\n【特徴量重要度（上位）】")
    print(df_imp.head(6).to_string(index=False))


def plot_calibration(model, X_test: np.ndarray, y_test: np.ndarray, save_dir: Path) -> None:
    """
    予測確率のキャリブレーション曲線を描画する

    完璧なモデルでは「予測確率 x% の事象が実際に x% の頻度で起きる」

    Args:
        model: 学習済みモデル
        X_test: テスト特徴量
        y_test: テストラベル
        save_dir: 保存ディレクトリ
    """
    proba_matrix = model.predict_proba(X_test)

    # 各クラス（艇）の1着確率を1つの系列にまとめる
    all_proba = proba_matrix.flatten()
    # 各行・各クラスが実際の正解かどうか
    n_rows, n_classes = proba_matrix.shape
    all_actual = np.zeros(n_rows * n_classes)
    for i, label in enumerate(y_test):
        all_actual[i * n_classes + label] = 1

    # 10分位ごとに実際の正解率を計算
    n_bins = 10
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    actual_rates = []

    for low, high in zip(bin_edges[:-1], bin_edges[1:], strict=False):
        mask = (all_proba >= low) & (all_proba < high)
        if mask.sum() > 0:
            actual_rates.append(all_actual[mask].mean())
        else:
            actual_rates.append(np.nan)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="完全キャリブレーション")
    ax.plot(bin_centers, actual_rates, "o-", color="steelblue", linewidth=2, label="モデル予測")
    ax.set_xlabel("予測確率")
    ax.set_ylabel("実際の正解率")
    ax.set_title("キャリブレーション曲線")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    save_path = save_dir / "calibration_curve.png"
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"キャリブレーション曲線を保存しました: {save_path}")


def print_classification_report(model, X_test: np.ndarray, y_test: np.ndarray) -> None:
    """
    分類レポートを表示する（クラスごとの precision/recall/f1）

    Args:
        model: 学習済みモデル
        X_test: テスト特徴量
        y_test: テストラベル
    """
    from sklearn.metrics import classification_report, confusion_matrix

    y_pred = model.predict(X_test)

    print("\n【分類レポート（艇番別）】")
    target_names = [f"{i+1}号艇" for i in range(6)]
    print(classification_report(y_test, y_pred, target_names=target_names))

    # 混同行列
    cm = confusion_matrix(y_test, y_pred)
    print("【混同行列】（行=実際, 列=予測）")
    cm_df = pd.DataFrame(cm, index=target_names, columns=target_names)
    print(cm_df.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="競艇AIモデル分析")
    parser.add_argument(
        "--model-name", type=str, default="boat_race_model", help="分析するモデル名"
    )
    parser.add_argument(
        "--save-dir", type=str, default="output/analysis", help="出力ディレクトリ"
    )
    parser.add_argument(
        "--n-races", type=int, default=500, help="評価用サンプルレース数"
    )
    args = parser.parse_args()

    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # モデルをロード
    try:
        model = load_model(args.model_name)
    except FileNotFoundError:
        print(
            "モデルが見つかりません。先に学習を実行してください:\n"
            "  python scripts/train_model.py --use-sample"
        )
        sys.exit(1)

    # 評価データ生成
    logger.info(f"評価用サンプルデータを生成します（{args.n_races} レース）")
    df = preprocess_dataframe(generate_sample_training_data(n_races=args.n_races))

    # 学習/テスト分割（後半20%をテスト用）
    n_test = int(len(df) * 0.2)
    test_df = df.iloc[-n_test:]
    X_test = test_df[FEATURE_COLUMNS].values
    y_test = test_df["label"].values.astype(int)

    print(f"\n評価データ: {len(test_df)} 行（{n_test // 6} レース）")

    # 分析実行
    plot_feature_importance(model, save_dir)
    plot_calibration(model, X_test, y_test, save_dir)
    print_classification_report(model, X_test, y_test)

    print(f"\n全グラフを {save_dir}/ に保存しました")


if __name__ == "__main__":
    main()
