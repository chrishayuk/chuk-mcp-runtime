#!/usr/bin/env python
# examples/show_registry.py
"""
examples/show_registry.py
-------------------------

List all MCP tools grouped by namespace, then run a quick echo round-trip.

* Reads `proxy_config.yaml` next to this script (or a custom `--config` path).
* Falls back to project-root `stdio_proxy_config.yaml` if the default is missing.
* Works in both dot-name and underscore (OpenAI) modes.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import os
import sys

# ── project path -----------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── internal imports -------------------------------------------------
from chuk_mcp_runtime.proxy.manager import ProxyServerManager
from chuk_mcp_runtime.server.config_loader import find_project_root, load_config
from chuk_tool_processor.registry import ToolRegistryProvider


# ── helpers ----------------------------------------------------------
async def display_registry_info():
    """Display information about all registered tools by namespace."""
    # Get the registry
    registry = await ToolRegistryProvider.get_registry()

    # Get all namespaces
    namespaces = await registry.list_namespaces()

    print("\n=== Registry grouped by namespace ===")
    for namespace in namespaces:
        # Get tools in this namespace
        tools_in_ns = await registry.list_tools(namespace=namespace)
        tool_names = [name for _, name in tools_in_ns]

        print(f"{namespace} ({len(tool_names)} tool(s))")

        # Print details for each tool
        for tool_name in sorted(tool_names):
            # Get tool and metadata
            metadata = await registry.get_metadata(tool_name, namespace)

            # Print basic info
            print(f"  • {tool_name}")

            # Print description if available
            if metadata and hasattr(metadata, "description") and metadata.description:
                desc = metadata.description
                # Truncate long descriptions
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                print(f"    Description: {desc}")

            # Print additional metadata if available
            if metadata and hasattr(metadata, "tags") and metadata.tags:
                print(f"    Tags: {', '.join(metadata.tags)}")


async def find_and_run_echo_tool(proxy):
    """Find an echo tool and run a test with it."""
    # Get all tools
    tools = await proxy.get_all_tools()

    # Find an echo tool
    echo_tool = None
    echo_name = None

    for name, tool in tools.items():
        if "echo" in name.lower():
            echo_tool = tool
            echo_name = name
            break

    if not echo_tool:
        print("\n(no echo tool found for round-trip demo)")
        return

    # Run the echo tool
    print(f"\n=== {echo_name} round-trip ===")
    try:
        # Create an instance if it's a class
        if inspect.isclass(echo_tool):
            tool_instance = echo_tool()
            result = await tool_instance.execute(message="Hello from show_registry demo!")
        else:
            # Otherwise it's a function
            result = await echo_tool(message="Hello from show_registry demo!")

        print("Result ->", result)
    except Exception as e:
        print(f"Error executing echo tool: {e}")


# ── main async demo --------------------------------------------------
async def main(config_path: str) -> None:
    """Main async function for the registry demo."""
    if not os.path.exists(config_path):
        alt = os.path.join(ROOT, "stdio_proxy_config.yaml")
        if os.path.exists(alt):
            print(f"⚠️  {config_path} not found - falling back to {alt}")
            config_path = alt
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")

    config = load_config([config_path])
    print(f"Loaded config → {config_path}")

    proxy = ProxyServerManager(config, find_project_root())
    await proxy.start_servers()

    try:
        # Display information about all registered tools
        await display_registry_info()

        # Show tools from the proxy
        tools = await proxy.get_all_tools()
        print(f"\nproxy.get_all_tools() → {len(tools)} " f"(openai_mode={proxy.openai_mode})")
        for name in sorted(tools.keys()):
            print(f"  • {name}")

        # Find and run an echo tool if available
        await find_and_run_echo_tool(proxy)

    finally:
        await proxy.stop_servers()


# ── CLI --------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-c",
        "--config",
        default=os.path.join(os.path.dirname(__file__), "proxy_config.yaml"),
        help="YAML config path (default: proxy_config.yaml next to script)",
    )
    asyncio.run(main(ap.parse_args().config))
