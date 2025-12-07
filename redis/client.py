#!/usr/bin/env python3
"""
Redis Clone クライアント

シンプルなRedis互換サーバーと通信するためのクライアント実装。
対話モードとプログラマティックな利用の両方に対応。
"""

import socket
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Self


class RedisClientError(Exception):
    """Redisクライアントの基底例外"""


class ConnectionError(RedisClientError):
    """接続エラー"""


class CommandError(RedisClientError):
    """コマンド実行エラー"""


@dataclass
class RedisConfig:
    """接続設定"""

    host: str = "127.0.0.1"
    port: int = 6380
    timeout: float = 5.0
    buffer_size: int = 4096


class RedisClient:
    """Redis Cloneクライアント"""

    def __init__(self, config: RedisConfig | None = None) -> None:
        self._config = config or RedisConfig()
        self._socket: socket.socket | None = None

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> Self:
        """サーバーに接続"""
        if self.is_connected:
            return self

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._config.timeout)
            sock.connect((self._config.host, self._config.port))
            self._socket = sock
        except socket.error as e:
            raise ConnectionError(
                f"接続失敗: {self._config.host}:{self._config.port}"
            ) from e

        return self

    def close(self) -> None:
        """接続を閉じる"""
        if self._socket:
            try:
                self._socket.close()
            except socket.error:
                pass
            finally:
                self._socket = None

    def __enter__(self) -> Self:
        return self.connect()

    def __exit__(self, *_) -> None:
        self.close()

    def execute(self, command: str) -> str:
        """コマンドを実行"""
        if not self._socket:
            raise ConnectionError("未接続です。connect()を呼び出してください")

        try:
            self._socket.sendall(f"{command}\r\n".encode("utf-8"))
            response = self._socket.recv(self._config.buffer_size)
            return response.decode("utf-8").strip()
        except socket.timeout as e:
            raise CommandError(f"タイムアウト: {command}") from e
        except socket.error as e:
            raise CommandError(f"通信エラー: {e}") from e

    # 便利メソッド
    def ping(self) -> str:
        return self.execute("PING")

    def get(self, key: str) -> str:
        return self.execute(f"GET {key}")

    def set(self, key: str, value: str, ex: int | None = None) -> str:
        cmd = f"SET {key} {value}"
        if ex is not None:
            cmd += f" EX {ex}"
        return self.execute(cmd)

    def delete(self, *keys: str) -> str:
        return self.execute(f"DEL {' '.join(keys)}")

    def exists(self, key: str) -> str:
        return self.execute(f"EXISTS {key}")

    def incr(self, key: str) -> str:
        return self.execute(f"INCR {key}")

    def decr(self, key: str) -> str:
        return self.execute(f"DECR {key}")

    def keys(self, pattern: str = "*") -> str:
        return self.execute(f"KEYS {pattern}")

    def ttl(self, key: str) -> str:
        return self.execute(f"TTL {key}")


def run_interactive(config: RedisConfig) -> None:
    """対話モード"""
    print("\n=== Redis Clone クライアント ===")
    print(f"接続先: {config.host}:{config.port}")
    print("終了: quit または Ctrl+C")
    print("=" * 35 + "\n")

    try:
        with RedisClient(config) as client:
            print(f"[+] 接続しました\n")

            while True:
                try:
                    command = input("redis> ").strip()
                except EOFError:
                    break

                if not command:
                    continue

                if command.upper() == "QUIT":
                    print(client.execute("QUIT"))
                    break

                try:
                    print(client.execute(command))
                except CommandError as e:
                    print(f"[エラー] {e}")

    except ConnectionError as e:
        print(f"[エラー] {e}")
    except KeyboardInterrupt:
        print("\n[+] 終了します")

    print("[+] 接続を閉じました")


def run_tests(config: RedisConfig) -> bool:
    """テストスイートを実行"""

    @dataclass
    class TestCase:
        name: str
        command: str
        expected: str | None = None  # Noneの場合は結果を表示のみ

    tests = [
        TestCase("PING応答", "PING", "PONG"),
        TestCase("値の設定", "SET mykey hello", "OK"),
        TestCase("値の取得", "GET mykey", "hello"),
        TestCase("キー存在確認", "EXISTS mykey", "1"),
        TestCase("カウンター初期化", "SET counter 10", "OK"),
        TestCase("インクリメント", "INCR counter", "11"),
        TestCase("インクリメント", "INCR counter", "12"),
        TestCase("デクリメント", "DECR counter", "11"),
        TestCase("TTL付き設定", "SET tempkey temporary EX 5", "OK"),
        TestCase("TTL確認", "TTL tempkey"),
        TestCase("全キー一覧", "KEYS *"),
        TestCase("キー削除", "DEL mykey", "1"),
        TestCase("削除後の確認", "EXISTS mykey", "0"),
    ]

    print("\n=== Redis Clone テスト ===")
    print(f"接続先: {config.host}:{config.port}\n")

    passed = 0
    failed = 0

    try:
        with RedisClient(config) as client:
            for test in tests:
                try:
                    result = client.execute(test.command)
                    ok = test.expected is None or result == test.expected

                    status = "✓" if ok else "✗"
                    print(f"{status} {test.name}")
                    print(f"  コマンド: {test.command}")
                    print(f"  結果: {result}")

                    if test.expected and not ok:
                        print(f"  期待値: {test.expected}")
                        failed += 1
                    else:
                        passed += 1

                except CommandError as e:
                    print(f"✗ {test.name}")
                    print(f"  エラー: {e}")
                    failed += 1

                print()

    except ConnectionError as e:
        print(f"[エラー] {e}")
        return False

    print(f"結果: {passed} passed, {failed} failed")
    return failed == 0


def main() -> int:
    """エントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(description="Redis Clone クライアント")
    parser.add_argument("--host", default="127.0.0.1", help="サーバーホスト")
    parser.add_argument("--port", type=int, default=6380, help="サーバーポート")
    parser.add_argument("--timeout", type=float, default=5.0, help="タイムアウト秒数")
    parser.add_argument("--test", action="store_true", help="テストモードで実行")

    args = parser.parse_args()

    config = RedisConfig(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
    )

    if args.test:
        return 0 if run_tests(config) else 1

    run_interactive(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
