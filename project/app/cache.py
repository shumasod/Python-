"""
Redis 予測キャッシュモジュール
同一レースへの重複リクエストをキャッシュしてレイテンシを削減する

環境変数:
  REDIS_URL      : Redis 接続URL（例: redis://localhost:6379/0）
  CACHE_TTL_SEC  : キャッシュ有効期間（秒）、デフォルト 300 秒
  CACHE_ENABLED  : "true" でキャッシュを有効化（デフォルト: false）

キャッシュキー設計:
  boat_race:predict:{race_id_hash}
  - race_id が指定されていない場合はリクエストボディのハッシュを使用
  - TTL は CACHE_TTL_SEC 秒で自動失効

依存パッケージ:
  pip install redis[asyncio]
"""
import hashlib
import json
import os
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

_CACHE_ENABLED = os.getenv("CACHE_ENABLED", "false").lower() == "true"
_REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_TTL_SEC       = int(os.getenv("CACHE_TTL_SEC", "300"))  # 5分
_KEY_PREFIX    = "boat_race:predict:"

# Redis クライアントのシングルトン
_redis_client = None


async def get_redis():
    """Redis クライアントのシングルトンを取得する"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as aioredis
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "redis が未インストールです。pip install 'redis[asyncio]' を実行してください。"
        ) from exc

    _redis_client = aioredis.from_url(
        _REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    logger.info(f"Redis 接続: {_REDIS_URL}")
    return _redis_client


async def close_redis() -> None:
    """Redis 接続をクローズする（アプリ終了時に呼ぶ）"""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis 接続をクローズしました")


def _make_cache_key(race_data: dict[str, Any], race_id: str | None = None) -> str:
    """
    キャッシュキーを生成する

    Args:
        race_data: レース情報辞書
        race_id: レースID（提供された場合はこれを優先して使用）

    Returns:
        Redis キー文字列
    """
    raw = race_id or json.dumps(race_data, sort_keys=True, ensure_ascii=False)

    key_hash = hashlib.md5(raw.encode()).hexdigest()
    return f"{_KEY_PREFIX}{key_hash}"


async def get_cached_prediction(
    race_data: dict[str, Any],
    race_id: str | None = None,
) -> dict[str, Any] | None:
    """
    キャッシュから予測結果を取得する

    Args:
        race_data: レース情報辞書
        race_id: レースID（None の場合はボディハッシュを使用）

    Returns:
        キャッシュヒット時は予測結果dict、ミス時は None
    """
    if not _CACHE_ENABLED:
        return None

    try:
        redis = await get_redis()
        key = _make_cache_key(race_data, race_id)
        cached = await redis.get(key)

        if cached:
            logger.info(f"キャッシュヒット: {key}")
            return json.loads(cached)

        logger.debug(f"キャッシュミス: {key}")
        return None

    except Exception as e:
        # Redis 障害時はキャッシュをスキップして通常処理へ
        logger.warning(f"キャッシュ取得エラー（スキップ）: {e}")
        return None


async def set_cached_prediction(
    race_data: dict[str, Any],
    result: dict[str, Any],
    race_id: str | None = None,
    ttl: int | None = None,
) -> bool:
    """
    予測結果をキャッシュに保存する

    Args:
        race_data: レース情報辞書
        result: 保存する予測結果dict
        race_id: レースID（None の場合はボディハッシュを使用）
        ttl: TTL秒数（None の場合は環境変数 CACHE_TTL_SEC を使用）

    Returns:
        True=保存成功, False=失敗
    """
    if not _CACHE_ENABLED:
        return False

    try:
        redis = await get_redis()
        key = _make_cache_key(race_data, race_id)
        value = json.dumps(result, ensure_ascii=False)
        await redis.setex(key, ttl or _TTL_SEC, value)
        logger.debug(f"キャッシュ保存: {key} (TTL={ttl or _TTL_SEC}秒)")
        return True

    except Exception as e:
        logger.warning(f"キャッシュ保存エラー（スキップ）: {e}")
        return False


async def invalidate_cache(race_id: str) -> bool:
    """
    特定レースのキャッシュを無効化する

    Args:
        race_id: 無効化するレースID

    Returns:
        True=削除成功, False=キーなし or エラー
    """
    if not _CACHE_ENABLED:
        return False

    try:
        redis = await get_redis()
        key = _make_cache_key({}, race_id)
        deleted = await redis.delete(key)
        if deleted:
            logger.info(f"キャッシュを無効化しました: {key}")
        return bool(deleted)
    except Exception as e:
        logger.warning(f"キャッシュ無効化エラー: {e}")
        return False


async def get_cache_stats() -> dict[str, Any]:
    """
    キャッシュ統計情報を取得する

    Returns:
        stats dict（接続状態・キー数・メモリ使用量など）
    """
    if not _CACHE_ENABLED:
        return {"enabled": False}

    try:
        redis = await get_redis()
        info = await redis.info("memory")
        key_count = len(await redis.keys(f"{_KEY_PREFIX}*"))
        return {
            "enabled": True,
            "redis_url": _REDIS_URL,
            "cached_predictions": key_count,
            "ttl_sec": _TTL_SEC,
            "used_memory_human": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        return {"enabled": True, "error": str(e)}
