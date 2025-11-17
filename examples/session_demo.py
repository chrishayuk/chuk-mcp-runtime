#!/usr/bin/env python3
"""
Session Management Demo

Demonstrates MCP session ID management:
- How sessions are created automatically on first write
- Capturing session IDs from server responses
- Session context is managed server-side (not passed as parameters)

This demo shows practical session ID handling:
1. Creates a file (server auto-creates session)
2. Captures the session_id from the response
3. Creates more files (all in same session context)
4. Lists files (server automatically uses session from context)

Note: Session IDs are managed server-side via request context.
Tools do not accept session_id as a parameter.

Run:
    uv run python examples/session_demo.py
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def load_env_file(env_file=".env"):
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / env_file
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value and key not in os.environ:
                        os.environ[key] = value


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


def extract_session_id(response):
    """Extract session_id from write_file response."""
    if "result" in response:
        result = response["result"]
        if "content" in result and len(result["content"]) > 0:
            text = result["content"][0].get("text", "")
            try:
                inner = json.loads(text)
                return inner.get("session_id")
            except json.JSONDecodeError:
                pass
    return None


def main():
    """Run session management demo."""
    load_env_file()

    print("=" * 80)
    print("Session Management Demo")
    print("=" * 80)
    print()
    print("This demo shows how to manage sessions for file isolation.")
    print()

    # Create temp config
    temp_dir = Path(tempfile.mkdtemp(prefix="session_demo_"))
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
    list_session_files: {enabled: true}
"""
    config_file.write_text(config_content)

    try:
        # Start server
        print("🚀 Starting MCP server...")
        env = os.environ.copy()
        env["ARTIFACT_STORAGE_PROVIDER"] = "memory"
        env["ARTIFACT_SESSION_PROVIDER"] = "memory"

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
                "clientInfo": {"name": "session-demo", "version": "1.0.0"},
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

        request_id = 2
        session_id = None

        # Step 1: Create first file without session_id (auto-creates session)
        print("=" * 80)
        print("Step 1: Creating First File (Auto-Create Session)")
        print("=" * 80)
        print()
        print("When you don't provide a session_id, the server automatically creates one.")
        print()

        write_msg = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "filename": "app.py",
                    "content": "# Main application file\nprint('Hello, World!')",
                    "mime": "text/plain",
                },
            },
        }

        response = send_and_receive(process, write_msg, expected_id=request_id)
        request_id += 1

        if "result" in response:
            session_id = extract_session_id(response)
            print("✅ Created app.py")
            print(f"📋 Session ID: {session_id}")
        else:
            print(f"❌ Failed: {response.get('error')}")
            return

        print()

        # Step 2: Add more files to the same session
        print("=" * 80)
        print("Step 2: Adding Files to the Same Session")
        print("=" * 80)
        print()
        print(f"Now we'll add more files (server maintains session: {session_id})")
        print("Note: Session context is managed server-side, not passed as parameters")
        print()

        additional_files = [
            {
                "filename": "config.json",
                "content": '{"debug": true, "port": 8080}',
                "mime": "application/json",
            },
            {
                "filename": "README.md",
                "content": "# My Project\nA demo project.",
                "mime": "text/markdown",
            },
            {
                "filename": "requirements.txt",
                "content": "httpx>=0.24.0\nfastapi>=0.100.0",
                "mime": "text/plain",
            },
        ]

        for file_data in additional_files:
            # Note: session_id is managed by the server context, not passed as parameter
            write_msg = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": "write_file", "arguments": file_data},
            }

            response = send_and_receive(process, write_msg, expected_id=request_id)
            request_id += 1

            if "result" in response:
                print(f"✅ Created {file_data['filename']}")
            else:
                print(f"❌ Failed to create {file_data['filename']}")

        print()

        # Step 3: List files in the session
        print("=" * 80)
        print("Step 3: Listing Files in the Session")
        print("=" * 80)
        print()
        print(f"Querying session {session_id} for all files...")
        print()

        # Note: list_session_files gets session from context, no parameters needed
        list_msg = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": "list_session_files", "arguments": {}},
        }

        response = send_and_receive(process, list_msg, expected_id=request_id)
        request_id += 1

        if "result" in response:
            result_content = response["result"].get("content", [])
            for content_item in result_content:
                if content_item.get("type") == "text":
                    try:
                        files = json.loads(content_item["text"])
                        if isinstance(files, list):
                            print(f"📁 Found {len(files)} files:")
                            for f in files:
                                print(f"   • {f['filename']}")
                                print(f"     Type: {f.get('mime', 'unknown')}")
                                print(f"     Size: {f.get('bytes', 0)} bytes")
                                print()
                        else:
                            print(content_item["text"])
                    except json.JSONDecodeError:
                        print(content_item["text"])
        else:
            print(f"❌ Failed: {response.get('error')}")

        # Summary
        print("=" * 80)
        print("Demo Complete!")
        print("=" * 80)
        print()
        print("✅ What we demonstrated:")
        print("   • Automatic session creation on first write_file")
        print("   • Capturing session_id from the server response")
        print("   • Server-side session context management")
        print("   • Listing all files in the current session")
        print()
        print("💡 Session ID management (server-side context):")
        print("   • Sessions are created automatically on first operation")
        print("   • Session context is maintained server-side per connection")
        print("   • Tools do NOT accept session_id as a parameter")
        print("   • Session IDs can be tracked in responses for reference")
        print("   • All operations within a connection use the same session")
        print()
        print("📝 Note:")
        print("   Session isolation behavior depends on your storage and session")
        print("   provider configuration. With memory providers, files may be")
        print("   visible across sessions within the same server instance.")
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
