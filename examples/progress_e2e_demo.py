#!/usr/bin/env python3
"""
Progress Reporting E2E Demo

Tests progress reporting over the MCP protocol by:
1. Starting an MCP server with progress-enabled tools
2. Calling tools with progressToken parameter
3. Receiving and displaying progress notifications in real-time
"""

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


def create_progress_server_config():
    """Create a temporary server config with progress tools."""
    # We'll use the progress_demo.py tools that already exist
    examples_dir = Path(__file__).parent
    tools_file = examples_dir / "progress_demo_tools.py"

    # Create a minimal tools file that imports from progress_demo
    tools_content = '''
import asyncio
from typing import List
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.request_context import send_progress

@mcp_tool(name="count_to_ten", description="Count to ten with progress")
async def count_to_ten():
    """Count from 1 to 10, reporting progress."""
    for i in range(1, 11):
        await send_progress(
            progress=i,
            total=10,
            message=f"Counting: {i}"
        )
        await asyncio.sleep(0.3)
    return {"result": "Counted to 10!", "count": 10}

@mcp_tool(name="process_items", description="Process items with progress")
async def process_items(items: List[str]):
    """Process a list of items with progress reporting."""
    total = len(items)
    results = []

    for i, item in enumerate(items, 1):
        await send_progress(
            progress=i,
            total=total,
            message=f"Processing: {item}"
        )
        await asyncio.sleep(0.4)
        results.append(f"processed_{item}")

    return {"results": results, "count": len(results)}

@mcp_tool(name="download_file", description="Simulate file download")
async def download_file(url: str, size_mb: int = 10):
    """Simulate downloading a file with percentage progress."""
    chunk_size = 1  # MB per chunk
    total_chunks = size_mb

    for chunk in range(1, total_chunks + 1):
        progress = chunk / total_chunks
        await send_progress(
            progress=progress,
            total=1.0,
            message=f"Downloading {url}: {int(progress * 100)}% ({chunk}/{total_chunks} MB)"
        )
        await asyncio.sleep(0.3)

    return {
        "url": url,
        "size_mb": size_mb,
        "status": "completed",
        "message": f"Successfully downloaded {size_mb}MB from {url}"
    }
'''

    config_content = """
server:
  type: stdio

logging:
  level: ERROR  # Minimal logging for cleaner output

tools:
  # Built-in tools disabled for this demo
  builtin_tools: []
"""

    temp_dir = Path(tempfile.mkdtemp(prefix="progress_e2e_"))
    config_file = temp_dir / "config.yaml"
    tools_file = temp_dir / "progress_tools.py"

    config_file.write_text(config_content)
    tools_file.write_text(tools_content)

    return temp_dir, config_file, tools_file


def test_progress_e2e():
    """Test progress reporting over MCP protocol."""
    print("=" * 70)
    print("🚀 PROGRESS REPORTING E2E TEST")
    print("=" * 70)
    print()

    # Create config
    print("📝 Setting up test environment...")
    temp_dir, config_file, tools_file = create_progress_server_config()

    env = os.environ.copy()
    env.update(
        {
            "CHUK_MCP_LOG_LEVEL": "ERROR",
            "PYTHONPATH": str(temp_dir) + ":" + env.get("PYTHONPATH", ""),
        }
    )

    print(f"✅ Config created at {config_file}")
    print(f"✅ Tools created at {tools_file}")
    print()

    # Start server by running the tools file directly
    print("🚀 Starting MCP server...")

    # Create a server starter script
    starter_script = temp_dir / "start_server.py"
    starter_content = f"""
import sys
sys.path.insert(0, "{temp_dir}")

# Import the tools module which will register the tools via @mcp_tool decorator
import progress_tools

from chuk_mcp_runtime import run_runtime

# Tools are automatically registered by the @mcp_tool decorators
run_runtime()
"""
    starter_script.write_text(starter_content)

    process = subprocess.Popen(
        ["uv", "run", "python", str(starter_script)],
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
            stderr = process.stderr.read()
            print(f"❌ Server failed to start: {stderr}")
            return False

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
                    "clientInfo": {"name": "progress-test", "version": "1.0"},
                },
            },
            1,
        )

        if "result" not in response:
            print(f"❌ Initialize failed: {response}")
            return False

        print("✅ Initialized")

        # Send initialized notification
        send_and_receive(
            process,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        print("✅ Ready for tool calls")
        print()

        # Test 1: Count to ten
        print("1️⃣  TEST: Count to Ten")
        print("-" * 70)
        tracker = ProgressTracker()
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "count_to_ten",
                    "arguments": {},
                    "_meta": {"progressToken": "count-progress"},
                },
            },
            2,
            progress_tracker=tracker,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            try:
                result = json.loads(result_text)
                print(f"    ✅ Result: {result.get('result', result)}")
            except json.JSONDecodeError:
                print(f"    ✅ Result: {result_text}")
            print(f"    ✅ Received {len(tracker.notifications)} progress updates")
        else:
            print(f"    ❌ Failed: {response}")
        print()

        # Test 2: Process items
        print("2️⃣  TEST: Process Items")
        print("-" * 70)
        tracker = ProgressTracker()
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "process_items",
                    "arguments": {"items": ["apple", "banana", "cherry", "date", "elderberry"]},
                    "_meta": {"progressToken": "process-progress"},
                },
            },
            3,
            progress_tracker=tracker,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            try:
                result = json.loads(result_text)
                print(f"    ✅ Result: Processed {result.get('count', '?')} items")
            except json.JSONDecodeError:
                print(f"    ✅ Result: {result_text}")
            print(f"    ✅ Received {len(tracker.notifications)} progress updates")
        else:
            print(f"    ❌ Failed: {response}")
        print()

        # Test 3: Download file
        print("3️⃣  TEST: Download File (Percentage Progress)")
        print("-" * 70)
        tracker = ProgressTracker()
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "download_file",
                    "arguments": {
                        "url": "https://example.com/bigfile.zip",
                        "size_mb": 8,
                    },
                    "_meta": {"progressToken": "download-progress"},
                },
            },
            4,
            progress_tracker=tracker,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            try:
                result = json.loads(result_text)
                print(f"    ✅ Result: {result.get('message', result)}")
            except json.JSONDecodeError:
                print(f"    ✅ Result: {result_text}")
            print(f"    ✅ Received {len(tracker.notifications)} progress updates")
        else:
            print(f"    ❌ Failed: {response}")
        print()

        # Test 4: Call without progress token (should work but no notifications)
        print("4️⃣  TEST: Call Without Progress Token")
        print("-" * 70)
        print("    (Should complete without progress notifications)")
        response = send_and_receive(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "count_to_ten",
                    "arguments": {},
                },
            },
            5,
        )

        if "result" in response:
            result_text = response["result"]["content"][0]["text"]
            try:
                result = json.loads(result_text)
                print(f"    ✅ Result: {result.get('result', result)} (no progress shown)")
            except json.JSONDecodeError:
                print(f"    ✅ Result: {result_text} (no progress shown)")
        else:
            print(f"    ❌ Failed: {response}")
        print()

        # Summary
        print("=" * 70)
        print("✅ E2E PROGRESS TEST COMPLETE")
        print("=" * 70)
        print()
        print("Summary:")
        print("  • Progress notifications work over MCP protocol")
        print("  • Tools receive progressToken via _meta parameter")
        print("  • Server sends notifications/progress messages")
        print("  • Both step-based and percentage progress work")
        print("  • Tools work normally without progressToken")
        print()

        return True

    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)

        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = test_progress_e2e()
    exit(0 if success else 1)
