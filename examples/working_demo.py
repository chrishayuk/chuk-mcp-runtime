#!/usr/bin/env python3
"""
examples/working_demo.py
──────────────────────────────────────────────────────────────────────────────
Properly working MCP demo that follows the complete handshake protocol.
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


@mcp_tool(name="test_concat", description="Test concatenation handling")
async def test_concat(name: str, age: int, city: str) -> str:
    """Test tool for concatenation handling."""
    return f"✅ Successfully parsed: {name} (age {age}) from {city}"


@mcp_tool(name="simple_echo", description="Simple echo")
async def simple_echo(message: str) -> str:
    """Simple echo tool."""
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


async def start_server():
    """Start the MCP server."""
    cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8116}}
    await MCPServer(cfg).serve()


WELCOME_RX = re.compile(r"([0-9a-f]{16,})")


async def run_mcp_demo():
    """Run a complete MCP demo with proper handshake."""
    await wait_port("127.0.0.1", 8116)
    print("🚀 Server is ready, starting MCP demo...\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Get session ID
        print("1. Getting session ID...")
        session_id = None
        async with client.stream(
            "GET", "http://127.0.0.1:8116/sse", headers={"accept": "text/event-stream"}
        ) as resp:
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith("data:"):
                    data = raw_line[5:].strip()
                    if data:
                        match = WELCOME_RX.search(data)
                        if match:
                            session_id = match.group(1)
                            print(f"   ✅ Session ID: {session_id}")
                            break

        if not session_id:
            print("   ❌ Failed to get session ID")
            return

        POST = f"http://127.0.0.1:8116/messages/?session_id={session_id}"

        # Step 2: Initialize
        print("2. Initializing MCP connection...")
        init_body = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "demo-client", "version": "1.0"},
            },
        }

        response = await client.post(POST, json=init_body)
        if response.status_code == 202:
            print("   ✅ Initialize successful")
        else:
            print(f"   ❌ Initialize failed: {response.status_code}")
            return

        # Step 3: Send initialized notification
        print("3. Sending initialized notification...")
        notify_body = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }

        response = await client.post(POST, json=notify_body)
        if response.status_code == 202:
            print("   ✅ Notification sent")
        else:
            print(f"   ❌ Notification failed: {response.status_code}")

        # Step 4: List tools
        print("4. Listing available tools...")
        list_body = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}

        response = await client.post(POST, json=list_body)
        print(f"   Response status: {response.status_code}")

        # Step 5: Test simple tool call
        print("5. Testing simple tool call...")
        await test_tool_call(
            client, session_id, "simple_echo", {"message": "Hello World!"}
        )

        # Step 6: Test concatenation scenarios (simulate different ways concatenation might occur)
        print("6. Testing parameter handling...")

        # Normal parameters
        await test_tool_call(
            client,
            session_id,
            "test_concat",
            {"name": "Alice", "age": 30, "city": "New York"},
        )

        # Test edge cases
        await test_tool_call(
            client,
            session_id,
            "test_concat",
            {"name": "Bob", "age": 25, "city": "Boston"},
        )


async def test_tool_call(
    client: httpx.AsyncClient, session_id: str, tool_name: str, arguments: dict
):
    """Test a tool call and wait for response."""
    POST = f"http://127.0.0.1:8116/messages/?session_id={session_id}"
    SSE = "http://127.0.0.1:8116/sse"

    # Set up response listener
    result_received = asyncio.Event()
    result_data = {"response": None}

    async def response_listener():
        async with client.stream(
            "GET", SSE, headers={"accept": "text/event-stream"}
        ) as resp:
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith("data:"):
                    data = raw_line[5:].strip()
                    if not data:
                        continue

                    try:
                        obj = json.loads(data)
                        if obj.get("id") == 99:  # Our tool call ID
                            result_data["response"] = obj
                            result_received.set()
                            break
                    except json.JSONDecodeError:
                        pass

    # Start listener
    listener_task = asyncio.create_task(response_listener())

    try:
        # Make tool call
        tool_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 99,
            "params": {"name": tool_name, "arguments": arguments},
        }

        print(f"   Calling {tool_name} with {arguments}")
        response = await client.post(POST, json=tool_body)

        if response.status_code != 202:
            print(f"   ❌ Tool call failed: {response.status_code}")
            return

        # Wait for response
        await asyncio.wait_for(result_received.wait(), timeout=10.0)

        # Show result
        if result_data["response"]:
            result = result_data["response"].get("result", {})
            if result.get("isError"):
                content = result.get("content", [])
                error_text = (
                    content[0].get("text", "Unknown error")
                    if content
                    else "Unknown error"
                )
                print(f"   ❌ Tool error: {error_text}")
            else:
                content = result.get("content", [])
                if content:
                    result_text = content[0].get("text", "No text")
                    print(f"   ✅ Result: {result_text}")
                else:
                    print(f"   ✅ Result: {result}")
        else:
            print("   ❌ No response received")

    except asyncio.TimeoutError:
        print("   ❌ Timeout waiting for response")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task


async def main():
    """Main demo function."""
    print("🔧 CHUK MCP Runtime - Working Demo")
    print("=" * 50)
    print("Testing complete MCP protocol with proper handshake")
    print("=" * 50)
    print()

    # Test JSON concatenation parser first
    print("📝 Testing JSON concatenation parser directly:")
    from chuk_mcp_runtime.server.server import parse_tool_arguments

    test_cases = [
        '{"name":"Alice"}{"age":30}{"city":"New York"}',
        '{"message":"hello"}{"extra":"data"}',
        "plain string",
        '{"normal": "json"}',
    ]

    for i, test in enumerate(test_cases, 1):
        result = parse_tool_arguments(test)
        print(f"   {i}. {test} → {result}")

    print("\n" + "=" * 50)
    print("🌐 Starting server and testing HTTP/MCP protocol...")
    print("=" * 50)

    server_task = asyncio.create_task(start_server())
    await asyncio.sleep(2.0)  # Give server time to start

    try:
        await run_mcp_demo()
        print("\n🎉 Demo completed successfully!")

    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n🔄 Shutting down server...")
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task


if __name__ == "__main__":
    asyncio.run(main())
