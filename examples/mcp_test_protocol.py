#!/usr/bin/env python3
"""
Test the raw MCP protocol to see if the issue is in the protocol handling
"""

import json
import subprocess
import tempfile
import time
import os
import select
from pathlib import Path


def test_mcp_protocol():
    """Test raw MCP protocol communication."""
    print("🔍 Testing Raw MCP Protocol")
    print("=" * 40)

    # Setup
    temp_dir = Path(tempfile.mkdtemp(prefix="test_protocol_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    env = os.environ.copy()
    env.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": str(artifacts_dir),
            "ARTIFACT_BUCKET": "test-protocol",
            "CHUK_MCP_LOG_LEVEL": "ERROR",  # Minimal logging to reduce noise
        }
    )

    print("🚀 Starting server...")
    process = subprocess.Popen(
        ["uv", "run", "chuk-mcp-runtime"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=0,
    )

    try:
        # Wait for startup
        time.sleep(3)

        if process.poll() is not None:
            stderr = process.stderr.read()
            print(f"❌ Server failed: {stderr}")
            return

        print("✅ Server started")

        # Test different MCP messages
        messages = [
            {
                "name": "initialize",
                "message": {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"},
                    },
                },
                "timeout": 5,
                "expect_response": True,
            },
            {
                "name": "initialized_notification",
                "message": {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                "timeout": 1,
                "expect_response": False,  # Notifications don't get responses
            },
            {
                "name": "tools/list",
                "message": {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                },
                "timeout": 10,
                "expect_response": True,
            },
        ]

        for test in messages:
            print(f"\n🧪 Testing {test['name']}...")

            # Send message
            msg = json.dumps(test["message"]) + "\n"
            print(f"📤 Sending: {msg.strip()}")

            try:
                process.stdin.write(msg)
                process.stdin.flush()
            except BrokenPipeError:
                print("❌ Broken pipe - server closed connection")
                break

            # Wait for response
            if test.get("expect_response", True):
                response_received = False
                start_time = time.time()

                while time.time() - start_time < test["timeout"]:
                    ready, _, _ = select.select([process.stdout], [], [], 0.5)
                    if ready:
                        try:
                            response_line = process.stdout.readline()
                            if response_line:
                                print(f"📥 Received: {response_line.strip()}")

                                try:
                                    response = json.loads(response_line)
                                    if response.get("id") == test["message"].get("id"):
                                        if "result" in response:
                                            print(f"✅ {test['name']} succeeded")
                                            if test["name"] == "tools/list":
                                                tools = response["result"].get(
                                                    "tools", []
                                                )
                                                print(f"   Found {len(tools)} tools")
                                        elif "error" in response:
                                            print(
                                                f"⚠️  {test['name']} returned error: {response['error']}"
                                            )
                                        response_received = True
                                        break
                                except json.JSONDecodeError:
                                    print(
                                        f"⚠️  Non-JSON response: {response_line.strip()}"
                                    )
                            else:
                                break
                        except Exception as e:
                            print(f"❌ Error reading response: {e}")
                            break

                    if process.poll() is not None:
                        print("❌ Server process died")
                        break

                if not response_received:
                    print(
                        f"❌ {test['name']} timed out after {test['timeout']} seconds"
                    )
            else:
                # For notifications, just wait a moment
                print(f"✅ {test['name']} notification sent")
                time.sleep(0.5)

            # Small delay between tests
            time.sleep(0.5)

        # Check if server is still alive
        if process.poll() is None:
            print("\n✅ Server survived all tests")
        else:
            print(f"\n❌ Server died during testing (exit code: {process.returncode})")
            stderr = process.stderr.read()
            if stderr:
                print(f"Stderr: {stderr}")

    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)

        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_mcp_protocol()
