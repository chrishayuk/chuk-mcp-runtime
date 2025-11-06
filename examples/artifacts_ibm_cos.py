#!/usr/bin/env python3
"""
Artifacts Demo - IBM Cloud Object Storage Provider

Demonstrates artifacts functionality with IBM Cloud Object Storage (COS).
Files are stored in IBM COS for enterprise-grade durability and compliance.

Features:
- write_file: Create files stored in IBM COS
- list_session_files: List all files in current session
- Enterprise-grade storage with SLA guarantees
- Regional and cross-regional storage options
- Built-in encryption and compliance features

Requirements:
- IBM Cloud credentials configured (via .env file or environment variables)
- IBM COS bucket created
- chuk-artifacts[ibm_cos] installed: pip install chuk-artifacts[ibm_cos]

Environment variables (can be set in .env file):
- ARTIFACT_BUCKET: IBM COS bucket name (required)
- IBM_COS_ENDPOINT or S3_ENDPOINT_URL: IBM COS endpoint URL (required)
- IBM_COS_APIKEY or IBM_API_KEY_ID: IBM Cloud API key (required)
- IBM_COS_INSTANCE_CRN or IBM_SERVICE_INSTANCE_ID: IBM COS service instance ID (required)
- IBM_AUTH_ENDPOINT: IBM IAM endpoint (optional, default: https://iam.cloud.ibm.com/identity/token)

Run:
    # Using .env file (recommended):
    uv run python examples/artifacts_ibm_cos.py

    # Or with environment variables:
    ARTIFACT_BUCKET=my-bucket \\
    IBM_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud \\
    IBM_COS_APIKEY=your-api-key \\
    IBM_COS_INSTANCE_CRN=your-instance-crn \\
    uv run python examples/artifacts_ibm_cos.py
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def load_env_file(env_file=".env", include_commented_ibm=True):
    """Load environment variables from .env file.

    Args:
        env_file: Path to .env file
        include_commented_ibm: If True, also load commented IBM_COS_* variables
    """
    env_path = Path(__file__).parent.parent / env_file
    if env_path.exists():
        in_ibm_section = False
        with open(env_path) as f:
            for line in f:
                line = line.strip()

                # Track if we're in the IBM COS section
                if "IBM Cloud Object Storage credentials" in line:
                    in_ibm_section = True
                elif line.startswith("###") and in_ibm_section:
                    in_ibm_section = False

                # Handle commented IBM COS variables specially
                if include_commented_ibm and in_ibm_section:
                    if line.startswith("# ") and not line.startswith("# #"):
                        line = line[2:]  # Remove "# " prefix

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
    """Run artifacts demo with IBM COS provider."""
    # Load environment from .env file
    load_env_file()

    print("=" * 80)
    print("Artifacts Demo - IBM Cloud Object Storage Provider")
    print("=" * 80)
    print()

    # Check for required environment variables
    bucket = os.getenv("ARTIFACT_BUCKET")
    endpoint = os.getenv("IBM_COS_ENDPOINT") or os.getenv("S3_ENDPOINT_URL")

    # Check for either native IBM COS credentials or AWS-style S3 credentials
    api_key = os.getenv("IBM_API_KEY_ID") or os.getenv("IBM_COS_APIKEY")
    instance_id = os.getenv("IBM_SERVICE_INSTANCE_ID") or os.getenv("IBM_COS_INSTANCE_CRN")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Determine which credential type we're using
    using_aws_credentials = bool(aws_access_key and aws_secret_key)
    using_ibm_credentials = bool(api_key and instance_id)

    missing = []
    if not bucket:
        missing.append("ARTIFACT_BUCKET")
    if not endpoint:
        missing.append("IBM_COS_ENDPOINT or S3_ENDPOINT_URL")
    if not using_aws_credentials and not using_ibm_credentials:
        missing.append(
            "(AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) or (IBM_COS_APIKEY + IBM_COS_INSTANCE_CRN)"
        )

    if missing:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing)}")
        print()
        print("Usage (two options):")
        print()
        print("  Option 1: AWS S3-compatible credentials (recommended):")
        print("     ARTIFACT_BUCKET=my-bucket")
        print("     S3_ENDPOINT_URL=https://s3.us-south.cloud-object-storage.appdomain.cloud")
        print("     AWS_ACCESS_KEY_ID=your-access-key")
        print("     AWS_SECRET_ACCESS_KEY=your-secret-key")
        print()
        print("  Option 2: Native IBM COS credentials:")
        print("     ARTIFACT_BUCKET=my-bucket")
        print("     IBM_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud")
        print("     IBM_COS_APIKEY=your-api-key")
        print("     IBM_COS_INSTANCE_CRN=your-instance-crn")
        print()
        return

    print(f"🪣 Bucket: {bucket}")
    print(f"🌐 Endpoint: {endpoint}")
    if using_aws_credentials:
        print(f"🔑 Auth: AWS S3 credentials (Access Key: ...{aws_access_key[-8:]})")
    else:
        print(f"🔑 Auth: IBM COS credentials (API Key: ...{api_key[-8:]})")
    print()

    # Create temp config
    temp_dir = Path(tempfile.mkdtemp(prefix="artifacts_ibm_cos_"))
    config_file = temp_dir / "config.yaml"

    # Use s3 provider when AWS credentials are provided
    storage_provider = "s3" if using_aws_credentials else "ibm_cos"

    config_content = f"""
