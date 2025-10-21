#!/usr/bin/env python3
"""
Test to see exactly what happens when we call list_tools
"""

import asyncio
import os
import sys

# Add to path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.common.mcp_tool_decorator import (
    TOOLS_REGISTRY,
    initialize_tool_registry,
    mcp_tool,
)
from chuk_mcp_runtime.server.server import MCPServer


@mcp_tool(name="test_tool", description="Test tool")
async def test_tool(message: str) -> str:
    """Test tool."""
    return f"Test: {message}"


async def test_list_tools_directly():
    """Test the list_tools functionality directly."""
    print("🔍 Testing list_tools functionality directly...")

    # Initialize tools
    await initialize_tool_registry()

    print(f"Tools in registry: {list(TOOLS_REGISTRY.keys())}")

    # Create server instance
    cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8999}}
    server_instance = MCPServer(cfg)

    print("Created server instance")

    # Test the tools_registry
    print(f"Server tools registry: {list(server_instance.tools_registry.keys())}")

    # Try to manually call what list_tools does
    print("\nManually testing list_tools logic:")

    for tool_name, func in server_instance.tools_registry.items():
        print(f"\nProcessing tool: {tool_name}")
        print(f"  Function: {func}")
        print(f"  Has _mcp_tool: {hasattr(func, '_mcp_tool')}")

        if hasattr(func, "_mcp_tool"):
            tool_obj = func._mcp_tool
            print(f"  _mcp_tool object: {tool_obj}")
            print(f"  _mcp_tool type: {type(tool_obj)}")

            if hasattr(tool_obj, "name"):
                print(f"  Tool name: {tool_obj.name}")
            else:
                print("  ❌ No 'name' attribute")

            if hasattr(tool_obj, "description"):
                print(f"  Tool description: {tool_obj.description}")
            else:
                print("  ❌ No 'description' attribute")

            if hasattr(tool_obj, "inputSchema"):
                print(f"  Tool inputSchema type: {type(tool_obj.inputSchema)}")
                print(f"  Tool inputSchema: {tool_obj.inputSchema}")
            else:
                print("  ❌ No 'inputSchema' attribute")

            # Try to create a list with this tool
            try:
                print("  ✅ Can create list with this tool")

                # Try to convert to JSON (this might be where it fails)
                import json

                try:
                    # Try to serialize the tool object
                    serialized = {
                        "name": getattr(tool_obj, "name", "unknown"),
                        "description": getattr(tool_obj, "description", "unknown"),
                        "inputSchema": getattr(tool_obj, "inputSchema", {}),
                    }
                    json.dumps(serialized)
                    print("  ✅ Can serialize tool to JSON")
                except Exception as e:
                    print(f"  ❌ JSON serialization failed: {e}")
                    print("      This might be the cause of the ASGI exception!")

            except Exception as e:
                print(f"  ❌ Error with tool object: {e}")
        else:
            print("  ⚠️  Missing _mcp_tool attribute")


if __name__ == "__main__":
    asyncio.run(test_list_tools_directly())
