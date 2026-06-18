"""
モデル学習モジュール
LightGBMを使った競艇1着予測モデルの学習・保存を担当する
"""
import json
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import StratifiedKFold

from app.model.features import FEATURE_COLUMNS, N_BOATS
from app.utils.logger import get_logger

logger = get_logger(__name__)

# モデル保存ディレクトリ
MODEL_DIR = Path("models")

# LightGBM ハイパーパラメータ
LGBM_PARAMS = {
    "objective": "multiclass",      # 多クラス分類
    "num_class": N_BOATS,
    "metric": "multi_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "max_depth": -1,                 # 無制限
    "learning_rate": 0.05,
    "n_estimators": 500,
    "feature_fraction": 0.8,        # 列サブサンプリング
    "bagging_fraction": 0.8,        # 行サブサンプリング
    "bagging_freq": 5,
    "min_child_samples": 20,
    "reg_alpha": 0.1,               # L1正則化
    "reg_lambda": 0.1,              # L2正則化
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,                  # ログ非表示
}


def train_model(
    df: pd.DataFrame,
    model_name: str = "boat_race_model",
    n_splits: int = 5,
    early_stopping_rounds: int = 50,
) -> tuple[lgb.LGBMClassifier, dict]:
    """
    LightGBMモデルを学習する

    Args:
        df: 前処理済みの学習用DataFrame（FEATURE_COLUMNS + "label" カラムを含む）
        model_name: 保存するモデルのファイル名（拡張子なし）
        n_splits: Cross Validationの分割数
        early_stopping_rounds: Early Stoppingのラウンド数

    Returns:
        (学習済みモデル, 評価メトリクス辞書) のタプル
    """
    logger.info(f"モデル学習を開始します: {model_name}")

    # 特徴量・ラベル分離（DataFrameのまま保持して feature_names_in_ を正しく設定）
    X = df[FEATURE_COLUMNS]
    y = df["label"].values.astype(int)

    logger.info(f"学習データ shape: X={X.shape}, y={y.shape}")
    logger.info(f"クラス分布: {np.bincount(y)}")

    # Stratified K-Fold CV で汎化性能を評価
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    cv_logloss = []
    cv_accuracy = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[
                lgb.early_stopping(early_stopping_rounds, verbose=False),
                lgb.log_evaluation(period=-1),  # コールバック形式でログ抑制
            ],
        )

        # バリデーション評価
        y_pred_proba = model.predict_proba(X_val)
        y_pred = model.predict(X_val)
        fold_logloss = log_loss(y_val, y_pred_proba)
        fold_acc = accuracy_score(y_val, y_pred)
        cv_logloss.append(fold_logloss)
        cv_accuracy.append(fold_acc)
        logger.info(
            f"Fold {fold+1}/{n_splits} - logloss: {fold_logloss:.4f}, accuracy: {fold_acc:.4f}"
        )

    # 全データで最終モデルを学習
    logger.info("全データで最終モデルを学習中...")
    final_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    final_model.fit(X, y)

    metrics = {
        "cv_logloss_mean": float(np.mean(cv_logloss)),
        "cv_logloss_std": float(np.std(cv_logloss)),
        "cv_accuracy_mean": float(np.mean(cv_accuracy)),
        "cv_accuracy_std": float(np.std(cv_accuracy)),
        "n_samples": int(len(df)),
        "feature_columns": FEATURE_COLUMNS,
    }
    logger.info(
        f"CV結果 - logloss: {metrics['cv_logloss_mean']:.4f} ± {metrics['cv_logloss_std']:.4f}"
    )

    # モデルと設定を保存
    save_model(final_model, model_name, metrics)

    return final_model, metrics


def save_model(
    model: lgb.LGBMClassifier,
    model_name: str,
    metrics: dict | None = None,
) -> None:
    """
    モデルと評価メトリクスをファイルに保存する

    Args:
        model: 学習済みLGBMClassifier
        model_name: 保存ファイル名（拡張子なし）
        metrics: 評価メトリクス辞書（任意）
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / f"{model_name}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    logger.info(f"モデルを保存しました: {model_path}")

    if metrics:
        metrics_path = MODEL_DIR / f"{model_name}_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        logger.info(f"メトリクスを保存しました: {metrics_path}")


def load_model(model_name: str = "boat_race_model") -> lgb.LGBMClassifier:
    """
    保存済みモデルを読み込む

    Args:
        model_name: 読み込むモデルのファイル名（拡張子なし）

    Returns:
        読み込んだ LGBMClassifier

    Raises:
        FileNotFoundError: モデルファイルが存在しない場合
    """
    model_path = MODEL_DIR / f"{model_name}.pkl"
    if not model_path.exists():
        raise FileNotFoundError(
            f"モデルファイルが見つかりません: {model_path}. "
            "先に train_model.py を実行してください。"
        )

    with open(model_path, "rb") as f:
        model = pickle.load(f)
    logger.info(f"モデルを読み込みました: {model_path}")
    return model