server:
  type: stdio

logging:
  level: ERROR

artifacts:
  enabled: true
  storage_provider: {storage_provider}
  session_provider: memory

  tools:
    write_file: {{enabled: true}}
    upload_file: {{enabled: true}}
    list_session_files: {{enabled: true}}
"""
    config_file.write_text(config_content)

    print(f"📁 Config: {config_file}")
    print()

    try:
        # Start server
        print("🚀 Starting MCP server...")
        env = os.environ.copy()
        env["SESSION_PROVIDER"] = "memory"

        # Use S3 provider when AWS credentials are provided, otherwise use ibm_cos
        if using_aws_credentials:
            env["ARTIFACT_PROVIDER"] = "s3"
            env["ARTIFACT_BUCKET"] = bucket
            env["S3_ENDPOINT_URL"] = endpoint
            env["AWS_ACCESS_KEY_ID"] = aws_access_key
            env["AWS_SECRET_ACCESS_KEY"] = aws_secret_key
        else:
            env["ARTIFACT_PROVIDER"] = "ibm_cos"
            env["ARTIFACT_BUCKET"] = bucket
            env["IBM_COS_ENDPOINT"] = endpoint
            env["IBM_API_KEY_ID"] = api_key
            env["IBM_SERVICE_INSTANCE_ID"] = instance_id

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
            print("   • IBM Cloud credentials configured")
            print("   • IBM COS bucket created")
            print("   • chuk-artifacts[ibm_cos] installed")
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
                "clientInfo": {"name": "artifacts-ibm-cos-demo", "version": "1.0.0"},
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
        print("Creating Files in IBM COS")
        print("=" * 80)
        print()

        files_to_create = [
            {
                "filename": "terraform.tf",
                "content": 'provider "ibm" {\n  region = "us-south"\n}\n\nresource "ibm_cos_bucket" "data" {\n  bucket_name = "production-data"\n}',
                "mime": "text/plain",
                "summary": "Terraform configuration",
            },
            {
                "filename": "compliance.json",
                "content": '{"gdpr": true, "hipaa": true, "soc2": true, "audit_log": "enabled"}',
                "mime": "application/json",
                "summary": "Compliance metadata",
            },
            {
                "filename": "architecture.md",
                "content": "# IBM Cloud Architecture\n\n## Storage Strategy\n- Regional: us-south for low latency\n- Cross-regional: for disaster recovery",
                "mime": "text/markdown",
                "summary": "Architecture documentation",
            },
        ]

        for i, file_data in enumerate(files_to_create, start=2):
            print(f"📤 Uploading {file_data['filename']} to IBM COS...")
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
            "params": {
                "name": "list_session_files",
                "arguments": {},
            },
        }

        response = send_and_receive(process, list_msg, expected_id=10)
        if "result" in response:
            print("📋 Files in IBM COS:")
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
        print("✅ IBM COS storage provider features:")
        print("   • Enterprise-grade durability and availability")
        print("   • Compliance certifications (GDPR, HIPAA, SOC 2, ISO)")
        print("   • Built-in encryption at rest and in transit")
        print("   • Immutable Object Storage for data retention")
        print("   • Regional and cross-regional storage classes")
        print("   • Integrated with IBM Cloud platform")
        print()
        print(f"💡 Tip: Check your IBM COS bucket '{bucket}' in IBM Cloud Console")
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
        print("⚠️  Note: Files remain in IBM COS. Delete manually if needed via IBM Cloud Console")


if __name__ == "__main__":
    main()
