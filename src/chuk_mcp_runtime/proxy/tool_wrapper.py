# chuk_mcp_runtime/proxy/tool_wrapper.py
"""
chuk_mcp_runtime.proxy.tool_wrapper
===================================

Create local async wrappers for every remote MCP tool.
Fully async-native implementation.

 • dot wrapper … proxy.<server>.<tool>
 • underscore …  <server>_<tool>  (OpenAI-style)

Wrappers are inserted into
`chuk_mcp_runtime.common.mcp_tool_decorator.TOOLS_REGISTRY`
via `@mcp_tool` and—if present—also into `ToolRegistryProvider`.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.logging_config import get_logger

try:  # optional dependency
    from chuk_tool_processor.registry import ToolRegistryProvider
except ModuleNotFoundError:  # provider absent
    ToolRegistryProvider = None  # type: ignore

logger = get_logger("chuk_mcp_runtime.proxy.tool_wrapper")


# ───────────────────────── helpers ──────────────────────────
def _meta_get(meta: Any, key: str, default: Any) -> Any:
    """Fetch *key* from dict-or-object metadata safely."""
    return meta.get(key, default) if isinstance(meta, dict) else getattr(meta, key, default)


async def _tp_register(
    registry: Any,
    *,
    name: str,
    namespace: str,
    tool: Callable[..., Any],
    metadata: Any,
) -> None:
    """
    Register *tool* with ToolRegistryProvider.

    Uses the correct parameter names based on inspection of the registry.
    """
    if not hasattr(registry, "register_tool"):
        return

    try:
        # Use the correct parameter name 'tool' instead of 'func'
        await registry.register_tool(
            tool=tool,
            name=name,
            namespace=namespace,
            metadata=metadata,
        )
        logger.debug(f"Successfully registered tool {namespace}.{name} with registry")
    except Exception as exc:
        logger.debug("ToolRegistryProvider.register_tool failed: %s", exc)


# ───────────────────────── factory ──────────────────────────
async def create_proxy_tool(
    namespace: str,  # e.g. "proxy.time"
    tool_name: str,  # e.g. "get_current_time"
    stream_manager: Any,
    metadata: Optional[Any] = None,
) -> Callable[..., Any]:
    """Return an async wrapper that forwards to the remote MCP tool."""
    metadata = metadata or {}
    fq_name = f"{namespace}.{tool_name}"
    description = _meta_get(metadata, "description", f"Proxied tool: {fq_name}")
    server_name = namespace.split(".")[-1]

    # ------------------------------------------------------------------ #
    #   async wrapper - default-arg trick pins values at definition time #
    # ------------------------------------------------------------------ #
    @mcp_tool(name=fq_name, description=description)
    async def _proxy_wrapper(
        __tool: str = tool_name,
        __server: str = server_name,
        **kwargs,
    ):
        # Defense in depth: Filter out session_id if it somehow gets passed
        # (shouldn't happen with proper session management, but just in case)
        if "session_id" in kwargs:
            logger.warning(
                "Unexpected session_id in remote call to %s.%s - filtering out",
                __server,
                __tool,
            )
            kwargs = {k: v for k, v in kwargs.items() if k != "session_id"}

        logger.debug("Calling remote %s.%s with %s", __server, __tool, kwargs)
        result = await stream_manager.call_tool(
            tool_name=__tool,
            arguments=kwargs,
            server_name=__server,
        )
        if result.get("isError"):
            raise RuntimeError(result.get("error", "Unknown MCP error"))
        return result.get("content")

    # attach diagnostics
    _proxy_wrapper._proxy_server = server_name  # type: ignore[attr-defined]
    _proxy_wrapper._proxy_metadata = metadata  # type: ignore[attr-defined]

    # optional ToolRegistryProvider registration (safe version)
    if ToolRegistryProvider is not None:
        registry = await ToolRegistryProvider.get_registry()
        await _tp_register(
            registry,
            name=tool_name,
            namespace=namespace,
            tool=_proxy_wrapper,  # Use 'tool' instead of 'func'
            metadata=metadata,
        )

    return _proxy_wrapper
