#!/usr/bin/env python3
"""
Debug script to check what happens during server startup with tools
"""

import json
import subprocess
import tempfile
import time
import os
import select
from pathlib import Path


def debug_server_tools():
    """Debug the server tool initialization in detail."""
    print("🔍 Debug Server Tools Initialization")
    print("=" * 50)

    # Setup
    temp_dir = Path(tempfile.mkdtemp(prefix="debug_server_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    env = os.environ.copy()
    env.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": str(artifacts_dir),
            "ARTIFACT_BUCKET": "debug-server",
            "CHUK_MCP_LOG_LEVEL": "DEBUG",  # Maximum verbosity
        }
    )

    print("🚀 Starting server with maximum logging...")
    process = subprocess.Popen(
        ["uv", "run", "chuk-mcp-runtime"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine all output
        env=env,
        text=True,
        bufsize=0,
    )

    try:
        # Capture detailed startup logs
        print("📝 Server startup logs:")
        startup_logs = []
        start_time = time.time()

        while time.time() - start_time < 8:  # Extended time
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if ready:
                line = process.stdout.readline()
                if line:
                    print(f"   {line.rstrip()}")
                    startup_logs.append(line)
                else:
                    break

            if process.poll() is not None:
                break

        print(f"\n📊 Analysis after {int(time.time() - start_time)} seconds:")

        if process.poll() is None:
            print("✅ Server is running")
        else:
            print(f"❌ Server exited with code: {process.returncode}")
            return

        # Analyze the logs
        log_text = "".join(startup_logs)

        # Check for key events
        checks = [
            ("Tools registered successfully", "✅ Artifacts tools registered"),
            ("Tools available in registry:", "✅ Tools found in registry"),
            ("Using existing tools registry", "✅ Server using populated registry"),
            ("Initializing tool metadata", "✅ Tool metadata initialization started"),
            (
                "Tools with metadata after initialization",
                "✅ Tool metadata initialization completed",
            ),
            ("Starting stdio server", "✅ Server reached stdio mode"),
        ]

        for pattern, message in checks:
            if pattern in log_text:
                print(message)
            else:
                print(f"❌ Missing: {pattern}")

        # Extract specific counts
        import re

        # Tools in registry
        match = re.search(r"Tools available in registry: (\d+) total", log_text)
        if match:
            print(f"📊 Registry tools: {match.group(1)}")

        # Tools with metadata
        match = re.search(
            r"Tools with metadata after initialization: (\d+)/(\d+)", log_text
        )
        if match:
            print(f"📊 Tools with metadata: {match.group(1)}/{match.group(2)}")

        # Now test initialization
        print("\n🧪 Testing MCP initialization...")
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
            print(f"✅ Init response received: {len(response)} chars")
        else:
            print("❌ Init timeout")
            return

        # Test tools/list with detailed monitoring
        print("\n🧪 Testing tools/list with monitoring...")
        tools_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        print("📤 Sending tools/list request...")
        process.stdin.write(json.dumps(tools_msg) + "\n")
        process.stdin.flush()

        # Monitor for response or additional logs
        response_received = False
        for i in range(15):  # 15 second timeout
            ready, _, _ = select.select([process.stdout], [], [], 1)
            if ready:
                line = process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line)
                        if response.get("id") == 2:
                            print(f"✅ Tools list response received!")
                            if "result" in response:
                                tools = response["result"].get("tools", [])
                                print(f"📊 Found {len(tools)} tools in response")
                                response_received = True
                                break
                            else:
                                print(f"❌ No result in response: {response}")
                                break
                    except json.JSONDecodeError:
                        # Might be a log line, not JSON response
                        print(f"📝 Server log: {line.rstrip()}")
                else:
                    break

            if process.poll() is not None:
                print("❌ Server process died")
                break

            print(f"⏳ Waiting for tools/list response... ({i+1}/15)")

        if not response_received:
            print("❌ tools/list timed out - this is the core issue!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)

        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    debug_server_tools()
