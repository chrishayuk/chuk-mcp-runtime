# chuk_mcp_runtime/proxy/__init__.py
"""
CHUK MCP Runtime Proxy Package

This package provides proxy functionality for CHUK MCP Runtime,
allowing it to manage and communicate with other MCP servers.
"""

from chuk_mcp_runtime.proxy.manager import ProxyServerManager

__all__ = ["ProxyServerManager"]
