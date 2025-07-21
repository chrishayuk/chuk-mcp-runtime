# chuk_mcp_runtime/common/errors.py
"""
Error classes for the CHUK MCP runtime.

This module defines standard error classes used across the CHUK MCP runtime.
"""


class ChukMcpRuntimeError(Exception):
    """Base exception class for all CHUK MCP runtime errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ConfigurationError(ChukMcpRuntimeError):
    """Exception raised for configuration errors."""

    pass


class ImportError(ChukMcpRuntimeError):
    """Exception raised for errors during module importing."""

    pass


class ToolExecutionError(ChukMcpRuntimeError):
    """Exception raised for errors during tool execution."""

    pass


class ServerError(ChukMcpRuntimeError):
    """Exception raised for server errors."""

    pass


class ValidationError(ChukMcpRuntimeError):
    """Exception raised for validation errors."""

    pass
