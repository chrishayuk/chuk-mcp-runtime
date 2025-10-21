#!/usr/bin/env python
# examples/debug_proxy_config.py
"""
debug_proxy_config.py
---------------------

Validate and debug a proxy configuration file.
This script checks:
1. File existence
2. YAML syntax
3. Server paths and commands
4. Server directory existence
"""

import argparse
import os
from pathlib import Path

import yaml


def check_path_exists(path, name, is_dir=False):
    """Check if a path exists and is a file or directory."""
    if not path:
        print(f"❌ {name} path is empty")
        return False

    path_obj = Path(path)
    if not path_obj.exists():
        print(f"❌ {name} does not exist: {path}")
        return False

    if is_dir and not path_obj.is_dir():
        print(f"❌ {name} is not a directory: {path}")
        return False
    elif not is_dir and not path_obj.is_file():
        print(f"❌ {name} is not a file: {path}")
        return False

    print(f"✅ {name} exists: {path}")
    return True


def check_command_exists(command):
    """Check if a command exists in PATH."""
    import shutil

    cmd_path = shutil.which(command)
    if not cmd_path:
        print(f"❌ Command not found in PATH: {command}")
        return False

    print(f"✅ Command found: {command} → {cmd_path}")
    return True


def validate_config(config_path, project_root=None):
    """Validate the proxy configuration file."""
    print(f"\n=== Validating proxy configuration: {config_path} ===\n")

    # Check if config file exists
    if not check_path_exists(config_path, "Config file"):
        return False

    # Load and parse YAML
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        print("✅ YAML syntax is valid")
    except Exception as e:
        print(f"❌ Error parsing YAML: {e}")
        return False

    # Check if proxy is enabled
    proxy_enabled = config.get("proxy", {}).get("enabled", False)
    print(f"{'✅' if proxy_enabled else '❌'} Proxy enabled: {proxy_enabled}")

    if not proxy_enabled:
        print("ℹ️ Proxy is disabled - no servers will be started")
        return True

    # Get proxy namespace
    namespace = config.get("proxy", {}).get("namespace", "proxy")
    print(f"ℹ️ Proxy namespace: {namespace}")

    # Check OpenAI compatibility mode
    openai_mode = config.get("proxy", {}).get("openai_compatible", False)
    print(f"ℹ️ OpenAI compatibility mode: {openai_mode}")

    # Check MCP servers
    mcp_servers = config.get("mcp_servers", {})
    if not mcp_servers:
        print("❌ No MCP servers defined")
        return False

    print(f"\n=== Found {len(mcp_servers)} MCP server(s) ===\n")

    # Process each server
    for server_name, server_config in mcp_servers.items():
        print(f"--- Server: {server_name} ---")

        # Check if server is enabled
        enabled = server_config.get("enabled", True)
        print(f"{'✅' if enabled else '❌'} Enabled: {enabled}")
        if not enabled:
            print("ℹ️ Server is disabled - skipping validation")
            continue

        # Check server type
        server_type = server_config.get("type", "stdio")
        print(f"ℹ️ Type: {server_type}")

        if server_type != "stdio":
            print(f"ℹ️ Non-stdio servers not validated: {server_type}")
            continue

        # Check location
        location = server_config.get("location", "")
        if location:
            # If location is relative, join with project root
            if not os.path.isabs(location) and project_root:
                full_path = os.path.join(project_root, location)
            else:
                full_path = location

            check_path_exists(full_path, "Server location", is_dir=True)
        else:
            print("❌ No location specified")

        # Check command
        command = server_config.get("command", "python")
        check_command_exists(command)

        # Check args
        args = server_config.get("args", [])
        if args:
            print(f"ℹ️ Command args: {args}")
        else:
            print("⚠️ No command args specified")

        print("")  # Add spacing between servers

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate proxy configuration")
    parser.add_argument("config", help="Path to the proxy configuration YAML file")
    parser.add_argument("--root", help="Project root directory (for resolving relative paths)")

    args = parser.parse_args()

    # If root not specified, use current directory
    project_root = args.root or os.getcwd()

    validate_config(args.config, project_root)
