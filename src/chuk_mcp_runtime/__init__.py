# chuk_mcp_runtime/__init__.py
"""
CHUK MCP Runtime Package

This package provides a runtime for CHUK MCP (Messaging Control Protocol) servers
with integrated proxy support for connecting to remote MCP servers.

Fully async-native implementation.
"""

__version__ = "0.2.0"

# Import key functions from entry module
from chuk_mcp_runtime.entry import run_runtime, run_runtime_async, main, main_async

__all__ = [
    "run_runtime",
    "run_runtime_async",
    "main",
    "main_async",
]
