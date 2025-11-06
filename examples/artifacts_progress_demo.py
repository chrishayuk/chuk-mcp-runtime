#!/usr/bin/env python3
"""
Artifacts Progress Reporting Demo

Demonstrates MCP progress notifications during artifact file operations.
Shows real-time progress tracking for file uploads and writes.

Based on progress_e2e_demo.py pattern.

Run:
    uv run python examples/artifacts_progress_demo.py
"""

import base64
import json
import os
import select
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional


class ProgressTracker:
    """Tracks and displays progress notifications."""

    def __init__(self):
        self.notifications = []
        self.last_progress = {}

    def handle_notification(self, notification):
        """Handle a progress notification."""
        if notification.get("method") == "notifications/progress":
            params = notification.get("params", {})
            token = params.get("progressToken")
            progress = params.get("progress", 0)
            total = params.get("total", 1)
            message = params.get("message", "")

            self.notifications.append(params)
            self.last_progress[token] = params

            # Display progress bar
            if total and total > 0:
                percent = (progress / total) * 100
                bar_length = 40
                filled = int(bar_length * progress / total)
                bar = "█" * filled + "░" * (bar_length - filled)
                print(f"    📊 [{bar}] {percent:.1f}% | {message}")
            else:
                print(f"    📊 Progress: {progress} | {message}")

            return True
        return False


def send_and_receive(
    process,
    msg,
    expected_id=None,
    progress_tracker: Optional[ProgressTracker] = None,
    timeout=30,
):
    """Send message and get response, handling progress notifications."""
    process.stdin.write(json.dumps(msg) + "\n")
    process.stdin.flush()

    if expected_id is None:  # Just a notification
        time.sleep(0.5)
        return {"success": True}

    start_time = time.time()
    response = None

    while time.time() - start_time < timeout:
        ready, _, _ = select.select([process.stdout], [], [], 0.1)
        if ready:
            response_line = process.stdout.readline()
            if response_line:
                try:
                    msg_obj = json.loads(response_line)

                    # Check if it's a progress notification
                    if progress_tracker and msg_obj.get("method") == "notifications/progress":
                        progress_tracker.handle_notification(msg_obj)
                        continue

                    # Check if it's our response
                    if msg_obj.get("id") == expected_id:
                        response = msg_obj
                        break

                except json.JSONDecodeError:
                    continue

        if process.poll() is not None:
            return {"error": "Server died"}

    # After getting response, wait a bit for any trailing progress notifications
    if response and progress_tracker:
        time.sleep(0.5)
        while True:
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if not ready:
                break
            response_line = process.stdout.readline()
            if response_line:
                try:
                    msg_obj = json.loads(response_line)
                    if msg_obj.get("method") == "notifications/progress":
                        progress_tracker.handle_notification(msg_obj)
                except json.JSONDecodeError:
                    pass

    return response or {"error": "timeout"}


