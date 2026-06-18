"""
自動再学習スクリプト
ドリフト検知 → 再学習 → バージョン登録 → (自動昇格) → 通知

実行例:
  # ドリフトを検知したとき自動で再学習
  python scripts/auto_retrain.py

  # ドリフトに関わらず強制実行
  python scripts/auto_retrain.py --force

  # 再学習後に自動で本番昇格
  python scripts/auto_retrain.py --auto-promote

  # 既存 CSV を使って再学習
  python scripts/auto_retrain.py --data-path data/training.csv --force
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model.drift import DriftDetector
from app.model.features import generate_sample_training_data, preprocess_dataframe
from app.model.train import train_model
from app.model.versioning import ModelRegistry
from app.utils.logger import get_logger
from app.utils.notification import build_retrain_summary, notify_sync

logger = get_logger(__name__)


# ============================================================
# ドリフト判定
# ============================================================

def check_drift(data_path: str | None, n_races: int) -> tuple[bool, dict]:
    """
    現在データのドリフトを検査する。

    Returns:
        (needs_retraining, report_dict)
    """
    detector = DriftDetector()

    # 参照分布（過去データを模したサンプル）
    ref_df = preprocess_dataframe(generate_sample_training_data(n_races=2000))
    detector.set_reference(ref_df)

    # 現在データ
    if data_path:
        from app.data.loader import load_training_data
        current_df = load_training_data(file_path=data_path)
    else:
        current_df = preprocess_dataframe(generate_sample_training_data(n_races=n_races))

    report = detector.check(current_df)
    return report.needs_retraining, {
        "needs_retraining": report.needs_retraining,
        "n_alerts":         sum(
            1 for r in report.feature_results if r.status == "alert"
        ),
        "n_features":       len(report.feature_results),
    }


# ============================================================
# 学習・登録・昇格
# ============================================================

def run_training(data_path: str | None, n_races: int, n_splits: int, notes: str):
    """モデルを学習してレジストリに登録する。登録バージョン名を返す。"""
    if data_path:
        from app.data.loader import load_training_data
        df = load_training_data(file_path=data_path)
    else:
        df = preprocess_dataframe(generate_sample_training_data(n_races=n_races))

    logger.info(f"学習データ: {len(df)} 行")

    model, metrics = train_model(df, model_name="boat_race_model", n_splits=n_splits)

    logger.info(
        f"学習完了 — CV LogLoss: {metrics['cv_logloss_mean']:.4f} ± "
        f"{metrics['cv_logloss_std']:.4f}"
    )

    registry = ModelRegistry()
    version = registry.register(model, metrics, notes=notes)
    logger.info(f"レジストリ登録: {version}")
    return version, metrics


def promote_version(version: str) -> None:
    """指定バージョンを本番に昇格する。"""
    registry = ModelRegistry()
    registry.promote(version)
    logger.info(f"本番昇格完了: {version}")


# ============================================================
# 通知
# ============================================================

def _send_notification(version: str, metrics: dict, drift_info: dict) -> None:
    """Slack / LINE に再学習完了通知を送る（失敗は握りつぶす）。"""
    try:
        alerts = drift_info.get("n_alerts", 0)
        trigger = f"ドリフト検知 ({alerts}特徴量でアラート)" if drift_info.get(
            "needs_retraining"
        ) else "手動実行"
        extra = f"\n\nトリガー: {trigger}"
        msg = build_retrain_summary(version, metrics) + extra
        results = notify_sync(msg)
        if results:
            logger.info(f"通知送信: {results}")
    except Exception as exc:
        logger.warning(f"通知送信失敗（再学習は成功）: {exc}")


# ============================================================
# エントリーポイント
# ============================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="自動再学習スクリプト")
    p.add_argument(
        "--force", action="store_true",
        help="ドリフト未検知でも強制再学習",
    )
    p.add_argument(
        "--auto-promote", action="store_true",
        help="学習後に自動で本番昇格",
    )
    p.add_argument(
        "--data-path", default=None,
        help="学習 CSV パス（省略時はサンプルデータ生成）",
    )
    p.add_argument(
        "--n-races", type=int, default=2000,
        help="サンプルデータのレース数（--data-path 未指定時）",
    )
    p.add_argument(
        "--n-splits", type=int, default=5,
        help="CV 分割数",
    )
    p.add_argument(
        "--notes", default="",
        help="バージョン備考",
    )
    p.add_argument(
        "--no-notify", action="store_true",
        help="完了通知を送らない",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("=== 自動再学習パイプライン開始 ===")

    # ---- ドリフト検査 ----
    logger.info("ドリフトを検査しています...")
    needs_retrain, drift_info = check_drift(args.data_path, args.n_races)

    if not needs_retrain and not args.force:
        logger.info(
            f"ドリフト未検知 (アラート特徴量: {drift_info['n_alerts']} / "
            f"{drift_info['n_features']}) — 再学習は不要です。"
        )
        logger.info("強制実行するには --force を付けてください。")
        print("\n再学習スキップ（ドリフトなし）")
        return

    if needs_retrain:
        logger.info(
            f"ドリフト検知: {drift_info['n_alerts']} 特徴量でアラート → 再学習を開始します"
        )
    else:
        logger.info("--force 指定により再学習を強制実行します")

    # ---- 再学習 ----
    notes = args.notes or (
        "自動再学習 (ドリフト検知)" if needs_retrain else "自動再学習 (強制)"
    )
    version, metrics = run_training(
        args.data_path, args.n_races, args.n_splits, notes
    )

    # ---- 自動昇格 ----
    if args.auto_promote:
        promote_version(version)
        print(f"\n✓ 本番モデルを更新しました: {version}")
    else:
        print(
            f"\n学習完了: {version}\n"
            f"本番昇格するには: python scripts/promote_model.py --version {version}"
        )

    # ---- 通知 ----
    if not args.no_notify:
        _send_notification(version, metrics, drift_info)

    logger.info("=== 自動再学習パイプライン完了 ===")


if __name__ == "__main__":
    main()
