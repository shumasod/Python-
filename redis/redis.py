#!/usr/bin/env python3
"""
Redis Clone Server

シンプルなインメモリKey-Valueストア。
RESP (Redis Serialization Protocol) 互換のレスポンスを返す。

サポートコマンド:
  - 文字列: SET, GET, APPEND, STRLEN
  - 数値: INCR, DECR, INCRBY, DECRBY
  - キー: DEL, EXISTS, EXPIRE, TTL, KEYS, RENAME, TYPE
  - サーバー: PING, ECHO, INFO, DBSIZE, FLUSHDB
"""

import logging
import re
import signal
import socket
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# RESP Protocol
# =============================================================================


class RespType(Enum):
    """RESPデータ型"""

    SIMPLE_STRING = "+"
    ERROR = "-"
    INTEGER = ":"
    BULK_STRING = "$"
    ARRAY = "*"


class Resp:
    """RESPプロトコル エンコーダー"""

    @staticmethod
    def ok() -> str:
        return "+OK\r\n"

    @staticmethod
    def pong() -> str:
        return "+PONG\r\n"

    @staticmethod
    def simple_string(value: str) -> str:
        return f"+{value}\r\n"

    @staticmethod
    def error(message: str) -> str:
        return f"-ERR {message}\r\n"

    @staticmethod
    def integer(value: int) -> str:
        return f":{value}\r\n"

    @staticmethod
    def bulk_string(value: str | None) -> str:
        if value is None:
            return "$-1\r\n"
        return f"${len(value)}\r\n{value}\r\n"

    @staticmethod
    def array(items: list[str]) -> str:
        if items is None:
            return "*-1\r\n"
        response = f"*{len(items)}\r\n"
        for item in items:
            response += Resp.bulk_string(item)
        return response


# =============================================================================
# Storage Layer
# =============================================================================


@dataclass
class Entry:
    """ストレージエントリ"""

    value: Any
    expires_at: float | None = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def ttl(self) -> int:
        if self.expires_at is None:
            return -1
        remaining = int(self.expires_at - time.time())
        return remaining if remaining > 0 else -2


class Storage:
    """スレッドセーフなKey-Valueストレージ"""

    def __init__(self) -> None:
        self._data: dict[str, Entry] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Entry | None:
        """エントリを取得（期限切れチェック付き）"""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._data[key]
                return None
            return entry

    def set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """値を設定"""
        with self._lock:
            exists = self.get(key) is not None

            if nx and exists:
                return False
            if xx and not exists:
                return False

            expires_at = time.time() + ex if ex else None
            self._data[key] = Entry(value=value, expires_at=expires_at)
            return True

    def delete(self, *keys: str) -> int:
        """キーを削除"""
        count = 0
        with self._lock:
            for key in keys:
                if key in self._data:
                    del self._data[key]
                    count += 1
        return count

    def exists(self, *keys: str) -> int:
        """存在するキーの数を返す"""
        count = 0
        for key in keys:
            if self.get(key) is not None:
                count += 1
        return count

    def expire(self, key: str, seconds: int) -> bool:
        """有効期限を設定"""
        with self._lock:
            entry = self.get(key)
            if entry is None:
                return False
            entry.expires_at = time.time() + seconds
            return True

    def keys(self, pattern: str = "*") -> list[str]:
        """パターンにマッチするキーを取得"""
        with self._lock:
            # 期限切れをクリーンアップ
            valid_keys = [k for k in self._data if self.get(k) is not None]

        if pattern == "*":
            return valid_keys

        regex = re.compile(pattern.replace("*", ".*").replace("?", "."))
        return [k for k in valid_keys if regex.fullmatch(k)]

    def rename(self, old_key: str, new_key: str) -> bool:
        """キーをリネーム"""
        with self._lock:
            entry = self.get(old_key)
            if entry is None:
                return False
            self._data[new_key] = entry
            del self._data[old_key]
            return True

    def size(self) -> int:
        """有効なキーの数"""
        return len(self.keys())

    def flush(self) -> None:
        """全データ削除"""
        with self._lock:
            self._data.clear()


# =============================================================================
# Command System
# =============================================================================


@dataclass
class CommandContext:
    """コマンド実行コンテキスト"""

    storage: Storage
    args: list[str]
    client_address: tuple[str, int]


class Command(ABC):
    """コマンドの基底クラス"""

    name: str
    min_args: int = 0
    max_args: int | None = None

    @abstractmethod
    def execute(self, ctx: CommandContext) -> str:
        """コマンドを実行"""

    def validate_args(self, args: list[str]) -> str | None:
        """引数を検証。エラーがあればエラーメッセージを返す"""
        if len(args) < self.min_args:
            return f"wrong number of arguments for '{self.name}' command"
        if self.max_args is not None and len(args) > self.max_args:
            return f"wrong number of arguments for '{self.name}' command"
        return None


# --- 文字列コマンド ---


