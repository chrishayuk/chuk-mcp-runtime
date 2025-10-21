#!/usr/bin/env python3
"""
examples/stream_demo.py
──────────────────────────────────────────────────────────────────────────────
• Starts an MCP server (SSE) **with a tiny streaming tool** (`echo_stream`)
• Performs a valid JSON-RPC handshake over the /messages endpoint
• Streams every token as it arrives from /sse

This is the smallest possible end-to-end demo that:
   - obeys the JSON-RPC 2.0 shapes (`initialize`, `notifications/initialized`,
     `tools/call`)
   - handles the session-ID handshake required by SseServerTransport
"""

import asyncio
import contextlib
import json
import os
import re
import socket
import sys

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# 0  ‒  Add chuk-runtime to PYTHONPATH if you run from repo root
# ─────────────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.server import MCPServer


# ─────────────────────────────────────────────────────────────────────────────
# 1  ‒  Define one tiny streaming tool
# ─────────────────────────────────────────────────────────────────────────────
@mcp_tool(name="echo_stream", description="Echo words live", timeout=10)
async def echo_stream(text: str, delay: float = 0.20):
    """
    Echo words with a delay between each word.

    Args:
        text: The text to echo word by word
        delay: Delay between words in seconds
    """
    for word in text.split():
        await asyncio.sleep(delay)
        yield {"delta": word + " "}


# ─────────────────────────────────────────────────────────────────────────────
# 2  ‒  Helper: wait until port is listening
# ─────────────────────────────────────────────────────────────────────────────
async def wait_port(host: str, port: int, timeout: float = 10.0):
    limit = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < limit:
        try:
            with socket.create_connection((host, port), 0.2):
                return
        except OSError:
            await asyncio.sleep(0.1)
    raise RuntimeError(f"{host}:{port} still closed after {timeout}s")


# ─────────────────────────────────────────────────────────────────────────────
# 3  ‒  Run the SSE MCP server in-process
# ─────────────────────────────────────────────────────────────────────────────
async def start_server():
    cfg = {"server": {"type": "sse"}, "sse": {"host": "127.0.0.1", "port": 8111}}
    await MCPServer(cfg).serve()


# ─────────────────────────────────────────────────────────────────────────────
# 4  ‒  Client: JSON-RPC handshake + streaming call
# ─────────────────────────────────────────────────────────────────────────────
WELCOME_RX = re.compile(r"(?:/messages/\?session_id=)?([0-9a-f]{16,})")


async def run_client(prompt: str):
    await wait_port("127.0.0.1", 8111)
    print(f"[DEBUG] Server is ready, starting client with prompt: '{prompt}'")

    SSE = "http://127.0.0.1:8111/sse"
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 4A. Connect to /sse - grab the server-issued session ID
        session_fut: asyncio.Future[str] = asyncio.Future()
        streaming_done = asyncio.Event()

        async def sse_reader():
            try:
                async with client.stream(
                    "GET", SSE, headers={"accept": "text/event-stream"}
                ) as resp:
                    print(f"[DEBUG] Connected to SSE, status: {resp.status_code}")
                    async for raw_line in resp.aiter_lines():
                        print(f"[DEBUG] SSE line: {raw_line}")
                        if not raw_line.startswith("data:"):
                            continue
                        data = raw_line[5:].strip()
                        if not data:  # heartbeat
                            continue

                        # First message from transport → session_id
                        if not session_fut.done():
                            print(f"[DEBUG] Looking for session ID in: {data}")
                            # Try JSON first
                            try:
                                obj = json.loads(data)
                                if isinstance(obj, dict) and "session_id" in obj:
                                    print(f"[DEBUG] Found session_id in JSON: {obj['session_id']}")
                                    session_fut.set_result(obj["session_id"])
                                    continue
                            except json.JSONDecodeError:
                                pass
                            m = WELCOME_RX.search(data)  # Changed from fullmatch to search
                            if m:
                                print(f"[DEBUG] Found session_id via regex: {m.group(1)}")
                                session_fut.set_result(m.group(1))
                                continue

                            # If it looks like a simple session ID string
                            if len(data) >= 16 and all(c in "0123456789abcdef" for c in data):
                                print(f"[DEBUG] Found session_id as plain string: {data}")
                                session_fut.set_result(data)
                                continue

                        # Streaming chunks (TextContent)
                        try:
                            obj = json.loads(data)
                            print(f"[DEBUG] Parsed JSON object: {obj}")
                            if obj.get("type") == "text":
                                sys.stdout.write(obj["text"])
                                sys.stdout.flush()
                            elif "result" in obj and obj.get("id") == 2:
                                # Tool call completed
                                print(f"[DEBUG] Tool call completed: {obj}")
                                streaming_done.set()
                        except json.JSONDecodeError:
                            print(f"[DEBUG] Non-JSON data: {data}")

            except Exception as e:
                print(f"[ERROR] SSE reader error: {e}")
                if not session_fut.done():
                    session_fut.set_exception(e)

        reader_task = asyncio.create_task(sse_reader())

        try:
            session_id = await asyncio.wait_for(session_fut, timeout=15)
            print(f"[DEBUG] Got session ID: {session_id}")
        except asyncio.TimeoutError:
            print("[ERROR] Timeout waiting for session ID")
            reader_task.cancel()
            return

        # 4B. Perform JSON-RPC initialize over /messages
        POST = f"http://127.0.0.1:8111/messages/?session_id={session_id}"

        async def rpc(id_: int | None, method: str, params: dict | None):
            body = {
                "jsonrpc": "2.0",
                "method": method,
                **({"id": id_} if id_ is not None else {}),
                **({"params": params} if params is not None else {}),
            }
            print(f"[DEBUG] Sending RPC: {json.dumps(body, indent=2)}")
            response = await client.post(POST, json=body)
            print(f"[DEBUG] RPC response status: {response.status_code}")

        # 4C. JSON-RPC handshake
        await rpc(
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "stream-demo", "version": "1.0"},
            },
        )
        await rpc(None, "notifications/initialized", {})  # notification (id=None)

        # 4D. JSON-RPC tools/call - streaming tool
        print(f"[DEBUG] Calling tool with prompt: '{prompt}'")
        await rpc(
            2,
            "tools/call",
            {
                "name": "echo_stream",
                "arguments": {"text": prompt, "delay": 0.5},
            },
        )

        # Wait for streaming to complete or timeout
        try:
            await asyncio.wait_for(streaming_done.wait(), timeout=30.0)
            print("\n[DEBUG] Streaming completed successfully")
        except asyncio.TimeoutError:
            print("\n[DEBUG] Streaming timed out")

        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 5  ‒  Main driver
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    prompt = " ".join(sys.argv[1:]) or "Hello streaming world!"
    print(f"[DEBUG] Starting with prompt: '{prompt}'")

    server_task = asyncio.create_task(start_server())

    # Give server a moment to start
    await asyncio.sleep(1.0)

    try:
        await run_client(prompt)
        print("\n[done]")
    except Exception as e:
        print(f"\n[ERROR] Client error: {e}")
    finally:
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task


if __name__ == "__main__":
    asyncio.run(main())
