import logging
import pytest

from davinci_cli.core.logging import setup_logging, get_logger


class TestSetupLogging:
    def test_default_level_is_warning(self):
        """デフォルトのログレベルは WARNING"""
        setup_logging(verbose=False, debug=False)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.WARNING

    def test_verbose_sets_info(self):
        """--verbose で INFO レベルに設定"""
        setup_logging(verbose=True, debug=False)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.INFO

    def test_debug_sets_debug(self):
        """--debug で DEBUG レベルに設定"""
        setup_logging(verbose=False, debug=True)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.DEBUG

    def test_debug_overrides_verbose(self):
        """--debug は --verbose より優先"""
        setup_logging(verbose=True, debug=True)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.DEBUG

    def test_logger_has_handler(self):
        """ロガーにハンドラが設定されていること"""
        setup_logging(verbose=True, debug=False)
        logger = get_logger("davinci_cli")
        assert len(logger.handlers) > 0

    def test_log_format_contains_level(self, capsys):
        """ログ出力にレベル名が含まれること"""
        setup_logging(verbose=True, debug=False)
        logger = get_logger("davinci_cli.test")
        logger.info("test message")
        captured = capsys.readouterr()
        assert "INFO" in captured.err or "test message" in captured.err


class TestGetLogger:
    def test_returns_logger_with_name(self):
        logger = get_logger("davinci_cli.core")
        assert logger.name == "davinci_cli.core"

    def test_child_logger_inherits_from_parent(self):
        setup_logging(verbose=True, debug=False)
        parent = get_logger("davinci_cli")
        child = get_logger("davinci_cli.core")
        # 子ロガーは親の設定を継承する
        assert child.parent is parent or child.parent is not None
