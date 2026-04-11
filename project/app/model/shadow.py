"""
シャドウモードモジュール
本番モデルの予測に影響を与えず、新モデルをサイレント実行して比較する

仕組み:
  - リクエストを本番モデルで処理し、結果をそのまま返す
  - バックグラウンドで候補モデルも実行し、差分を記録する
  - 一定のサンプリングレートで実行（100%だとCPU負荷が増大）

使い方:
  from app.model.shadow import ShadowRunner

  runner = ShadowRunner(shadow_model, sample_rate=0.1)  # 10%サンプリング

  # FastAPI BackgroundTasks で非同期実行
  background_tasks.add_task(
      runner.run_shadow, X, race_id, production_proba
  )
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)

SHADOW_LOG_DIR = Path("data/shadow_logs")


@dataclass
class ShadowRecord:
    """シャドウ実行の1レコード"""
    race_id: str
    prod_top1: int          # 本番モデルの1位予測（0始まり）
    shadow_top1: int        # シャドウモデルの1位予測（0始まり）
    prod_proba: list        # 本番モデルの確率ベクトル
    shadow_proba: list      # シャドウモデルの確率ベクトル
    kl_divergence: float    # KL ダイバージェンス（分布の乖離度）
    top1_match: bool        # 1位予測が一致しているか
    shadow_latency_ms: float


class ShadowRunner:
    """
    シャドウ実行器

    Args:
        shadow_model: 評価対象の新モデル（predict_proba メソッドを持つ）
        sample_rate: 実行するリクエストの割合（0.0〜1.0）
        name: ログファイル名の識別子
    """

    def __init__(
        self,
        shadow_model: object,
        sample_rate: float = 0.1,
        name: str = "shadow",
    ) -> None:
        self.shadow_model = shadow_model
        self.sample_rate = sample_rate
        self.name = name

        # 累積統計
        self._n_sampled = 0
        self._n_top1_match = 0
        self._kl_sum = 0.0

    def _should_run(self, race_id: str) -> bool:
        """決定論的サンプリング: race_id のハッシュでサンプリング判定"""
        h = int(hashlib.md5(race_id.encode()).hexdigest(), 16)
        return (h % 10000) / 10000.0 < self.sample_rate

    @staticmethod
    def _kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
        """KL ダイバージェンス D_KL(p || q) を計算する"""
        p = np.clip(p / p.sum(), 1e-9, 1.0)
        q = np.clip(q / q.sum(), 1e-9, 1.0)
        return float(np.sum(p * np.log(p / q)))

    def run_shadow(
        self,
        X: np.ndarray,
        race_id: str,
        production_proba: np.ndarray,
    ) -> Optional[ShadowRecord]:
        """
        シャドウモデルを実行して差分を記録する

        Args:
            X: 特徴量行列 shape=(6, n_features)
            race_id: レースID（サンプリング判定に使用）
            production_proba: 本番モデルの予測確率行列 shape=(6, 6)

        Returns:
            ShadowRecord（サンプリングされなかった場合は None）
        """
        if not self._should_run(race_id):
            return None

        try:
            start = time.monotonic()
            shadow_proba = self.shadow_model.predict_proba(X)
            latency_ms = (time.monotonic() - start) * 1000

            # 1着確率ベクトル（shape=(6,)）
            prod_win = production_proba[:, 0]
            shadow_win = shadow_proba[:, 0]

            prod_top1 = int(np.argmax(prod_win))
            shadow_top1 = int(np.argmax(shadow_win))
            kl = self._kl_divergence(prod_win, shadow_win)

            record = ShadowRecord(
                race_id=race_id,
                prod_top1=prod_top1,
                shadow_top1=shadow_top1,
                prod_proba=prod_win.tolist(),
                shadow_proba=shadow_win.tolist(),
                kl_divergence=kl,
                top1_match=(prod_top1 == shadow_top1),
                shadow_latency_ms=latency_ms,
            )

            # 統計更新
            self._n_sampled += 1
            if record.top1_match:
                self._n_top1_match += 1
            self._kl_sum += kl

            self._save_record(record)

            logger.debug(
                f"[Shadow] race={race_id} match={record.top1_match} "
                f"KL={kl:.4f} latency={latency_ms:.1f}ms"
            )
            return record

        except Exception as e:
            logger.error(f"[Shadow] 実行エラー race={race_id}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """累積統計を返す"""
        if self._n_sampled == 0:
            return {"n_sampled": 0, "top1_match_rate": None, "avg_kl": None}
        return {
            "n_sampled": self._n_sampled,
            "top1_match_rate": round(self._n_top1_match / self._n_sampled, 4),
            "avg_kl_divergence": round(self._kl_sum / self._n_sampled, 6),
            "sample_rate": self.sample_rate,
        }

    def print_stats(self) -> None:
        """統計をコンソールに表示する"""
        stats = self.get_stats()
        print(f"\n{'='*50}")
        print(f" シャドウモード統計: {self.name}")
        print(f"{'='*50}")
        print(f" サンプル数   : {stats['n_sampled']}")
        if stats["top1_match_rate"] is not None:
            print(f" 1位一致率    : {stats['top1_match_rate']*100:.1f}%")
            print(f" 平均KL距離   : {stats['avg_kl_divergence']:.6f}")
        print("=" * 50)

    def _save_record(self, record: ShadowRecord) -> None:
        """JSONL ファイルに追記保存する"""
        SHADOW_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = SHADOW_LOG_DIR / f"{self.name}.jsonl"
        entry = {
            "race_id": record.race_id,
            "prod_top1": record.prod_top1,
            "shadow_top1": record.shadow_top1,
            "kl_divergence": record.kl_divergence,
            "top1_match": record.top1_match,
            "shadow_latency_ms": record.shadow_latency_ms,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @classmethod
    def from_registry(
        cls,
        shadow_version: str,
        sample_rate: float = 0.1,
        name: str = "shadow",
    ) -> "ShadowRunner":
        """
        ModelRegistry から特定バージョンをシャドウモデルとしてロードする

        Args:
            shadow_version: 評価したいモデルのバージョン名
            sample_rate: サンプリングレート
            name: ログ識別名

        Returns:
            設定済み ShadowRunner
        """
        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()
        model = registry.load_version(shadow_version)
        return cls(shadow_model=model, sample_rate=sample_rate, name=name)
