# chuk_mcp_runtime/tools/session_tools.py
"""
Session Management Tools for CHUK MCP Runtime

This module provides MCP tools for managing session context and state.
These tools allow clients to manage their session lifecycle directly.

NOTE: These tools are DISABLED by default and must be explicitly enabled
in configuration to be available.
"""

from typing import Any, Dict, Optional

from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY, mcp_tool
from chuk_mcp_runtime.server.logging_config import get_logger
from chuk_mcp_runtime.session.session_management import (
    clear_session_context,
    get_session_context,
    set_session_context,
)

logger = get_logger("chuk_mcp_runtime.tools.session")

# FIXED: Default configuration for session tools - DISABLED by default
DEFAULT_SESSION_TOOLS_CONFIG = {
    "enabled": False,  # DISABLED by default - must be explicitly enabled
    "tools": {
        "get_current_session": {
            "enabled": False,  # DISABLED by default
            "description": "Get information about the current session context",
        },
        "set_session": {
            "enabled": False,  # DISABLED by default
            "description": "Set the session context for subsequent operations",
        },
        "clear_session": {
            "enabled": False,  # DISABLED by default
            "description": "Clear the current session context",
        },
        "list_sessions": {
            "enabled": False,  # DISABLED by default
            "description": "List all active sessions",
        },
        "get_session_info": {
            "enabled": False,  # DISABLED by default
            "description": "Get detailed information about a specific session",
        },
        "create_session": {
            "enabled": False,  # DISABLED by default
            "description": "Create a new session with optional metadata",
        },
    },
}

# Global configuration state
_session_tools_config: Dict[str, Any] = {}
_enabled_session_tools: set = set()


def configure_session_tools(config: Dict[str, Any]) -> None:
    """Configure session tools based on configuration."""
    global _session_tools_config, _enabled_session_tools

    # Get session tools configuration
    _session_tools_config = config.get("session_tools", DEFAULT_SESSION_TOOLS_CONFIG)

    # Clear enabled tools
    _enabled_session_tools.clear()

    # Check if session tools are enabled globally
    if not _session_tools_config.get("enabled", False):
        logger.debug(
            "Session tools disabled in configuration - use 'session_tools.enabled: true' to enable"
        )
        return

    # Process individual tool configuration
    tools_config = _session_tools_config.get("tools", DEFAULT_SESSION_TOOLS_CONFIG["tools"])

    for tool_name, tool_config in tools_config.items():
        if tool_config.get("enabled", False):
            _enabled_session_tools.add(tool_name)
            logger.debug(f"Enabled session tool: {tool_name}")
        else:
            logger.debug(
                f"Disabled session tool: {tool_name} - use 'session_tools.tools.{tool_name}.enabled: true' to enable"
            )

    if _enabled_session_tools:
        logger.debug(
            f"Configured {len(_enabled_session_tools)} session tools: {', '.join(sorted(_enabled_session_tools))}"
        )
    else:
        logger.debug("No session tools enabled - all tools require explicit configuration")


def is_session_tool_enabled(tool_name: str) -> bool:
    """Check if a specific session tool is enabled."""
    return tool_name in _enabled_session_tools


# ============================================================================
# Session Management Tools
# ============================================================================


@mcp_tool(
    name="get_current_session",
    description="Get information about the current session context",
)
async def get_current_session() -> Dict[str, Any]:
    """
    Get information about the current session.

    Returns:
        Dictionary containing current session information including:
        - session_id: Current session ID or None
        - status: 'active' if session exists, 'no_session' if not
        - message: Human-readable status message
    """
    current_session = get_session_context()

    if current_session:
        return {
            "session_id": current_session,
            "status": "active",
            "message": f"Current session: {current_session}",
        }
    else:
        return {
            "session_id": None,
            "status": "no_session",
            "message": "No session context available. A session will be auto-created when needed.",
        }


@mcp_tool(name="set_session", description="Set the session context for subsequent operations")
async def set_session_context_tool(session_id: str) -> str:
    """
    Set the session context for subsequent operations.

    Args:
        session_id: Session ID to use for subsequent operations.
                   Must be a valid session ID (alphanumeric, dots, underscores, hyphens)

    Returns:
        Success message confirming the session was set

    Raises:
        ValueError: If the session ID is invalid or cannot be set
    """
    try:
        # Basic validation for session ID format
        if not session_id or not isinstance(session_id, str):
            raise ValueError("Session ID must be a non-empty string")

        set_session_context(session_id)
        return f"Session context set to: {session_id}"
    except Exception as e:
        raise ValueError(f"Failed to set session context: {str(e)}")


@mcp_tool(name="clear_session", description="Clear the current session context")
async def clear_session_context_tool() -> str:
    """
    Clear the current session context.

    Returns:
        Success message confirming the session was cleared
    """
    previous_session = get_session_context()
    clear_session_context()

    if previous_session:
        return f"Session context cleared (was: {previous_session})"
    else:
        return "Session context cleared (no previous session)"


@mcp_tool(name="list_sessions", description="List all active sessions")
async def list_sessions_tool() -> Dict[str, Any]:
    """
    List all active sessions.

    Returns:
        Dictionary containing:
        - sessions: List of active session IDs (limited functionality without session manager)
        - count: Number of active sessions
        - current_session: Current session ID if any
    """
    current = get_session_context()

    # Note: Without direct access to session manager, we can only return current session
    sessions = [current] if current else []

    return {
        "sessions": sessions,
        "count": len(sessions),
        "current_session": current,
        "note": "Limited to current session context - full session listing requires session manager integration",
    }


