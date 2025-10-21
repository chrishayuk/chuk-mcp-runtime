#!/usr/bin/env python3
"""
Final diagnostic to see what's happening on the server side
"""

import asyncio
import contextlib
import json
import os
import re
import socket
import sys

import httpx

# Add to path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.server import MCPServer


@mcp_tool(name="debug_tool", description="Debug tool with extensive logging")
async def debug_tool(test_param: str) -> str:
    """Debug tool that logs everything."""
    print(f"[DEBUG_TOOL] Called with parameter: {test_param}")
    print(f"[DEBUG_TOOL] Parameter type: {type(test_param)}")
    result = f"Debug tool received: {test_param}"
    print(f"[DEBUG_TOOL] Returning: {result}")
    return result


async def start_server_with_debug():
    """Start server with debug logging."""
    print("[SERVER] Starting server with debug logging...")

    cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8118}}

    # Enable debug logging
    import logging

    logging.basicConfig(level=logging.DEBUG)

    try:
        server = MCPServer(cfg)
        print("[SERVER] Server created, starting serve()...")
        await server.serve()
    except Exception as e:
        print(f"[SERVER] Exception in server: {e}")
        import traceback

        traceback.print_exc()


async def wait_port(host: str, port: int, timeout: float = 10.0):
    """Wait for port to be available."""
    limit = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < limit:
        try:
            with socket.create_connection((host, port), 0.2):
                return
        except OSError:
            await asyncio.sleep(0.1)
    raise RuntimeError(f"{host}:{port} still closed after {timeout}s")


async def test_direct_tool_execution():
    """Test tool execution directly without MCP."""
    print("\n[DIRECT] Testing tool execution directly...")

    from chuk_mcp_runtime.common.mcp_tool_decorator import (
        TOOLS_REGISTRY,
        initialize_tool_registry,
    )

    await initialize_tool_registry()

    if "debug_tool" in TOOLS_REGISTRY:
        tool_func = TOOLS_REGISTRY["debug_tool"]
        print(f"[DIRECT] Found tool function: {tool_func}")

        try:
            result = await tool_func(test_param="direct test")
            print(f"[DIRECT] Direct execution result: {result}")
            print("[DIRECT] ✅ Direct tool execution works")
        except Exception as e:
            print(f"[DIRECT] ❌ Direct execution failed: {e}")
            import traceback

            traceback.print_exc()
    else:
        print("[DIRECT] ❌ Tool not found in registry")


async def test_minimal_http():
    """Test just the HTTP part with minimal MCP calls."""
    await wait_port("127.0.0.1", 8118)
    print("\n[HTTP] Testing minimal HTTP interactions...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Just test that we can POST to the messages endpoint
            print("[HTTP] Testing basic POST to messages endpoint...")

            # Get session ID first
            session_id = None
            async with client.stream(
                "GET",
                "http://127.0.0.1:8118/sse",
                headers={"accept": "text/event-stream"},
            ) as resp:
                async for raw_line in resp.aiter_lines():
                    if raw_line.startswith("data:"):
                        data = raw_line[5:].strip()
                        if data:
                            match = re.search(r"([0-9a-f]{16,})", data)
                            if match:
                                session_id = match.group(1)
                                print(f"[HTTP] Got session ID: {session_id}")
                                break

            if not session_id:
                print("[HTTP] ❌ No session ID")
                return

            POST = f"http://127.0.0.1:8118/messages/?session_id={session_id}"

            # Test 1: Initialize (we know this works)
            print("[HTTP] Testing initialize...")
            init_body = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "debug-client", "version": "1.0"},
                },
            }

            response = await client.post(POST, json=init_body)
            print(f"[HTTP] Initialize response: {response.status_code}")

            if response.status_code != 202:
                print("[HTTP] ❌ Initialize failed")
                return

            # Test 2: List tools (this might work)
            print("[HTTP] Testing tools/list...")
            list_body = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}

            response = await client.post(POST, json=list_body)
            print(f"[HTTP] Tools list response: {response.status_code}")

            # Test 3: Tool call (this is where it breaks)
            print("[HTTP] Testing tools/call...")
            print("[HTTP] This is where we expect the ASGI exception...")

            tool_body = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 3,
                "params": {
                    "name": "debug_tool",
                    "arguments": {"test_param": "http test"},
                },
            }

            print(f"[HTTP] Sending tool call: {json.dumps(tool_body, indent=2)}")
            response = await client.post(POST, json=tool_body)
            print(f"[HTTP] Tool call response: {response.status_code}")

        except Exception as e:
            print(f"[HTTP] Exception: {e}")
            import traceback

            traceback.print_exc()


async def main():
    """Main diagnostic function."""
    print("🔍 CHUK MCP Runtime - Final Diagnostic")
    print("=" * 60)
    print("This will help isolate exactly where the ASGI issue occurs")
    print("=" * 60)

    # Test 1: Direct tool execution (no HTTP/MCP)
    await test_direct_tool_execution()

    print("\n" + "=" * 60)
    print("🌐 Starting server for HTTP tests...")
    print("=" * 60)

    # Test 2: Start server and test HTTP
    server_task = asyncio.create_task(start_server_with_debug())
    await asyncio.sleep(3.0)  # Give server more time to start

    try:
        await test_minimal_http()

    except Exception as e:
        print(f"\n❌ Main test error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n🔄 Shutting down...")
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task


if __name__ == "__main__":
    asyncio.run(main())
