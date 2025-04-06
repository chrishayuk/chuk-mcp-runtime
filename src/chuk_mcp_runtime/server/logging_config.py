# chuk_mcp_runtime/server/logging_config.py
"""
Logging configuration module for CHUK MCP servers.

This module sets up a shared logger with configurable logging levels,
formats, and output handlers based on configuration.
"""
import os
import sys
import logging
from logging import Logger
from typing import Dict, Any, Optional

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
        handler = logging.StreamHandler(sys.stdout)
        
        # Set formatter
        log_format = log_config.get("format", 
                                  '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)
        
        root_logger.addHandler(handler)
    
    # Set library loggers to higher level to reduce noise
    if log_config.get("quiet_libraries", True):
        for lib in ["urllib3", "requests", "asyncio"]:
            logging.getLogger(lib).setLevel(logging.WARNING)

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
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
        name = module.__name__ if module else "chuk_mcp_runtime"
    
    # Ensure our base prefix is in the name
    if not name.startswith("chuk_mcp_runtime"):
        name = f"chuk_mcp_runtime.{name}"
    
    # Configure global logging if config is provided
    if config:
        configure_logging(config)
    
    # Get logger
    logger = logging.getLogger(name)
    
    return logger

# Create a default logger for the module
logger = get_logger("chuk_mcp_runtime.logging")