#!/usr/bin/env python
"""
examples/openai_compatibility_demo.py
-------------------------------------

Minimal, deterministic demo of ProxyServerManager *in OpenAI-only mode*.

Fully async-native implementation that maintains compatibility with the original.

Run:

    uv run examples/openai_compatibility_demo.py --only-openai-tools
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

# ── logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(name)s: %(message)s",
)
LOG = logging.getLogger("openai_demo")

# ── import path ───────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── internal imports ──────────────────────────────────────────────────
from chuk_tool_processor.registry import ToolRegistryProvider

from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY
from chuk_mcp_runtime.common.openai_compatibility import (
    OpenAIToolsAdapter,
    initialize_openai_compatibility,
)
from chuk_mcp_runtime.proxy.manager import ProxyServerManager
from chuk_mcp_runtime.server.config_loader import load_config


# ───────────────────────── helpers ────────────────────────────────────
async def fresh_registry() -> None:
    """Wipe the global ToolRegistryProvider (so no stale dot tools remain)."""
    # Get the registry using the async API
    reg = await ToolRegistryProvider.get_registry()

    # Try to clear the registry
    if hasattr(reg, "clear") and asyncio.iscoroutinefunction(reg.clear):
        await reg.clear()  # type: ignore[attr-defined]
        LOG.debug("Registry cleared with async clear method")
    elif hasattr(reg, "clear"):
        reg.clear()  # type: ignore[attr-defined]
        LOG.debug("Registry cleared with sync clear method")
    else:
        # Fallback: directly clear internal data structures
        for attr in ("_tools", "_metadata"):
            bucket = getattr(reg, attr, None)
            if isinstance(bucket, dict):
                bucket.clear()
        LOG.debug("Registry cleared by direct attribute access")


def tmp_cfg(only_openai: bool) -> Path:
    """Write a one-off JSON config that starts *only* the time server."""
    cfg: Dict = {
        "proxy": {
            "enabled": True,
            "namespace": "proxy",
            "openai_compatible": True,
            "keep_root_aliases": False,
            "only_openai_tools": only_openai,
        },
        "mcp_servers": {
            "time": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time", "--local-timezone", "America/New_York"],
            }
        },
    }
    fd, name = tempfile.mkstemp(suffix=".json", text=True)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
    LOG.info("config → %s", name)
    return Path(name)


async def execute_tool(tool: Any, **kwargs) -> Any:
    """Execute a tool correctly whether it's a class, instance, or function."""
    # If it's a class, create an instance
    if inspect.isclass(tool):
        instance = tool()
        # If the instance has an execute method, call it
        if hasattr(instance, "execute") and callable(instance.execute):
            result = instance.execute(**kwargs)
            # If the result is awaitable, await it
            if inspect.isawaitable(result):
                return await result
            return result
    # If it's already an instance with an execute method
    elif hasattr(tool, "execute") and callable(tool.execute):
        result = tool.execute(**kwargs)
        # If the result is awaitable, await it
        if inspect.isawaitable(result):
            return await result
        return result
    # If it's a function or coroutine function, call it directly
    elif callable(tool):
        result = tool(**kwargs)
        # If the result is awaitable, await it
        if inspect.isawaitable(result):
            return await result
        return result
    # If we can't figure out how to call it
    raise TypeError(f"Cannot execute tool of type {type(tool)}")


async def demo(only_openai_tools: bool, debug: bool) -> None:
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    await fresh_registry()  # ensure a clean slate - now async

    cfg = tmp_cfg(only_openai_tools)
    proxy = ProxyServerManager(load_config([str(cfg)]), str(ROOT))
    await proxy.start_servers()

    try:
        # Explicitly initialize OpenAI compatibility
        await initialize_openai_compatibility()
        LOG.info("Initialized OpenAI compatibility")

        # Get tools - now with async method
        tools = await proxy.get_all_tools()  # underscore aliases only
        print(f"\nproxy.get_all_tools() → {len(tools)}")
        for t in sorted(tools):
            print(" ", t)

        # ── call the two tools correctly ──────────────────────────────
        # Adjust tool names based on what we find in the registry
        print("\n• demo calls")

        # Find the current time tool
        get_time_tool = None
        get_time_name = None
        for name, tool in tools.items():
            if name == "time_get_current_time" or "get_current_time" in name:
                get_time_tool = tool
                get_time_name = name
                print(f"  Found get_current_time tool as: {name}")
                print(f"  Tool type: {type(tool).__name__}")
                break

        if get_time_tool:
            try:
                res_now = await execute_tool(get_time_tool, timezone="America/New_York")
                print(f"  {get_time_name} →", res_now)
            except Exception as e:
                print(f"  ❌ Error executing {get_time_name}: {e}")
        else:
            print("  ❌ get_current_time tool not found")

        # Find the convert time tool
        convert_tool = None
        convert_name = None
        for name, tool in tools.items():
            if name == "time_convert_time" or "convert_time" in name:
                convert_tool = tool
                convert_name = name
                print(f"  Found convert_time tool as: {name}")
                print(f"  Tool type: {type(convert_tool).__name__}")
                break

        if convert_tool:
            try:
                res_conv = await execute_tool(
                    convert_tool,
                    source_timezone="America/New_York",
                    time="15:30",
                    target_timezone="Europe/London",
                )
                print(f"  {convert_name} →", res_conv)
            except Exception as e:
                print(f"  ❌ Error executing {convert_name}: {e}")
        else:
            print("  ❌ convert_time tool not found")

        # ── OpenAI schema dump ────────────────────────────────────────
        adapter = OpenAIToolsAdapter()

        # Show underscore tools in TOOLS_REGISTRY
        print("\n• TOOLS_REGISTRY underscore tools")
        underscore_tools = [
            (name, fn)
            for name, fn in TOOLS_REGISTRY.items()
            if "_" in name and "." not in name and hasattr(fn, "_mcp_tool")
        ]
        print(f"  Found {len(underscore_tools)} underscore tools in TOOLS_REGISTRY")

        for name, fn in sorted(underscore_tools):
            meta = fn._mcp_tool  # type: ignore[attr-defined]
            print(f"  • {name}")
            print(f"    Description: {meta.description}")
            print(f"    Schema: {len(meta.inputSchema.get('properties', {}))} properties")

        # Show OpenAI schemas
        print("\n• OpenAI schema generation")
        schemas = await adapter.get_openai_tools_definition()
        print(f"  get_openai_tools_definition() → {len(schemas)} objects")
        for schema in schemas:
            print(f"  • {schema['function']['name']}")
            print(f"    Description: {schema['function']['description']}")
            print(
                f"    Parameters: {len(schema['function'].get('parameters', {}).get('properties', {}))} properties"
            )

    finally:
        await proxy.stop_servers()
        cfg.unlink(missing_ok=True)
        print("\n🛑 proxy shut down - temp config deleted.")


# ───────────────────────── main ───────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-openai-tools", action="store_true")
    ap.add_argument("--debug", action="store_true")
    asyncio.run(demo(**vars(ap.parse_args())))
