"""
Redis キャッシュモジュールのテスト

Redis への実接続は行わず、redis.asyncio をモックしてテストする。
CACHE_ENABLED=false のパスは接続なしで動作することを確認する。
"""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# _make_cache_key
# ============================================================

class TestMakeCacheKey:
    def test_race_id_used_when_provided(self):
        """`race_id` があるとき、その MD5 ハッシュをキーに使うこと"""
        from app.cache import _make_cache_key
        key1 = _make_cache_key({}, race_id="race_001")
        key2 = _make_cache_key({}, race_id="race_001")
        assert key1 == key2  # 冪等

    def test_different_race_ids_give_different_keys(self):
        """異なる race_id は異なるキーになること"""
        from app.cache import _make_cache_key
        assert _make_cache_key({}, "a") != _make_cache_key({}, "b")

    def test_race_data_hash_when_no_race_id(self):
        """race_id なしのとき、race_data ボディのハッシュを使うこと"""
        from app.cache import _make_cache_key
        data = {"boats": [1, 2, 3]}
        k1 = _make_cache_key(data, race_id=None)
        k2 = _make_cache_key(data, race_id=None)
        assert k1 == k2

    def test_different_race_data_gives_different_keys(self):
        """レースデータが異なれば異なるキーになること"""
        from app.cache import _make_cache_key
        k1 = _make_cache_key({"boats": [1]})
        k2 = _make_cache_key({"boats": [2]})
        assert k1 != k2

    def test_key_has_prefix(self):
        """キーが期待するプレフィックスを持つこと"""
        from app.cache import _make_cache_key, _KEY_PREFIX
        key = _make_cache_key({}, "test")
        assert key.startswith(_KEY_PREFIX)

    def test_key_is_string(self):
        """キーが文字列であること"""
        from app.cache import _make_cache_key
        assert isinstance(_make_cache_key({}, "r1"), str)


# ============================================================
# get_cached_prediction（CACHE_ENABLED=false）
# ============================================================

class TestGetCachedPredictionDisabled:
    @pytest.mark.anyio
    async def test_disabled_returns_none(self, monkeypatch):
        """CACHE_ENABLED=false のとき None を返すこと（Redis接続なし）"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", False)

        from app.cache import get_cached_prediction
        result = await get_cached_prediction({"boats": []})
        assert result is None


# ============================================================
# set_cached_prediction（CACHE_ENABLED=false）
# ============================================================

class TestSetCachedPredictionDisabled:
    @pytest.mark.anyio
    async def test_disabled_returns_false(self, monkeypatch):
        """CACHE_ENABLED=false のとき False を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", False)

        from app.cache import set_cached_prediction
        result = await set_cached_prediction({"boats": []}, {"result": 1})
        assert result is False


# ============================================================
# invalidate_cache（CACHE_ENABLED=false）
# ============================================================

class TestInvalidateCacheDisabled:
    @pytest.mark.anyio
    async def test_disabled_returns_false(self, monkeypatch):
        """CACHE_ENABLED=false のとき False を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", False)

        from app.cache import invalidate_cache
        result = await invalidate_cache("race_001")
        assert result is False


# ============================================================
# get_cache_stats（CACHE_ENABLED=false）
# ============================================================

class TestGetCacheStatsDisabled:
    @pytest.mark.anyio
    async def test_disabled_returns_enabled_false(self, monkeypatch):
        """CACHE_ENABLED=false のとき {"enabled": False} を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", False)

        from app.cache import get_cache_stats
        stats = await get_cache_stats()
        assert stats == {"enabled": False}


# ============================================================
# キャッシュ有効時のモックテスト
# ============================================================

