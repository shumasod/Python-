"""
レートリミットモジュール
SlowAPI を使ったリクエスト頻度制限

環境変数:
  RATE_LIMIT_ENABLED : "true" で有効（デフォルト: false）
  RATE_LIMIT_DEFAULT : デフォルト制限（例: "60/minute"）

依存: pip install slowapi
"""
import os
from typing import Callable

from fastapi import Request, Response

from app.utils.logger import get_logger

logger = get_logger(__name__)

_ENABLED       = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
_DEFAULT_LIMIT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")

# slowapi を条件付きインポート
_limiter = None
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[_DEFAULT_LIMIT] if _ENABLED else [],
        enabled=_ENABLED,
    )
    logger.info(f"レートリミット: {'有効' if _ENABLED else '無効'} ({_DEFAULT_LIMIT})")
except ImportError:  # pragma: no cover
    logger.warning("slowapi が未インストールです。pip install slowapi を実行してください。")


def get_limiter():
    """Limiter インスタンスを返す（slowapi 未インストール時は None）"""
    return _limiter


def rate_limit(limit_string: str = "60/minute"):
    """
    エンドポイントに適用するレートリミットデコレータ

    slowapi 未インストール時はデコレータをスキップする

    使い方:
        @router.post("/predict")
        @rate_limit("30/minute")
        async def predict_endpoint(request: Request, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if _limiter is None or not _ENABLED:
            return func
        return _limiter.limit(limit_string)(func)
    return decorator


async def rate_limit_exceeded_handler(request: Request, exc) -> Response:
    """
    レートリミット超過時のエラーレスポンス

    main.py に登録:
        from slowapi.errors import RateLimitExceeded
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    """
    from fastapi.responses import JSONResponse
    logger.warning(f"レートリミット超過: {request.client.host} → {request.url.path}")
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"リクエスト頻度が上限を超えました。しばらく待ってから再試行してください。",
            "limit": str(exc.detail) if hasattr(exc, "detail") else _DEFAULT_LIMIT,
        },
    )
