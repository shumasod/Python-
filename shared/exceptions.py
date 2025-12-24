"""統一された例外階層."""
from typing import Optional, Dict, Any


class AppError(Exception):
    """アプリケーション基本例外."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'code': self.code,
            'details': self.details
        }

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ConfigurationError(AppError):
    """設定エラー."""
    pass


class ValidationError(AppError):
    """検証エラー."""
    pass


class ConnectionError(AppError):
    """接続エラー."""
    pass


class StorageError(AppError):
    """ストレージエラー."""
    pass


class AuthenticationError(AppError):
    """認証エラー."""
    pass


class AuthorizationError(AppError):
    """認可エラー."""
    pass


class NotFoundError(AppError):
    """リソース未検出エラー."""
    pass


class ConflictError(AppError):
    """競合エラー."""
    pass


class TimeoutError(AppError):
    """タイムアウトエラー."""
    pass


class RateLimitError(AppError):
    """レート制限エラー."""
    pass
