"""
モデルバージョン管理モジュール
学習するたびにバージョン付きでモデルを保存し、
ロールバック・比較ができるようにする

バージョン命名規則: boat_race_model_v{YYYYMMDD}_{n}
  例: boat_race_model_v20240415_1

使い方:
  from app.model.versioning import ModelRegistry

  registry = ModelRegistry()
  # 学習済みモデルを登録
  version = registry.register(model, metrics)

  # 本番モデルに昇格
  registry.promote(version)

  # 本番モデルを取得
  model = registry.load_production()

  # バージョン一覧
  registry.list_versions()

  # ロールバック
  registry.promote("boat_race_model_v20240401_1")
"""
import json
import pickle
import shutil
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import lightgbm as lgb

from app.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path("models")
REGISTRY_FILE = MODEL_DIR / "registry.json"

# 本番モデルのシンボリックファイル名（predict.py がこれを読む）
PRODUCTION_MODEL = "boat_race_model"


class ModelRegistry:
    """
    モデルのバージョン管理レジストリ

    models/
    ├── boat_race_model.pkl          ← 本番（シンボリックコピー）
    ├── boat_race_model_metrics.json
    ├── versions/
    │   ├── boat_race_model_v20240415_1.pkl
    │   ├── boat_race_model_v20240415_1_metrics.json
    │   └── boat_race_model_v20240422_1.pkl
    └── registry.json                ← バージョン管理台帳
    """

    def __init__(self) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        (MODEL_DIR / "versions").mkdir(exist_ok=True)
        self._registry = self._load_registry()

    # ---- レジストリ読み書き ----

    def _load_registry(self) -> Dict[str, Any]:
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE, encoding="utf-8") as f:
                return json.load(f)
        return {"production": None, "versions": []}

    def _save_registry(self) -> None:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, ensure_ascii=False, indent=2)

    # ---- バージョン登録 ----

    def register(
        self,
        model: lgb.LGBMClassifier,
        metrics: Dict[str, Any],
        notes: str = "",
    ) -> str:
        """
        学習済みモデルをバージョン付きで登録する

        Args:
            model: 学習済み LGBMClassifier
            metrics: 評価メトリクス辞書
            notes: 備考（データ期間・変更内容など）

        Returns:
            付与されたバージョン文字列（例: "boat_race_model_v20240415_1"）
        """
        today = date.today().strftime("%Y%m%d")

        # 同日に複数バージョンがある場合は連番を増やす
        existing_today = [
            v["version"] for v in self._registry["versions"]
            if v["version"].startswith(f"boat_race_model_v{today}_")
        ]
        seq = len(existing_today) + 1
        version = f"boat_race_model_v{today}_{seq}"

        # モデルファイルを versions/ に保存
        version_dir = MODEL_DIR / "versions"
        model_path = version_dir / f"{version}.pkl"
        metrics_path = version_dir / f"{version}_metrics.json"

        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        meta = {**metrics, "version": version, "notes": notes}
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # レジストリ更新
        self._registry["versions"].append({
            "version": version,
            "cv_logloss": metrics.get("cv_logloss_mean"),
            "cv_accuracy": metrics.get("cv_accuracy_mean"),
            "n_samples": metrics.get("n_samples"),
            "notes": notes,
            "is_production": False,
        })
        self._save_registry()

        logger.info(f"モデルを登録しました: {version}")
        return version

    # ---- 本番昇格 ----

    def promote(self, version: str) -> None:
        """
        指定バージョンを本番モデルとして昇格する
        （旧本番モデルのバックアップを自動取得）

        Args:
            version: 昇格するバージョン文字列

        Raises:
            FileNotFoundError: バージョンファイルが存在しない場合
        """
        src = MODEL_DIR / "versions" / f"{version}.pkl"
        if not src.exists():
            raise FileNotFoundError(f"バージョンが見つかりません: {src}")

        # 旧本番モデルをバックアップ
        prod_path = MODEL_DIR / f"{PRODUCTION_MODEL}.pkl"
        if prod_path.exists():
            backup = MODEL_DIR / f"{PRODUCTION_MODEL}_backup.pkl"
            shutil.copy2(prod_path, backup)
            logger.info(f"旧本番モデルをバックアップ: {backup}")

        # 本番モデルファイルを上書き
        shutil.copy2(src, prod_path)

        # メトリクスも上書き
        src_metrics = MODEL_DIR / "versions" / f"{version}_metrics.json"
        if src_metrics.exists():
            shutil.copy2(src_metrics, MODEL_DIR / f"{PRODUCTION_MODEL}_metrics.json")

        # レジストリの is_production フラグを更新
        for v in self._registry["versions"]:
            v["is_production"] = (v["version"] == version)
        self._registry["production"] = version
        self._save_registry()

        # キャッシュ済みモデルをクリア（次回リクエストで再ロード）
        try:
            import app.model.predict as predict_module
            predict_module._cached_model = None
            logger.info("モデルキャッシュをリセットしました（次回予測時に再ロード）")
        except Exception:
            pass

        logger.info(f"本番モデルを更新しました: {version}")

    # ---- ロード ----

    def load_production(self) -> lgb.LGBMClassifier:
        """本番モデルを読み込む"""
        from app.model.train import load_model
        return load_model(PRODUCTION_MODEL)

    def load_version(self, version: str) -> lgb.LGBMClassifier:
        """
        指定バージョンのモデルを読み込む

        Args:
            version: バージョン文字列

        Returns:
            LGBMClassifier
        """
        path = MODEL_DIR / "versions" / f"{version}.pkl"
        if not path.exists():
            raise FileNotFoundError(f"バージョンが見つかりません: {path}")
        with open(path, "rb") as f:
            model = pickle.load(f)
        logger.info(f"バージョンをロードしました: {version}")
        return model

    # ---- 一覧・情報表示 ----

    def list_versions(self) -> List[Dict[str, Any]]:
        """登録済みバージョン一覧を返す"""
        return self._registry.get("versions", [])

    def get_production_version(self) -> Optional[str]:
        """現在の本番バージョン文字列を返す"""
        return self._registry.get("production")

    def print_summary(self) -> None:
        """バージョン一覧をコンソールに表示する"""
        versions = self.list_versions()
        production = self.get_production_version()

        print(f"\n{'='*65}")
        print(f" モデルレジストリ  ( 本番: {production or 'なし'} )")
        print(f"{'='*65}")
        print(f"{'バージョン':<35} {'LogLoss':>8} {'Accuracy':>9} {'本番':>5}")
        print("-" * 65)
        for v in versions[-10:]:  # 最新10件
            prod_mark = "★" if v.get("is_production") else ""
            ll = f"{v['cv_logloss']:.4f}" if v.get("cv_logloss") else "N/A"
            acc = f"{v['cv_accuracy']:.4f}" if v.get("cv_accuracy") else "N/A"
            print(f"{v['version']:<35} {ll:>8} {acc:>9} {prod_mark:>5}")
        print("=" * 65)

    # ---- クリーンアップ ----

    def cleanup_old_versions(self, keep: int = 10) -> int:
        """
        古いバージョンを削除してディスクを節約する

        Args:
            keep: 保持する最新バージョン数（本番バージョンは常に保持）

        Returns:
            削除したファイル数
        """
        versions = self.list_versions()
        production = self.get_production_version()

        # 本番以外を古い順に並べる
        non_prod = [v for v in versions if not v.get("is_production")]
        to_delete = non_prod[:-keep] if len(non_prod) > keep else []

        deleted = 0
        for v in to_delete:
            ver = v["version"]
            for suffix in [".pkl", "_metrics.json"]:
                path = MODEL_DIR / "versions" / f"{ver}{suffix}"
                if path.exists():
                    path.unlink()
                    deleted += 1

        # レジストリから削除エントリを除去
        delete_names = {v["version"] for v in to_delete}
        self._registry["versions"] = [
            v for v in versions if v["version"] not in delete_names
        ]
        self._save_registry()

        logger.info(f"{len(to_delete)} バージョンを削除しました（{deleted} ファイル）")
        return deleted
