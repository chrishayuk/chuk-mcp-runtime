#!/usr/bin/env python3
"""
Test HTTP serving with better error isolation
"""

import asyncio
import contextlib
import json
import os
import re
import socket
import sys
import time

import httpx

# Add to path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.server.server import MCPServer
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool


@mcp_tool(name="echo_test", description="Simple echo test")
async def echo_test(message: str) -> str:
    """Simple echo test tool."""
    return f"Echo: {message}"


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


async def start_server_with_error_handling():
    """Start server with comprehensive error handling."""
    try:
        print("Starting server...")
        cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8115}}
        server = MCPServer(cfg)

        print("About to call serve()...")
        await server.serve()

    except Exception as e:
        print(f"ERROR in server: {e}")
        import traceback

        traceback.print_exc()


async def test_basic_http():
    """Test basic HTTP connectivity without MCP calls."""
    await wait_port("127.0.0.1", 8115)
    print("Port is open, testing basic HTTP...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test 1: Basic SSE endpoint
            print("1. Testing SSE endpoint...")
            try:
                response = await client.get(
                    "http://127.0.0.1:8115/sse", headers={"accept": "text/event-stream"}
                )
                print(f"   SSE response status: {response.status_code}")
                if response.status_code == 200:
                    print("   ✅ SSE endpoint working")
                else:
                    print(f"   ❌ SSE endpoint failed: {response.status_code}")
            except Exception as e:
                print(f"   ❌ SSE endpoint error: {e}")

            # Test 2: Try to get session ID
            print("2. Testing session ID extraction...")
            try:
                session_id = None
                async with client.stream(
                    "GET",
                    "http://127.0.0.1:8115/sse",
                    headers={"accept": "text/event-stream"},
                ) as resp:
                    print(f"   Stream response status: {resp.status_code}")

                    count = 0
                    async for raw_line in resp.aiter_lines():
                        count += 1
                        print(f"   Line {count}: {raw_line}")

                        if raw_line.startswith("data:"):
                            data = raw_line[5:].strip()
                            if data:
                                # Look for session ID
                                match = re.search(r"([0-9a-f]{16,})", data)
                                if match:
                                    session_id = match.group(1)
                                    print(f"   ✅ Found session ID: {session_id}")
                                    break

                        # Don't read forever
                        if count > 5:
                            break

                if not session_id:
                    print("   ❌ No session ID found")
                    return

                # Test 3: Try simple initialize call
                print("3. Testing JSON-RPC initialize...")
                POST = f"http://127.0.0.1:8115/messages/?session_id={session_id}"

                init_body = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"},
                    },
                }

                print(f"   Sending to: {POST}")
                print(f"   Body: {json.dumps(init_body, indent=2)}")

                response = await client.post(POST, json=init_body)
                print(f"   Initialize response status: {response.status_code}")

                if response.status_code == 202:
                    print("   ✅ Initialize call accepted")
                else:
                    print(f"   ❌ Initialize call failed: {response.status_code}")
                    print(f"   Response: {response.text}")

            except Exception as e:
                print(f"   ❌ Session/Initialize error: {e}")
                import traceback

                traceback.print_exc()

    except Exception as e:
        print(f"HTTP test error: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """Main test function."""
    print("🧪 HTTP Server Test")
    print("=" * 40)

    # Start server
    server_task = asyncio.create_task(start_server_with_error_handling())

    # Give server time to start
    await asyncio.sleep(2.0)

    try:
        # Test HTTP functionality
        await test_basic_http()

    except Exception as e:
        print(f"Test error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\nShutting down...")
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task


if __name__ == "__main__":
    asyncio.run(main())
