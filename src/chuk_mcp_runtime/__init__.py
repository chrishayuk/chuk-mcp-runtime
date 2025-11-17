# chuk_mcp_runtime/__init__.py
"""
CHUK MCP Runtime Package

This package provides a runtime for CHUK MCP (Messaging Control Protocol) servers
with integrated proxy support for connecting to remote MCP servers.

Fully async-native, Pydantic-based, type-safe implementation.
"""

__version__ = "0.2.0"

# ─────────────────────────── Core Entry Points ──────────────────────────────
from chuk_mcp_runtime.common.mcp_resource_decorator import mcp_resource

# ─────────────────────────── Tool Decorators ──────────────────────────────
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.entry import main, main_async, run_runtime, run_runtime_async

# ─────────────────────────── Progress & Context ──────────────────────────────
from chuk_mcp_runtime.server.request_context import (
    MCPRequestContext,
    get_request_context,
    send_progress,
)

# ─────────────────────────── Server ──────────────────────────────
from chuk_mcp_runtime.server.server import MCPServer

# ─────────────────────────── Session Management ──────────────────────────────
from chuk_mcp_runtime.session import (
    MCPSessionManager,
    SessionContext,
    SessionError,
    SessionNotFoundError,
    SessionValidationError,
    create_mcp_session_manager,
    get_session_or_none,
    get_user_or_none,
    require_session,
    require_user,
)

# ─────────────────────────── Types (Pydantic Models) ──────────────────────────────
from chuk_mcp_runtime.types import (
    # Artifact Models
    ArtifactMetadata,
    # Configuration Models
    ArtifactsConfig,
    # Enums
    AuthType,
    HostConfig,
    LoggingConfig,
    LogLevel,
    MCPServerConfig,
    ProxyConfig,
    RuntimeConfig,
    ServerConfig,
    ServerType,
    # Session Models
    SessionInfo,
    SessionProvider,
    SessionsConfig,
    SessionStats,
    SSEConfig,
    StorageProvider,
    StorageStats,
    StreamableHTTPConfig,
    # Tool Models
    ToolCallResult,
    ToolMetadata,
    ToolsConfig,
)

# ─────────────────────────── Public API ──────────────────────────────
__all__ = [
    # Entry points
    "run_runtime",
    "run_runtime_async",
    "main",
    "main_async",
    # Server
    "MCPServer",
    # Progress & Context
    "send_progress",
    "get_request_context",
    "MCPRequestContext",
    # Session Management
    "MCPSessionManager",
    "SessionContext",
    "create_mcp_session_manager",
    "require_session",
    "require_user",
    "get_session_or_none",
    "get_user_or_none",
    "SessionError",
    "SessionNotFoundError",
    "SessionValidationError",
    # Decorators
    "mcp_tool",
    "mcp_resource",
    # Enums
    "ServerType",
    "LogLevel",
    "StorageProvider",
    "SessionProvider",
    "AuthType",
    # Configuration Models
    "RuntimeConfig",
    "HostConfig",
    "ServerConfig",
    "LoggingConfig",
    "ToolsConfig",
    "ProxyConfig",
    "SessionsConfig",
    "ArtifactsConfig",
    "SSEConfig",
    "StreamableHTTPConfig",
    "MCPServerConfig",
    # Session Models
    "SessionInfo",
    "SessionStats",
    # Tool Models
    "ToolMetadata",
    "ToolCallResult",
    # Artifact Models
    "ArtifactMetadata",
    "StorageStats",
]
