"""
リトライ・サーキットブレーカーユーティリティのテスト
"""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.retry import CircuitBreaker, CircuitOpenError, CircuitState, retry


# ============================================================
# @retry デコレータのテスト
# ============================================================

class TestRetryDecorator:
    def test_success_on_first_attempt(self):
        """初回成功時はそのまま値を返すこと"""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.0)
        def ok():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert ok() == "ok"
        assert call_count == 1

    def test_retries_on_failure_then_succeeds(self):
        """失敗後にリトライして成功すること"""
        attempts = []

        @retry(max_attempts=3, base_delay=0.0, jitter=False)
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("一時的エラー")
            return "done"

        with patch("time.sleep"):
            result = flaky()

        assert result == "done"
        assert len(attempts) == 3

    def test_raises_after_max_attempts(self):
        """最大試行回数を超えたら例外を送出すること"""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.0, jitter=False)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("永続エラー")

        with patch("time.sleep"):
            with pytest.raises(RuntimeError, match="永続エラー"):
                always_fails()

        assert call_count == 3

    def test_only_retries_specified_exceptions(self):
        """指定外の例外はリトライしないこと"""
        call_count = 0

        @retry(max_attempts=5, base_delay=0.0, exceptions=(ValueError,))
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("対象外エラー")

        with pytest.raises(TypeError):
            raises_type_error()

        assert call_count == 1  # リトライなし

    def test_retries_only_matching_exceptions(self):
        """指定した例外のみリトライすること"""
        attempts = []

        @retry(max_attempts=3, base_delay=0.0, jitter=False, exceptions=(ConnectionError,))
        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise ConnectionError("接続エラー")
            return "ok"

        with patch("time.sleep"):
            assert flaky() == "ok"
        assert len(attempts) == 2

    def test_backoff_delay_increases(self):
        """バックオフ遅延が指数的に増加すること"""
        sleep_calls = []

        @retry(max_attempts=4, base_delay=1.0, backoff_factor=2.0, jitter=False)
        def always_fails():
            raise ValueError("fail")

        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            with pytest.raises(ValueError):
                always_fails()

        # 3回スリープ: 1s, 2s, 4s
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)
        assert sleep_calls[2] == pytest.approx(4.0)

    def test_max_delay_cap(self):
        """max_delay を超えないこと"""
        sleep_calls = []

        @retry(max_attempts=5, base_delay=10.0, backoff_factor=10.0, max_delay=15.0, jitter=False)
        def always_fails():
            raise ValueError("fail")

        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            with pytest.raises(ValueError):
                always_fails()

        assert all(s <= 15.0 for s in sleep_calls)

    def test_jitter_reduces_delay(self):
        """ジッターが有効な場合、遅延が base_delay * factor 未満になること"""
        sleep_calls = []

        @retry(max_attempts=3, base_delay=10.0, backoff_factor=1.0, jitter=True)
        def always_fails():
            raise ValueError("fail")

        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            with pytest.raises(ValueError):
                always_fails()

        # jitter は 50%〜100% → 最大 10.0、最小 5.0
        for s in sleep_calls:
            assert 5.0 <= s <= 10.0 + 1e-9

    def test_on_retry_callback_called(self):
        """on_retry コールバックがリトライごとに呼ばれること"""
        retry_calls = []

        @retry(
            max_attempts=3,
            base_delay=0.0,
            jitter=False,
            on_retry=lambda attempt, exc: retry_calls.append((attempt, str(exc))),
        )
        def always_fails():
            raise ValueError("cb_test")

        with patch("time.sleep"):
            with pytest.raises(ValueError):
                always_fails()

        assert len(retry_calls) == 2  # 試行1,2 の失敗後
        assert retry_calls[0][0] == 1
        assert retry_calls[1][0] == 2
        assert "cb_test" in retry_calls[0][1]

    def test_preserves_function_name(self):
        """デコレータがラップした関数の名前を保持すること"""
        @retry(max_attempts=1)
        def my_named_func():
            return 42

        assert my_named_func.__name__ == "my_named_func"

    def test_returns_value_correctly(self):
        """関数の戻り値を正しく返すこと"""
        @retry(max_attempts=1)
        def compute():
            return {"result": [1, 2, 3]}

        assert compute() == {"result": [1, 2, 3]}


# ============================================================
# CircuitBreaker のテスト
# ============================================================

