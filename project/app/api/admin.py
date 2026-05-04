"""
管理者用 API エンドポイント
モデル状態・A/Bテスト・シャドウモード・ドリフト情報をまとめて返す

エンドポイント:
  GET  /api/v1/admin/status          : システム全体ステータス
  GET  /api/v1/admin/models          : モデルバージョン一覧
  POST /api/v1/admin/models/promote  : モデル昇格
  GET  /api/v1/admin/drift           : 最新ドリフトレポート
  GET  /api/v1/admin/ab-test         : A/Bテスト統計
  GET  /api/v1/admin/shadow          : シャドウモード統計
"""
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import verify_api_key
from app.config import (
    AB_LOG_DIR,
    DRIFT_REPORT_DIR,
    SHADOW_LOG_DIR,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 管理者権限確認（通常の API Key 認証に加え ADMIN_KEY 環境変数で絞り込み可）
_ADMIN_KEY = os.getenv("ADMIN_API_KEY", "")


def verify_admin_key(api_key: str = Depends(verify_api_key)) -> str:
    """管理者 API Key を検証する（ADMIN_API_KEY 未設定時は通常認証と同等）"""
    if _ADMIN_KEY and api_key != _ADMIN_KEY:
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return api_key


# ============================================================
# レスポンス スキーマ
# ============================================================

class ModelVersionInfo(BaseModel):
    version: str
    registered_at: str
    cv_logloss_mean: float
    cv_accuracy_mean: float
    n_samples: int
    notes: Optional[str] = None
    is_production: bool = False


class SystemStatusResponse(BaseModel):
    status: str
    production_model: Optional[str]
    n_registered_versions: int
    prediction_store: Dict[str, Any]
    drift_status: Optional[str]
    ab_test_active: bool
    shadow_active: bool


class PromoteRequest(BaseModel):
    version: str


# ============================================================
# ヘルパー
# ============================================================

def _read_shadow_stats(name: str = "shadow") -> Dict[str, Any]:
    log_path = SHADOW_LOG_DIR / f"{name}.jsonl"
    if not log_path.exists():
        return {"n_sampled": 0, "log_path": str(log_path)}

    n = 0
    n_match = 0
    kl_sum = 0.0
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            if entry.get("top1_match"):
                n_match += 1
            kl_sum += entry.get("kl_divergence", 0.0)

    return {
        "name": name,
        "n_sampled": n,
        "top1_match_rate": round(n_match / n, 4) if n else None,
        "avg_kl_divergence": round(kl_sum / n, 6) if n else None,
    }


def _read_ab_stats() -> List[Dict[str, Any]]:
    ab_dir = AB_LOG_DIR
    if not ab_dir.exists():
        return []

    results = []
    for log_file in ab_dir.glob("*.jsonl"):
        n = 0
        variants: Dict[str, Dict] = {}
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                variant = entry.get("variant", "unknown")
                if variant not in variants:
                    variants[variant] = {"n": 0, "n_correct": 0}
                variants[variant]["n"] += 1
                if entry.get("true_winner") is not None:
                    # correct は predict 後に record_result 経由で更新される
                    pass
                n += 1

        results.append({
            "test_name": log_file.stem,
            "n_total_records": n,
            "variants": list(variants.keys()),
        })
    return results


def _latest_drift_status() -> Optional[str]:
    drift_dir = DRIFT_REPORT_DIR
    if not drift_dir.exists():
        return None

    reports = sorted(drift_dir.glob("*.json"))
    if not reports:
        return None

    try:
        with open(reports[-1], encoding="utf-8") as f:
            report = json.load(f)
        return "needs_retraining" if report.get("needs_retraining") else "stable"
    except (json.JSONDecodeError, OSError):
        return None


# ============================================================
# エンドポイント
# ============================================================

@router.get(
    "/admin/status",
    response_model=SystemStatusResponse,
    summary="システム全体ステータス",
)
async def get_system_status(
    _api_key: str = Depends(verify_admin_key),
) -> SystemStatusResponse:
    """モデル・キャッシュ・ドリフト・A/Bテスト・シャドウの統合ステータスを返す"""
    from app.model.versioning import ModelRegistry

    registry = ModelRegistry()
    versions = registry.list_versions()
    prod_version = registry.get_production_version()

    # キャッシュ統計
    cache_info: Dict[str, Any] = {}
    try:
        from app.cache import get_cache_stats
        cache_info = await get_cache_stats()
    except Exception:
        cache_info = {"status": "unavailable"}

    # シャドウ・AB テストのログ存在確認
    shadow_active = any(
        SHADOW_LOG_DIR.glob("*.jsonl")
    ) if SHADOW_LOG_DIR.exists() else False

    ab_active = any(
        AB_LOG_DIR.glob("*.jsonl")
    ) if AB_LOG_DIR.exists() else False

    return SystemStatusResponse(
        status="ok",
        production_model=prod_version,
        n_registered_versions=len(versions),
        prediction_store=cache_info,
        drift_status=_latest_drift_status(),
        ab_test_active=ab_active,
        shadow_active=shadow_active,
    )


@router.get(
    "/admin/models",
    response_model=List[ModelVersionInfo],
    summary="登録済みモデルバージョン一覧",
)
async def list_models(
    _api_key: str = Depends(verify_admin_key),
) -> List[ModelVersionInfo]:
    """登録済みモデルバージョンの一覧と各バージョンのメトリクスを返す"""
    from app.model.versioning import ModelRegistry

    registry = ModelRegistry()
    versions = registry.list_versions()
    prod_version = registry.get_production_version()

    return [
        ModelVersionInfo(
            version=v["version"],
            registered_at=v.get("registered_at", ""),
            cv_logloss_mean=v.get("metrics", {}).get("cv_logloss_mean", 0.0),
            cv_accuracy_mean=v.get("metrics", {}).get("cv_accuracy_mean", 0.0),
            n_samples=v.get("metrics", {}).get("n_samples", 0),
            notes=v.get("notes"),
            is_production=(v["version"] == prod_version),
        )
        for v in versions
    ]


@router.post(
    "/admin/models/promote",
    summary="モデルを本番に昇格",
    description="指定バージョンを本番モデルとして昇格します。旧本番はバックアップされます。",
)
async def promote_model(
    body: PromoteRequest,
    _api_key: str = Depends(verify_admin_key),
) -> Dict[str, str]:
    """モデルバージョンを本番に昇格する"""
    from app.model.versioning import ModelRegistry

    registry = ModelRegistry()
    versions = [v["version"] for v in registry.list_versions()]

    if body.version not in versions:
        raise HTTPException(
            status_code=404,
            detail=f"バージョン '{body.version}' が見つかりません",
        )

    try:
        old_version = registry.get_production_version()
        registry.promote(body.version)
        logger.info(f"モデル昇格: {old_version} → {body.version}")
        return {
            "message": f"昇格完了: {body.version}",
            "previous_version": old_version or "なし",
            "new_version": body.version,
        }
    except Exception as e:
        logger.error(f"モデル昇格エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/admin/drift",
    summary="最新ドリフトレポート",
)
async def get_drift_report(
    _api_key: str = Depends(verify_admin_key),
) -> Dict[str, Any]:
    """最新のドリフト検知レポートを返す"""
    drift_dir = DRIFT_REPORT_DIR
    if not drift_dir.exists():
        return {"message": "ドリフトレポートがありません。make drift を実行してください。"}

    reports = sorted(drift_dir.glob("*.json"))
    if not reports:
        return {"message": "ドリフトレポートがありません"}

    try:
        with open(reports[-1], encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"レポート読み込みエラー: {e}")


@router.get(
    "/admin/ab-test",
    summary="A/Bテスト統計サマリー",
)
async def get_ab_test_stats(
    _api_key: str = Depends(verify_admin_key),
) -> List[Dict[str, Any]]:
    """全 A/B テストログの統計サマリーを返す"""
    return _read_ab_stats()


@router.get(
    "/admin/shadow",
    summary="シャドウモード統計",
)
async def get_shadow_stats(
    name: str = "shadow",
    _api_key: str = Depends(verify_admin_key),
) -> Dict[str, Any]:
    """シャドウモードの累積統計を返す"""
    return _read_shadow_stats(name)


@router.delete(
    "/admin/shadow/{name}",
    summary="シャドウログをクリア",
)
async def clear_shadow_log(
    name: str,
    _api_key: str = Depends(verify_admin_key),
) -> Dict[str, str]:
    """指定シャドウログファイルを削除する"""
    log_path = SHADOW_LOG_DIR / f"{name}.jsonl"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"ログ {name} が見つかりません")
    log_path.unlink()
    logger.info(f"シャドウログ削除: {log_path}")
    return {"message": f"{name} のログを削除しました"}
