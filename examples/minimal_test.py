#!/usr/bin/env python3
"""
Minimal test to isolate the ASGI exception issue
"""

import asyncio
import json
import os
import sys

# Add to path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.server.server import MCPServer
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool


@mcp_tool(name="simple_test", description="Simple test tool")
async def simple_test(message: str) -> str:
    """Simple test tool."""
    return f"Received: {message}"


async def test_basic_functionality():
    """Test just the basic server startup and tool registration."""
    print("Testing basic server functionality...")

    # Test the JSON parser directly
    from chuk_mcp_runtime.server.server import parse_tool_arguments

    print("1. Testing JSON parser:")
    test_input = '{"message":"hello"}{"extra":"world"}'
    result = parse_tool_arguments(test_input)
    print(f"   Input: {test_input}")
    print(f"   Output: {result}")

    print("\n2. Testing tool registration:")
    from chuk_mcp_runtime.common.mcp_tool_decorator import (
        TOOLS_REGISTRY,
        initialize_tool_registry,
    )

    await initialize_tool_registry()
    print(f"   Registered tools: {list(TOOLS_REGISTRY.keys())}")

    print("\n3. Testing server creation (no serving):")
    try:
        cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8114}}
        server = MCPServer(cfg)
        print("   Server created successfully")

        # Test tool resolution
        if "simple_test" in server.tools_registry:
            print("   Tool 'simple_test' found in registry")
        else:
            print("   ERROR: Tool 'simple_test' not found in registry")

    except Exception as e:
        print(f"   ERROR creating server: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())