class SetCommand(Command):
    name = "SET"
    min_args = 2

    def execute(self, ctx: CommandContext) -> str:
        key, value = ctx.args[0], ctx.args[1]
        ex = None
        nx = False
        xx = False

        i = 2
        while i < len(ctx.args):
            opt = ctx.args[i].upper()
            if opt == "EX" and i + 1 < len(ctx.args):
                try:
                    ex = int(ctx.args[i + 1])
                    i += 2
                except ValueError:
                    return Resp.error("invalid expire time")
            elif opt == "NX":
                nx = True
                i += 1
            elif opt == "XX":
                xx = True
                i += 1
            else:
                i += 1

        success = ctx.storage.set(key, value, ex=ex, nx=nx, xx=xx)
        return Resp.ok() if success else Resp.bulk_string(None)


class GetCommand(Command):
    name = "GET"
    min_args = 1
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        entry = ctx.storage.get(ctx.args[0])
        if entry is None:
            return Resp.bulk_string(None)
        return Resp.bulk_string(str(entry.value))


class AppendCommand(Command):
    name = "APPEND"
    min_args = 2
    max_args = 2

    def execute(self, ctx: CommandContext) -> str:
        key, value = ctx.args[0], ctx.args[1]
        entry = ctx.storage.get(key)

        if entry is None:
            ctx.storage.set(key, value)
            return Resp.integer(len(value))

        new_value = str(entry.value) + value
        ctx.storage.set(key, new_value)
        return Resp.integer(len(new_value))


class StrlenCommand(Command):
    name = "STRLEN"
    min_args = 1
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        entry = ctx.storage.get(ctx.args[0])
        if entry is None:
            return Resp.integer(0)
        return Resp.integer(len(str(entry.value)))


# --- 数値コマンド ---


class IncrCommand(Command):
    name = "INCR"
    min_args = 1
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        return self._modify(ctx, 1)

    def _modify(self, ctx: CommandContext, delta: int) -> str:
        key = ctx.args[0]
        entry = ctx.storage.get(key)

        if entry is None:
            ctx.storage.set(key, str(delta))
            return Resp.integer(delta)

        try:
            value = int(entry.value) + delta
            ctx.storage.set(key, str(value))
            return Resp.integer(value)
        except ValueError:
            return Resp.error("value is not an integer")


class DecrCommand(IncrCommand):
    name = "DECR"

    def execute(self, ctx: CommandContext) -> str:
        return self._modify(ctx, -1)


class IncrByCommand(IncrCommand):
    name = "INCRBY"
    min_args = 2
    max_args = 2

    def execute(self, ctx: CommandContext) -> str:
        try:
            delta = int(ctx.args[1])
        except ValueError:
            return Resp.error("value is not an integer")
        ctx.args = [ctx.args[0]]
        return self._modify(ctx, delta)


class DecrByCommand(IncrByCommand):
    name = "DECRBY"

    def execute(self, ctx: CommandContext) -> str:
        try:
            delta = int(ctx.args[1])
        except ValueError:
            return Resp.error("value is not an integer")
        ctx.args = [ctx.args[0]]
        return self._modify(ctx, -delta)


# --- キーコマンド ---


class DelCommand(Command):
    name = "DEL"
    min_args = 1

    def execute(self, ctx: CommandContext) -> str:
        count = ctx.storage.delete(*ctx.args)
        return Resp.integer(count)


class ExistsCommand(Command):
    name = "EXISTS"
    min_args = 1

    def execute(self, ctx: CommandContext) -> str:
        count = ctx.storage.exists(*ctx.args)
        return Resp.integer(count)


class ExpireCommand(Command):
    name = "EXPIRE"
    min_args = 2
    max_args = 2

    def execute(self, ctx: CommandContext) -> str:
        try:
            seconds = int(ctx.args[1])
        except ValueError:
            return Resp.error("invalid expire time")

        success = ctx.storage.expire(ctx.args[0], seconds)
        return Resp.integer(1 if success else 0)


class TtlCommand(Command):
    name = "TTL"
    min_args = 1
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        entry = ctx.storage.get(ctx.args[0])
        if entry is None:
            return Resp.integer(-2)
        return Resp.integer(entry.ttl())


class KeysCommand(Command):
    name = "KEYS"
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        pattern = ctx.args[0] if ctx.args else "*"
        keys = ctx.storage.keys(pattern)
        return Resp.array(keys)


class RenameCommand(Command):
    name = "RENAME"
    min_args = 2
    max_args = 2

    def execute(self, ctx: CommandContext) -> str:
        success = ctx.storage.rename(ctx.args[0], ctx.args[1])
        if not success:
            return Resp.error("no such key")
        return Resp.ok()


class TypeCommand(Command):
    name = "TYPE"
    min_args = 1
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        entry = ctx.storage.get(ctx.args[0])
        if entry is None:
            return Resp.simple_string("none")
        return Resp.simple_string("string")


# --- サーバーコマンド ---


class PingCommand(Command):
    name = "PING"
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        if ctx.args:
            return Resp.bulk_string(ctx.args[0])
        return Resp.pong()


class EchoCommand(Command):
    name = "ECHO"
    min_args = 1
    max_args = 1

    def execute(self, ctx: CommandContext) -> str:
        return Resp.bulk_string(ctx.args[0])


class DbSizeCommand(Command):
    name = "DBSIZE"
    max_args = 0

    def execute(self, ctx: CommandContext) -> str:
        return Resp.integer(ctx.storage.size())


class FlushDbCommand(Command):
    name = "FLUSHDB"
    max_args = 0

    de
