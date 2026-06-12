"""
ロガー設定モジュール
アプリケーション全体で共通のロギング設定を提供する
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str, log_level: str = "INFO") -> logging.Logger:
    """
    名前付きロガーを取得する

    Args:
        name: ロガー名（通常は __name__ を渡す）
        log_level: ログレベル文字列（DEBUG/INFO/WARNING/ERROR）

    Returns:
        設定済みの Logger インスタンス
    """
    logger = logging.getLogger(name)

    # 既にハンドラが設定されている場合は再設定しない
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # フォーマット: タイムスタンプ・ログレベル・モジュール名・メッセージ
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 標準出力ハンドラ
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # ファイルハンドラ（ローテーション付き: 10MB × 5世代）
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
