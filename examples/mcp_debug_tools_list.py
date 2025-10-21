#!/usr/bin/env python3
"""
Debug script to specifically test the tools/list functionality
"""

import json
import os
import select
import subprocess
import tempfile
import time
from pathlib import Path


def debug_tools_list():
    """Debug the tools/list specific issue."""
    print("🔍 Debug Tools List Issue")
    print("=" * 40)

    # Setup
    temp_dir = Path(tempfile.mkdtemp(prefix="debug_tools_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    env = os.environ.copy()
    env.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": str(artifacts_dir),
            "ARTIFACT_BUCKET": "debug-tools",
            "CHUK_MCP_LOG_LEVEL": "DEBUG",  # More verbose
        }
    )

    print("🚀 Starting server with debug logging...")
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
        # Wait and capture startup logs
        time.sleep(4)

        if process.poll() is not None:
            stderr = process.stderr.read()
            print(f"❌ Server failed: {stderr}")
            return

        print("✅ Server started, testing initialization...")

        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "debug", "version": "1.0"},
            },
        }

        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()

        ready, _, _ = select.select([process.stdout], [], [], 5)
        if ready:
            response = process.stdout.readline()
            print(f"✅ Init response: {response.strip()}")
        else:
            print("❌ Init timeout")
            return

        # Send initialized notification (CRITICAL - this was missing!)
        print("📤 Sending initialized notification...")
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }

        process.stdin.write(json.dumps(initialized_msg) + "\n")
        process.stdin.flush()
        time.sleep(0.5)  # Brief pause
        print("✅ Initialization sequence complete")

        # Send initialized notification (CRITICAL - this was missing!)
        print("📤 Sending initialized notification...")
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }

        process.stdin.write(json.dumps(initialized_msg) + "\n")
        process.stdin.flush()
        time.sleep(0.5)  # Brief pause
        print("✅ Initialization sequence complete")

        print("\n🧪 Now testing tools/list with detailed monitoring...")

        tools_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        print(f"📤 Sending: {json.dumps(tools_msg)}")
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()
        print("✅ Message sent, waiting for response...")

        # Wait with longer timeout and check stderr for any errors
        for i in range(30):  # 30 seconds total
            ready, _, _ = select.select([process.stdout], [], [], 1)
            if ready:
                response = process.stdout.readline()
                print(f"✅ Got response: {response.strip()}")
                try:
                    parsed = json.loads(response)
                    if "result" in parsed:
                        tools = parsed["result"].get("tools", [])
                        print(f"🎉 Success! Found {len(tools)} tools")
                        for i, tool in enumerate(tools[:3]):
                            print(
                                f"   {i+1}. {tool.get('name')}: {tool.get('description', '')[:50]}..."
                            )
                    else:
                        print(f"⚠️  Unexpected response: {parsed}")
                except json.JSONDecodeError:
                    print(f"⚠️  Could not parse: {response}")
                return

            # Check if process died
            if process.poll() is not None:
                print("❌ Server process died")
                stderr = process.stderr.read()
                if stderr:
                    print(f"Error output: {stderr}")
                return

            print(f"⏳ Waiting... ({i+1}/30 seconds)")

        print("❌ Timeout after 30 seconds")

        # Check stderr for any error messages
        print("\n📋 Checking for error messages...")

        # Try to read any pending stderr
        if hasattr(select, "select"):
            ready, _, _ = select.select([process.stderr], [], [], 0.1)
            if ready:
                stderr = process.stderr.read()
                if stderr:
                    print(f"🚨 Stderr: {stderr}")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if process and process.poll() is None:
            print("🛑 Terminating server...")
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    debug_tools_list()
