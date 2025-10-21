# tests/server/test_logging_config_coverage.py
"""
Additional tests to improve logging_config coverage.
"""

import logging

from chuk_mcp_runtime.server.logging_config import configure_logging, get_logger


def test_configure_logging_with_logger_overrides():
    """Test configuring logging with specific logger overrides."""
    config = {
        "logging": {
            "level": "INFO",
            "loggers": {"chuk_mcp_runtime.test": "DEBUG", "chuk_mcp_runtime.other": "WARNING"},
        }
    }

    configure_logging(config)

    # Check that specific loggers were configured
    test_logger = logging.getLogger("chuk_mcp_runtime.test")
    other_logger = logging.getLogger("chuk_mcp_runtime.other")

    assert test_logger.level == logging.DEBUG
    assert other_logger.level == logging.WARNING


def test_configure_logging_with_invalid_log_level():
    """Test configuring logging with invalid log level name."""
    config = {"logging": {"level": "INFO", "loggers": {"chuk_mcp_runtime.test": "INVALID_LEVEL"}}}

    # Should not raise, just skip invalid level
    configure_logging(config)

    # Logger should have default level (WARNING)
    test_logger = logging.getLogger("chuk_mcp_runtime.test")
    assert test_logger.level == logging.WARNING


def test_configure_logging_with_mixed_valid_invalid():
    """Test configuring with mix of valid and invalid log levels."""
    config = {
        "logging": {
            "level": "INFO",
            "loggers": {
                "chuk_mcp_runtime.valid": "ERROR",
                "chuk_mcp_runtime.invalid": "NOTAREALEVEL",
                "chuk_mcp_runtime.another": "DEBUG",
            },
        }
    }

    configure_logging(config)

    # Valid loggers should be configured
    valid_logger = logging.getLogger("chuk_mcp_runtime.valid")
    another_logger = logging.getLogger("chuk_mcp_runtime.another")

    assert valid_logger.level == logging.ERROR
    assert another_logger.level == logging.DEBUG


def test_get_logger_with_none_name():
    """Test get_logger when name is None (infers from caller)."""
    # When name is None, it should infer from the calling module
    logger = get_logger(None)

    # Should have returned a logger (name will be inferred)
    assert logger is not None
    assert isinstance(logger, logging.Logger)


def test_get_logger_name_inference():
    """Test that logger name is inferred correctly from module."""
    # This should infer the name from the test module
    logger = get_logger()

    # Logger should exist and have a name
    assert logger is not None
    assert logger.name.startswith("chuk_mcp_runtime")


def test_get_logger_with_config():
    """Test get_logger with configuration."""
    config = {"logging": {"level": "DEBUG"}}

    logger = get_logger("test_module", config)
    assert logger is not None


def test_get_logger_adds_prefix():
    """Test that get_logger adds chuk_mcp_runtime prefix."""
    logger = get_logger("mymodule")

    # Should have added the prefix
    assert logger.name == "chuk_mcp_runtime.mymodule"


def test_get_logger_preserves_prefix():
    """Test that get_logger preserves existing prefix."""
    logger = get_logger("chuk_mcp_runtime.already_prefixed")

    # Should not double the prefix
    assert logger.name == "chuk_mcp_runtime.already_prefixed"
