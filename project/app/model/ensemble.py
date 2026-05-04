"""
アンサンブルモデルモジュール
複数の学習済みモデルを組み合わせて予測精度を向上させる

対応手法:
  - Averaging   : 各モデルの確率平均（シンプルで安定）
  - Weighted    : 検証スコアを重みにした加重平均
  - Stacking    : メタモデルで出力を統合（要追加学習）

使い方:
  from app.model.ensemble import EnsemblePredictor

  ens = EnsemblePredictor()
  ens.add_model("lgbm_v1", model1, weight=0.6)
  ens.add_model("lgbm_v2", model2, weight=0.4)

  proba = ens.predict_proba(X)   # shape: (n_samples, 6)
"""
from dataclasses import dataclass
from typing import List, Optional

import lightgbm as lgb
import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ModelEntry:
    """アンサンブルに含まれる1モデルのメタデータ"""
    name: str
    model: lgb.LGBMClassifier
    weight: float = 1.0
    cv_logloss: Optional[float] = None


class EnsemblePredictor:
    """
    複数 LGBMClassifier のアンサンブル予測器

    Attributes:
        models: 登録済みモデルリスト
        method: アンサンブル手法 ("average" / "weighted")
    """

    def __init__(self, method: str = "weighted") -> None:
        """
        Args:
            method: "average"（単純平均）or "weighted"（重み付き平均）
        """
        if method not in ("average", "weighted"):
            raise ValueError(f"method は 'average' または 'weighted' を指定してください: {method}")
        self.method = method
        self._models: List[ModelEntry] = []

    def add_model(
        self,
        name: str,
        model: lgb.LGBMClassifier,
        weight: float = 1.0,
        cv_logloss: Optional[float] = None,
    ) -> None:
        """
        アンサンブルにモデルを追加する

        Args:
            name: モデル識別名
            model: 学習済み LGBMClassifier
            weight: 重み（weighted モード時に使用）
            cv_logloss: CV Log Loss（weighted モードで自動重み計算に使用）
        """
        if cv_logloss is not None:
            # Log Loss が小さいほど重みを大きく（逆数比例）
            weight = 1.0 / max(cv_logloss, 1e-6)

        self._models.append(ModelEntry(name=name, model=model, weight=weight, cv_logloss=cv_logloss))
        logger.info(f"モデルを追加しました: {name} (weight={weight:.4f})")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        アンサンブル確率予測を返す

        Args:
            X: 特徴量行列 shape=(n_samples, n_features)

        Returns:
            各クラスの確率行列 shape=(n_samples, 6)

        Raises:
            RuntimeError: モデルが1つも登録されていない場合
        """
        if not self._models:
            raise RuntimeError("モデルが1つも登録されていません。add_model() を呼んでください。")

        probas = np.array([entry.model.predict_proba(X) for entry in self._models])
        # probas shape: (n_models, n_samples, n_classes)

        if self.method == "average" or len(self._models) == 1:
            return probas.mean(axis=0)

        # 重み付き平均
        weights = np.array([entry.weight for entry in self._models])
        weights = weights / weights.sum()  # 正規化
        return np.average(probas, axis=0, weights=weights)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        最大確率クラスのラベルを返す

        Args:
            X: 特徴量行列

        Returns:
            予測ラベル配列 shape=(n_samples,)
        """
        return self.predict_proba(X).argmax(axis=1)

    def summary(self) -> None:
        """登録済みモデルの一覧を表示する"""
        total_weight = sum(e.weight for e in self._models)
        print(f"\n{'='*55}")
        print(f" アンサンブル ({self.method}モード) - {len(self._models)}モデル")
        print(f"{'='*55}")
        print(f"{'名前':<30} {'重み':>7} {'相対比率':>8} {'LogLoss':>9}")
        print("-" * 55)
        for e in self._models:
            ratio = e.weight / total_weight * 100
            ll = f"{e.cv_logloss:.4f}" if e.cv_logloss else "N/A"
            print(f"{e.name:<30} {e.weight:>7.4f} {ratio:>7.1f}% {ll:>9}")
        print("=" * 55)

    @classmethod
    def from_registry(
        cls,
        version_names: Optional[List[str]] = None,
        method: str = "weighted",
        top_n: int = 3,
    ) -> "EnsemblePredictor":
        """
        ModelRegistry から複数バージョンを読み込んでアンサンブルを構築する

        Args:
            version_names: 使用するバージョン名リスト（None なら上位 top_n を自動選択）
            method: アンサンブル手法
            top_n: 自動選択時に使用するバージョン数

        Returns:
            構築済み EnsemblePredictor
        """
        from app.model.versioning import ModelRegistry

        registry = ModelRegistry()
        ensemble = cls(method=method)

        if version_names is None:
            # LogLoss が小さい順に top_n 件を自動選択
            versions = registry.list_versions()
            sorted_versions = sorted(
                [v for v in versions if v.get("cv_logloss")],
                key=lambda v: v["cv_logloss"],
            )
            selected = sorted_versions[:top_n]
            if not selected:
                # フォールバック: 最新バージョンを使用
                selected = versions[-top_n:]
        else:
            selected = [
                v for v in registry.list_versions()
                if v["version"] in version_names
            ]

        if not selected:
            raise RuntimeError("有効なモデルバージョンが見つかりません。先にモデルを学習してください。")

        for v in selected:
            try:
                model = registry.load_version(v["version"])
                ensemble.add_model(
                    name=v["version"],
                    model=model,
                    cv_logloss=v.get("cv_logloss"),
                )
            except FileNotFoundError:
                logger.warning(f"バージョンファイルが見つかりません: {v['version']}")

        ensemble.summary()
        return ensemble
