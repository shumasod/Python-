"""
app/db.py のテスト

asyncpg は環境に未インストールのため、sys.modules に fake モジュールを注入し
非同期接続プール／クエリ発行をモックする。
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# ヘルパー
# ============================================================

def _install_fake_asyncpg(monkeypatch, pool_mock):
    """sys.modules に fake asyncpg を差し込み、create_pool が pool_mock を返すようにする"""
    fake = SimpleNamespace(create_pool=AsyncMock(return_value=pool_mock))
    monkeypatch.setitem(sys.modules, "asyncpg", fake)
    return fake


def _make_pool_mock():
    """asyncpg.Pool を模した MagicMock を返す"""
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock()

    # acquire() は async context manager
    class _Acquire:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            return False

    pool = MagicMock()
    pool.acquire = lambda: _Acquire()
    pool.close = AsyncMock()
    pool._conn = conn  # テストから conn にアクセスしやすいように
    return pool


# ============================================================
# get_pool / close_pool
# ============================================================

class TestGetPool:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        import app.db as db_mod
        monkeypatch.setattr(db_mod, "_pool", None)

    @pytest.mark.anyio
    async def test_import_error_when_asyncpg_missing(self, monkeypatch):
        """asyncpg 未インストール時に ImportError を発生させること"""
        monkeypatch.setitem(sys.modules, "asyncpg", None)
        import app.db as db_mod
        with pytest.raises(ImportError):
            await db_mod.get_pool()

    @pytest.mark.anyio
    async def test_pool_is_cached(self, monkeypatch):
        """2回目以降はキャッシュされた pool を返すこと"""
        pool = _make_pool_mock()
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        p1 = await db_mod.get_pool()
        p2 = await db_mod.get_pool()
        assert p1 is p2
        # create_pool は1回しか呼ばれない
        assert sys.modules["asyncpg"].create_pool.call_count == 1

    @pytest.mark.anyio
    async def test_close_pool_sets_none(self, monkeypatch):
        """close_pool 後に _pool が None に戻ること"""
        pool = _make_pool_mock()
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        await db_mod.get_pool()
        await db_mod.close_pool()
        assert db_mod._pool is None
        pool.close.assert_awaited_once()

    @pytest.mark.anyio
    async def test_close_pool_noop_when_no_pool(self, monkeypatch):
        """pool なしで close_pool を呼んでもエラーにならないこと"""
        import app.db as db_mod
        await db_mod.close_pool()  # 例外が出ないこと


# ============================================================
# log_prediction
# ============================================================

class TestLogPrediction:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        import app.db as db_mod
        monkeypatch.setattr(db_mod, "_pool", None)

    @pytest.mark.anyio
    async def test_inserts_row(self, monkeypatch):
        """INSERT クエリが正しい引数で実行されること"""
        pool = _make_pool_mock()
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        await db_mod.log_prediction(
            race_id="race_001",
            request_body={"a": 1},
            response_body={"b": 2},
            latency_ms=42,
        )
        pool._conn.execute.assert_awaited_once()
        # 第1引数（SQL文）に "INSERT" を含むこと
        args = pool._conn.execute.await_args.args
        assert "INSERT" in args[0]
        assert args[1] == "race_001"
        assert args[4] == 42

    @pytest.mark.anyio
    async def test_swallows_db_errors(self, monkeypatch):
        """DB 接続エラーを握りつぶして例外を投げないこと"""
        # asyncpg を注入せず ImportError を発生させ、log_prediction が吸収するか検証
        monkeypatch.setitem(sys.modules, "asyncpg", None)
        import app.db as db_mod
        # 例外が出なければ OK
        await db_mod.log_prediction("r1", {}, {}, 0)

    @pytest.mark.anyio
    async def test_handles_none_race_id(self, monkeypatch):
        """race_id=None を許容すること"""
        pool = _make_pool_mock()
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        await db_mod.log_prediction(
            race_id=None,
            request_body={},
            response_body={},
            latency_ms=5,
        )
        args = pool._conn.execute.await_args.args
        assert args[1] is None

    @pytest.mark.anyio
    async def test_unicode_json_not_escaped(self, monkeypatch):
        """JSON シリアライズで日本語がエスケープされず保存されること"""
        pool = _make_pool_mock()
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        await db_mod.log_prediction(
            race_id="r1",
            request_body={"場": "江戸川"},
            response_body={"msg": "成功"},
            latency_ms=1,
        )
        args = pool._conn.execute.await_args.args
        # ensure_ascii=False なので日本語がそのまま格納される
        assert "江戸川" in args[2]
        assert "成功" in args[3]


# ============================================================
# get_prediction_stats
# ============================================================

class TestGetPredictionStats:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        import app.db as db_mod
        monkeypatch.setattr(db_mod, "_pool", None)

    @pytest.mark.anyio
    async def test_returns_dict_from_row(self, monkeypatch):
        """fetchrow 結果を dict に変換して返すこと"""
        pool = _make_pool_mock()
        pool._conn.fetchrow = AsyncMock(return_value={
            "total_requests": 100,
            "avg_latency_ms": 45,
            "max_latency_ms": 300,
            "oldest_request": None,
            "latest_request": None,
        })
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        stats = await db_mod.get_prediction_stats(days=7)
        assert stats["total_requests"] == 100
        assert stats["avg_latency_ms"] == 45

    @pytest.mark.anyio
    async def test_returns_empty_on_error(self, monkeypatch):
        """例外時に空 dict を返すこと"""
        monkeypatch.setitem(sys.modules, "asyncpg", None)
        import app.db as db_mod
        stats = await db_mod.get_prediction_stats(days=7)
        assert stats == {}

    @pytest.mark.anyio
    async def test_returns_empty_when_row_none(self, monkeypatch):
        """fetchrow が None を返したときに空 dict を返すこと"""
        pool = _make_pool_mock()
        pool._conn.fetchrow = AsyncMock(return_value=None)
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        stats = await db_mod.get_prediction_stats(days=7)
        assert stats == {}

    @pytest.mark.anyio
    async def test_days_passed_to_query(self, monkeypatch):
        """days 引数が fetchrow に渡されること"""
        pool = _make_pool_mock()
        pool._conn.fetchrow = AsyncMock(return_value={})
        _install_fake_asyncpg(monkeypatch, pool)

        import app.db as db_mod
        await db_mod.get_prediction_stats(days=30)
        args = pool._conn.fetchrow.await_args.args
        assert args[-1] == 30
