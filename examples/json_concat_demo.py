#!/usr/bin/env python3
"""
examples/realistic_concat_demo.py
──────────────────────────────────────────────────────────────────────────────
More realistic demo of JSON concatenation - simulates how concatenated JSON
would actually arrive at the server (e.g., through HTTP body parsing issues).
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

# ─────────────────────────────────────────────────────────────────────────────
# 0  ‒  Add chuk-runtime to PYTHONPATH if you run from repo root
# ─────────────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.server.server import MCPServer
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool


# ─────────────────────────────────────────────────────────────────────────────
# 1  ‒  Define test tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp_tool(name="test_tool", description="Tool to test parameter parsing")
async def test_tool(name: str, age: int, city: str, active: bool = True) -> str:
    """
    Test tool with multiple parameters.

    Args:
        name: Person's name
        age: Person's age
        city: Person's city
        active: Whether person is active
    """
    return f"✅ Parsed successfully: {name}, {age}, {city}, {active}"


# ─────────────────────────────────────────────────────────────────────────────
# 2  ‒  Helper functions
# ─────────────────────────────────────────────────────────────────────────────


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
    cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8113}}
    await MCPServer(cfg).serve()


# ─────────────────────────────────────────────────────────────────────────────
# 3  ‒  Test different scenarios
# ─────────────────────────────────────────────────────────────────────────────

WELCOME_RX = re.compile(r"(?:/messages/\?session_id=)?([0-9a-f]{16,})")


async def test_scenarios():
    """Test different parameter scenarios."""
    await wait_port("127.0.0.1", 8113)
    print("[INFO] Server is ready, testing parameter handling...\n")

    test_cases = [
        {
            "name": "Normal Parameters",
            "description": "Standard JSON object - should work fine",
            "arguments": {
                "name": "Alice",
                "age": 30,
                "city": "New York",
                "active": True,
            },
        },
        {
            "name": "Missing Parameter",
            "description": "Missing required parameter - should show helpful error",
            "arguments": {"name": "Bob", "age": 25},  # Missing city
        },
        {
            "name": "Wrong Type",
            "description": "Wrong parameter type - should show type error",
            "arguments": {
                "name": "Charlie",
                "age": "not-a-number",
                "city": "Chicago",
                "active": True,
            },
        },
        {
            "name": "Extra Parameters",
            "description": "Extra parameters - should work (extras ignored)",
            "arguments": {
                "name": "David",
                "age": 40,
                "city": "Denver",
                "active": False,
                "extra": "ignored",
            },
        },
    ]

    # Test manual JSON concatenation by directly calling the parse function
    print("=== Testing JSON Concatenation Parser Directly ===")

    # Import the function we want to test
    from chuk_mcp_runtime.server.server import parse_tool_arguments

    concat_tests = [
        '{"name":"Alice"}{"age":30}{"city":"New York"}{"active":true}',
        '{"name":"Bob","age":25}{"city":"Boston"}',
        '{"database":"mydb"}{"host":"localhost"}{"port":5432}',
        "plain string",
        '{"valid": "json"}',
        "",
    ]

    for i, test_input in enumerate(concat_tests, 1):
        print(f"Test {i}: {test_input}")
        try:
            result = parse_tool_arguments(test_input)
            print(f"  Result: {result}")
        except Exception as e:
            print(f"  Error: {e}")
        print()

    print("=" * 60)
    print()

    # Test actual tool calls
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_case in enumerate(test_cases, 1):
            print(f"=== Tool Test {i}: {test_case['name']} ===")
            print(f"Description: {test_case['description']}")
            print(f"Arguments: {test_case['arguments']}")
            print()

            try:
                # Get session and do handshake
                session_id = await get_session_id(client, "http://127.0.0.1:8113/sse")
                await perform_handshake(client, session_id)

                # Test the tool call
                result = await call_tool(
                    client, session_id, "test_tool", test_case["arguments"]
                )

                if result:
                    print(f"Result: {result}")
                else:
                    print("No result received")

            except Exception as e:
                print(f"❌ Error: {e}")

            print("-" * 40)
            print()


async def get_session_id(client: httpx.AsyncClient, sse_url: str) -> str:
    """Get session ID from SSE endpoint."""
    async with client.stream(
        "GET", sse_url, headers={"accept": "text/event-stream"}
    ) as resp:
        async for raw_line in resp.aiter_lines():
            if raw_line.startswith("data:"):
                data = raw_line[5:].strip()
                if data:
                    m = WELCOME_RX.search(data)
                    if m:
                        return m.group(1)
    raise RuntimeError("Could not get session ID")


async def perform_handshake(client: httpx.AsyncClient, session_id: str):
    """Perform JSON-RPC handshake."""
    POST = f"http://127.0.0.1:8113/messages/?session_id={session_id}"

    async def rpc(id_: int | None, method: str, params: dict | None):
        body = {
            "jsonrpc": "2.0",
            "method": method,
            **({"id": id_} if id_ is not None else {}),
            **({"params": params} if params is not None else {}),
        }
        await client.post(POST, json=body)

    await rpc(
        1,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "realistic-demo", "version": "1.0"},
        },
    )
    await rpc(None, "notifications/initialized", {})


async def call_tool(
    client: httpx.AsyncClient, session_id: str, tool_name: str, arguments: dict
) -> str:
    """Call a tool and return the result."""
    POST = f"http://127.0.0.1:8113/messages/?session_id={session_id}"
    SSE = "http://127.0.0.1:8113/sse"

    result_received = asyncio.Event()
    result_data = {"response": None}

    # Listen for response
    async def sse_listener():
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
                        if obj.get("id") == 2:  # Our tool call
                            result_data["response"] = obj
                            result_received.set()
                            break
                    except json.JSONDecodeError:
                        pass

    # Start listener
    listener_task = asyncio.create_task(sse_listener())

    try:
        # Make the tool call
        body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {"name": tool_name, "arguments": arguments},
        }

        await client.post(POST, json=body)

        # Wait for response
        await asyncio.wait_for(result_received.wait(), timeout=10.0)

        # Extract result
        response = result_data["response"]
        if response and "result" in response:
            content = response["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                return content[0].get("text", "No text content")
            return str(content)

        return "No response"

    except asyncio.TimeoutError:
        return "Timeout waiting for response"
    finally:
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task


# ─────────────────────────────────────────────────────────────────────────────
# 4  ‒  Main driver
# ─────────────────────────────────────────────────────────────────────────────


async def main():
    """Main demo function."""
    print("🔧 CHUK MCP Runtime - Realistic Parameter Handling Demo")
    print("=" * 60)
    print("Testing both JSON concatenation parsing and general parameter handling.")
    print("=" * 60)
    print()

    server_task = asyncio.create_task(start_server())

    # Give server a moment to start
    await asyncio.sleep(2.0)

    try:
        await test_scenarios()
        print("\n🎉 Demo completed!")

    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task


if __name__ == "__main__":
    asyncio.run(main())
