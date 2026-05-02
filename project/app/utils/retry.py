"""
リトライ・サーキットブレーカーユーティリティ

外部 HTTP 呼び出し（スクレイパー・オッズ取得）に適用する
指数バックオフ + ジッターによるリトライと、
連続失敗時に一定時間呼び出しをスキップするサーキットブレーカーを提供する

使い方:
  from app.utils.retry import retry, CircuitBreaker

  # デコレータ方式
  @retry(max_attempts=3, base_delay=1.0, exceptions=(requests.Timeout,))
  def fetch_results(url):
      return requests.get(url, timeout=10)

  # サーキットブレーカー
  cb = CircuitBreaker(name="boatrace-site", failure_threshold=5, recovery_timeout=60)

  @cb.call
  def scrape_page(url):
      return requests.get(url)
"""
import functools
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type

from app.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# リトライデコレータ
# ============================================================

def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    指数バックオフ + ジッターによるリトライデコレータ

    Args:
        max_attempts: 最大試行回数（初回含む）
        base_delay: 初回リトライまでの待機秒数
        max_delay: 最大待機秒数（バックオフ上限）
        backoff_factor: バックオフ倍率（デフォルト 2.0 = 1s, 2s, 4s, ...）
        jitter: True の場合、待機時間にランダムなばらつきを加える
        exceptions: リトライ対象の例外クラスタプル
        on_retry: リトライ時に呼び出すコールバック (attempt, exc) -> None

    使い方:
        @retry(max_attempts=3, base_delay=2.0, exceptions=(requests.Timeout,))
        def fetch(url: str) -> str:
            return requests.get(url).text
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exc: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc

                    if attempt == max_attempts:
                        logger.error(
                            f"[retry] {func.__name__} 最大試行回数到達 "
                            f"({max_attempts}/{max_attempts}): {exc}"
                        )
                        raise

                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)  # 50%〜100% のランダム

                    logger.warning(
                        f"[retry] {func.__name__} 失敗 ({attempt}/{max_attempts}), "
                        f"{delay:.2f}s 後にリトライ: {exc}"
                    )

                    if on_retry:
                        on_retry(attempt, exc)

                    time.sleep(delay)

            raise last_exc  # pragma: no cover  型チェック用センチネル

        return wrapper
    return decorator


# ============================================================
# サーキットブレーカー
# ============================================================

class CircuitState(Enum):
    CLOSED   = "closed"    # 正常: リクエスト通過
    OPEN     = "open"      # 障害: リクエスト拒否
    HALF_OPEN = "half_open"  # 復旧試行中


@dataclass
class CircuitBreaker:
    """
    サーキットブレーカー実装

    状態遷移:
      CLOSED → (failure_threshold 回連続失敗) → OPEN
      OPEN   → (recovery_timeout 秒経過)       → HALF_OPEN
      HALF_OPEN → (成功)                        → CLOSED
      HALF_OPEN → (失敗)                        → OPEN

    使い方:
        cb = CircuitBreaker("boatrace-site", failure_threshold=5, recovery_timeout=60)

        @cb.call
        def scrape(url):
            return requests.get(url)

        # または明示的に
        result = cb.execute(lambda: requests.get(url))
    """
    name: str
    failure_threshold: int = 5       # OPEN に遷移する連続失敗回数
    recovery_timeout: float = 60.0   # OPEN → HALF_OPEN の待機秒数
    success_threshold: int = 1       # HALF_OPEN → CLOSED に必要な連続成功回数

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _success_count: int = field(default=0, init=False, repr=False)
    _last_failure_time: float = field(default=0.0, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(f"[circuit:{self.name}] OPEN → HALF_OPEN (経過: {elapsed:.0f}s)")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info(f"[circuit:{self.name}] HALF_OPEN → CLOSED")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0  # 成功でリセット

    def _on_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"[circuit:{self.name}] HALF_OPEN → OPEN (復旧失敗): {exc}")
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                logger.error(
                    f"[circuit:{self.name}] CLOSED → OPEN "
                    f"(連続失敗 {self._failure_count} 回): {exc}"
                )
                self._state = CircuitState.OPEN

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        サーキットブレーカー経由で関数を実行する

        Args:
            func: 実行する関数
            *args, **kwargs: func に渡す引数

        Raises:
            CircuitOpenError: サーキットが OPEN 状態の場合
            Exception: func が送出した例外
        """
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"サーキット '{self.name}' が OPEN です。"
                f"復旧まで約 {self.recovery_timeout:.0f}s 待機してください。"
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as exc:
            self._on_failure(exc)
            raise

    def call(self, func: Callable) -> Callable:
        """デコレータとして使用するためのメソッド"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return self.execute(func, *args, **kwargs)
        return wrapper

    @property
    def stats(self) -> dict:
        """現在の状態統計を返す"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_ago_sec": (
                round(time.monotonic() - self._last_failure_time, 1)
                if self._last_failure_time else None
            ),
        }


class CircuitOpenError(Exception):
    """サーキットブレーカーが OPEN 状態のときに発生する例外"""
    pass
