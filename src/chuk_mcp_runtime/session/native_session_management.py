# chuk_mcp_runtime/session/native_session_management.py
"""
Native chuk-sessions integration for CHUK MCP Runtime.

This module replaces the bridge pattern with direct chuk-sessions usage,
providing cleaner, more efficient session management.
"""

from __future__ import annotations

import os
import time
from contextvars import ContextVar
from typing import Any, Dict, Optional

from chuk_sessions import SessionManager

from chuk_mcp_runtime.server.logging_config import get_logger

logger = get_logger("chuk_mcp_runtime.session.native")

# ───────────────────────── Context Variables ──────────────────────────
_session_ctx: ContextVar[Optional[str]] = ContextVar("session_context", default=None)
_user_ctx: ContextVar[Optional[str]] = ContextVar("user_context", default=None)


# ───────────────────────── Exception Types ─────────────────────────────
class SessionError(Exception):
    """Base exception for session-related errors."""

    pass


class SessionNotFoundError(SessionError):
    """Session does not exist or has expired."""

    pass


class SessionValidationError(SessionError):
    """Session validation failed."""

    pass


# ───────────────────────── Native Session Manager ──────────────────────
class MCPSessionManager:
    """
    Native session manager for MCP Runtime using chuk-sessions.

    Provides clean, efficient session management without bridge complexity.
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        default_ttl_hours: int = 24,
        auto_extend_threshold: float = 0.1,  # Extend when 10% of TTL remains
    ):
        self.sandbox_id = sandbox_id or self._infer_sandbox_id()
        self.default_ttl_hours = default_ttl_hours
        self.auto_extend_threshold = auto_extend_threshold

        # Create the underlying SessionManager
        self._session_manager = SessionManager(
            sandbox_id=self.sandbox_id, default_ttl_hours=default_ttl_hours
        )

        logger.info(f"Initialized MCPSessionManager for sandbox: {self.sandbox_id}")

    def _infer_sandbox_id(self) -> str:
        """Infer sandbox ID from environment or generate one."""
        sandbox = (
            os.getenv("MCP_SANDBOX_ID")
            or os.getenv("CHUK_SANDBOX_ID")
            or os.getenv("SANDBOX_ID")
            or os.getenv("POD_NAME")
            or f"mcp-runtime-{int(time.time())}"
        )
        return sandbox

    # ─────────────────── Session Lifecycle ───────────────────────

    async def create_session(
        self,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new session with optional user and metadata."""
        session_id = await self._session_manager.allocate_session(
            user_id=user_id,
            ttl_hours=ttl_hours or self.default_ttl_hours,
            custom_metadata=metadata or {},
        )

        logger.debug(f"Created session {session_id} for user {user_id}")
        return session_id

    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get complete session information."""
        info = await self._session_manager.get_session_info(session_id)
        if not info:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return info

    async def validate_session(self, session_id: str) -> bool:
        """Validate that a session exists and hasn't expired."""
        return await self._session_manager.validate_session(session_id)

    async def extend_session(self, session_id: str, additional_hours: int = None) -> bool:
        """Extend session TTL."""
        hours = additional_hours or self.default_ttl_hours
        return await self._session_manager.extend_session_ttl(session_id, hours)

    async def update_session_metadata(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """Update session metadata."""
        return await self._session_manager.update_session_metadata(session_id, metadata)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        success = await self._session_manager.delete_session(session_id)
        if success:
            logger.debug(f"Deleted session {session_id}")
        return success

    # ─────────────────── Context Management ───────────────────────

    def set_current_session(self, session_id: str, user_id: Optional[str] = None):
        """Set the current session context."""
        _session_ctx.set(session_id)
        if user_id:
            _user_ctx.set(user_id)
        logger.debug(f"Set session context to {session_id}")

    def get_current_session(self) -> Optional[str]:
        """Get the current session ID from context."""
        return _session_ctx.get()

    def get_current_user(self) -> Optional[str]:
        """Get the current user ID from context."""
        return _user_ctx.get()

    def clear_context(self):
        """Clear session and user context."""
        _session_ctx.set(None)
        _user_ctx.set(None)
        logger.debug("Cleared session context")

    async def auto_create_session_if_needed(self, user_id: Optional[str] = None) -> str:
        """Auto-create session if none exists in context."""
        current = self.get_current_session()

        if current and await self.validate_session(current):
            # Check if session needs extension
            await self._maybe_extend_session(current)
            return current

        # Create new session
        session_id = await self.create_session(
            user_id=user_id,
            metadata={
                "auto_created": True,
                "created_at": time.time(),
                "mcp_version": "0.2.0",
            },
        )

        self.set_current_session(session_id, user_id)
        logger.info(f"Auto-created session {session_id} for user {user_id}")
        return session_id

    async def _maybe_extend_session(self, session_id: str):
        """Extend session if it's close to expiring."""
        try:
            info = await self.get_session_info(session_id)
            expires_at = info.get("expires_at")
            created_at = info.get("created_at")

            if expires_at and created_at:
                # Calculate remaining time as percentage
                total_ttl = expires_at - created_at
                remaining = expires_at - time.time()
                remaining_ratio = remaining / total_ttl

                if remaining_ratio < self.auto_extend_threshold:
                    await self.extend_session(session_id)
                    logger.debug(f"Auto-extended session {session_id}")

        except Exception as e:
            logger.warning(f"Failed to check/extend session {session_id}: {e}")

    # ─────────────────── Admin & Monitoring ───────────────────────

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        return await self._session_manager.cleanup_expired_sessions()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._session_manager.get_cache_stats()

    async def list_active_sessions(self) -> Dict[str, Any]:
        """List active sessions (admin function)."""
        stats = self.get_cache_stats()
        return {
            "sandbox_id": self.sandbox_id,
            "active_sessions": stats.get("cache_size", 0),
            "cache_stats": stats,
        }


# ───────────────────────── Context Managers ─────────────────────────────


class SessionContext:
    """Async context manager for session operations."""

    def __init__(
        self,
        session_manager: MCPSessionManager,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        auto_create: bool = True,
    ):
        self.session_manager = session_manager
        self.session_id = session_id
        self.user_id = user_id
        self.auto_create = auto_create
        self.previous_session: str | None = None
        self.previous_user: str | None = None

    async def __aenter__(self) -> str:
        # Save previous context
        self.previous_session = self.session_manager.get_current_session()
        self.previous_user = self.session_manager.get_current_user()

        # Set new context
        if self.session_id:
            # Use provided session
            if not await self.session_manager.validate_session(self.session_id):
                raise SessionValidationError(f"Session {self.session_id} is invalid")
            self.session_manager.set_current_session(self.session_id, self.user_id)
            return self.session_id
        elif self.auto_create:
            # Auto-create session
            session_id = await self.session_manager.auto_create_session_if_needed(self.user_id)
            return session_id
        else:
            raise SessionError("No session provided and auto_create=False")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Restore previous context
        if self.previous_session:
            self.session_manager.set_current_session(self.previous_session, self.previous_user)
        else:
            self.session_manager.clear_context()


# ───────────────────────── Tool Integration Helpers ─────────────────────


def require_session() -> str:
    """Get current session or raise error."""
    session_id = _session_ctx.get()
    if not session_id:
        raise SessionError("No session context available")
    return session_id


def get_session_or_none() -> Optional[str]:
    """Get current session or None."""
    return _session_ctx.get()


def get_user_or_none() -> Optional[str]:
    """Get current user or None."""
    return _user_ctx.get()


async def with_session_auto_inject(
    session_manager: MCPSessionManager, tool_name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Auto-inject session_id into tool arguments if needed.

    This replaces the complex session injection logic in the server.
    """
    # List of tools that need session injection
    ARTIFACT_TOOLS = {
        "upload_file",
        "write_file",
        "read_file",
        "delete_file",
        "list_session_files",
        "list_directory",
        "copy_file",
        "move_file",
        "get_file_metadata",
        "get_presigned_url",
        "get_storage_stats",
    }

    if tool_name not in ARTIFACT_TOOLS:
        return arguments

    # If session_id already provided, use it
    if "session_id" in arguments:
        session_id = arguments["session_id"]
        if session_id and await session_manager.validate_session(session_id):
            session_manager.set_current_session(session_id)
            return arguments

    # Auto-create or get current session
    session_id = await session_manager.auto_create_session_if_needed()

    # Inject session_id
    return {**arguments, "session_id": session_id}


# ───────────────────────── Decorators ─────────────────────────────────


def session_required(func):
    """Decorator to require valid session context."""

    async def wrapper(*args, **kwargs):
        session_id = get_session_or_none()
        if not session_id:
            raise SessionError(f"Tool '{func.__name__}' requires session context")
        return await func(*args, **kwargs)

    return wrapper


def session_optional(func):
    """Decorator for tools that can work with or without session."""

    async def wrapper(*args, **kwargs):
        # Just pass through - tools can check context themselves
        return await func(*args, **kwargs)

    return wrapper


# ───────────────────────── Factory Function ─────────────────────────────


def create_mcp_session_manager(
    config: Optional[Dict[str, Any]] = None,
) -> MCPSessionManager:
    """Factory function to create session manager from config."""
    if not config:
        config = {}

    session_config = config.get("sessions", {})

    return MCPSessionManager(
        sandbox_id=session_config.get("sandbox_id"),
        default_ttl_hours=session_config.get("default_ttl_hours", 24),
        auto_extend_threshold=session_config.get("auto_extend_threshold", 0.1),
    )


# ───────────────────────── Backwards Compatibility ─────────────────────


# Keep these for existing code that imports from session_management
def set_session_context(session_id: str):
    """Legacy compatibility function."""
    _session_ctx.set(session_id)


def get_session_context() -> Optional[str]:
    """Legacy compatibility function."""
    return _session_ctx.get()


def clear_session_context():
    """Legacy compatibility function."""
    _session_ctx.set(None)


def validate_session_parameter(
    session_id: Optional[str],
    operation: str,
    session_manager: Optional[MCPSessionManager] = None,
) -> str:
    """Legacy compatibility with auto-creation."""
    if session_id:
        return session_id

    current = get_session_context()
    if current:
        return current

    if session_manager:
        # This would need to be made async in the calling code
        raise SessionError(f"Operation '{operation}' requires session_id or session manager")

    raise SessionError(f"Operation '{operation}' requires valid session_id")
