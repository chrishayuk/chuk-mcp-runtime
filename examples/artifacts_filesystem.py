#!/usr/bin/env python3
"""
Artifacts Demo - Filesystem Storage Provider

Demonstrates artifacts functionality with filesystem storage.
Files are persisted to disk for durability and inspection.

Features:
- write_file: Create files stored on disk
- list_session_files: List all files in current session
- Persistent storage - files survive server restarts
- Easy inspection - files visible in filesystem

Run:
    uv run python examples/artifacts_filesystem.py
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def send_and_receive(process, msg, expected_id=None, timeout=10):
    """Send message and get response."""
    process.stdin.write(json.dumps(msg) + "\n")
    process.stdin.flush()

    if expected_id is None:
        time.sleep(0.1)
        return {"success": True}

    start_time = time.time()
    while time.time() - start_time < timeout:
        if process.stdout.readable():
            response_line = process.stdout.readline()
            if response_line:
                try:
                    msg_obj = json.loads(response_line)
                    if msg_obj.get("id") == expected_id:
                        return msg_obj
                except json.JSONDecodeError:
                    continue
        if process.poll() is not None:
            return {"error": "Server died"}
        time.sleep(0.1)
    return {"error": "timeout"}


def main():
    """Run artifacts demo with filesystem provider."""
    print("=" * 80)
    print("Artifacts Demo - Filesystem Storage Provider")
    print("=" * 80)
    print()

    # Create temp directories
    temp_dir = Path(tempfile.mkdtemp(prefix="artifacts_fs_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    config_file = temp_dir / "config.yaml"

    config_content = """
server:
  type: stdio

logging:
  level: INFO

artifacts:
  enabled: true
  storage_provider: filesystem
  session_provider: memory

  tools:
    write_file: {enabled: true}
    upload_file: {enabled: true}
    list_session_files: {enabled: true}
"""
    config_file.write_text(config_content)

    print(f"📁 Config: {config_file}")
    print(f"📁 Storage: {artifacts_dir}")
    print()

    try:
        # Start server
        print("🚀 Starting MCP server...")
        env = os.environ.copy()
        env["ARTIFACT_SESSION_PROVIDER"] = "memory"
        env["ARTIFACT_STORAGE_PROVIDER"] = "filesystem"
        env["ARTIFACT_FS_ROOT"] = str(artifacts_dir)

        process = subprocess.Popen(
            ["chuk-mcp-server", "--config", str(config_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        time.sleep(1)

        if process.poll() is not None:
            stderr = process.stderr.read()
            print(f"❌ Server failed: {stderr}")
            return

        print("✅ Server started")
        print()

        # Initialize
        print("🔌 Initializing MCP connection...")
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "artifacts-fs-demo", "version": "1.0.0"},
            },
        }

        response = send_and_receive(process, init_msg, expected_id=1)
        if "error" in response:
            print(f"❌ Initialize failed: {response['error']}")
            return

        print("✅ Initialized")
        print()

        # Send initialized notification
        initialized_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        send_and_receive(process, initialized_msg)

        # Create files
        print("=" * 80)
        print("Creating Files")
        print("=" * 80)
        print()

        files_to_create = [
            {
                "filename": "deployment.yaml",
                "content": "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: my-app",
                "mime": "text/yaml",
                "summary": "Kubernetes deployment",
            },
            {
                "filename": "data.json",
                "content": '{"users": 150, "sessions": 1200, "revenue": 45000}',
                "mime": "application/json",
                "summary": "Analytics data",
            },
            {
                "filename": "report.md",
                "content": "# Q4 Report\n\n## Highlights\n- Revenue up 25%\n- New users: 1500",
                "mime": "text/markdown",
                "summary": "Quarterly report",
            },
        ]

        session_id = None
        for i, file_data in enumerate(files_to_create, start=2):
            # Add session_id to subsequent requests
            if session_id:
                file_data["session_id"] = session_id

            print(f"📝 Creating {file_data['filename']}...")
            write_msg = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/call",
                "params": {"name": "write_file", "arguments": file_data},
            }

            response = send_and_receive(process, write_msg, expected_id=i)
            if "result" in response:
                result = response["result"]
                if "content" in result and len(result["content"]) > 0:
                    text = result["content"][0].get("text", "")
                    # Parse the inner JSON to get session_id
                    import json
                    try:
                        inner = json.loads(text)
                        # Capture session_id from first response
                        if not session_id:
                            session_id = inner.get("session_id")
                            print(f"   ✅ Created (session: {session_id})")
                        else:
                            print(f"   ✅ Created")
                    except json.JSONDecodeError:
                        print(f"   ✅ Created")
                else:
                    print(f"   ✅ Created")
            else:
                print(f"   ❌ Failed: {response.get('error')}")
            print()

        # List files
        print("=" * 80)
        print("Listing Session Files")
        print("=" * 80)
        print()

        list_msg = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "list_session_files", "arguments": {"session_id": session_id}},
        }

        response = send_and_receive(process, list_msg, expected_id=10)
        if "result" in response:
            print("📋 Files in session:")
            result_content = response["result"].get("content", [])
            for content_item in result_content:
                if content_item.get("type") == "text":
                    try:
                        files = json.loads(content_item["text"])
                        if isinstance(files, list):
                            for f in files:
                                print(f"  • {f['filename']}")
                                print(f"    Type: {f.get('mime', 'unknown')}")
                                print(f"    Size: {f.get('bytes', 0)} bytes")
                                print(f"    Summary: {f.get('summary', 'N/A')}")
                                print()
                        else:
                            print(content_item["text"])
                    except json.JSONDecodeError:
                        print(content_item["text"])
        else:
            print(f"❌ Failed: {response.get('error')}")
        print()

        # Show filesystem contents
        print("=" * 80)
        print("Filesystem Contents")
        print("=" * 80)
        print()
        print(f"📁 Directory: {artifacts_dir}")
        print()

        # List actual files
        if artifacts_dir.exists():
            all_files = list(artifacts_dir.rglob("*"))
            file_count = len([f for f in all_files if f.is_file()])
            print(f"Found {file_count} files on disk")
            for file_path in sorted(all_files):
                if file_path.is_file():
                    relative = file_path.relative_to(artifacts_dir)
                    size = file_path.stat().st_size
                    print(f"  • {relative} ({size} bytes)")
        print()

        # Summary
        print("=" * 80)
        print("Demo Complete!")
        print("=" * 80)
        print()
        print("✅ Filesystem storage provider features:")
        print("   • Persistent - files survive server restarts")
        print("   • Inspectable - files visible in filesystem")
        print("   • No external dependencies")
        print("   • Local development and single-server deployments")
        print()
        print(f"💡 Tip: Check {artifacts_dir} to see the stored files")
        print()

    finally:
        print("🧹 Cleaning up...")
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)

        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print("✅ Cleanup complete")


if __name__ == "__main__":
    main()
