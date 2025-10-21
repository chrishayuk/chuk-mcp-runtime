# chuk_mcp_runtime/tools/artifacts_tools.py
"""
Configurable MCP Tools Integration for chuk_artifacts

This module provides configurable MCP tools that can be enabled/disabled
and customized via config.yaml settings.

NOTE: These tools are DISABLED by default and must be explicitly enabled
in configuration to be available.
"""

import base64
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union

# runtime
from chuk_artifacts import ArtifactNotFoundError, ArtifactStore

from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY, mcp_tool
from chuk_mcp_runtime.server.logging_config import get_logger
from chuk_mcp_runtime.session.session_management import validate_session_parameter

# logger
logger = get_logger("chuk_mcp_runtime.tools.artifacts")

# Global artifact store instance and configuration
_artifact_store: Optional[ArtifactStore] = None
_artifacts_config: Dict[str, Any] = {}
_enabled_tools: Set[str] = set()

# FIXED: Default tool configuration - DISABLED by default
DEFAULT_TOOL_CONFIG = {
    "enabled": False,  # DISABLED by default - must be explicitly enabled in config
    "tools": {
        "upload_file": {
            "enabled": False,
            "description": "Upload files with base64 content",
        },
        "write_file": {"enabled": False, "description": "Create or update text files"},
        "read_file": {"enabled": False, "description": "Read file contents"},
        "list_session_files": {
            "enabled": False,
            "description": "List files in session",
        },
        "delete_file": {"enabled": False, "description": "Delete files"},
        "list_directory": {"enabled": False, "description": "List directory contents"},
        "copy_file": {"enabled": False, "description": "Copy files within session"},
        "move_file": {"enabled": False, "description": "Move/rename files"},
        "get_file_metadata": {"enabled": False, "description": "Get file metadata"},
        "get_presigned_url": {
            "enabled": False,
            "description": "Generate presigned URLs",
        },
        "get_storage_stats": {
            "enabled": False,
            "description": "Get storage statistics",
        },
    },
}


def configure_artifacts_tools(config: Dict[str, Any]) -> None:
    """Configure artifacts tools based on config.yaml settings."""
    global _artifacts_config, _enabled_tools

    # Get artifacts configuration
    _artifacts_config = config.get("artifacts", {})

    # Determine which tools are enabled
    _enabled_tools.clear()

    # Check if artifacts tools are enabled globally
    if not _artifacts_config.get("enabled", False):
        logger.info(
            "Artifact tools disabled in configuration - use 'artifacts.enabled: true' to enable"
        )
        return

    # Process individual tool configuration
    tool_settings = _artifacts_config.get("tools", DEFAULT_TOOL_CONFIG["tools"])

    # Loop through each tool and see if we should enable it
    for tool_name, tool_config in tool_settings.items():
        if tool_config.get("enabled", False):
            _enabled_tools.add(tool_name)
            logger.debug(f"Enabled artifact tool: {tool_name}")
        else:
            logger.debug(
                f"Disabled artifact tool: {tool_name} - use 'artifacts.tools.{tool_name}.enabled: true' to enable"
            )

    # Log the results
    if _enabled_tools:
        logger.info(
            f"Configured {len(_enabled_tools)} artifact tools: {', '.join(sorted(_enabled_tools))}"
        )
    else:
        logger.info("No artifact tools enabled - all tools require explicit configuration")


def is_tool_enabled(tool_name: str) -> bool:
    """Check if a specific tool is enabled."""
    return tool_name in _enabled_tools


async def get_artifact_store() -> ArtifactStore:
    """Get or create the global artifact store instance."""
    global _artifact_store

    if _artifact_store is None:
        # Use configuration or environment variables or sensible defaults
        storage_provider = _artifacts_config.get("storage_provider") or os.getenv(
            "ARTIFACT_STORAGE_PROVIDER", "filesystem"
        )
        session_provider = _artifacts_config.get("session_provider") or os.getenv(
            "ARTIFACT_SESSION_PROVIDER", "memory"
        )
        bucket = _artifacts_config.get("bucket") or os.getenv("ARTIFACT_BUCKET", "mcp-runtime")

        # Set up filesystem root if using filesystem storage
        if storage_provider == "filesystem":
            fs_root = (
                _artifacts_config.get("filesystem_root")
                or os.getenv("ARTIFACT_FS_ROOT")
                or os.path.expanduser("~/.chuk_mcp_artifacts")
            )
            os.environ["ARTIFACT_FS_ROOT"] = fs_root

        _artifact_store = ArtifactStore(
            storage_provider=storage_provider,
            session_provider=session_provider,
            bucket=bucket,
        )

        logger.info(f"Created artifact store: {storage_provider}/{session_provider} -> {bucket}")

    return _artifact_store


