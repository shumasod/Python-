"""
カスタム例外クラス
"""

from typing import Optional, Dict, Any


class BaseAppException(Exception):
    """アプリケーションの基底例外クラス"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Args:
            message: エラーメッセージ
            details: 追加の詳細情報
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """例外情報を辞書形式で返す"""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'details': self.details
        }


class PredictionError(BaseAppException):
    """予測処理に関するエラー"""
    
    def __init__(self, message: str = "予測の実行中にエラーが発生しました", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class DataProcessingError(BaseAppException):
    """データ処理に関するエラー"""
    
    def __init__(self, message: str = "データ処理中にエラーが発生しました", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class ModelError(BaseAppException):
    """モデルに関するエラー"""
    
    def __init__(self, message: str = "モデルエラーが発生しました", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class ModelNotFoundError(ModelError):
    """モデルが見つからない場合のエラー"""
    
    def __init__(self, model_path: str):
        message = f"モデルが見つかりません: {model_path}"
        details = {'model_path': model_path}
        super().__init__(message, details)


class ModelLoadError(ModelError):
    """モデルの読み込みに失敗した場合のエラー"""
    
    def __init__(self, model_path: str, reason: Optional[str] = None):
        message = f"モデルの読み込みに失敗しました: {model_path}"
        details = {'model_path': model_path}
        if reason:
            details['reason'] = reason
        super().__init__(message, details)


class ModelSaveError(ModelError):
    """モデルの保存に失敗した場合のエラー"""
    
    def __init__(self, model_path: str, reason: Optional[str] = None):
        message = f"モデルの保存に失敗しました: {model_path}"
        details = {'model_path': model_path}
        if reason:
            details['reason'] = reason
        super().__init__(message, details)


class DataValidationError(DataProcessingError):
    """データバリデーションエラー"""
    
    def __init__(self, field: str, reason: str):
        message = f"データバリデーションエラー: {field}"
        details = {'field': field, 'reason': reason}
        super().__init__(message, details)


class ScrapingError(DataProcessingError):
    """スクレイピング処理に関するエラー"""
    
    def __init__(self, url: str, reason: Optional[str] = None):
        message = f"データのスクレイピングに失敗しました: {url}"
        details = {'url': url}
        if reason:
            details['reason'] = reason
        super().__init__(message, details)


class FeatureExtractionError(DataProcessingError):
    """特徴量抽出エラー"""
    
    def __init__(self, message: str = "特徴量の抽出に失敗しました", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class TrainingError(ModelError):
    """モデルのトレーニングエラー"""
    
    def __init__(self, message: str = "モデルのトレーニングに失敗しました", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class ConfigurationError(BaseAppException):
    """設定に関するエラー"""
    
    def __init__(self, parameter: str, reason: str):
        message = f"設定エラー: {parameter}"
        details = {'parameter': parameter, 'reason': reason}
        super().__init__(message, details)


class ResourceNotFoundError(BaseAppException):
    """リソースが見つからない場合のエラー"""
    
    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type}が見つかりません: {resource_id}"
        details = {'resource_type': resource_type, 'resource_id': resource_id}
        super().__init__(message, details)


class InvalidInputError(BaseAppException):
    """入力データが無効な場合のエラー"""
    
    def __init__(self, message: str = "入力データが無効です", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class APIError(BaseAppException):
    """API呼び出しに関するエラー"""
    
    def __init__(self, endpoint: str, status_code: int, reason: Optional[str] = None):
        message = f"APIエラー: {endpoint} (Status: {status_code})"
        details = {'endpoint': endpoint, 'status_code': status_code}
        if reason:
            details['reason'] = reason
        super().__init__(message, details)


class DatabaseError(BaseAppException):
    """データベース操作に関するエラー"""
    
    def __init__(self, operation: str, reason: Optional[str] = None):
        message = f"データベースエラー: {operation}"
        details = {'operation': operation}
        if reason:
            details['reason'] = reason
        super().__init__(message, details)


class AuthenticationError(BaseAppException):
    """認証エラー"""
    
    def __init__(self, message: str = "認証に失敗しました", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class AuthorizationError(BaseAppException):
    """認可エラー"""
    
    def __init__(self, message: str = "権限がありません", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class RateLimitError(BaseAppException):
    """レート制限エラー"""
    
    def __init__(self, limit: int, window: str):
        message = f"レート制限を超えました: {limit}リクエスト/{window}"
        details = {'limit': limit, 'window': window}
        super().__init__(message, details)
