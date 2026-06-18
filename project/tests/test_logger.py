"""
app/utils/logger.py のテスト
"""
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGetLogger:
    def test_returns_logger_instance(self):
        """Logger インスタンスを返すこと"""
        from app.utils.logger import get_logger
        logger = get_logger("test.module.x1")
        assert isinstance(logger, logging.Logger)

    def test_name_is_set(self):
        """渡した名前が反映されること"""
        from app.utils.logger import get_logger
        logger = get_logger("test.module.x2")
        assert logger.name == "test.module.x2"

    def test_default_level_is_info(self):
        """デフォルトレベルが INFO であること"""
        from app.utils.logger import get_logger
        logger = get_logger("test.module.x3")
        assert logger.level == logging.INFO

    def test_explicit_level_debug(self):
        """DEBUG レベルを指定できること"""
        from app.utils.logger import get_logger
        logger = get_logger("test.module.x4", log_level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_explicit_level_warning(self):
        """WARNING レベルを指定できること"""
        from app.utils.logger import get_logger
        logger = get_logger("test.module.x5", log_level="WARNING")
        assert logger.level == logging.WARNING

    def test_invalid_level_falls_back_to_info(self):
        """不正なレベル文字列は INFO にフォールバックすること"""
        from app.utils.logger import get_logger
        logger = get_logger("test.module.x6", log_level="INVALID")
        assert logger.level == logging.INFO

    def test_handlers_attached(self):
        """StreamHandler と RotatingFileHandler が付与されること"""
        from app.utils.logger import get_logger
        from logging.handlers import RotatingFileHandler
        logger = get_logger("test.module.x7")
        types = {type(h) for h in logger.handlers}
        assert logging.StreamHandler in {t for t in types for _ in [0] if issubclass(t, logging.StreamHandler)} or \
               any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        assert any(isinstance(h, RotatingFileHandler) for h in logger.handlers)

    def test_second_call_returns_same_handlers(self):
        """同名で2回呼ぶとハンドラが重複しないこと"""
        from app.utils.logger import get_logger
        logger1 = get_logger("test.module.x8")
        n1 = len(logger1.handlers)
        logger2 = get_logger("test.module.x8")
        assert logger1 is logger2
        assert len(logger2.handlers) == n1

    def test_logs_directory_created(self):
        """logs/ ディレクトリが作成されること"""
        from app.utils.logger import get_logger
        get_logger("test.module.x9")
        assert Path("logs").exists()