@mcp_tool(
    name="get_session_info",
    description="Get detailed information about a specific session",
)
async def get_session_info_tool(session_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific session.

    Args:
        session_id: Session ID to get information about

    Returns:
        Dictionary containing session information and metadata
    """
    try:
        # Basic validation
        if not session_id or not isinstance(session_id, str):
            raise ValueError("Session ID must be a non-empty string")

        # Get basic session info
        current = get_session_context()
        is_current = current == session_id

        result = {
            "session_id": session_id,
            "is_current": is_current,
            "status": "active" if is_current else "unknown",
            "note": "Limited session info available - requires session manager for full details",
        }

        if is_current:
            result["metadata"] = {
                "context_source": "session_context",
                "tools_used": "session_management_tools",
            }

        return result

    except Exception as e:
        raise ValueError(f"Failed to get session info: {str(e)}")


@mcp_tool(name="create_session", description="Create a new session with optional metadata")
async def create_session_tool(
    session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new session with optional metadata.

    Args:
        session_id: Optional session ID. If not provided, a unique ID will be generated
        metadata: Optional metadata to associate with the session

    Returns:
        Dictionary containing information about the created session
    """
    import time
    import uuid

    # Generate session ID if not provided
    if session_id is None:
        timestamp = int(time.time())
        random_suffix = str(uuid.uuid4().hex)[:8]
        session_id = f"session-{timestamp}-{random_suffix}"

    try:
        # Basic validation
        if not session_id or not isinstance(session_id, str):
            raise ValueError("Session ID must be a non-empty string")

        # Set the session context
        set_session_context(session_id)

        # Add creation metadata
        creation_meta = {
            "created_at": time.time(),
            "created_via": "session_management_tools",
            "note": "Basic session creation - full functionality requires session manager integration",
        }

        if metadata:
            creation_meta.update(metadata)

        return {
            "session_id": session_id,
            "status": "created",
            "is_current": True,
            "metadata": creation_meta,
        }

    except Exception as e:
        raise ValueError(f"Failed to create session: {str(e)}")


# ============================================================================
# Registration Functions
# ============================================================================


async def register_session_tools(config: Dict[str, Any] | None = None) -> bool:
    """
    Register (or remove) session-management tools according to *config*.

    * If the `session_tools` block is missing **or** has `enabled: false`
      the six helpers are removed from ``TOOLS_REGISTRY`` and the function
      returns ``False``.
    * Otherwise, only the helpers whose own `enabled: true` flag is set are
      initialised and kept in the registry.

    Returns
    -------
    bool
        ``True`` iff at least one helper ends up registered.
    """
    # ------------------------------------------------------------------ 0. helpers
    ALL_SESSION_TOOLS = {
        "get_current_session": get_current_session,
        "set_session": set_session_context_tool,
        "clear_session": clear_session_context_tool,
        "list_sessions": list_sessions_tool,
        "get_session_info": get_session_info_tool,
        "create_session": create_session_tool,
    }

    def prune_all() -> None:
        """Remove every session helper from TOOLS_REGISTRY (present or not)."""
        for t in ALL_SESSION_TOOLS:
            TOOLS_REGISTRY.pop(t, None)

    # ------------------------------------------------------------------ 1. config gate
    sess_cfg = (config or {}).get("session_tools", {})
    if not sess_cfg.get("enabled", False):
        prune_all()
        logger.debug(
            "Session tools disabled - use 'session_tools.enabled: true' in config to enable"
        )
        return False

    # Which helpers are individually enabled?
    enabled_tools = {
        name for name, tcfg in sess_cfg.get("tools", {}).items() if tcfg.get("enabled", False)
    }
    if not enabled_tools:
        prune_all()
        logger.debug(
            "Session tools block present but no individual tools enabled - use 'session_tools.tools.<tool_name>.enabled: true' to enable specific tools"
        )
        return False

    # ------------------------------------------------------------------ 2. initialize registry metadata
    from chuk_mcp_runtime.common.mcp_tool_decorator import initialize_tool_registry

    await initialize_tool_registry()

    # ------------------------------------------------------------------ 3. prune everything, then keep only wanted ones
    prune_all()
    registered = 0

    for name in enabled_tools:
        ALL_SESSION_TOOLS[name]

        # Ensure tool is properly initialized
        from chuk_mcp_runtime.common.mcp_tool_decorator import ensure_tool_initialized

        try:
            initialized_fn = await ensure_tool_initialized(name)
            TOOLS_REGISTRY[name] = initialized_fn
            registered += 1
            logger.debug("Registered session tool: %s", name)
        except Exception as e:
            logger.error("Failed to register session tool %s: %s", name, e)

    if registered > 0:
        logger.debug(
            "Registered %d session tool(s): %s",
            registered,
            ", ".join(sorted(enabled_tools)),
        )
    else:
        logger.warning("No session tools were successfully registered")

    return bool(registered)


def get_session_tools_info() -> Dict[str, Any]:
    """Get information about available and configured session tools."""
    all_tools = list(DEFAULT_SESSION_TOOLS_CONFIG["tools"].keys())

    return {
        "available": True,  # Session tools are always available
        "configured": bool(_session_tools_config),
        "enabled_globally": _session_tools_config.get("enabled", False)
        if _session_tools_config
        else False,
        "enabled_tools": list(_enabled_session_tools),
        "disabled_tools": [t for t in all_tools if t not in _enabled_session_tools],
        "total_tools": len(all_tools),
        "enabled_count": len(_enabled_session_tools),
        "config": _session_tools_config,
        "default_state": "disabled",
        "enable_instructions": {
            "global": "Set 'session_tools.enabled: true' in configuration",
            "individual": "Set 'session_tools.tools.<tool_name>.enabled: true' for each desired tool",
        },
    }


def get_enabled_session_tools() -> list[str]:
    """Get list of currently enabled session tools."""
    return list(_enabled_session_tools)
