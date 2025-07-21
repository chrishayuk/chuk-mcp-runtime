#!/usr/bin/env python3
"""
examples/mcp_debug.py

Debug script to check what's happening with the MCP server.
"""

import subprocess
import tempfile
import time
import os
from pathlib import Path


def debug_server():
    """Run the server with debug output and check its status."""
    print("🔍 MCP Server Debug")
    print("=" * 40)

    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="mcp_debug_"))
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    print(f"📁 Temp directory: {temp_dir}")

    # Set up environment with more logging
    env = os.environ.copy()
    env.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": str(artifacts_dir),
            "ARTIFACT_BUCKET": "debug-test",
            "CHUK_MCP_LOG_LEVEL": "DEBUG",  # More verbose logging
        }
    )

    # Start server
    cmd = ["uv", "run", "chuk-mcp-runtime"]
    print(f"🚀 Starting server: {' '.join(cmd)}")
    print("📝 Server output:")

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            env=env,
            text=True,
            bufsize=0,
        )

        # Read initial output for a few seconds
        import select

        start_time = time.time()
        output_lines = []

        while time.time() - start_time < 5:  # Read for 5 seconds
            if hasattr(select, "select"):
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        print(f"   {line.rstrip()}")
                        output_lines.append(line)
                    else:
                        break
            else:
                # Fallback for Windows
                try:
                    line = process.stdout.readline()
                    if line:
                        print(f"   {line.rstrip()}")
                        output_lines.append(line)
                    time.sleep(0.1)
                except:
                    break

            if process.poll() is not None:
                break

        print(f"\n📊 Server status after 5 seconds:")
        if process.poll() is None:
            print("✅ Server is still running")
        else:
            print(f"❌ Server exited with code: {process.returncode}")

        # Look for key indicators in the output
        output_text = "".join(output_lines)

        if "Starting stdio server" in output_text:
            print("✅ Server reached stdio startup")
        else:
            print("❌ Server did not reach stdio startup")

        if "tools registered successfully" in output_text:
            print("✅ Tools were registered")
        else:
            print("❌ Tools were not registered")

        if "Tools available in registry:" in output_text:
            import re

            match = re.search(r"Tools available in registry: (\d+) total", output_text)
            if match:
                count = match.group(1)
                print(f"✅ Found {count} tools in registry")
            else:
                print("❌ Could not parse tool count")

        # Try to send a simple message
        if process.poll() is None:
            print("\n🧪 Testing basic communication...")
            init_msg = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"debug","version":"1.0"}}}\n'

            try:
                process.stdin.write(init_msg)
                process.stdin.flush()
                print("✅ Sent initialization message")

                # Try to read response with timeout
                if hasattr(select, "select"):
                    ready, _, _ = select.select([process.stdout], [], [], 5)
                    if ready:
                        response = process.stdout.readline()
                        print(f"✅ Got response: {response.strip()}")
                    else:
                        print("❌ No response within 5 seconds")

            except Exception as e:
                print(f"❌ Communication failed: {e}")

        return process

    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

    finally:
        if "process" in locals() and process and process.poll() is None:
            print("\n🛑 Terminating server...")
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    debug_server()