class TestCacheEnabledMocked:
    """CACHE_ENABLED=true + Redis をモックしたテスト"""

    def _make_mock_redis(self, cached_value=None):
        """AsyncMock Redis クライアントを返す"""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=cached_value)
        mock.setex = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.info = AsyncMock(return_value={"used_memory_human": "1.5M"})
        mock.keys = AsyncMock(return_value=["key1", "key2"])
        return mock

    @pytest.mark.anyio
    async def test_cache_hit_returns_dict(self, monkeypatch):
        """キャッシュヒット時に辞書を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        monkeypatch.setattr(cache_module, "_redis_client", None)

        cached_data = {"win_probabilities": [0.1] * 6}
        mock_redis = self._make_mock_redis(json.dumps(cached_data))
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import get_cached_prediction
        result = await get_cached_prediction({"boats": []}, race_id="r1")
        assert result == cached_data

    @pytest.mark.anyio
    async def test_cache_miss_returns_none(self, monkeypatch):
        """キャッシュミス時に None を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = self._make_mock_redis(cached_value=None)
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import get_cached_prediction
        result = await get_cached_prediction({}, race_id="miss")
        assert result is None

    @pytest.mark.anyio
    async def test_set_cache_calls_setex(self, monkeypatch):
        """set_cached_prediction が redis.setex を呼ぶこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = self._make_mock_redis()
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import set_cached_prediction
        result = await set_cached_prediction({}, {"win": 1}, race_id="r1")
        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.anyio
    async def test_set_cache_respects_ttl(self, monkeypatch):
        """カスタム TTL が setex に渡されること"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = self._make_mock_redis()
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import set_cached_prediction
        await set_cached_prediction({}, {}, race_id="r1", ttl=999)
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 999  # TTL が第2引数

    @pytest.mark.anyio
    async def test_invalidate_calls_delete(self, monkeypatch):
        """invalidate_cache が redis.delete を呼ぶこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = self._make_mock_redis()
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import invalidate_cache
        result = await invalidate_cache("r_del")
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.anyio
    async def test_get_stats_returns_dict(self, monkeypatch):
        """get_cache_stats が期待する形式の辞書を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = self._make_mock_redis()
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import get_cache_stats
        stats = await get_cache_stats()
        assert stats["enabled"] is True
        assert "cached_predictions" in stats
        assert "ttl_sec" in stats
        assert stats["cached_predictions"] == 2  # mock keys = 2

    @pytest.mark.anyio
    async def test_redis_error_in_get_returns_none(self, monkeypatch):
        """Redis エラー時に get がフォールバックして None を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import get_cached_prediction
        result = await get_cached_prediction({})
        assert result is None  # エラーは握りつぶす

    @pytest.mark.anyio
    async def test_redis_error_in_set_returns_false(self, monkeypatch):
        """Redis エラー時に set がフォールバックして False を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=ConnectionError("redis down"))
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import set_cached_prediction
        result = await set_cached_prediction({}, {})
        assert result is False


# ============================================================
# get_redis / close_redis（未カバー行）
# ============================================================

class TestGetRedis:
    @pytest.mark.anyio
    async def test_get_redis_creates_client(self, monkeypatch):
        """get_redis が redis.asyncio.from_url でクライアントを生成すること"""
        import types
        import app.cache as cache_module

        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)
        monkeypatch.setattr(cache_module, "_redis_client", None)

        mock_client = AsyncMock()
        fake_aioredis = types.SimpleNamespace(
            from_url=MagicMock(return_value=mock_client)
        )
        fake_redis_pkg = types.SimpleNamespace(asyncio=fake_aioredis)

        import sys
        monkeypatch.setitem(sys.modules, "redis", fake_redis_pkg)
        monkeypatch.setitem(sys.modules, "redis.asyncio", fake_aioredis)

        from app.cache import get_redis
        client = await get_redis()
        assert client is mock_client

    @pytest.mark.anyio
    async def test_close_redis_clears_client(self, monkeypatch):
        """close_redis が接続をクローズしてクライアントをリセットすること"""
        import app.cache as cache_module

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        monkeypatch.setattr(cache_module, "_redis_client", mock_client)

        from app.cache import close_redis
        await close_redis()

        mock_client.aclose.assert_called_once()
        assert cache_module._redis_client is None

    @pytest.mark.anyio
    async def test_close_redis_when_none(self, monkeypatch):
        """_redis_client が None のとき close_redis は何もしないこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_redis_client", None)

        from app.cache import close_redis
        await close_redis()  # 例外にならないこと

    @pytest.mark.anyio
    async def test_invalidate_error_returns_false(self, monkeypatch):
        """invalidate_cached_prediction が Redis エラーのとき False を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=ConnectionError("down"))
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import invalidate_cache
        result = await invalidate_cache("race_123")
        assert result is False

    @pytest.mark.anyio
    async def test_get_cache_stats_error_returns_dict(self, monkeypatch):
        """get_cache_stats が Redis エラーのとき error キー付き dict を返すこと"""
        import app.cache as cache_module
        monkeypatch.setattr(cache_module, "_CACHE_ENABLED", True)

        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(side_effect=ConnectionError("down"))
        monkeypatch.setattr(cache_module, "_redis_client", mock_redis)

        from app.cache import get_cache_stats
        stats = await get_cache_stats()
        assert stats["enabled"] is True
        assert "error" in stats
