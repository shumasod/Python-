"""
データベース接続・予測ログ保存モジュール
PostgreSQL への非同期接続と予測結果の永続化を担当する

依存: asyncpg（requirements.txt に追加が必要）
  pip install asyncpg

環境変数:
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

# DB接続情報は環境変数から取得（ハードコーディング禁止）
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "boatracedb"),
    "user":     os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# シングルトン接続プール
_pool = None


async def get_pool():
    """
    asyncpg 接続プールのシングルトンを取得する
    アプリ起動時（lifespan）に初期化しておくことを推奨

    Returns:
        asyncpg.Pool インスタンス

    Raises:
        ImportError: asyncpg がインストールされていない場合
        Exception: DB接続に失敗した場合
    """
    global _pool
    if _pool is not None:
        return _pool

    try:
        import asyncpg
    except ImportError:
        raise ImportError(
            "asyncpg がインストールされていません。"
            "pip install asyncpg を実行してください。"
        )

    logger.info(f"DB接続プールを初期化します: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    _pool = await asyncpg.create_pool(
        **DB_CONFIG,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("DB接続プール初期化完了")
    return _pool


async def close_pool() -> None:
    """接続プールをクローズする（アプリ終了時に呼ぶ）"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("DB接続プールをクローズしました")


@asynccontextmanager
async def get_connection() -> AsyncGenerator:
    """
    接続プールから1接続を取得するコンテキストマネージャー

    使用例:
        async with get_connection() as conn:
            await conn.execute("SELECT 1")
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def log_prediction(
    race_id: Optional[str],
    request_body: Dict[str, Any],
    response_body: Dict[str, Any],
    latency_ms: int,
) -> None:
    """
    予測リクエスト・レスポンスを DB に記録する

    Args:
        race_id: レースID（None 可）
        request_body: APIリクエスト辞書
        response_body: APIレスポンス辞書
        latency_ms: 処理時間（ミリ秒）
    """
    try:
        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO prediction_logs
                    (race_id, request_body, response_body, latency_ms)
                VALUES ($1, $2, $3, $4)
                """,
                race_id,
                json.dumps(request_body, ensure_ascii=False),
                json.dumps(response_body, ensure_ascii=False),
                latency_ms,
            )
        logger.debug(f"予測ログを保存しました: race_id={race_id}, latency={latency_ms}ms")

    except Exception as e:
        # ログ保存の失敗はサイレントに処理（APIレスポンスには影響させない）
        logger.warning(f"予測ログの保存に失敗しました: {e}")


async def get_prediction_stats(days: int = 7) -> Dict[str, Any]:
    """
    過去N日間の予測統計を取得する

    Args:
        days: 集計対象日数

    Returns:
        統計辞書（件数・平均レイテンシ等）
    """
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                              AS total_requests,
                    AVG(latency_ms)::INTEGER              AS avg_latency_ms,
                    MAX(latency_ms)                       AS max_latency_ms,
                    MIN(created_at)                       AS oldest_request,
                    MAX(created_at)                       AS latest_request
                FROM prediction_logs
                WHERE created_at >= NOW() - INTERVAL '1 day' * $1
                """,
                days,
            )
            return dict(row) if row else {}
    except Exception as e:
        logger.warning(f"統計取得に失敗しました: {e}")
        return {}
