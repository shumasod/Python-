"""
JRA競馬予測アプリケーション

Flask アプリケーションファクトリとAPIエンドポイント定義。
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable, TypeVar

from flask import Flask, Response, jsonify, render_template, request

# =============================================================================
# Type Definitions
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


class Environment(Enum):
    """実行環境"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class AppConfig:
    """アプリケーション設定"""

    # Basic
    app_name: str = "JRA競馬予測"
    version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT

    # Server
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    secret_key: str = field(default_factory=lambda: os.urandom(24).hex())

    # Model
    model_path: Path | None = None
    auto_train: bool = True

    # Scraping
    base_url: str = "https://example.com/races"
    num_pages: int = 10
    scrape_timeout: int = 30

    # Logging
    log_level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    log_to_file: bool = True

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    @classmethod
    def from_env(cls) -> AppConfig:
        """環境変数から設定を読み込み"""
        env_str = os.getenv("APP_ENV", "development").lower()
        try:
            environment = Environment(env_str)
        except ValueError:
            environment = Environment.DEVELOPMENT

        model_path_str = os.getenv("MODEL_PATH")

        return cls(
            environment=environment,
            host=os.getenv("FLASK_HOST", "0.0.0.0"),
            port=int(os.getenv("FLASK_PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
            secret_key=os.getenv("SECRET_KEY", os.urandom(24).hex()),
            model_path=Path(model_path_str) if model_path_str else None,
            base_url=os.getenv("SCRAPE_BASE_URL", "https://example.com/races"),
            num_pages=int(os.getenv("SCRAPE_NUM_PAGES", "10")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_to_file=os.getenv("LOG_TO_FILE", "true").lower() == "true",
        )

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT


# =============================================================================
# Logging
# =============================================================================


def setup_logging(config: AppConfig) -> logging.Logger:
    """ロギングをセットアップ"""
    config.log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if config.log_to_file:
        log_file = config.log_dir / f"app_{datetime.now():%Y%m%d}.log"
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    return logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class AppError(Exception):
    """アプリケーションエラーの基底クラス"""

    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationError(AppError):
    """バリデーションエラー"""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, HTTPStatus.BAD_REQUEST, details)


class PredictionError(AppError):
    """予測エラー"""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, HTTPStatus.INTERNAL_SERVER_ERROR, details)


class ModelNotLoadedError(AppError):
    """モデル未読み込みエラー"""

    def __init__(self) -> None:
        super().__init__(
            "モデルが読み込まれていません",
            HTTPStatus.SERVICE_UNAVAILABLE,
        )


# =============================================================================
# Response Helpers
# =============================================================================


@dataclass
class APIResponse:
    """API レスポンス"""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.details:
            result["details"] = self.details
        return result


def success_response(
    data: dict[str, Any],
    status_code: int = HTTPStatus.OK,
) -> tuple[Response, int]:
    """成功レスポンスを生成"""
    return jsonify(APIResponse(success=True, data=data).to_dict()), status_code


def error_response(
    message: str,
    status_code: int = HTTPStatus.BAD_REQUEST,
    details: dict[str, Any] | None = None,
) -> tuple[Response, int]:
    """エラーレスポンスを生成"""
    return (
        jsonify(APIResponse(success=False, error=message, details=details).to_dict()),
        status_code,
    )


# =============================================================================
# Decorators
# =============================================================================


def require_json(f: F) -> F:
    """JSON リクエストを要求するデコレータ"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not request.is_json:
            return error_response(
                "Content-Type は application/json である必要があります",
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
        if not request.json:
            return error_response("リクエストボディが空です")
        return f(*args, **kwargs)

    return decorated  # type: ignore


def handle_errors(f: F) -> F:
    """エラーハンドリングデコレータ"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except AppError as e:
            logging.getLogger(__name__).warning("AppError: %s", e.message)
            return error_response(e.message, e.status_code, e.details)
        except Exception as e:
            logging.getLogger(__name__).exception("Unexpected error: %s", e)
            return error_response(
                "予期せぬエラーが発生しました",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    return decorated  # type: ignore


# =============================================================================
# Services
# =============================================================================


class ModelService:
    """モデル管理サービス"""

    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._model: Any = None
        self._preprocessor: Any = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_type(self) -> str | None:
        if self._model is None:
            return None
        return type(self._model).__name__

    def initialize(self) -> None:
        """モデルを初期化"""
        self._logger.info("モデル初期化開始")

        if self._config.model_path and self._config.model_path.exists():
            self._load_model(self._config.model_path)
        elif self._config.auto_train:
            self._train_new_model()
        else:
            self._logger.warning("モデルが設定されていません")

    def _load_model(self, path: Path) -> None:
        """保存済みモデルを読み込み"""
        self._logger.info("モデル読み込み: %s", path)

        try:
            # 実際のモデル読み込みロジック
            # from .models import JRAPredictionApp
            # self._model = JRAPredictionApp.load(path)
            self._loaded = True
            self._logger.info("モデル読み込み完了")
        except Exception as e:
            self._logger.error("モデル読み込みエラー: %s", e)
            raise PredictionError(f"モデル読み込み失敗: {e}")

    def _train_new_model(self) -> None:
        """新しいモデルをトレーニング"""
        self._logger.info("新規モデルトレーニング開始")

        try:
            # 実際のトレーニングロジック
            # scraper = DataScraper(self._config.base_url)
            # data = scraper.scrape(self._config.num_pages)
            # self._model = JRAPredictionApp()
            # self._model.train(data)

            if self._config.model_path:
                self._save_model(self._config.model_path)

            self._loaded = True
            self._logger.info("モデルトレーニング完了")

        except Exception as e:
            self._logger.error("トレーニングエラー: %s", e)
            raise PredictionError(f"モデルトレーニング失敗: {e}")

    def _save_model(self, path: Path) -> None:
        """モデルを保存"""
        path.parent.mkdir(parents=True, exist_ok=True)
        # self._model.save(path)
        self._logger.info("モデル保存: %s", path)

    def predict(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """予測を実行"""
        if not self._loaded:
            raise ModelNotLoadedError()

        # 実際の予測ロジック
        # df = self._preprocess(input_data)
        # prediction = self._model.predict(df)
        # confidence = self._model.predict_proba(df).max()

        # デモ用のダミーレスポンス
        prediction = "本命馬"
        confidence = 0.85

        return {
            "prediction": prediction,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }


class InputValidator:
    """入力バリデーター"""

    REQUIRED_FIELDS = ["horse_name", "jockey", "weight"]
    OPTIONAL_FIELDS = ["age", "previous_results", "odds"]

    @classmethod
    def validate(cls, data: dict[str, Any]) -> dict[str, Any]:
        """入力データをバリデート"""
        errors: list[str] = []

        # 必須フィールドチェック
        for field_name in cls.REQUIRED_FIELDS:
            if field_name not in data:
                errors.append(f"必須フィールドがありません: {field_name}")
            elif not data[field_name]:
                errors.append(f"フィールドが空です: {field_name}")

        # 数値フィールドの型チェック
        if "weight" in data:
            try:
                data["weight"] = float(data["weight"])
                if data["weight"] <= 0:
                    errors.append("体重は正の数である必要があります")
            except (ValueError, TypeError):
                errors.append("体重は数値である必要があります")

        if "age" in data and data["age"] is not None:
            try:
                data["age"] = int(data["age"])
                if not 2 <= data["age"] <= 20:
                    errors.append("年齢は2〜20の範囲である必要があります")
            except (ValueError, TypeError):
                errors.append("年齢は整数である必要があります")

        if errors:
            raise ValidationError(
                "入力データが無効です",
                {"validation_errors": errors},
            )

        return data


# =============================================================================
# Application Factory
# =============================================================================


def create_app(config: AppConfig | None = None) -> Flask:
    """Flask アプリケーションを作成"""
    if config is None:
        config = AppConfig.from_env()

    # ロギング設定
    logger = setup_logging(config)
    logger.info("=" * 50)
    logger.info("%s v%s 起動", config.app_name, config.version)
    logger.info("環境: %s", config.environment.value)
    logger.info("=" * 50)

    # Flask アプリ作成
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["JSON_AS_ASCII"] = False

    # サービス初期化
    model_service = ModelService(config, logger)

    # 起動時にモデル初期化（テスト環境以外）
    if config.environment != Environment.TESTING:
        try:
            model_service.initialize()
        except Exception as e:
            logger.error("モデル初期化失敗: %s", e)
            if config.is_production:
                raise

    # アプリケーションコンテキストに保存
    app.extensions["model_service"] = model_service
    app.extensions["config"] = config

    # ルート登録
    register_routes(app, model_service, config, logger)
    register_error_handlers(app, config, logger)

    return app


def register_routes(
    app: Flask,
    model_service: ModelService,
    config: AppConfig,
    logger: logging.Logger,
) -> None:
    """ルートを登録"""

    @app.route("/")
    def index() -> str | tuple[Response, int]:
        """ホームページ"""
        try:
            return render_template("index.html", config=config)
        except Exception as e:
            logger.error("テンプレートエラー: %s", e)
            return error_response(
                "ページの表示に失敗しました",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    @app.route("/health")
    def health() -> tuple[Response, int]:
        """ヘルスチェック"""
        status = "healthy" if model_service.is_loaded else "degraded"
        return success_response({
            "status": status,
            "version": config.version,
            "environment": config.environment.value,
            "model_loaded": model_service.is_loaded,
            "timestamp": datetime.now().isoformat(),
        })

    @app.route("/ready")
    def readiness() -> tuple[Response, int]:
        """レディネスチェック"""
        if not model_service.is_loaded:
            return error_response(
                "モデルが準備できていません",
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
        return success_response({"ready": True})

    @app.route("/api/v1/predict", methods=["POST"])
    @require_json
    @handle_errors
    def predict() -> tuple[Response, int]:
        """予測API"""
        logger.info("予測リクエスト受信")

        # バリデーション
        validated_data = InputValidator.validate(request.json)

        # 予測実行
        result = model_service.predict(validated_data)

        logger.info(
            "予測完了: %s (信頼度: %.2f)",
            result["prediction"],
            result["confidence"],
        )

        return success_response(result)

    @app.route("/api/v1/info")
    def api_info() -> tuple[Response, int]:
        """API情報"""
        return success_response({
            "name": config.app_name,
            "version": config.version,
            "endpoints": [
                {"path": "/", "method": "GET", "description": "ホームページ"},
                {"path": "/health", "method": "GET", "description": "ヘルスチェック"},
                {"path": "/ready", "method": "GET", "description": "レディネスチェック"},
                {"path": "/api/v1/predict", "method": "POST", "description": "予測API"},
                {"path": "/api/v1/info", "method": "GET", "description": "API情報"},
            ],
            "model": {
                "loaded": model_service.is_loaded,
                "type": model_service.model_type,
            },
        })


def register_error_handlers(
    app: Flask,
    config: AppConfig,
    logger: logging.Logger,
) -> None:
    """エラーハンドラーを登録"""

    @app.errorhandler(HTTPStatus.NOT_FOUND)
    def not_found(_: Exception) -> tuple[Response, int]:
        return error_response(
            "ページが見つかりません",
            HTTPStatus.NOT_FOUND,
            {"path": request.path},
        )

    @app.errorhandler(HTTPStatus.METHOD_NOT_ALLOWED)
    def method_not_allowed(e: Exception) -> tuple[Response, int]:
        return error_response(
            "許可されていないHTTPメソッドです",
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"method": request.method},
        )

    @app.errorhandler(HTTPStatus.INTERNAL_SERVER_ERROR)
    def internal_error(e: Exception) -> tuple[Response, int]:
        logger.exception("Internal server error")
        message = str(e) if config.is_development else "サーバーエラーが発生しました"
        return error_response(message, HTTPStatus.INTERNAL_SERVER_ERROR)


# =============================================================================
# Entry Point
# =============================================================================


def main() -> None:
    """アプリケーションエントリーポイント"""
    config = AppConfig.from_env()
    app = create_app(config)

    print("=" * 50)
    print(f"{config.app_name} v{config.version}")
    print("=" * 50)
    print(f"環境: {config.environment.value}")
    print(f"URL: http://{config.host}:{config.port}")
    print(f"デバッグ: {config.debug}")
    print("=" * 50)

    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug,
    )


if __name__ == "__main__":
    main()