class TestCircuitBreakerInitialState:
    def test_initial_state_is_closed(self):
        """初期状態は CLOSED であること"""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_execute_success_returns_value(self):
        """成功時に戻り値が返ること"""
        cb = CircuitBreaker(name="test")
        result = cb.execute(lambda: 42)
        assert result == 42

    def test_execute_reraises_circuit_open_error(self):
        """func が CircuitOpenError を投げたとき再 raise されること"""
        cb = CircuitBreaker(name="test_reraise", failure_threshold=10)
        def nested_open():
            raise CircuitOpenError("nested circuit open")
        with pytest.raises(CircuitOpenError, match="nested"):
            cb.execute(nested_open)


class TestCircuitBreakerTransitions:
    def test_closed_to_open_after_threshold(self):
        """failure_threshold 回連続失敗で OPEN に遷移すること"""
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60.0)

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.execute(lambda: (_ for _ in ()).throw(ValueError("err")))

        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        """OPEN 状態でリクエストを拒否すること"""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=60.0)

        for _ in range(2):
            with pytest.raises(Exception):
                cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            cb.execute(lambda: "should not run")

    def test_open_to_half_open_after_timeout(self):
        """recovery_timeout 後に HALF_OPEN に遷移すること"""
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.05)

        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        """HALF_OPEN で成功すると CLOSED に戻ること"""
        cb = CircuitBreaker(
            name="test", failure_threshold=1, recovery_timeout=0.05, success_threshold=1
        )

        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        result = cb.execute(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        """HALF_OPEN で失敗すると再び OPEN に戻ること"""
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.05)

        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("y")))

        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """成功後に失敗カウントがリセットされること"""
        cb = CircuitBreaker(name="test", failure_threshold=3)

        # 2回失敗（閾値未達）
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert cb._failure_count == 2

        # 1回成功 → カウントリセット
        cb.execute(lambda: "ok")
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    def test_call_decorator_works(self):
        """@cb.call デコレータとして使えること"""
        cb = CircuitBreaker(name="deco-test", failure_threshold=5)
        call_count = 0

        @cb.call
        def my_func():
            nonlocal call_count
            call_count += 1
            return "hello"

        assert my_func() == "hello"
        assert call_count == 1

    def test_call_decorator_preserves_name(self):
        """@cb.call がラップした関数名を保持すること"""
        cb = CircuitBreaker(name="test")

        @cb.call
        def named_func():
            return 1

        assert named_func.__name__ == "named_func"

    def test_call_decorator_propagates_exception(self):
        """@cb.call が例外を伝播させること"""
        cb = CircuitBreaker(name="test", failure_threshold=10)

        @cb.call
        def bad_func():
            raise ValueError("expected")

        with pytest.raises(ValueError, match="expected"):
            bad_func()


class TestCircuitBreakerStats:
    def test_stats_returns_dict(self):
        """stats が辞書を返すこと"""
        cb = CircuitBreaker(name="stats-test")
        s = cb.stats
        assert isinstance(s, dict)
        assert s["name"] == "stats-test"
        assert s["state"] == "closed"

    def test_stats_failure_count(self):
        """stats に失敗カウントが反映されること"""
        cb = CircuitBreaker(name="stats-test", failure_threshold=5)

        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert cb.stats["failure_count"] == 1

    def test_stats_last_failure_ago(self):
        """stats の last_failure_ago_sec が None でないこと（失敗後）"""
        cb = CircuitBreaker(name="test")

        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert cb.stats["last_failure_ago_sec"] is not None
        assert cb.stats["last_failure_ago_sec"] >= 0.0

    def test_stats_no_failure_returns_none_for_time(self):
        """失敗がない場合 last_failure_ago_sec が None であること"""
        cb = CircuitBreaker(name="fresh")
        assert cb.stats["last_failure_ago_sec"] is None


class TestCircuitOpenError:
    def test_circuit_open_error_is_exception(self):
        """`CircuitOpenError` が Exception のサブクラスであること"""
        assert issubclass(CircuitOpenError, Exception)

    def test_circuit_open_error_message(self):
        """エラーメッセージを持てること"""
        err = CircuitOpenError("テストエラー")
        assert "テストエラー" in str(err)

    def test_circuit_open_error_not_retried_by_circuit(self):
        """CircuitOpenError がサーキットブレーカーの失敗カウントに含まれないこと"""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.05)

        # まず OPEN にする
        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert cb.state == CircuitState.OPEN
        failure_count_before = cb._failure_count

        # OPEN の状態で呼ぶと CircuitOpenError → 失敗カウントに加算されない
        with pytest.raises(CircuitOpenError):
            cb.execute(lambda: "noop")

        assert cb._failure_count == failure_count_before
