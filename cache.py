import redis
import json
from typing import Any, Optional, Tuple, Dict
from dataclasses import dataclass
import logging
from datetime import datetime
import hashlib
import pickle
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from contextlib import contextmanager

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Redisの設定を保持するデータクラス"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False
    max_retries: int = 3
    retry_interval: float = 1.0


class CacheException(Exception):
    """キャッシュ操作に関する例外クラス"""
    pass


class RedisCache:
    def __init__(self, config: Optional[RedisConfig] = None):
        """
        RedisCache クラスの初期化

        Args:
            config: Redis設定。Noneの場合はデフォルト設定を使用
        """
        self.config = config or RedisConfig()
        self._redis_client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self) -> None:
        """Redisサーバーへの接続を確立"""
        try:
            self._redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                decode_responses=self.config.decode_responses,
                ssl=self.config.ssl
            )
            # 接続テスト
            self._redis_client.ping()
            logger.info("Redis に接続しました")
        except RedisConnectionError as e:
            logger.error(f"Redis接続エラー: {e}")
            raise CacheException(f"Redisサーバーへの接続に失敗しました: {e}")
        except Exception as e:
            logger.error(f"Redis接続時の予期せぬエラー: {e}")
            raise CacheException(f"Redis 接続でエラー: {e}")

    @contextmanager
    def _redis_operation(self):
        """
        Redis操作のコンテキストマネージャー。
        再試行ロジックを含む。
        """
        if self._redis_client is None:
            self._connect()

        retry_count = 0
        while True:
            try:
                yield self._redis_client
                break
            except RedisConnectionError as e:
                retry_count += 1
                logger.warning(f"Redis 接続エラー発生。再試行 {retry_count}/{self.config.max_retries}: {e}")
                if retry_count >= self.config.max_retries:
                    raise CacheException("Redis接続の再試行が失敗しました") from e
                # 再接続
                try:
                    self._connect()
                except CacheException:
                    # 次のループで再試行回数が増える
                    pass
            except RedisError as e:
                logger.error(f"Redis 操作エラー: {e}")
                raise CacheException(f"Redis操作エラー: {e}") from e
            except Exception as e:
                logger.error(f"予期せぬエラー: {e}")
                raise CacheException(f"Redis 操作時の予期せぬエラー: {e}") from e

    def _generate_key(self, key: str) -> str:
        """
        キーのハッシュ値を生成
        """
        if not isinstance(key, str):
            key = str(key)
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _serialize_value(self, value: Any) -> bytes:
        """
        値をシリアライズ（dict/list は JSON、それ以外は pickle）
        """
        try:
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False).encode("utf-8")
            return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.exception("値のシリアライズに失敗しました")
            raise CacheException(f"値のシリアライズに失敗しました: {e}") from e

    def _deserialize_value(self, data: Union[bytes, str]) -> Any:
        """
        値をデシリアライズ（まず UTF-8 デコード -> JSON を試す、
        だめなら pickle を試す）
        """
        try:
            # redis-py が str を返す設定（decode_responses=True）の場合もあるので対応
            if isinstance(data, str):
                raw = data
            else:
                # bytes
                try:
                    raw = data.decode("utf-8")
                except UnicodeDecodeError:
                    # バイナリは pickle として扱う
                    return pickle.loads(data)

            # raw が文字列なら JSON を試す
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # JSONでなければ pickle のバイト列を試す（エンコードし直す）
                try:
                    return pickle.loads(raw.encode("utf-8"))
                except Exception:
                    # 最終フォールバックとして文字列を返す
                    return raw
        except Exception as e:
            logger.exception("デシリアライズに失敗しました")
            raise CacheException(f"値のデシリアライズに失敗しました: {e}") from e

    def set_cache(
        self,
        key: str,
        value: Any,
        expiration: int = 3600,
        nx: bool = False
    ) -> bool:
        """
        キャッシュにデータを設定
        """
        hashed_key = self._generate_key(key)
        payload = {
            "value": value,
            "timestamp": datetime.utcnow().isoformat()
        }
        serialized_value = self._serialize_value(payload)

        with self._redis_operation() as redis_client:
            try:
                if nx:
                    result = redis_client.set(
                        hashed_key,
                        serialized_value,
                        ex=expiration,
                        nx=True
                    )
                    return bool(result)
                # setex は戻り値 None の場合があるため True/False を安定的に返す
                redis_client.setex(hashed_key, expiration, serialized_value)
                return True
            except RedisError as e:
                logger.error(f"キャッシュ設定エラー - キー: {key}, エラー: {e}")
                return False

    def get_cache(self, key: str) -> Optional[Any]:
        """
        キャッシュからデータを取得
