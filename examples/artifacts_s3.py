#!/usr/bin/env python3
"""
Artifacts Demo - AWS S3 Storage Provider

Demonstrates artifacts functionality with AWS S3 storage.
Files are stored in S3 for scalability and durability.

Features:
- write_file: Create files stored in S3
- list_session_files: List all files in current session
- Cloud-native - scales automatically
- Durable - 99.999999999% durability
- Multi-region support

Requirements:
- AWS credentials configured (via ~/.aws/credentials, .env file, or environment variables)
- S3 bucket created
- chuk-artifacts[s3] installed: pip install chuk-artifacts[s3]

Environment variables (can be set in .env file):
- ARTIFACT_BUCKET: S3 bucket name (required)
- AWS_ACCESS_KEY_ID: AWS access key
- AWS_SECRET_ACCESS_KEY: AWS secret key
- AWS_REGION or AWS_DEFAULT_REGION: AWS region (default: us-east-1)
- S3_ENDPOINT_URL or AWS_ENDPOINT_URL_S3: Custom S3 endpoint (optional)

Run:
    # Using .env file (recommended):
    uv run python examples/artifacts_s3.py

    # Or with environment variables:
    ARTIFACT_BUCKET=my-bucket uv run python examples/artifacts_s3.py
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


def main():
    """Run artifacts demo with S3 provider."""
    # Load environment from .env file
    load_env_file()

    print("=" * 80)
    print("Artifacts Demo - AWS S3 Storage Provider")
    print("=" * 80)
    print()

    # Check for S3 bucket
    bucket = os.getenv("ARTIFACT_BUCKET")
    if not bucket:
        print("❌ Error: ARTIFACT_BUCKET environment variable not set")
        print()
        print("Usage:")
        print("  1. Set in .env file: ARTIFACT_BUCKET=my-bucket")
        print(
            "  2. Or set via command: ARTIFACT_BUCKET=my-bucket uv run python examples/artifacts_s3.py"
        )
        print()
        return

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    endpoint = os.getenv("S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3")

    print(f"🪣 S3 Bucket: {bucket}")
    print(f"🌎 Region: {region}")
    if endpoint:
        print(f"🔗 Endpoint: {endpoint}")
    print()

    # Create temp config
    temp_dir = Path(tempfile.mkdtemp(prefix="artifacts_s3_"))
    config_file = temp_dir / "config.yaml"

    config_content = """
server:
  type: stdio

logging:
  level: ERROR

artifacts:
  enabled: true
  storage_provider: s3
  session_provider: memory

  tools:
    write_file: {enabled: true}
    upload_file: {enabled: true}
    list_session_files: {enabled: true}
"""
    config_file.write_text(config_content)

    print(f"📁 Config: {config_file}")
    print()

    try:
        # Start server
        print("🚀 Starting MCP server...")
        env = os.environ.copy()
        env["ARTIFACT_SESSION_PROVIDER"] = "memory"
        env["ARTIFACT_STORAGE_PROVIDER"] = "s3"
        env["ARTIFACT_BUCKET"] = bucket

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
            print()
            print("💡 Tip: Ensure you have:")
            print("   • AWS credentials configured")
            print("   • S3 bucket created")
            print("   • chuk-artifacts[s3] installed")
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
                "clientInfo": {"name": "artifacts-s3-demo", "version": "1.0.0"},
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
        print("Creating Files in S3")
        print("=" * 80)
        print()

        files_to_create = [
            {
                "filename": "cloudformation.yaml",
                "content": "AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  MyBucket:\n    Type: AWS::S3::Bucket",
                "mime": "text/yaml",
                "summary": "CloudFormation template",
            },
            {
                "filename": "metrics.json",
                "content": '{"requests": 50000, "errors": 12, "latency_p99": 150}',
                "mime": "application/json",
                "summary": "API metrics",
            },
            {
                "filename": "analysis.md",
                "content": "# Cloud Infrastructure Analysis\n\n## Cost Optimization\n- Migrate to ARM instances: 20% savings\n- Use Spot instances: 40% savings",
                "mime": "text/markdown",
                "summary": "Infrastructure analysis",
            },
        ]

        for i, file_data in enumerate(files_to_create, start=2):
            print(f"📤 Uploading {file_data['filename']} to S3...")
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
                    try:
                        inner = json.loads(text)
                        # Display session info from first response
                        if i == 2:
                            session_id = inner.get("session_id")
                            print(f"   ✅ Uploaded (session: {session_id})")
                        else:
                            print("   ✅ Uploaded")
                    except json.JSONDecodeError:
                        print("   ✅ Uploaded")
                else:
                    print("   ✅ Uploaded")
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
            "params": {"name": "list_session_files", "arguments": {}},
        }

        response = send_and_receive(process, list_msg, expected_id=10)
        if "result" in response:
            print("📋 Files in S3:")
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

        # Summary
        print("=" * 80)
        print("Demo Complete!")
        print("=" * 80)
        print()
        print("✅ S3 storage provider features:")
        print("   • Scalable - automatic scaling with demand")
        print("   • Durable - 99.999999999% durability (11 nines)")
        print("   • Available - 99.99% availability SLA")
        print("   • Versioning - optional file version history")
        print("   • Encryption - server-side encryption at rest")
        print("   • Multi-region - deploy close to users")
        print()
        print(f"💡 Tip: Check your S3 bucket '{bucket}' in AWS Console to see files")
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
        print()
        print("⚠️  Note: Files remain in S3. Delete manually if needed:")
        print(f"   aws s3 rm s3://{bucket}/ --recursive")


if __name__ == "__main__":
    main()