def main():
    """Run artifacts progress demo."""
    print("=" * 70)
    print("🚀 ARTIFACTS PROGRESS REPORTING DEMO")
    print("=" * 70)
    print()
    print("Demonstrates real-time progress tracking for artifact operations.")
    print()

    # Create temp config
    temp_dir = Path(tempfile.mkdtemp(prefix="artifacts_progress_"))
    config_file = temp_dir / "config.yaml"

    config_content = """
server:
  type: stdio

logging:
  level: ERROR

artifacts:
  enabled: true
  storage_provider: memory
  session_provider: memory

  tools:
    write_file: {enabled: true}
    upload_file: {enabled: true}
    list_session_files: {enabled: true}
"""
    config_file.write_text(config_content)

    env = os.environ.copy()
    env["ARTIFACT_PROVIDER"] = "vfs-memory"
    env["SESSION_PROVIDER"] = "memory"
    env["CHUK_MCP_LOG_LEVEL"] = "ERROR"

    print(f"📝 Config created at {config_file}")
    print()

    try:
        # Start server
        print("🚀 Starting MCP server...")
        process = subprocess.Popen(
            ["chuk-mcp-server", "--config", str(config_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
            env=env,
        )

        time.sleep(2)

        if process.poll() is not None:
            stderr = process.stderr.read()
            print(f"❌ Server failed: {stderr}")
            return

        print("✅ Server started")
        print()

        # Initialize
        print("🤝 Initializing MCP connection...")
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"experimental": {}},
                    "clientInfo": {"name": "artifacts-progress-demo", "version": "1.0"},
                },
            },
            1,
        )

        if "result" not in response:
            print(f"❌ Initialize failed: {response}")
            return

        print("✅ Initialized")

        # Send initialized notification
        send_and_receive(
            process,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        print("✅ Ready for tool calls")
        print()

        # Test 1: Write file with progress
        print("1️⃣  TEST: Write File with Progress Tracking")
        print("-" * 70)
        print("    Creating config.yaml (3-step progress)...")
        tracker = ProgressTracker()
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "write_file",
                    "arguments": {
                        "filename": "config.yaml",
                        "content": "# Configuration\napi_key: test123\nendpoint: https://api.example.com\nretries: 3",
                        "mime": "text/yaml",
                        "summary": "Configuration file",
                    },
                    "_meta": {"progressToken": "write-progress"},
                },
            },
            2,
            progress_tracker=tracker,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            print(f"    ✅ Result: {result_text}")
            print(f"    ✅ Received {len(tracker.notifications)} progress updates")
        else:
            print(f"    ❌ Failed: {response.get('error', 'Unknown error')}")
        print()

        # Test 2: Upload binary file with progress
        print("2️⃣  TEST: Upload Binary File with Progress Tracking")
        print("-" * 70)
        test_data = b"Binary test data " * 1000
        encoded_data = base64.b64encode(test_data).decode()
        print(f"    Uploading test_data.bin ({len(test_data):,} bytes, 4-step progress)...")

        tracker = ProgressTracker()
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "upload_file",
                    "arguments": {
                        "filename": "test_data.bin",
                        "content": encoded_data,
                        "mime": "application/octet-stream",
                        "summary": "Test binary file",
                    },
                    "_meta": {"progressToken": "upload-progress"},
                },
            },
            3,
            progress_tracker=tracker,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            print(f"    ✅ Result: {result_text}")
            print(f"    ✅ Received {len(tracker.notifications)} progress updates")
        else:
            print(f"    ❌ Failed: {response.get('error', 'Unknown error')}")
        print()

        # Test 3: Multiple files with progress
        print("3️⃣  TEST: Multiple File Operations with Progress")
        print("-" * 70)

        files_to_create = [
            {
                "filename": "readme.md",
                "content": "# Project README\n\nWelcome!",
                "mime": "text/markdown",
            },
            {
                "filename": "package.json",
                "content": '{"name": "test", "version": "1.0.0"}',
                "mime": "application/json",
            },
            {
                "filename": "main.py",
                "content": "def main():\n    print('Hello')",
                "mime": "text/x-python",
            },
        ]

        for i, file_data in enumerate(files_to_create, start=1):
            print(f"    Creating {i}/{len(files_to_create)}: {file_data['filename']}")
            tracker = ProgressTracker()
            response = send_and_receive(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 10 + i,
                    "method": "tools/call",
                    "params": {
                        "name": "write_file",
                        "arguments": {
                            "filename": file_data["filename"],
                            "content": file_data["content"],
                            "mime": file_data["mime"],
                            "summary": f"Created {file_data['filename']}",
                        },
                        "_meta": {"progressToken": f"write-{i}"},
                    },
                },
                10 + i,
                progress_tracker=tracker,
            )

            if "result" in response:
                print(f"    ✅ Created with {len(tracker.notifications)} progress updates")
            else:
                print(f"    ❌ Failed: {response.get('error', 'Unknown error')}")
        print()

        # Test 4: Call without progress token
        print("4️⃣  TEST: Write File Without Progress Token")
        print("-" * 70)
        print("    (Should complete without progress notifications)")
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "write_file",
                    "arguments": {
                        "filename": "silent.txt",
                        "content": "No progress shown",
                        "summary": "Silent file",
                    },
                },
            },
            20,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            print(f"    ✅ Result: {result_text} (no progress shown)")
        else:
            print(f"    ❌ Failed: {response.get('error', 'Unknown error')}")
        print()

        # List all files
        print("5️⃣  VERIFY: List All Created Files")
        print("-" * 70)
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {"name": "list_session_files", "arguments": {}},
            },
            30,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            try:
                files = json.loads(result_text)
                if isinstance(files, list):
                    print(f"    📁 Total files created: {len(files)}")
                    for f in files:
                        print(f"       • {f['filename']} ({f.get('bytes', 0):,} bytes)")
            except json.JSONDecodeError:
                print(f"    {result_text}")
        print()

        # Summary
        print("=" * 70)
        print("✅ ARTIFACTS PROGRESS DEMO COMPLETE")
        print("=" * 70)
        print()
        print("Summary:")
        print("  • upload_file reports 4-step progress:")
        print("    1. Decoding base64")
        print("    2. Preparing upload (with size)")
        print("    3. Uploading to storage")
        print("    4. Complete (with artifact ID)")
        print()
        print("  • write_file reports 3-step progress:")
        print("    1. Preparing to write")
        print("    2. Writing to storage")
        print("    3. Complete (with artifact ID)")
        print()
        print("  • Progress notifications work over MCP protocol")
        print("  • Tools receive progressToken via _meta parameter")
        print("  • Tools work normally without progressToken")
        print()
        print("💡 Implementation:")
        print("  • See src/chuk_mcp_runtime/tools/artifacts_tools.py")
        print("  • Uses send_progress() from request_context")
        print("  • Gracefully handles missing progress token")
        print()

    finally:
        print("🧹 Cleaning up...")
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)

        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print("✅ Cleanup complete")


if __name__ == "__main__":
    main()