def _check_availability():
    """Check if chuk_artifacts is available and raise helpful error if not."""
    return True


def _check_tool_enabled(tool_name: str):
    """Check if a tool is enabled and raise error if not."""
    if not is_tool_enabled(tool_name):
        raise ValueError(
            f"Tool '{tool_name}' is disabled in configuration - use 'artifacts.tools.{tool_name}.enabled: true' to enable"
        )


# ============================================================================
# Artifact Management Tools - All decorated with @mcp_tool
# ============================================================================


@mcp_tool(name="upload_file", description="Upload files with base64 content")
async def upload_file(
    content: str,
    filename: str,
    mime: str = "application/octet-stream",
    summary: str = "File uploaded via MCP",
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Upload a file with base64 encoded content to the artifact store.

    Args:
        content: Base64 encoded file content
        filename: Name of the file to create
        mime: MIME type of the file (default: application/octet-stream)
        summary: Description of the file (default: File uploaded via MCP)
        session_id: Session ID (optional, will use current session if not provided)
        meta: Additional metadata for the file (optional)

    Returns:
        Success message with artifact ID
    """
    _check_tool_enabled("upload_file")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    effective_session = await validate_session_parameter(session_id, "upload_file", session_manager)

    store = await get_artifact_store()

    try:
        file_data = base64.b64decode(content)
        upload_meta = {
            "uploaded_via": "mcp",
            "upload_time": datetime.now().isoformat(),
            **(meta or {}),
        }

        artifact_id = await store.store(
            data=file_data,
            mime=mime,
            summary=summary,
            filename=filename,
            session_id=effective_session,
            meta=upload_meta,
        )

        return f"File uploaded successfully. Artifact ID: {artifact_id}"

    except Exception as e:
        raise ValueError(f"Failed to upload file: {str(e)}")


@mcp_tool(name="write_file", description="Create or update text files")
async def write_file(
    content: str,
    filename: str,
    mime: str = "text/plain",
    summary: str = "File created via MCP",
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create or update a text file in the artifact store.

    Args:
        content: Text content of the file
        filename: Name of the file to create
        mime: MIME type of the file (default: text/plain)
        summary: Description of the file (default: File created via MCP)
        session_id: Session ID (optional, will use current session if not provided)
        meta: Additional metadata for the file (optional)

    Returns:
        Success message with artifact ID
    """
    _check_tool_enabled("write_file")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    effective_session = await validate_session_parameter(session_id, "write_file", session_manager)

    store = await get_artifact_store()

    try:
        write_meta = {
            "created_via": "mcp",
            "creation_time": datetime.now().isoformat(),
            **(meta or {}),
        }

        artifact_id = await store.write_file(
            content=content,
            filename=filename,
            mime=mime,
            summary=summary,
            session_id=effective_session,
            meta=write_meta,
        )

        return f"File created successfully. Artifact ID: {artifact_id}"

    except Exception as e:
        raise ValueError(f"Failed to write file: {str(e)}")


@mcp_tool(name="read_file", description="Read file contents")
async def read_file(
    artifact_id: str, as_text: bool = True, session_id: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Read the content of a file from the artifact store.

    Args:
        artifact_id: Unique identifier of the file to read
        as_text: Whether to return content as text (default: True) or as binary with metadata
        session_id: Session ID (optional, will use current session if not provided)

    Returns:
        File content as text, or dictionary with content and metadata if as_text=False
    """
    _check_tool_enabled("read_file")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    await validate_session_parameter(session_id, "read_file", session_manager)

    store = await get_artifact_store()

    try:
        if as_text:
            content = await store.read_file(artifact_id, as_text=True)
            return content
        else:
            data = await store.retrieve(artifact_id)
            metadata = await store.metadata(artifact_id)

            return {
                "content": base64.b64encode(data).decode(),
                "filename": metadata.get("filename", "unknown"),
                "mime": metadata.get("mime", "application/octet-stream"),
                "size": len(data),
                "metadata": metadata,
            }

    except ArtifactNotFoundError:
        raise ValueError(f"File not found: {artifact_id}")
    except Exception as e:
        raise ValueError(f"Failed to read file: {str(e)}")


@mcp_tool(name="list_session_files", description="List files in session")
async def list_session_files(
    session_id: Optional[str] = None, include_metadata: bool = False
) -> List[Dict[str, Any]]:
    """
    List all files in the specified session.

    Args:
        session_id: Session ID (optional, will use current session if not provided)
        include_metadata: Whether to include full metadata for each file (default: False)

    Returns:
        List of files in the session with basic or full metadata
    """
    _check_tool_enabled("list_session_files")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    effective_session = await validate_session_parameter(
        session_id, "list_session_files", session_manager
    )

    store = await get_artifact_store()

    try:
        files = await store.list_by_session(effective_session)

        if include_metadata:
            return files
        else:
            return [
                {
                    "artifact_id": f.get("artifact_id"),
                    "filename": f.get("filename", "unknown"),
                    "mime": f.get("mime", "unknown"),
                    "bytes": f.get("bytes", 0),
                    "summary": f.get("summary", ""),
                    "created": f.get("created", ""),
                }
                for f in files
            ]

    except Exception as e:
        raise ValueError(f"Failed to list files: {str(e)}")


@mcp_tool(name="delete_file", description="Delete files")
async def delete_file(artifact_id: str, session_id: Optional[str] = None) -> str:
    """
    Delete a file from the artifact store.

    Args:
        artifact_id: Unique identifier of the file to delete
        session_id: Session ID (optional, will use current session if not provided)

    Returns:
        Success or failure message
    """
    _check_tool_enabled("delete_file")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    await validate_session_parameter(session_id, "delete_file", session_manager)

    store = await get_artifact_store()

    try:
        deleted = await store.delete(artifact_id)

        if deleted:
            return f"File deleted successfully: {artifact_id}"
        else:
            return f"File not found or already deleted: {artifact_id}"

    except Exception as e:
        raise ValueError(f"Failed to delete file: {str(e)}")


@mcp_tool(name="list_directory", description="List directory contents")
async def list_directory(
    directory_path: str, session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List files in a specific directory within the session.

    Args:
        directory_path: Path to the directory to list
        session_id: Session ID (optional, will use current session if not provided)

    Returns:
        List of files in the specified directory
    """
    _check_tool_enabled("list_directory")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    effective_session = await validate_session_parameter(
        session_id, "list_directory", session_manager
    )

    store = await get_artifact_store()

    try:
        files = await store.get_directory_contents(effective_session, directory_path)

        return [
            {
                "artifact_id": f.get("artifact_id"),
                "filename": f.get("filename", "unknown"),
                "mime": f.get("mime", "unknown"),
                "bytes": f.get("bytes", 0),
                "summary": f.get("summary", ""),
            }
            for f in files
        ]

    except Exception as e:
        raise ValueError(f"Failed to list directory: {str(e)}")


@mcp_tool(name="copy_file", description="Copy files within session")
async def copy_file(
    artifact_id: str,
    new_filename: str,
    new_summary: Optional[str] = None,
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Copy a file within the same session.

    Args:
        artifact_id: Unique identifier of the file to copy
        new_filename: Name for the copied file
        new_summary: Description for the copied file (optional)
        session_id: Session ID (optional, will use current session if not provided)
        meta: Additional metadata for the copied file (optional)

    Returns:
        Success message with new artifact ID
    """
    _check_tool_enabled("copy_file")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    await validate_session_parameter(session_id, "copy_file", session_manager)

    store = await get_artifact_store()

    try:
        copy_meta = {
            "copied_via": "mcp",
            "copy_time": datetime.now().isoformat(),
            "original_artifact_id": artifact_id,
            **(meta or {}),
        }

        # Use the actual API parameters that work
        new_artifact_id = await store.copy_file(
            artifact_id, new_filename=new_filename, new_meta=copy_meta
        )

        return f"File copied successfully. New artifact ID: {new_artifact_id}"

    except Exception as e:
        raise ValueError(f"Failed to copy file: {str(e)}")


@mcp_tool(name="move_file", description="Move/rename files")
async def move_file(
    artifact_id: str,
    new_filename: str,
    new_summary: Optional[str] = None,
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Move/rename a file within the same session.

    Args:
        artifact_id: Unique identifier of the file to move/rename
        new_filename: New name for the file
        new_summary: New description for the file (optional)
        session_id: Session ID (optional, will use current session if not provided)
        meta: Additional metadata for the moved file (optional)

    Returns:
        Success message confirming the move
    """
    _check_tool_enabled("move_file")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    await validate_session_parameter(session_id, "move_file", session_manager)

    store = await get_artifact_store()

    try:
        move_meta = {
            "moved_via": "mcp",
            "move_time": datetime.now().isoformat(),
            **(meta or {}),
        }

        await store.move_file(artifact_id, new_filename=new_filename, new_meta=move_meta)

        return f"File moved successfully: {artifact_id} -> {new_filename}"

    except Exception as e:
        raise ValueError(f"Failed to move file: {str(e)}")


@mcp_tool(name="get_file_metadata", description="Get file metadata")
async def get_file_metadata(artifact_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed metadata for a file.

    Args:
        artifact_id: Unique identifier of the file
        session_id: Session ID (optional, will use current session if not provided)

    Returns:
        Dictionary containing file metadata (size, type, creation date, etc.)
    """
    _check_tool_enabled("get_file_metadata")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    await validate_session_parameter(session_id, "get_file_metadata", session_manager)

    store = await get_artifact_store()

    try:
        metadata = await store.metadata(artifact_id)
        return metadata

    except ArtifactNotFoundError:
        raise ValueError(f"File not found: {artifact_id}")
    except Exception as e:
        raise ValueError(f"Failed to get metadata: {str(e)}")


@mcp_tool(name="get_presigned_url", description="Generate presigned URLs")
async def get_presigned_url(
    artifact_id: str, expires_in: str = "medium", session_id: Optional[str] = None
) -> str:
    """
    Get a presigned URL for downloading a file.

    Args:
        artifact_id: Unique identifier of the file
        expires_in: URL expiration time - 'short', 'medium', or 'long' (default: medium)
        session_id: Session ID (optional, will use current session if not provided)

    Returns:
        Presigned URL for downloading the file
    """
    _check_tool_enabled("get_presigned_url")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    await validate_session_parameter(session_id, "get_presigned_url", session_manager)

    store = await get_artifact_store()

    try:
        if expires_in == "short":
            url = await store.presign_short(artifact_id)
        elif expires_in == "long":
            url = await store.presign_long(artifact_id)
        else:  # medium (default)
            url = await store.presign_medium(artifact_id)

        return url

    except ArtifactNotFoundError:
        raise ValueError(f"File not found: {artifact_id}")
    except Exception as e:
        raise ValueError(f"Failed to generate presigned URL: {str(e)}")


@mcp_tool(name="get_storage_stats", description="Get storage statistics")
async def get_storage_stats(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get statistics about the artifact store.

    Args:
        session_id: Session ID (optional, will use current session if not provided)

    Returns:
        Dictionary with storage statistics including file count and total bytes
    """
    _check_tool_enabled("get_storage_stats")

    # FIXED: Use async session validation
    from chuk_mcp_runtime.session.native_session_management import (
        create_mcp_session_manager,
    )

    session_manager = create_mcp_session_manager({})
    effective_session = await validate_session_parameter(
        session_id, "get_storage_stats", session_manager
    )

    store = await get_artifact_store()

    try:
        stats = await store.get_stats()
        session_files = await store.list_by_session(effective_session)
        session_stats = {
            "session_id": effective_session,
            "session_file_count": len(session_files),
            "session_total_bytes": sum(f.get("bytes", 0) for f in session_files),
        }

        stats.update(session_stats)
        return stats

    except Exception as e:
        raise ValueError(f"Failed to get storage stats: {str(e)}")


# ============================================================================
# Registration and Utility Functions
# ============================================================================

# Map of tool name to function
TOOL_FUNCTIONS = {
    "upload_file": upload_file,
    "write_file": write_file,
    "read_file": read_file,
    "list_session_files": list_session_files,
    "delete_file": delete_file,
    "list_directory": list_directory,
    "copy_file": copy_file,
    "move_file": move_file,
    "get_file_metadata": get_file_metadata,
    "get_presigned_url": get_presigned_url,
    "get_storage_stats": get_storage_stats,
}

# ============================================================================
# Registration function for artifact-management helpers
# ============================================================================


async def register_artifacts_tools(config: Dict[str, Any] | None = None) -> bool:
    """Register artifact helpers according to *config*."""
    art_cfg = (config or {}).get("artifacts", {})
    if not art_cfg.get("enabled", False):
        for t in TOOL_FUNCTIONS:
            TOOLS_REGISTRY.pop(t, None)
        logger.info("Artifacts disabled - use 'artifacts.enabled: true' in config to enable")
        return False

    enabled_helpers = {n for n, tc in art_cfg.get("tools", {}).items() if tc.get("enabled", False)}
    if not enabled_helpers:
        for t in TOOL_FUNCTIONS:
            TOOLS_REGISTRY.pop(t, None)
        logger.info(
            "All artifact tools disabled individually - use 'artifacts.tools.<tool_name>.enabled: true' to enable specific tools"
        )
        return False

    # 1) make sure store is OK
    await get_artifact_store()  # raises if mis-configured

    # 2) prune everything that might still be there
    for t in TOOL_FUNCTIONS:
        TOOLS_REGISTRY.pop(t, None)

    # ---- KEEP _enabled_tools IN-SYNC ---------------------------------
    _enabled_tools.clear()
    _enabled_tools.update(enabled_helpers)
    # ------------------------------------------------------------------

    # 3) register the wanted helpers
    registered = 0
    for name in enabled_helpers:
        TOOL_FUNCTIONS[name]

        # Ensure tool is properly initialized
        from chuk_mcp_runtime.common.mcp_tool_decorator import ensure_tool_initialized

        try:
            initialized_fn = await ensure_tool_initialized(name)
            TOOLS_REGISTRY[name] = initialized_fn
            registered += 1
            logger.debug("Registered artifact tool: %s", name)
        except Exception as e:
            logger.error("Failed to register artifact tool %s: %s", name, e)

    if registered > 0:
        logger.info(
            "Registered %d artifact tool(s): %s",
            registered,
            ", ".join(sorted(enabled_helpers)),
        )
    else:
        logger.warning("No artifact tools were successfully registered")

    return bool(registered)


def get_artifacts_tools_info() -> Dict[str, Any]:
    """Get information about available and configured artifact tools."""
    all_tools = list(DEFAULT_TOOL_CONFIG["tools"].keys())

    return {
        "available": True,
        "configured": bool(_artifacts_config),
        "enabled_globally": _artifacts_config.get("enabled", False) if _artifacts_config else False,
        "enabled_tools": list(_enabled_tools),
        "disabled_tools": [t for t in all_tools if t not in _enabled_tools],
        "total_tools": len(all_tools),
        "enabled_count": len(_enabled_tools),
        "config": _artifacts_config,
        "default_state": "disabled",
        "enable_instructions": {
            "global": "Set 'artifacts.enabled: true' in configuration",
            "individual": "Set 'artifacts.tools.<tool_name>.enabled: true' for each desired tool",
        },
    }


def get_enabled_tools() -> List[str]:
    """Get list of currently enabled tools."""
    return list(_enabled_tools)


# Tool list for external reference (all possible tools)
ALL_ARTIFACT_TOOLS = list(DEFAULT_TOOL_CONFIG["tools"].keys())


# Dynamic tool list based on configuration
def get_artifact_tools() -> List[str]:
    """Get currently enabled artifact tools."""
    return get_enabled_tools()


# Legacy property-style access (keeping for compatibility)
def ARTIFACT_TOOLS() -> List[str]:
    """Get currently enabled artifact tools."""
    return get_enabled_tools()


# Add the required CHUK_ARTIFACTS_AVAILABLE flag for compatibility
CHUK_ARTIFACTS_AVAILABLE = True
