"""
詳細ヘルスチェック API
DB接続・モデルロード状態・ディスク使用量などを返す

GET /health/detail
"""
import os
import platform
import shutil
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_START_TIME = time.time()  # サーバー起動時刻


@router.get("/health/detail", summary="詳細ヘルスチェック")
async def health_detail() -> Dict[str, Any]:
    """
    各コンポーネントの状態を返す

    レスポンス:
    - **status**: overall（ok / degraded / down）
    - **uptime_sec**: 起動からの経過秒数
    - **model**: モデルファイルのロード状態
    - **db**: DB接続状態（USE_DB=true の場合のみ）
    - **disk**: モデル・データディレクトリのディスク使用量
    - **system**: OS・Pythonバージョン情報
    """
    checks: Dict[str, Any] = {}
    overall = "ok"

    # ---- モデル状態チェック ----
    checks["model"] = _check_model()
    if checks["model"]["status"] != "ok":
        overall = "degraded"

    # ---- DB 接続チェック ----
    use_db = os.getenv("USE_DB", "false").lower() == "true"
    if use_db:
        checks["db"] = await _check_db()
        if checks["db"]["status"] == "error":
            overall = "degraded"
    else:
        checks["db"] = {"status": "disabled", "message": "USE_DB=false"}

    # ---- ディスク使用量 ----
    checks["disk"] = _check_disk()

    # ---- システム情報 ----
    checks["system"] = {
        "python": platform.python_version(),
        "os": platform.system(),
        "uptime_sec": int(time.time() - _START_TIME),
    }

    return {
        "status": overall,
        "uptime_sec": int(time.time() - _START_TIME),
        "checks": checks,
    }


def _check_model() -> Dict[str, Any]:
    """モデルファイルの存在・ロード状態を確認する"""
    model_dir = Path("models")
    model_path = model_dir / "boat_race_model.pkl"

    if not model_path.exists():
        return {
            "status": "warn",
            "message": "モデルファイルが見つかりません",
            "path": str(model_path),
        }

    try:
        # キャッシュ済みモデルを取得（ファイルI/Oを伴わない）
        from app.model.predict import _cached_model
        loaded = _cached_model is not None
        size_kb = model_path.stat().st_size // 1024

        return {
            "status": "ok",
            "loaded": loaded,
            "path": str(model_path),
            "size_kb": size_kb,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _check_db() -> Dict[str, Any]:
    """DB接続を検証する（SELECT 1 を実行）"""
    try:
        from app.db import get_connection
        start = time.monotonic()
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        logger.warning(f"DBヘルスチェック失敗: {e}")
        return {"status": "error", "message": str(e)}


def _check_disk() -> Dict[str, Any]:
    """モデル・データディレクトリのディスク使用量を確認する"""
    result: Dict[str, Any] = {}
    for name, path in [("models", "models"), ("data", "data"), ("logs", "logs")]:
        p = Path(path)
        if p.exists():
            total_bytes = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            result[name] = f"{total_bytes / 1024:.1f} KB"
        else:
            result[name] = "directory not found"

    # ルートディスク空き容量
    try:
        usage = shutil.disk_usage("/")
        result["root_free_gb"] = round(usage.free / (1024 ** 3), 1)
    except Exception:
        result["root_free_gb"] = "unknown"

    return result
