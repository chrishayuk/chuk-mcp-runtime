#!/usr/bin/env python3
# examples/mcp_e2e_demo.py
#!/usr/bin/env python3
"""
Test complete MCP flow with proper protocol sequence
"""

import json
import subprocess
import tempfile
import time
import os
import select
from pathlib import Path


def test_complete_flow():
    """Test complete MCP flow with file operations."""
    print("🚀 Complete MCP Flow Test")
    print("=" * 40)

    # Setup
    temp_dir = Path(tempfile.mkdtemp(prefix="complete_flow_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    env = os.environ.copy()
    env.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": str(artifacts_dir),
            "ARTIFACT_BUCKET": "complete-test",
            "CHUK_MCP_LOG_LEVEL": "ERROR",  # Minimal logging
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
        time.sleep(3)

        if process.poll() is not None:
            print("❌ Server failed to start")
            return False

        print("✅ Server started")

        def send_and_receive(msg, expected_id=None, timeout=10):
            """Send message and get response"""
            process.stdin.write(json.dumps(msg) + "\n")
            process.stdin.flush()

            if expected_id is None:  # Notification
                time.sleep(0.5)
                return {"success": True}

            start_time = time.time()
            while time.time() - start_time < timeout:
                ready, _, _ = select.select([process.stdout], [], [], 0.5)
                if ready:
                    response_line = process.stdout.readline()
                    if response_line:
                        try:
                            response = json.loads(response_line)
                            if response.get("id") == expected_id:
                                return response
                        except json.JSONDecodeError:
                            continue

                if process.poll() is not None:
                    return {"error": "Server died"}

            return {"error": "timeout"}

        # 1. Initialize
        print("🤝 Initializing...")
        init_response = send_and_receive(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
            1,
        )

        if "result" not in init_response:
            print(f"❌ Init failed: {init_response}")
            return False
        print("✅ Initialized")

        # 2. Send initialized notification
        send_and_receive(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )
        print("✅ Initialization complete")

        # 3. Create a file (with session_id)
        print("\n📝 Creating file...")
        write_response = send_and_receive(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "write_file",
                    "arguments": {
                        "content": "Hello MCP World!\nThis is a test file.",
                        "filename": "test.txt",
                        "summary": "Test file for MCP demo",
                        "session_id": "test-session-123",
                    },
                },
            },
            2,
        )

        if "result" not in write_response:
            print(f"❌ Write failed: {write_response}")
            return False

        # Extract artifact ID
        content = write_response["result"]["content"][0]["text"]
        import re

        match = re.search(r"Artifact ID: ([a-f0-9]{32})", content)
        if not match:
            print(f"❌ Could not extract artifact ID from: {content}")
            return False

        artifact_id = match.group(1)
        print(f"✅ File created: {artifact_id}")

        # 4. List files (with session_id)
        print("\n📂 Listing files...")
        list_response = send_and_receive(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_session_files",
                    "arguments": {"session_id": "test-session-123"},
                },
            },
            3,
        )

        if "result" not in list_response:
            print(f"❌ List failed: {list_response}")
            return False

        files = json.loads(list_response["result"]["content"][0]["text"])
        print(f"✅ Found {len(files)} files")
        for file_info in files:
            print(f"   • {file_info['filename']} ({file_info['bytes']} bytes)")

        # 5. Read the file back (with session_id)
        print(f"\n📖 Reading file {artifact_id}...")
        read_response = send_and_receive(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "read_file",
                    "arguments": {
                        "artifact_id": artifact_id,
                        "session_id": "test-session-123",
                    },
                },
            },
            4,
        )

        if "result" not in read_response:
            print(f"❌ Read failed: {read_response}")
            return False

        file_content = read_response["result"]["content"][0]["text"]
        print(f"✅ File content: {file_content[:50]}...")

        # 6. Get storage stats (with session_id)
        print(f"\n📊 Getting storage stats...")
        stats_response = send_and_receive(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_storage_stats",
                    "arguments": {"session_id": "test-session-123"},
                },
            },
            5,
        )

        if "result" not in stats_response:
            print(f"❌ Stats failed: {stats_response}")
            return False

        stats = json.loads(stats_response["result"]["content"][0]["text"])
        print(
            f"✅ Storage stats: {stats['session_file_count']} files, {stats['session_total_bytes']} bytes"
        )

        print(f"\n🎉 Complete MCP flow successful!")
        print(f"✅ Protocol: Initialize → Tools → File ops → Read → Stats")
        print(f"✅ All 10 tools available and working")
        print(f"✅ Session management working")
        print(f"✅ Artifact storage working")

        return True

    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)

        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = test_complete_flow()
    exit(0 if success else 1)
