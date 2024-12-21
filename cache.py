import redis
import json
from typing import Any, Optional

class RedisCache:
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        self.redis_client = redis.Redis(host=host, port=port, db=db)

    def set_cache(self, key: str, value: Any, expiration: int = 3600) -> None:
        """
        キャッシュにデータを設定する
        :param key: キャッシュのキー
        :param value: 保存する値
        :param expiration: 有効期限（秒）、デフォルトは1時間
        """
        self.redis_client.setex(key, expiration, json.dumps(value))

    def get_cache(self, key: str) -> Optional[Any]:
        """
        キャッシュからデータを取得する
        :param key: キャッシュのキー
        :return: キャッシュされた値、またはNone（キーが存在しない場合）
        """
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    def delete_cache(self, key: str) -> None:
        """
        特定のキーのキャッシュを削除する
        :param key: 削除するキャッシュのキー
        """
        self.redis_client.delete(key)

    def clear_all_cache(self) -> None:
        """
        全てのキャッシュを削除する
        """
        self.redis_client.flushdb()

# 使用例
if __name__ == "__main__":
    cache = RedisCache()

    # キャッシュにデータを設定
    cache.set_cache("user_1", {"name": "John Doe", "age": 30})
    cache.set_cache("user_2", {"name": "Jane Doe", "age": 28})

    # キャッシュからデータを取得
    user_1 = cache.get_cache("user_1")
    print(f"User 1: {user_1}")

    # 特定のキャッシュを削除
    cache.delete_cache("user_2")

    # 全てのキャッシュを削除
    cache.clear_all_cache()

    # 削除後にデータを取得しようとする（Noneが返される）
    user_1_after_clear = cache.get_cache("user_1")
    print(f"User 1 after clear: {user_1_after_clear}")