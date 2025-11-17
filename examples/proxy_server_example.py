#!/usr/bin/env python
# examples/proxy_server_example.py
"""
examples/proxy_server_example.py
--------------------------------

Proxy round-trip demo driven by *proxy_config.yaml*.

• Boots the *echo2* MCP server via ``ProxyServerManager``.
• Prints the registry grouped by namespace.
• Calls the wrapper ``proxy.echo2.echo`` directly and shows the result.

The simplified ProxyServerManager now has a single switch:

    proxy.openai_compatible:
        false → dot wrappers (e.g. proxy.echo2.echo)
        true  → underscore wrappers (e.g. echo2_echo)

This demo assumes *openai_compatible: false* so dot names exist.

Fully async-native implementation.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from typing import Any, Dict, List, Tuple

# ── project paths ----------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── internal imports -------------------------------------------------
from chuk_mcp_runtime.common.openai_compatibility import initialize_openai_compatibility
from chuk_mcp_runtime.proxy.manager import ProxyServerManager
from chuk_mcp_runtime.server.config_loader import find_project_root, load_config

try:
    from chuk_tool_processor.registry import ToolRegistryProvider
except ModuleNotFoundError:  # optional
    ToolRegistryProvider = None  # type: ignore

# --------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.join(HERE, "proxy_config.yaml")


async def group_registry() -> Dict[str, List[str]]:
    """Return registry grouped by namespace (if the provider is present)."""
    grouped: Dict[str, List[str]] = {}
    if not ToolRegistryProvider:
        return grouped

    # Get the registry using the async API
    registry = await ToolRegistryProvider.get_registry()

    # List tools using the async API
    tools_list: List[Tuple[str, str]] = await registry.list_tools()

    for ns, name in tools_list:
        grouped.setdefault(ns or "(no-ns)", []).append(name)

    for tools in grouped.values():
        tools.sort()
    return grouped


async def safe_execute_tool(tool: Any, **kwargs) -> Any:
    """Safely execute a tool without recursion issues."""
    if inspect.isclass(tool):
        # If it's a class, create an instance and call execute
        instance = tool()
        method = getattr(instance, "execute", None)
        if callable(method):
            result = method(**kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
    elif hasattr(tool, "_proxy_wrapper") and callable(tool._proxy_wrapper):
        # If it has a _proxy_wrapper attribute (our implementation detail)
        result = tool._proxy_wrapper(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
    elif hasattr(tool, "_proxy_server") and callable(tool):
        # It's one of our proxy wrappers, use the stream manager directly
        server_name = getattr(tool, "_proxy_server", None)
        if server_name:
            # Extract the tool name from the function's name or _mcp_tool if available
            tool_name = getattr(tool, "__name__", "echo")
            if hasattr(tool, "_mcp_tool"):
                tool_name = tool._mcp_tool.name
            # Special case for echo - hardcode the tool name
            if server_name == "echo2":
                tool_name = "echo"

            print(f"Direct execution via stream manager: {server_name}.{tool_name}")
            # This avoids the wrapper that's causing recursion

            # Get the global proxy instance from our module
            proxy = globals().get("proxy")
            if proxy and hasattr(proxy, "stream_manager"):
                result = await proxy.stream_manager.call_tool(
                    tool_name=tool_name,
                    arguments=kwargs,
                    server_name=server_name,
                )
                return result.get("content")

    # Default - try to call it directly
    result = tool(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def main() -> None:
    # Make proxy global so we can access it in safe_execute_tool
    global proxy

    # 1) load config (no keep_root_aliases anymore) --------------------
    config = load_config([CONFIG_YAML])
    project_root = find_project_root()

    # 2) start proxy manager ------------------------------------------
    proxy = ProxyServerManager(config, project_root)
    await proxy.start_servers()

    try:
        # Initialize OpenAI compatibility
        await initialize_openai_compatibility()

        # 3) dump registry --------------------------------------------
        grouped = await group_registry()
        print("\n=== Registry grouped by namespace ===")
        if grouped:
            for ns, names in sorted(grouped.items()):
                print(f"{ns} ({len(names)} tool(s))")
                for n in names:
                    print("  •", n)
        else:
            print("(ToolRegistryProvider not installed)")

        # 4) call wrapper directly ------------------------------------
        wrappers = await proxy.get_all_tools()  # Using async method
        dot_name = "proxy.echo2.echo"
        if dot_name not in wrappers:
            raise RuntimeError(
                f"{dot_name} not found - make sure openai_compatible is set to *false* in the YAML"
            )

        echo_wrapper = wrappers[dot_name]
        print("\n=== proxy.echo2.echo round-trip ===")
        try:
            print("Calling echo_wrapper with 'Hello from wrapper call!'")
            # Use our safe executor to avoid recursion
            result = await safe_execute_tool(echo_wrapper, message="Hello from wrapper call!")
            print("Result ->", result)
        except Exception as e:
            print(f"Error calling echo_wrapper: {e}")
            print("Tool type:", type(echo_wrapper).__name__)
            print("Is async:", asyncio.iscoroutinefunction(echo_wrapper))
            print("Dir:", dir(echo_wrapper))

    finally:
        await proxy.stop_servers()


if __name__ == "__main__":
    asyncio.run(main())
