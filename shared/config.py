"""設定管理."""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseConfig:
    """基本設定."""

    # アプリケーション設定
    app_name: str = "Python Utilities"
    debug: bool = False
    testing: bool = False

    # ログ設定
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None

    # データベース設定
    database_url: Optional[str] = None

    # Redis設定
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # API設定
    api_host: str = "0.0.0.0"
    api_port: int = 5000
    api_timeout: int = 30

    # セキュリティ設定
    secret_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'BaseConfig':
        """環境変数から設定を読み込む."""
        return cls(
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            testing=os.getenv('TESTING', 'False').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file=os.getenv('LOG_FILE'),
            database_url=os.getenv('DATABASE_URL'),
            redis_host=os.getenv('REDIS_HOST', 'localhost'),
            redis_port=int(os.getenv('REDIS_PORT', '6379')),
            redis_db=int(os.getenv('REDIS_DB', '0')),
            api_host=os.getenv('API_HOST', '0.0.0.0'),
            api_port=int(os.getenv('API_PORT', '5000')),
            secret_key=os.getenv('SECRET_KEY'),
        )


@dataclass
class DevelopmentConfig(BaseConfig):
    """開発環境設定."""

    debug: bool = True
    log_level: str = "DEBUG"
    database_url: str = "sqlite:///dev.db"


@dataclass
class ProductionConfig(BaseConfig):
    """本番環境設定."""

    debug: bool = False
    log_level: str = "WARNING"

    def __post_init__(self):
        """本番環境の検証."""
        if not self.secret_key:
            raise ValueError("SECRET_KEY must be set in production")
        if not self.database_url:
            raise ValueError("DATABASE_URL must be set in production")


@dataclass
class TestingConfig(BaseConfig):
    """テスト環境設定."""

    testing: bool = True
    debug: bool = True
    log_level: str = "DEBUG"
    database_url: str = "sqlite:///:memory:"


# 環境ごとの設定マッピング
_CONFIG_MAP = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}


def get_config(env: Optional[str] = None) -> BaseConfig:
    """
    環境に応じた設定を取得.

    Args:
        env: 環境名（development, production, testing）
            Noneの場合は環境変数ENVから取得

    Returns:
        設定オブジェクト
    """
    if env is None:
        env = os.getenv('ENV', 'development')

    config_class = _CONFIG_MAP.get(env, DevelopmentConfig)
    return config_class.from_env()
