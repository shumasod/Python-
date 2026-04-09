"""
API Key 認証モジュール
本番環境では全エンドポイントに API Key を要求する

設定:
  環境変数 API_KEYS にカンマ区切りで有効なキーを設定する
  例: API_KEYS=key-prod-abc123,key-dev-xyz789

  環境変数 API_AUTH_ENABLED=false で認証を無効化できる（開発用）

使い方（FastAPI）:
  from app.api.auth import verify_api_key

  @router.post("/predict")
  async def predict(api_key: str = Depends(verify_api_key)):
      ...
"""
import hashlib
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---- 設定 ----

# X-API-Key ヘッダーから取得
_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# 認証が有効かどうか（開発環境では false で無効化）
_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "true").lower() == "true"

# 有効な API Key セット（ハッシュ化して保持）
_VALID_KEY_HASHES: set[str] = set()


def _load_api_keys() -> None:
    """環境変数から API Key を読み込む（ハッシュ化して保持）"""
    raw_keys = os.getenv("API_KEYS", "")
    if not raw_keys:
        # デフォルトで開発用キーを生成（起動時にログ出力）
        default_key = "dev-key-" + secrets.token_hex(8)
        logger.warning(
            f"API_KEYS 環境変数が未設定です。開発用キーを生成しました: {default_key}\n"
            "本番では必ず API_KEYS を設定してください。"
        )
        _VALID_KEY_HASHES.add(_hash_key(default_key))
        return

    for key in raw_keys.split(","):
        key = key.strip()
        if key:
            _VALID_KEY_HASHES.add(_hash_key(key))

    logger.info(f"{len(_VALID_KEY_HASHES)} 個の API Key を読み込みました")


def _hash_key(key: str) -> str:
    """API Key を SHA-256 でハッシュ化する（タイミング攻撃対策）"""
    return hashlib.sha256(key.encode()).hexdigest()


# 起動時にキーを読み込む
_load_api_keys()


def verify_api_key(
    api_key: Optional[str] = Security(_API_KEY_HEADER),
) -> str:
    """
    API Key を検証する FastAPI Dependency

    Args:
        api_key: X-API-Key ヘッダーの値

    Returns:
        検証済みの API Key 文字列

    Raises:
        HTTPException 401: API Key が無効または未指定の場合
    """
    if not _AUTH_ENABLED:
        return "auth-disabled"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key ヘッダーが必要です",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # タイミング攻撃を防ぐため compare_digest を使用
    key_hash = _hash_key(api_key)
    if not any(
        secrets.compare_digest(key_hash, valid_hash)
        for valid_hash in _VALID_KEY_HASHES
    ):
        logger.warning(f"無効な API Key でのアクセス試行: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効な API Key です",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


def generate_api_key(prefix: str = "br") -> str:
    """
    新しい API Key を生成する

    Args:
        prefix: キーのプレフィックス（用途識別用）

    Returns:
        生成した API Key 文字列
    """
    token = secrets.token_urlsafe(32)
    return f"{prefix}-{token}"
