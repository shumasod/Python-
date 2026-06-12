"""
app/api/ratelimit.py のテスト

slowapi は環境に未インストールのため、無効パス（_limiter=None）を検証する。
有効パスは slowapi をモックして動作を確認する。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# get_limiter
# ============================================================

class TestGetLimiter:
    def test_returns_none_when_slowapi_missing(self, monkeypatch):
        """slowapi 未インストール時に None を返すこと"""
        import app.api.ratelimit as rl
        monkeypatch.setattr(rl, "_limiter", None)
        assert rl.get_limiter() is None

    def test_returns_limiter_when_set(self, monkeypatch):
        """_limiter がセットされているとき返すこと"""
        import app.api.ratelimit as rl
        mock_limiter = MagicMock()
        monkeypatch.setattr(rl, "_limiter", mock_limiter)
        assert rl.get_limiter() is mock_limiter


# ============================================================
# rate_limit デコレータ
# ============================================================

class TestRateLimitDecorator:
    def test_passthrough_when_disabled(self, monkeypatch):
        """_limiter=None のとき関数をそのまま返すこと"""
        import app.api.ratelimit as rl
        monkeypatch.setattr(rl, "_limiter", None)
        monkeypatch.setattr(rl, "_ENABLED", False)

        original = lambda: "ok"
        decorated = rl.rate_limit("10/minute")(original)
        assert decorated is original

    def test_passthrough_when_not_enabled(self, monkeypatch):
        """_ENABLED=False のとき関数をそのまま返すこと"""
        import app.api.ratelimit as rl
        mock_limiter = MagicMock()
        monkeypatch.setattr(rl, "_limiter", mock_limiter)
        monkeypatch.setattr(rl, "_ENABLED", False)

        fn = lambda: "test"
        result = rl.rate_limit("30/minute")(fn)
        assert result is fn

    def test_applies_limit_when_enabled(self, monkeypatch):
        """_ENABLED=True のとき limiter.limit() が呼ばれること"""
        import types
        import app.api.ratelimit as rl

        # slowapi が未インストールなので fake を注入する
        fake_slowapi = types.ModuleType("slowapi")
        fake_slowapi.Limiter = MagicMock()
        monkeypatch.setitem(sys.modules, "slowapi", fake_slowapi)

        limited_fn = MagicMock(return_value=lambda: "limited")
        mock_limiter = MagicMock()
        mock_limiter.limit.return_value = limited_fn
        monkeypatch.setattr(rl, "_limiter", mock_limiter)
        monkeypatch.setattr(rl, "_ENABLED", True)

        fn = lambda: "original"
        rl.rate_limit("5/minute")(fn)
        mock_limiter.limit.assert_called_once_with("5/minute")

    def test_default_limit_string(self, monkeypatch):
        """デフォルト引数が "60/minute" であること"""
        import inspect
        import app.api.ratelimit as rl
        sig = inspect.signature(rl.rate_limit)
        assert sig.parameters["limit_string"].default == "60/minute"


# ============================================================
# rate_limit_exceeded_handler
# ============================================================

class TestRateLimitExceededHandler:
    @pytest.mark.anyio
    async def test_returns_429_response(self):
        """429 ステータスの JSONResponse を返すこと"""
        from fastapi.responses import JSONResponse
        import app.api.ratelimit as rl

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/v1/predict"

        mock_exc = MagicMock()
        mock_exc.detail = "60 per 1 minute"

        response = await rl.rate_limit_exceeded_handler(mock_request, mock_exc)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 429

    @pytest.mark.anyio
    async def test_response_contains_detail(self):
        """レスポンスに 'detail' キーが含まれること"""
        import json
        import app.api.ratelimit as rl

        mock_request = MagicMock()
        mock_request.client.host = "1.2.3.4"
        mock_request.url.path = "/test"
        mock_exc = MagicMock()
        mock_exc.detail = "30/minute"

        response = await rl.rate_limit_exceeded_handler(mock_request, mock_exc)
        body = json.loads(response.body)
        assert "detail" in body
        assert "limit" in body

    @pytest.mark.anyio
    async def test_exc_without_detail_attr(self):
        """exc に detail 属性がなくてもエラーにならないこと"""
        import app.api.ratelimit as rl

        mock_request = MagicMock()
        mock_request.client.host = "0.0.0.0"
        mock_request.url.path = "/x"
        exc_without_detail = Exception("no detail attr")

        response = await rl.rate_limit_exceeded_handler(mock_request, exc_without_detail)
        assert response.status_code == 429


# ============================================================
# 環境変数設定
# ============================================================

class TestEnvConfig:
    def test_default_limit_env(self, monkeypatch):
        """RATE_LIMIT_DEFAULT のデフォルト値が "60/minute" であること"""
        import app.api.ratelimit as rl
        assert "minute" in rl._DEFAULT_LIMIT

    def test_enabled_flag_type(self):
        """_ENABLED がブール値であること"""
        import app.api.ratelimit as rl
        assert isinstance(rl._ENABLED, bool)
