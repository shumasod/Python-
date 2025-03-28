import redis
import json
from typing import Any, Optional, Union, Dict
from dataclasses import dataclass
import logging
from datetime import datetime
import hashlib
import pickle
from redis.exceptions import RedisError
from contextlib import contextmanager

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RedisConfig:
    """Redisの設定を保持するデータクラス"""
    host: str = 'localhost'
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
        self._redis_client = None
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
        except redis.ConnectionError as e:
            logger.error(f"Redis接続エラー: {e}")
            raise CacheException(f"Redisサーバーへの接続に失敗しました: {e}")

    @contextmanager
    def _redis_operation(self):
        """Redis操作のコンテキストマネージャー"""
        retry_count = 0
        while retry_count < self.config.max_retries:
            try:
                yield self._redis_client
                break
            except redis.ConnectionError:
                retry_count += 1
                if retry_count == self.config.max_retries:
                    raise CacheException("Redis接続の再試行が失敗しました")
                self._connect()
            except RedisError as e:
                raise CacheException(f"Redis操作エラー: {e}")

    def _generate_key(self, key: str) -> str:
        """
        キーのハッシュ値を生成
        
        Args:
            key: 元のキー
        Returns:
            ハッシュ化されたキー
        """
        return hashlib.md5(key.encode()).hexdigest()

    def _serialize_value(self, value: Any) -> bytes:
        """
        値をシリアライズ
        
        Args:
            value: シリアライズする値
        Returns:
            シリアライズされたバイトデータ
        """
        try:
            if isinstance(value, (dict, list)):
                return json.dumps(value).encode()
            return pickle.dumps(value)
        except (TypeError, pickle.PickleError) as e:
            raise CacheException(f"値のシリアライズに失敗しました: {e}")

    def _deserialize_value(self, data: bytes) -> Any:
        """
        値をデシリアライズ
        
        Args:
            data: デシリアライズするバイトデータ
        Returns:
            デシリアライズされた値
        """
        try:
            try:
                return json.loads(data)
            except UnicodeDecodeError:
                return pickle.loads(data)
        except (json.JSONDecodeError, pickle.UnpicklingError) as e:
            raise CacheException(f"値のデシリアライズに失敗しました: {e}")

    def set_cache(
        self, 
        key: str, 
        value: Any, 
        expiration: int = 3600,
        nx: bool = False
    ) -> bool:
        """
        キャッシュにデータを設定
        
        Args:
            key: キャッシュのキー
            value: 保存する値
            expiration: 有効期限（秒）
            nx: Trueの場合、キーが存在しない場合のみ設定
        Returns:
            bool: 設定が成功したかどうか
        """
        hashed_key = self._generate_key(key)
        serialized_value = self._serialize_value({
            'value': value,
            'timestamp': datetime.utcnow().isoformat()
        })

        with self._redis_operation() as redis_client:
            try:
                if nx:
                    return bool(redis_client.set(
                        hashed_key, 
                        serialized_value,
                        ex=expiration,
                        nx=True
                    ))
                redis_client.setex(hashed_key, expiration, serialized_value)
                return True
            except RedisError as e:
                logger.error(f"キャッシュ設定エラー - キー: {key}, エラー: {e}")
                return False

    def get_cache(self, key: str) -> Optional[Any]:
        """
        キャッシュからデータを取得
        
        Args:
            key: キャッシュのキー
        Returns:
            キャッシュされた値またはNone
        """
        hashed_key = self._generate_key(key)
        
        with self._redis_operation() as redis_client:
            try:
                data = redis_client.get(hashed_key)
                if data:
                    cache_data = self._deserialize_value(data)
                    return cache_data.get('value')
                return None
            except RedisError as e:
                logger.error(f"キャッシュ取得エラー - キー: {key}, エラー: {e}")
                return None

    def delete_cache(self, key: str) -> bool:
        """
        特定のキーのキャッシュを削除
        
        Args:
            key: 削除するキャッシュのキー
        Returns:
            bool: 削除が成功したかどうか
        """
        hashed_key = self._generate_key(key)
        
        with self._redis_operation() as redis_client:
            try:
                return bool(redis_client.delete(hashed_key))
            except RedisError as e:
                logger.error(f"キャッシュ削除エラー - キー: {key}, エラー: {e}")
                return False

    def clear_all_cache(self) -> bool:
        """
        全てのキャッシュを削除
        
        Returns:
            bool: 削除が成功したかどうか
        """
        with self._redis_operation() as redis_client:
            try:
                redis_client.flushdb()
                return True
            except RedisError as e:
                logger.error(f"全キャッシュ削除エラー: {e}")
                return False

    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュの統計情報を取得
        
        Returns:
            Dict: 統計情報
        """
        with self._redis_operation() as redis_client:
            try:
                info = redis_client.info()
                return {
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_keys': redis_client.dbsize(),
                    'uptime': info.get('uptime_in_seconds')
                }
            except RedisError as e:
                logger.error(f"統計情報取得エラー: {e}")
                return {}

def create_redis_cache(
    host: str = 'localhost',
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
    ssl: bool = False
) -> RedisCache:
    """
    RedisCache インスタンスを作成するファクトリ関数
    
    Args:
        host: Redisホスト
        port: Redisポート
        db: データベース番号
        password: パスワード
        ssl: SSL使用フラグ
    Returns:
        RedisCache: 設定済みのRedisCache インスタンス
    """
    config = RedisConfig(
        host=host,
        port=port,
        db=db,
        password=password,
        ssl=ssl
    )
    return RedisCache(config)

# 使用例
if __name__ == "__main__":
    try:
        # 設定済みのRedisインスタンスを作成
        cache = create_redis_cache(password="secure_password", ssl=True)
        
        # キャッシュにデータを設定
        cache.set_cache("user_1", {"name": "John Doe", "age": 30})
        cache.set_cache("user_2", {"name": "Jane Doe", "age": 28})
        
        # キャッシュからデータを取得
        user_1 = cache.get_cache("user_1")
        print(f"User 1: {user_1}")
        
        # 統計情報の取得
        stats = cache.get_stats()
        print(f"Cache Stats: {stats}")
        
        # 特定のキャッシュを削除
        cache.delete_cache("user_2")
        
        # 全てのキャッシュを削除
        cache.clear_all_cache()
        
    except CacheException as e:
        logger.error(f"キャッシュ操作エラー: {e}")
