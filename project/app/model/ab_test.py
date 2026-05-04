"""
A/B テストモジュール
本番環境で複数モデルのバージョンを並行稼働させ、
予測精度・ユーザー反応を比較する

仕組み:
  - トラフィックを重みに従って分割し、各モデルへ振り分ける
  - 各リクエストの結果・レイテンシを記録する
  - 統計的有意性検定（Welch の t 検定）で勝者を判定する

使い方:
  from app.model.ab_test import ABTestRouter

  router = ABTestRouter()
  router.add_variant("control",    model_v1, traffic_weight=0.7)
  router.add_variant("challenger", model_v2, traffic_weight=0.3)

  # リクエスト時: race_id を基にモデルを決定論的に振り分け
  variant, proba = router.predict(X, race_id="race_001")

  # 結果を記録（レース終了後に正解ラベルを記録）
  router.record_result(race_id="race_001", true_winner=1)

  # 統計レポート
  router.print_report()
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.config import AB_LOG_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VariantRecord:
    """A/B テストの1バリアント設定"""
    name: str
    model: object
    traffic_weight: float
    # 累積統計
    n_requests: int = 0
    n_correct: int = 0           # 予測1位が正解だった件数
    total_latency_ms: float = 0.0
    log_loss_sum: float = 0.0


@dataclass
class ABTestReport:
    """A/B テスト統計レポート"""
    variants: List[Dict]
    winner: Optional[str]
    is_significant: bool     # 統計的有意差があるか
    p_value: float
    message: str


class ABTestRouter:
    """
    トラフィックを複数モデルに分割するルーター

    決定論的振り分け:
      race_id を MD5 ハッシュして 0〜1 に変換し、
      重み累積区間のどこに落ちるかでバリアントを選択する
      → 同じ race_id は常に同じバリアントに割り当てられる（一貫性保証）
    """

    def __init__(self, name: str = "default") -> None:
        """
        Args:
            name: このA/Bテストの識別名
        """
        self.name = name
        self._variants: List[VariantRecord] = []
        # race_id → (variant_name, true_winner) の記録
        self._race_log: Dict[str, Dict] = {}

    def add_variant(
        self,
        name: str,
        model: object,
        traffic_weight: float = 0.5,
    ) -> None:
        """
        バリアント（モデル）を追加する

        Args:
            name: バリアント名（"control" / "challenger" など）
            model: 予測モデル（predict_proba メソッドを持つ）
            traffic_weight: トラフィック配分の重み（合計は自動正規化）
        """
        self._variants.append(VariantRecord(
            name=name,
            model=model,
            traffic_weight=traffic_weight,
        ))
        logger.info(f"A/Bバリアント追加: {name} (weight={traffic_weight})")

    def _select_variant(self, race_id: str) -> VariantRecord:
        """
        race_id のハッシュ値からバリアントを決定論的に選択する

        Args:
            race_id: レースID（ハッシュシードとして使用）

        Returns:
            選択された VariantRecord
        """
        # ハッシュ値を 0.0〜1.0 に変換
        h = int(hashlib.md5(race_id.encode()).hexdigest(), 16)
        normalized = (h % 10000) / 10000.0

        # 重みを正規化して累積区間を作成
        total = sum(v.traffic_weight for v in self._variants)
        cumulative = 0.0
        for variant in self._variants:
            cumulative += variant.traffic_weight / total
            if normalized < cumulative:
                return variant

        return self._variants[-1]  # pragma: no cover  フォールバック（浮動小数点誤差対策）

    def predict(
        self,
        X: np.ndarray,
        race_id: str,
    ) -> Tuple[str, np.ndarray]:
        """
        race_id に基づいてバリアントを選択し、予測確率を返す

        Args:
            X: 特徴量行列 shape=(6, n_features)
            race_id: レースID（バリアント選択に使用）

        Returns:
            (バリアント名, 確率行列 shape=(6, 6))
        """
        import time

        if not self._variants:
            raise RuntimeError("バリアントが未登録です。add_variant() を呼んでください。")

        variant = self._select_variant(race_id)
        start = time.monotonic()
        proba = variant.model.predict_proba(X)
        latency_ms = (time.monotonic() - start) * 1000

        # 統計記録
        variant.n_requests += 1
        variant.total_latency_ms += latency_ms

        # レースログに記録（正解が来たら record_result() で更新）
        self._race_log[race_id] = {
            "variant": variant.name,
            "predicted_1st": int(np.argmax(proba[:, 0])),  # 1着予測
            "proba": proba[:, 0].tolist(),
            "latency_ms": latency_ms,
            "true_winner": None,
        }

        logger.debug(f"A/B選択: {variant.name} (race_id={race_id})")
        return variant.name, proba

    def record_result(self, race_id: str, true_winner: int) -> None:
        """
        レース結果（実際の1着艇番）を記録する

        Args:
            race_id: レースID
            true_winner: 実際の1着艇番（1〜6）
        """
        if race_id not in self._race_log:
            logger.warning(f"predict() が呼ばれていないレースです: {race_id}")
            return

        log = self._race_log[race_id]
        log["true_winner"] = true_winner

        # 正解判定（予測1位の艇番 == 実際の1着、0始まり→1始まり変換）
        predicted_boat = log["predicted_1st"] + 1
        is_correct = (predicted_boat == true_winner)

        # バリアントの統計を更新
        for variant in self._variants:
            if variant.name == log["variant"]:
                if is_correct:
                    variant.n_correct += 1
                # Log Loss の計算
                proba = np.array(log["proba"])
                proba = np.clip(proba / proba.sum(), 1e-9, 1.0)
                # 1着確率のみ使用する簡易 Log Loss
                winner_proba = proba[true_winner - 1]
                variant.log_loss_sum += -np.log(winner_proba)
                break

        # ファイルに追記保存（永続化）
        self._save_log_entry(race_id, log)

    def get_report(self) -> ABTestReport:
        """
        統計レポートを生成する（Welch の t 検定で有意差を判定）

        Returns:
            ABTestReport
        """
        from scipy import stats

        if len(self._variants) < 2:
            return ABTestReport(
                variants=[], winner=None,
                is_significant=False, p_value=1.0,
                message="バリアントが2つ以上必要です",
            )

        variant_stats = []
        for v in self._variants:
            hit_rate = v.n_correct / v.n_requests if v.n_requests > 0 else 0
            avg_latency = v.total_latency_ms / v.n_requests if v.n_requests > 0 else 0
            avg_logloss = v.log_loss_sum / v.n_requests if v.n_requests > 0 else 0

            variant_stats.append({
                "name": v.name,
                "n_requests": v.n_requests,
                "hit_rate": round(hit_rate, 4),
                "avg_latency_ms": round(avg_latency, 1),
                "avg_log_loss": round(avg_logloss, 4),
            })

        # 2バリアント間の的中率を比較（比率の差の検定）
        v0, v1 = self._variants[0], self._variants[1]
        p_value = 1.0
        winner = None
        is_significant = False

        if v0.n_requests >= 30 and v1.n_requests >= 30:
            # 比率の検定（二項分布近似 z 検定）
            p0 = v0.n_correct / v0.n_requests
            p1 = v1.n_correct / v1.n_requests
            n0, n1 = v0.n_requests, v1.n_requests
            p_pool = (v0.n_correct + v1.n_correct) / (n0 + n1)
            se = np.sqrt(p_pool * (1 - p_pool) * (1 / n0 + 1 / n1))
            if se > 0:
                z = (p0 - p1) / se
                p_value = float(2 * (1 - stats.norm.cdf(abs(z))))
                is_significant = p_value < 0.05

                if is_significant:
                    winner = v0.name if p0 > p1 else v1.name

        if is_significant and winner:
            message = f"統計的有意差あり (p={p_value:.4f}): {winner} が勝者"
        elif p_value < 0.1:
            better = v0.name if v0.n_correct / max(v0.n_requests, 1) > v1.n_correct / max(v1.n_requests, 1) else v1.name
            message = f"有意差なし (p={p_value:.4f}) - データ蓄積中。{better} がやや優勢"
        else:
            message = f"有意差なし (p={p_value:.4f}) - 引き続きデータを収集してください"

        return ABTestReport(
            variants=variant_stats,
            winner=winner,
            is_significant=is_significant,
            p_value=p_value,
            message=message,
        )

    def print_report(self) -> None:
        """統計レポートをコンソールに表示する"""
        report = self.get_report()

        print(f"\n{'='*60}")
        print(f" A/B テスト結果: {self.name}")
        print(f"{'='*60}")
        print(f" {'バリアント':<15} {'件数':>6} {'的中率':>8} {'LogLoss':>9} {'レイテンシ':>10}")
        print("-" * 60)
        for v in report.variants:
            print(
                f" {v['name']:<15} {v['n_requests']:>6} "
                f"{v['hit_rate']*100:>7.1f}% {v['avg_log_loss']:>9.4f} "
                f"{v['avg_latency_ms']:>9.1f}ms"
            )
        print("-" * 60)
        print(f" 判定: {report.message}")
        if report.winner:
            print(f" 勝者: {report.winner} ★")
        print("=" * 60)

    def _save_log_entry(self, race_id: str, log: Dict) -> None:
        """ログエントリをJSONLファイルに追記保存する"""
        AB_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = AB_LOG_DIR / f"{self.name}.jsonl"

        def _to_serializable(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        entry = {k: _to_serializable(v) for k, v in {"race_id": race_id, **log}.items()}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @classmethod
    def from_registry(
        cls,
        control_version: str,
        challenger_version: str,
        control_weight: float = 0.7,
        name: str = "model_ab_test",
    ) -> "ABTestRouter":
        """
        ModelRegistry から2バージョンを読み込んでA/Bテストを構築する

        Args:
            control_version: コントロールバージョン名
            challenger_version: チャレンジャーバージョン名
            control_weight: コントロールへのトラフィック割合
            name: テスト識別名

        Returns:
            設定済み ABTestRouter
        """
        from app.model.versioning import ModelRegistry
        registry = ModelRegistry()

        router = cls(name=name)
        router.add_variant(
            "control",
            registry.load_version(control_version),
            traffic_weight=control_weight,
        )
        router.add_variant(
            "challenger",
            registry.load_version(challenger_version),
            traffic_weight=1.0 - control_weight,
        )
        return router
