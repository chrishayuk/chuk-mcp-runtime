"""
Enhanced logging configuration module for CHUK MCP servers.

This module sets up a shared logger with configurable logging levels,
formats, and per-logger overrides based on configuration.
"""

import logging
import os
import sys
from logging import Logger
from typing import Any, Dict


def configure_logging(config: Dict[str, Any] = None) -> None:
    """
    Configure the root logger based on the provided configuration.

    Args:
        config: Configuration dictionary containing logging settings.
    """
    # Extract logging configuration
    log_config = config.get("logging", {}) if config else {}

    # Determine log level from config or environment
    log_level_name = log_config.get("level", os.getenv("CHUK_MCP_LOG_LEVEL", "INFO"))
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers if requested
    if log_config.get("reset_handlers", False):
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # Add handlers if none exist
    if not root_logger.handlers:
        # Send logs to stderr instead of stdout.
        handler = logging.StreamHandler(sys.stderr)

        # Set formatter
        log_format = log_config.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)

        root_logger.addHandler(handler)

    # Set library loggers to higher level to reduce noise
    if log_config.get("quiet_libraries", True):
        for lib in ["urllib3", "requests", "asyncio", "httpx"]:
            logging.getLogger(lib).setLevel(logging.WARNING)

    # Quiet the specific library logging for mcp.server.lowlevel.server
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)

    # Quiet chuk runtime component initialization logs
    for component in [
        "chuk_sessions.session_manager",
        "chuk_artifacts.store",
        "chuk_mcp_runtime.server",
    ]:
        logging.getLogger(component).setLevel(logging.WARNING)

    # NEW: Configure specific loggers from config
    logger_overrides = log_config.get("loggers", {})
    for logger_name, level_name in logger_overrides.items():
        try:
            level = getattr(logging, level_name.upper(), logging.WARNING)
            logging.getLogger(logger_name).setLevel(level)
        except AttributeError:
            # Invalid log level name, skip
            continue


def get_logger(name: str = None, config: Dict[str, Any] = None) -> Logger:
    """
    Get a configured logger with the specified name.

    Args:
        name: The name of the logger. If None, uses the calling module's name.
        config: Optional configuration dictionary.

    Returns:
        A logger instance.
    """
    # If name is None, try to infer from caller's module
    if name is None:
        import inspect

        current_frame = inspect.currentframe()
        frame = current_frame.f_back if current_frame else None
        module = inspect.getmodule(frame) if frame else None
        name = module.__name__ if module else "chuk_mcp_runtime"

    # Ensure our base prefix is in the name
    if not name.startswith("chuk_mcp_runtime"):
        name = f"chuk_mcp_runtime.{name}"

    # Configure global logging if config is provided
    if config:
        configure_logging(config)

    # Get logger
    logger = logging.getLogger(name)

    # return the logger
    return logger


# Create a default logger for the module
logger = get_logger("chuk_mcp_runtime.logging")
