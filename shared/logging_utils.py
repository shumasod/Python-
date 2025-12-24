"""中央ロギング設定."""
import logging
import sys
from pathlib import Path
from typing import Optional
from .config import get_config


def setup_logging(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    ロギングを設定.

    Args:
        name: ロガー名（通常は__name__）
        level: ログレベル（省略時は設定から取得）
        log_file: ログファイルパス（省略時は標準出力のみ）
        format_string: ログフォーマット（省略時は設定から取得）

    Returns:
        設定済みのロガー

    Example:
        >>> logger = setup_logging(__name__)
        >>> logger.info("Application started")
    """
    config = get_config()

    # ログレベル
    if level is None:
        level = config.log_level

    # フォーマット
    if format_string is None:
        format_string = config.log_format

    # ロガー作成
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # 既存のハンドラをクリア
    logger.handlers.clear()

    # フォーマッタ
    formatter = logging.Formatter(
        fmt=format_string,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 標準出力ハンドラ
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(getattr(logging, level.upper()))
    logger.addHandler(stream_handler)

    # ファイルハンドラ（オプション）
    if log_file or config.log_file:
        file_path = Path(log_file) if log_file else Path(config.log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, level.upper()))
        logger.addHandler(file_handler)

    # 親ロガーへの伝播を防ぐ
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    既存のロガーを取得、または新しいロガーを作成.

    Args:
        name: ロガー名

    Returns:
        ロガー
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger
