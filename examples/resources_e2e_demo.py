#!/usr/bin/env python3
"""
MCP Resources E2E Demo

Demonstrates MCP resources integration by:
1. Starting an MCP server with custom resources and artifacts enabled
2. Listing resources via resources/list
3. Reading resource content via resources/read
4. Showing both custom resources (@mcp_resource) and artifact resources

Run:
    uv run python examples/resources_e2e_demo.py
"""

import json
import os
import select
import subprocess
import tempfile
import time
from pathlib import Path


def send_and_receive(process, msg, expected_id=None, timeout=10):
    """Send message and get response."""
    process.stdin.write(json.dumps(msg) + "\n")
    process.stdin.flush()

    if expected_id is None:  # Just a notification
        time.sleep(0.1)
        return {"success": True}

    start_time = time.time()

    while time.time() - start_time < timeout:
        ready, _, _ = select.select([process.stdout], [], [], 0.1)
        if ready:
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

    return {"error": "timeout"}


def create_resources_server_config():
    """Create a temporary server config with custom resources and artifacts."""

    # Custom resources definition
    resources_content = '''
"""Custom resources for demo."""
import json
import os
from datetime import datetime
from chuk_mcp_runtime.common.mcp_resource_decorator import mcp_resource


@mcp_resource(
    uri="config://database",
    name="Database Configuration",
    description="Database connection settings",
    mime_type="application/json",
)
async def get_database_config():
    """Return database configuration."""
    config = {
        "host": "localhost",
        "port": 5432,
        "database": "demo_db",
        "pool_size": 10,
    }
    return json.dumps(config, indent=2)


@mcp_resource(
    uri="config://app/settings",
    name="Application Settings",
    description="Application configuration",
    mime_type="application/json",
)
def get_app_settings():
    """Return app settings (sync function)."""
    settings = {
        "app_name": "MCP Resources Demo",
        "version": "1.0.0",
        "features": {
            "dark_mode": True,
            "notifications": True,
        },
    }
    return json.dumps(settings, indent=2)


@mcp_resource(
    uri="system://info",
    name="System Information",
    description="Current system status",
    mime_type="text/plain",
)
async def get_system_info():
    """Return system information."""
    info = f"""System Information
==================
Platform: {os.uname().sysname}
Node: {os.uname().nodename}
User: {os.getenv('USER', 'unknown')}
PID: {os.getpid()}
Timestamp: {datetime.now().isoformat()}
"""
    return info


@mcp_resource(
    uri="docs://api/overview",
    name="API Documentation",
    description="API endpoints guide",
    mime_type="text/markdown",
)
def get_api_docs():
    """Return API documentation."""
    return """# API Documentation

## Authentication
All requests require Bearer token:
```
Authorization: Bearer YOUR_TOKEN
```

## Endpoints
- GET /api/users - List users
- POST /api/users - Create user
- GET /api/users/{id} - Get user by ID

## Rate Limiting
1000 requests per hour per API key
"""
'''

    config_content = """
server:
  type: stdio

logging:
  level: ERROR  # Minimal logging for cleaner output

# Enable artifacts with memory session provider
artifacts:
  enabled: true
  storage_provider: filesystem
  session_provider: memory

  tools:
    write_file: {enabled: true}
    upload_file: {enabled: true}
    list_session_files: {enabled: true}

tools:
  # Import custom resources module to register them
  modules_to_import:
    - custom_resources
"""

    # Create sitecustomize.py to auto-import custom resources
    # Python automatically imports sitecustomize.py if it's on sys.path
    sitecustomize_content = """
# Auto-imported by Python on startup
import custom_resources
"""

    temp_dir = Path(tempfile.mkdtemp(prefix="resources_e2e_"))
    config_file = temp_dir / "config.yaml"
    resources_file = temp_dir / "custom_resources.py"
    sitecustomize_file = temp_dir / "sitecustomize.py"

    config_file.write_text(config_content)
    resources_file.write_text(resources_content)
    sitecustomize_file.write_text(sitecustomize_content)

    return temp_dir, config_file, resources_file


def main():
    """Run the resources E2E demo."""

    print("=" * 80)
    print("MCP Resources E2E Demo")
    print("=" * 80)
    print()

    # Create server config and resources
    temp_dir, config_file, resources_file = create_resources_server_config()

    print(f"📁 Created temp config in: {temp_dir}")
    print()

    try:
        # Start MCP server
        print("🚀 Starting MCP server with resources...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(temp_dir)

        process = subprocess.Popen(
            ["chuk-mcp-server", "--config", str(config_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        # Give server time to start
        time.sleep(1)

        if process.poll() is not None:
            stderr = process.stderr.read()
            print(f"❌ Server failed to start: {stderr}")
            return

        print("✅ Server started")
        print()

        # ================================================================
        # Part 1: Initialize
        # ================================================================
        print("=" * 80)
        print("Part 1: Initialize MCP Connection")
        print("=" * 80)
        print()

        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "resources-demo-client", "version": "1.0.0"},
            },
        }

        response = send_and_receive(process, init_msg, expected_id=1)
        if "error" in response:
            print(f"❌ Initialize failed: {response['error']}")
            return

        print("✅ MCP connection initialized")
        print()

        # Send initialized notification
        initialized_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        send_and_receive(process, initialized_msg)

        # ================================================================
        # Part 2: Create Some Artifact Resources (via tools)
        # ================================================================
        print("=" * 80)
        print("Part 2: Creating Artifact Resources via Tools")
        print("=" * 80)
        print()

        # Create a text file
        print("📝 Creating report.md via write_file tool...")
        write_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "filename": "report.md",
                    "content": "# Monthly Report\n\nSales increased by 20%",
                    "mime": "text/markdown",
                    "summary": "Monthly sales report",
                },
            },
        }

        response = send_and_receive(process, write_msg, expected_id=2)
        session_id = None
        if "result" in response:
            # Extract session_id from response
            result = response["result"]
            if "content" in result and len(result["content"]) > 0:
                text = result["content"][0].get("text", "")
                try:
                    inner = json.loads(text)
                    session_id = inner.get("session_id")
                    print(f"   ✅ Created (session: {session_id})")
                except json.JSONDecodeError:
                    print(f"   ✅ {response['result']}")
            else:
                print(f"   ✅ {response['result']}")
        else:
            print(f"   ❌ Failed: {response.get('error')}")
        print()

        # Create a JSON file
        print("📊 Creating data.json via write_file tool...")
        data_arguments = {
            "filename": "data.json",
            "content": '{"sales": [100, 120, 150]}',
            "mime": "application/json",
            "summary": "Sales data",
        }
        # Add session_id if we captured it
        if session_id:
            data_arguments["session_id"] = session_id

        write_msg2 = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": data_arguments,
            },
        }

        response = send_and_receive(process, write_msg2, expected_id=3)
        if "result" in response:
            result = response["result"]
            if "content" in result and len(result["content"]) > 0:
                text = result["content"][0].get("text", "")
                try:
                    inner = json.loads(text)
                    print("   ✅ Created")
                except json.JSONDecodeError:
                    print(f"   ✅ {response['result']}")
            else:
                print(f"   ✅ {response['result']}")
        else:
            print(f"   ❌ Failed: {response.get('error')}")
        print()

        # ================================================================
        # Part 3: List All Resources
        # ================================================================
        print("=" * 80)
        print("Part 3: Listing All Resources")
        print("=" * 80)
        print()

        print("📋 Calling resources/list...")
        list_msg = {"jsonrpc": "2.0", "id": 4, "method": "resources/list"}

        response = send_and_receive(process, list_msg, expected_id=4)
        if "result" in response:
            resources = response["result"].get("resources", [])
            print(f"Found {len(resources)} resources:")
            print()

            custom_count = 0
            artifact_count = 0

            for i, resource in enumerate(resources, 1):
                uri = resource["uri"]
                name = resource["name"]
                mime = resource.get("mimeType", "unknown")
                desc = resource.get("description", "")

                # Categorize
                if uri.startswith("artifact://"):
                    resource_type = "ARTIFACT"
                    artifact_count += 1
                else:
                    resource_type = "CUSTOM"
                    custom_count += 1

                print(f"{i}. [{resource_type}] {name}")
                print(f"   URI:         {uri}")
                print(f"   MIME Type:   {mime}")
                print(f"   Description: {desc}")
                print()

            print(f"Summary: {custom_count} custom resources, {artifact_count} artifact resources")
            print()

        else:
            print(f"❌ Failed: {response.get('error')}")
            print()

        # ================================================================
        # Part 4: Read Specific Resources
        # ================================================================
        print("=" * 80)
        print("Part 4: Reading Specific Resources")
        print("=" * 80)
        print()

        # Read a custom resource
        print("📖 Reading custom resource: config://database")
        print("-" * 60)
        read_msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "config://database"},
        }

        response = send_and_receive(process, read_msg, expected_id=5)
        if "result" in response:
            contents = response["result"]["contents"]
            if contents:
                content = contents[0]
                if "text" in content:
                    print(content["text"])
                elif "blob" in content:
                    print(f"Binary content: {len(content['blob'])} bytes (base64)")
        else:
            print(f"❌ Failed: {response.get('error')}")
        print()

        # Read another custom resource
        print("📖 Reading custom resource: system://info")
        print("-" * 60)
        read_msg2 = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {"uri": "system://info"},
        }

        response = send_and_receive(process, read_msg2, expected_id=6)
        if "result" in response:
            contents = response["result"]["contents"]
            if contents:
                content = contents[0]
                if "text" in content:
                    print(content["text"][:300])  # First 300 chars
                    print("...")
        else:
            print(f"❌ Failed: {response.get('error')}")
        print()

        # Read an artifact resource (if any were created)
        if artifact_count > 0:
            # Find first artifact resource URI
            artifact_uri = None
            for resource in resources:
                if resource["uri"].startswith("artifact://"):
                    artifact_uri = resource["uri"]
                    artifact_name = resource["name"]
                    break

            if artifact_uri:
                print(f"📖 Reading artifact resource: {artifact_name}")
                print(f"   URI: {artifact_uri}")
                print("-" * 60)
                read_msg3 = {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "resources/read",
                    "params": {"uri": artifact_uri},
                }

                response = send_and_receive(process, read_msg3, expected_id=7)
                if "result" in response:
                    contents = response["result"]["contents"]
                    if contents:
                        content = contents[0]
                        if "text" in content:
                            print(content["text"])
                        elif "blob" in content:
                            print(f"Binary content: {len(content['blob'])} bytes")
                else:
                    print(f"❌ Failed: {response.get('error')}")
                print()

        # ================================================================
        # Summary
        # ================================================================
        print("=" * 80)
        print("Demo Complete!")
        print("=" * 80)
        print()
        print("✅ Demonstrated:")
        print("   1. Custom resources (@mcp_resource decorator)")
        print("   2. Artifact resources (from write_file tool)")
        print("   3. resources/list - List all resources")
        print("   4. resources/read - Read resource content")
        print()
        print("📌 Key Points:")
        print("   • Custom resources: config://, system://, docs://")
        print("   • Artifact resources: artifact://{id}")
        print("   • Both accessible via MCP protocol")
        print("   • Session isolation for artifact resources")
        print("   • Text and binary content support")
        print()

    finally:
        # Cleanup
        print("🧹 Cleaning up...")
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)

        # Remove temp files
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print("✅ Cleanup complete")


if __name__ == "__main__":
    main()
