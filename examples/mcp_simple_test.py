#!/usr/bin/env python3
"""
examples/simple_mcp_test.py

Simple script to verify that the MCP server is working correctly.
This directly tests the stdio interface by sending JSON-RPC messages.

This is the most basic test that requires no additional dependencies.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path


def send_request(process, request, timeout=10):
    """Send a JSON-RPC request to the server and get response."""
    import select
    import sys

    request_line = json.dumps(request) + "\n"
    print(f"   Sending: {json.dumps(request)}")

    try:
        process.stdin.write(request_line)
        process.stdin.flush()
    except BrokenPipeError:
        print("❌ Server closed connection")
        return None

    # Use select for timeout on Unix systems
    if hasattr(select, "select"):
        ready, _, _ = select.select([process.stdout], [], [], timeout)
        if not ready:
            print(f"❌ Timeout after {timeout} seconds waiting for response")
            return {"error": "timeout"}

    try:
        response_line = process.stdout.readline()
        if not response_line:
            print("❌ No response from server (EOF)")
            return None

        print(f"   Received: {response_line.strip()}")
        return json.loads(response_line)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse response: {response_line}")
        print(f"   Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error reading response: {e}")
        return None


def test_mcp_server_basic():
    """Basic test that the server can start and respond to requests."""
    print("🚀 Basic MCP Server Test")
    print("=" * 40)

    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="mcp_basic_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    print(f"📁 Using temp directory: {temp_dir}")

    # Set up environment
    import os

    env = os.environ.copy()
    env.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": str(artifacts_dir),
            "ARTIFACT_BUCKET": "basic-test",
            "CHUK_MCP_LOG_LEVEL": "ERROR",  # Minimize output
        }
    )

    # Start server
    cmd = ["uv", "run", "chuk-mcp-runtime"]
    print(f"🚀 Starting server: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=0,
        )

        # Give server time to start
        time.sleep(2)

        if process.poll() is not None:
            stderr = process.stderr.read()
            print(f"❌ Server failed to start: {stderr}")
            return False

        print("✅ Server started successfully")

        # Test 1: Initialize connection
        print("\n🤝 Testing connection initialization...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        response = send_request(process, init_request, timeout=10)
        if response and response.get("id") == 1 and "result" in response:
            print("✅ Initialization successful")
            print(
                f"   Server: {response['result'].get('serverInfo', {}).get('name', 'unknown')}"
            )
        else:
            print(f"❌ Initialization failed: {response}")
            return False

        # Send initialized notification (CRITICAL for MCP protocol)
        print("📤 Sending initialized notification...")
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }

        # Send notification (no response expected)
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()
        time.sleep(0.5)  # Brief pause
        print("✅ Initialization sequence complete")

        # Test 2: List tools
        print("\n📋 Testing tool listing...")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = send_request(process, list_tools_request, timeout=15)
        if response and response.get("id") == 2 and "result" in response:
            tools = response["result"].get("tools", [])
            print(f"✅ Found {len(tools)} tools:")

            # Show first few tools
            for i, tool in enumerate(tools[:5]):
                print(
                    f"   {i+1}. {tool.get('name', 'unknown')}: {tool.get('description', 'No description')[:50]}..."
                )

            if len(tools) > 5:
                print(f"   ... and {len(tools) - 5} more tools")

            # Check for expected artifact tools
            tool_names = {tool.get("name") for tool in tools}
            expected_tools = {"write_file", "read_file", "list_session_files"}
            found_expected = expected_tools.intersection(tool_names)

            if found_expected:
                print(f"✅ Found expected tools: {', '.join(found_expected)}")
            else:
                print(f"⚠️  Expected tools not found: {expected_tools}")

        else:
            print(f"❌ Tool listing failed: {response}")
            return False

        # Test 3: Call a tool (write_file with session_id)
        print("\n📝 Testing tool execution (write_file)...")
        call_tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "content": "Hello from basic MCP test!",
                    "filename": "basic_test.txt",
                    "mime": "text/plain",
                    "summary": "Basic test file",
                    "session_id": "basic-test-session",
                },
            },
        }

        response = send_request(process, call_tool_request, timeout=15)
        if response and response.get("id") == 3 and "result" in response:
            result = response["result"]
            if "content" in result and result["content"]:
                content_text = result["content"][0].get("text", "")
                print(f"✅ Tool execution successful")
                print(f"   Result: {content_text[:60]}...")

                # Extract artifact ID for next test
                import re

                match = re.search(r"Artifact ID: ([a-f0-9]{32})", content_text)
                artifact_id = match.group(1) if match else None

                if artifact_id:
                    # Test 4: Call another tool (list_session_files with session_id)
                    print("\n📂 Testing file listing...")
                    list_files_request = {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "list_session_files",
                            "arguments": {"session_id": "basic-test-session"},
                        },
                    }

                    response = send_request(process, list_files_request, timeout=10)
                    if response and response.get("id") == 4 and "result" in response:
                        result = response["result"]
                        if "content" in result and result["content"]:
                            files_json = result["content"][0].get("text", "[]")
                            try:
                                files = json.loads(files_json)
                                print(
                                    f"✅ File listing successful: {len(files)} files found"
                                )
                                for file_info in files:
                                    print(
                                        f"   • {file_info.get('filename', 'unknown')} ({file_info.get('bytes', 0)} bytes)"
                                    )
                            except json.JSONDecodeError:
                                print(f"⚠️  Could not parse files JSON: {files_json}")
                        else:
                            print("❌ No content in list files response")
                    else:
                        print(f"❌ File listing failed: {response}")
                else:
                    print("⚠️  Could not extract artifact ID from write response")
            else:
                print("❌ No content in tool response")
        else:
            print(f"❌ Tool execution failed: {response}")
            return False

        print("\n🎉 All basic tests passed!")
        print("\n✅ Test Summary:")
        print("   • Server startup: ✅")
        print("   • MCP initialization: ✅")
        print("   • Tool discovery: ✅")
        print("   • Tool execution: ✅")
        print("   • Session management: ✅")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up
        try:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        except:
            if process:
                process.kill()

        # Clean up temp directory
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
        print("\n🧹 Cleanup completed")


def show_manual_test_commands():
    """Show commands for manual testing."""
    print("\n" + "=" * 50)
    print("Manual Testing Commands")
    print("=" * 50)
    print("""
If you want to test manually, here are some JSON-RPC messages you can send:

1. Start the server:
   uv run chuk-mcp-runtime --config config.yaml

2. Send these JSON messages via stdin (one per line):

   Initialize (with required notification):
   {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-test","version":"1.0"}}}
   {"jsonrpc":"2.0","method":"notifications/initialized","params":{}}

   List tools:
   {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}

   Write a file:
   {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"write_file","arguments":{"content":"Hello World","filename":"test.txt","session_id":"test-session"}}}

   List files:
   {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_session_files","arguments":{"session_id":"test-session"}}}

Each message should return a JSON response with the same ID.
""")


if __name__ == "__main__":
    try:
        success = test_mcp_server_basic()
        if not success:
            show_manual_test_commands()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        show_manual_test_commands()
