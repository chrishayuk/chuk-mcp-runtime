# chuk_mcp_runtime/session/session_management.py
"""
Session management for CHUK MCP Runtime.

This is the main session management module that provides native chuk-sessions
integration with session context management and session-aware tools.

Usage Examples
--------------
from chuk_mcp_runtime.session.session_management import MCPSessionManager, SessionContext

session_manager = MCPSessionManager(sandbox_id="my-app")
async with SessionContext(session_manager, user_id="alice") as session_id:
    # Work within session context
    pass
"""

# Import everything from the native implementation
from typing import Optional

# Import pydantic types from chuk_sessions
from chuk_mcp_runtime.session.native_session_management import (
    # Core native classes
    MCPSessionManager,
    SessionContext,
    # Exceptions
    SessionError,
    SessionNotFoundError,
    SessionValidationError,
    clear_session_context,
    create_mcp_session_manager,
    get_session_context,
    get_session_or_none,
    get_user_or_none,
    # Context helpers
    require_session,
    require_user,
    session_optional,
    session_required,
    # Backwards compatibility functions (these exist for legacy support)
    set_session_context,
    # Tool integration
    with_session_auto_inject,
)


# Make validate_session_parameter fully async
async def validate_session_parameter(
    session_id: Optional[str],
    operation: str,
    session_manager: Optional[MCPSessionManager] = None,
) -> str:
    """
    Validate and return a session ID, creating one if necessary.

    Args:
        session_id: Optional session ID to validate
        operation: Name of the operation requiring the session (for error messages)
        session_manager: Optional session manager for auto-creation

    Returns:
        Valid session ID

    Raises:
        SessionError: If no session can be determined
        SessionValidationError: If provided session ID is invalid
    """
    # If session_id is provided, validate it
    if session_id:
        if session_manager and not await session_manager.validate_session(session_id):
            raise SessionValidationError(
                f"Invalid session ID for operation '{operation}': {session_id}"
            )
        return session_id

    # Try to get from context
    current = get_session_context()
    if current:
        if session_manager and not await session_manager.validate_session(current):
            # Current session is invalid, clear it
            clear_session_context()
        else:
            return current

    # Auto-create if session manager is available
    if session_manager:
        new_session = await session_manager.auto_create_session_if_needed()
        return new_session

    # No session available and can't create one
    raise SessionError(f"Operation '{operation}' requires valid session_id or session manager")


# Re-export everything for clean imports
__all__ = [
    # Core session management
    "MCPSessionManager",
    "SessionContext",
    "create_mcp_session_manager",
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
    # Fixed session validation
    "validate_session_parameter",
    # Legacy compatibility
    "set_session_context",
    "get_session_context",
    "clear_session_context",
]


# Convenience factory function
def create_session_manager(sandbox_id=None, default_ttl_hours=24, auto_extend_threshold=0.1):
    """
    Create a new session manager with the given configuration.

    Args:
        sandbox_id: Unique identifier for this sandbox/application
        default_ttl_hours: Default session lifetime in hours
        auto_extend_threshold: Threshold for automatic session extension (0.0-1.0)

    Returns:
        MCPSessionManager: Configured session manager instance
    """
    return MCPSessionManager(
        sandbox_id=sandbox_id,
        default_ttl_hours=default_ttl_hours,
        auto_extend_threshold=auto_extend_threshold,
    )


# Version info
__version__ = "2.0.0"
