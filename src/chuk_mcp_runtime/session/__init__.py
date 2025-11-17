# chuk_mcp_runtime/session/__init__.py
"""
Session management package for CHUK MCP Runtime.

This package provides session context management and session-aware tools
for maintaining state across tool calls in the MCP runtime.

Usage Examples
--------------
# Recommended imports
from chuk_mcp_runtime.session import MCPSessionManager, SessionContext

# Or from the main session management module
from chuk_mcp_runtime.session.session_management import MCPSessionManager, SessionContext

session_manager = MCPSessionManager(sandbox_id="my-app")
async with SessionContext(session_manager, user_id="alice") as session_id:
    # Work within session context
    pass
"""

# Import pydantic types from chuk_sessions
from chuk_sessions.enums import SessionStatus
from chuk_sessions.models import SessionMetadata

# Import from the main session management module for clean public API
from chuk_mcp_runtime.session.session_management import (
    # Core classes
    MCPSessionManager,
    SessionContext,
    # Exceptions
    SessionError,
    SessionNotFoundError,
    SessionValidationError,
    create_mcp_session_manager,
    create_session_manager,
    get_session_or_none,
    get_user_or_none,
    # Context helpers
    require_session,
    require_user,
    session_optional,
    session_required,
    # Tool integration
    with_session_auto_inject,
)

# Public API - what users should import
__all__ = [
    # Core session management (primary API)
    "MCPSessionManager",
    "SessionContext",
    "create_mcp_session_manager",
    "create_session_manager",
    # Types from chuk_sessions (pydantic native)
    "SessionMetadata",
    "SessionStatus",
    # Context functions
    "require_session",
    "require_user",
    "get_session_or_none",
    "get_user_or_none",
    # Tool integration
    "with_session_auto_inject",
    "session_required",
    "session_optional",
    # Exceptions
    "SessionError",
    "SessionNotFoundError",
    "SessionValidationError",
]

__version__ = "2.0.0"
