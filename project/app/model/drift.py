"""
モデルドリフト検知モジュール
本番予測分布の統計的変化を監視し、再学習が必要かを判定する

ドリフトの種類:
  - Covariate Shift : 入力特徴量の分布が変化（例: 天候・オッズの傾向変化）
  - Label Shift     : 正解ラベル（着順）の分布が変化
  - Prediction Drift: 予測確率の分布が変化（モデル劣化のサイン）

検知手法:
  - PSI (Population Stability Index) : 分布変化の定量指標
    PSI < 0.1  → 安定
    PSI < 0.2  → 軽微な変化（要注意）
    PSI >= 0.2 → 大きな変化（再学習推奨）
  - KL ダイバージェンス : 確率分布の差異

使い方:
  from app.model.drift import DriftDetector

  detector = DriftDetector()
  detector.set_reference(reference_df)   # 学習時の特徴量分布を登録

  # 本番データで検査
  report = detector.check(production_df)
  if report["needs_retraining"]:
      notify_slack("モデルドリフト検知: 再学習を推奨します")
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.model.features import FEATURE_COLUMNS
from app.utils.logger import get_logger

logger = get_logger(__name__)

DRIFT_REPORT_DIR = Path("data/drift_reports")
REFERENCE_FILE   = Path("models/drift_reference.json")

# PSI 判定閾値
PSI_WARN    = 0.1   # 要注意
PSI_ALERT   = 0.2   # 再学習推奨


@dataclass
class FeatureDriftResult:
    """1特徴量のドリフト検査結果"""
    feature: str
    psi: float
    kl_divergence: float
    status: str       # "stable" / "warn" / "alert"
    reference_mean: float
    current_mean: float
    mean_shift_pct: float   # 平均値の変化率 (%)


@dataclass
class DriftReport:
    """ドリフト検査レポート全体"""
    checked_at: str
    n_reference: int
    n_current: int
    feature_results: List[FeatureDriftResult] = field(default_factory=list)
    needs_retraining: bool = False
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "checked_at": self.checked_at,
            "n_reference": self.n_reference,
            "n_current": self.n_current,
            "needs_retraining": self.needs_retraining,
            "summary": self.summary,
            "features": [
                {
                    "feature": r.feature,
                    "psi": round(r.psi, 4),
                    "kl_divergence": round(r.kl_divergence, 4),
                    "status": r.status,
                    "reference_mean": round(r.reference_mean, 4),
                    "current_mean": round(r.current_mean, 4),
                    "mean_shift_pct": round(r.mean_shift_pct, 2),
                }
                for r in self.feature_results
            ],
        }


class DriftDetector:
    """
    特徴量ドリフト検知クラス

    学習時の特徴量分布（参照分布）と
    本番での特徴量分布（現在分布）を比較してドリフトを検知する
    """

    def __init__(self, n_bins: int = 10) -> None:
        """
        Args:
            n_bins: PSI計算に使うヒストグラムのビン数
        """
        self.n_bins = n_bins
        self._reference_stats: Dict[str, Dict] = {}

    # ---- 参照分布の登録 ----

    def set_reference(self, df: pd.DataFrame) -> None:
        """
        学習データから参照分布を設定・保存する

        Args:
            df: 学習用DataFrame（FEATURE_COLUMNS を含む）
        """
        self._reference_stats = {}
        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                continue
            values = df[col].dropna().values.astype(float)
            if len(values) == 0:
                continue

            hist, bin_edges = np.histogram(values, bins=self.n_bins, density=True)
            self._reference_stats[col] = {
                "mean":      float(values.mean()),
                "std":       float(values.std()),
                "min":       float(values.min()),
                "max":       float(values.max()),
                "hist":      hist.tolist(),
                "bin_edges": bin_edges.tolist(),
                "n":         len(values),
            }

        # ファイルに保存（次回起動時に再利用）
        REFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REFERENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._reference_stats, f, ensure_ascii=False, indent=2)

        logger.info(
            f"参照分布を保存しました: {REFERENCE_FILE} "
            f"({len(self._reference_stats)} 特徴量)"
        )

    def load_reference(self) -> bool:
        """
        保存済みの参照分布を読み込む

        Returns:
            True=読み込み成功, False=ファイルなし
        """
        if not REFERENCE_FILE.exists():
            logger.warning(f"参照分布ファイルが見つかりません: {REFERENCE_FILE}")
            return False

        with open(REFERENCE_FILE, encoding="utf-8") as f:
            self._reference_stats = json.load(f)
        logger.info(f"参照分布を読み込みました: {len(self._reference_stats)} 特徴量")
        return True

    # ---- ドリフト検査 ----

    def check(self, df: pd.DataFrame) -> DriftReport:
        """
        現在データの特徴量分布を参照分布と比較する

        Args:
            df: 本番データのDataFrame（FEATURE_COLUMNS を含む）

        Returns:
            DriftReport
        """
        from datetime import datetime

        if not self._reference_stats:
            if not self.load_reference():
                logger.error("参照分布がありません。先に set_reference() を呼んでください。")
                return DriftReport(
                    checked_at=datetime.now().isoformat(),
                    n_reference=0,
                    n_current=len(df),
                    needs_retraining=False,
                    summary="参照分布未設定のためチェック不可",
                )

        results: List[FeatureDriftResult] = []
        alert_features: List[str] = []
        warn_features:  List[str] = []

        for col, ref_stats in self._reference_stats.items():
            if col not in df.columns:
                continue

            current_values = df[col].dropna().values.astype(float)
            if len(current_values) == 0:
                continue

            psi, kl = self._calc_psi_kl(current_values, ref_stats)
            status = _psi_status(psi)
            current_mean = float(current_values.mean())
            ref_mean = ref_stats["mean"]
            mean_shift = ((current_mean - ref_mean) / (ref_mean + 1e-9)) * 100

            result = FeatureDriftResult(
                feature=col,
                psi=psi,
                kl_divergence=kl,
                status=status,
                reference_mean=ref_mean,
                current_mean=current_mean,
                mean_shift_pct=mean_shift,
            )
            results.append(result)

            if status == "alert":
                alert_features.append(col)
            elif status == "warn":
                warn_features.append(col)

        needs_retraining = len(alert_features) > 0
        if alert_features:
            summary = f"ドリフト検知: {', '.join(alert_features)} で大きな変化（PSI>=0.2）"
        elif warn_features:
            summary = f"軽微なドリフト: {', '.join(warn_features)} で変化（PSI>=0.1）"
        else:
            summary = "ドリフトなし: 全特徴量が安定しています"

        logger.info(summary)

        report = DriftReport(
            checked_at=datetime.now().isoformat(),
            n_reference=list(self._reference_stats.values())[0]["n"] if self._reference_stats else 0,
            n_current=len(df),
            feature_results=results,
            needs_retraining=needs_retraining,
            summary=summary,
        )

        # レポートをファイルに保存
        self._save_report(report)
        return report

    def _calc_psi_kl(
        self,
        current_values: np.ndarray,
        ref_stats: Dict,
    ) -> Tuple[float, float]:
        """
        PSI と KL ダイバージェンスを計算する

        Args:
            current_values: 現在データの値配列
            ref_stats: 参照分布の統計情報

        Returns:
            (PSI, KL divergence)
        """
        bin_edges = np.array(ref_stats["bin_edges"])

        # 参照分布ヒストグラム
        ref_hist = np.array(ref_stats["hist"])
        ref_hist = np.clip(ref_hist, 1e-8, None)  # ゼロ除算防止
        ref_hist = ref_hist / ref_hist.sum()

        # 現在分布ヒストグラム（参照と同じビンで計算）
        cur_hist, _ = np.histogram(current_values, bins=bin_edges, density=True)
        cur_hist = np.clip(cur_hist, 1e-8, None)
        cur_hist = cur_hist / cur_hist.sum()

        # PSI = Σ (actual% - expected%) * ln(actual% / expected%)
        psi = float(np.sum((cur_hist - ref_hist) * np.log(cur_hist / ref_hist)))

        # KL ダイバージェンス = Σ p * log(p / q)
        kl = float(np.sum(cur_hist * np.log(cur_hist / ref_hist)))

        return abs(psi), max(0.0, kl)

    def _save_report(self, report: DriftReport) -> None:
        """ドリフトレポートをJSONファイルに保存する"""
        DRIFT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = report.checked_at.replace(":", "-").replace(".", "-")
        path = DRIFT_REPORT_DIR / f"drift_{timestamp}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        logger.debug(f"ドリフトレポートを保存: {path}")

    def print_report(self, report: DriftReport) -> None:
        """ドリフトレポートをコンソールに表示する"""
        print(f"\n{'='*60}")
        print(f" ドリフト検査レポート  {report.checked_at}")
        print(f"{'='*60}")
        print(f" 参照サンプル数: {report.n_reference:,}  現在: {report.n_current:,}")
        print(f" 結論: {report.summary}")
        print(f" 再学習推奨: {'YES ⚠' if report.needs_retraining else 'NO ✓'}")
        print(f"{'='*60}")
        print(f" {'特徴量':<20} {'PSI':>7} {'KL':>7} {'平均変化':>9} {'状態':>7}")
        print("-" * 60)
        for r in sorted(report.feature_results, key=lambda x: x.psi, reverse=True):
            icon = {"stable": "✓", "warn": "△", "alert": "⚠"}[r.status]
            print(
                f" {r.feature:<20} {r.psi:>7.4f} {r.kl_divergence:>7.4f} "
                f"{r.mean_shift_pct:>+8.1f}% {icon:>7}"
            )
        print("=" * 60)


# ---- ユーティリティ ----

def _psi_status(psi: float) -> str:
    """PSI 値を stable / warn / alert に分類する"""
    if psi >= PSI_ALERT:
        return "alert"
    if psi >= PSI_WARN:
        return "warn"
    return "stable"
