#!/usr/bin/env python3
"""
Test script to check the tools registry directly
"""

import asyncio
import os


async def test_registry():
    """Test the tools registry directly."""
    print("🔍 Testing Tools Registry")
    print("=" * 30)

    # Set up environment
    os.environ.update(
        {
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": "/tmp/test_artifacts",
            "ARTIFACT_BUCKET": "test-registry",
        }
    )

    # Import and set up tools
    from chuk_mcp_runtime.tools import register_artifacts_tools
    from chuk_mcp_runtime.common.mcp_tool_decorator import (
        TOOLS_REGISTRY,
        initialize_tool_registry,
    )

    print("📋 Before registration:")
    print(f"   Registry size: {len(TOOLS_REGISTRY)}")

    # Register tools
    config = {
        "artifacts": {
            "storage_provider": "filesystem",
            "session_provider": "memory",
            "tools": {"enabled": True},
        }
    }

    success = await register_artifacts_tools(config)
    print(f"✅ Registration success: {success}")

    print(f"\n📋 After registration:")
    print(f"   Registry size: {len(TOOLS_REGISTRY)}")

    # Check each tool
    for name, func in TOOLS_REGISTRY.items():
        has_metadata = hasattr(func, "_mcp_tool")
        needs_init = hasattr(func, "_needs_init") and func._needs_init
        print(f"   • {name}: metadata={has_metadata}, needs_init={needs_init}")

        if has_metadata:
            tool_meta = func._mcp_tool
            print(f"     - Description: {tool_meta.description[:50]}...")
            print(
                f"     - Schema: {len(tool_meta.inputSchema.get('properties', {}))} params"
            )

    # Initialize tools
    print(f"\n🔧 Initializing tools...")
    await initialize_tool_registry()

    print(f"\n📋 After initialization:")
    for name, func in TOOLS_REGISTRY.items():
        has_metadata = hasattr(func, "_mcp_tool")
        needs_init = hasattr(func, "_needs_init") and func._needs_init
        print(f"   • {name}: metadata={has_metadata}, needs_init={needs_init}")

        if has_metadata:
            tool_meta = func._mcp_tool
            print(f"     - Name: {tool_meta.name}")
            print(f"     - Description: {tool_meta.description[:70]}...")
            schema_props = tool_meta.inputSchema.get("properties", {})
            print(f"     - Schema: {len(schema_props)} params")

            # Show parameter details
            if schema_props:
                print(f"     - Parameters:")
                for param_name, param_def in list(schema_props.items())[
                    :4
                ]:  # Show first 4 params
                    param_type = param_def.get("type", "unknown")
                    param_desc = param_def.get("description", "No description")
                    print(f"       • {param_name} ({param_type}): {param_desc}")

                if len(schema_props) > 4:
                    print(f"       ... and {len(schema_props) - 4} more parameters")

                # Show required parameters
                required = tool_meta.inputSchema.get("required", [])
                if required:
                    print(f"     - Required: {', '.join(required)}")
            print()  # Empty line for readability

    # Test the list_tools logic directly
    print(f"\n🧪 Testing list_tools logic:")
    tools_list = [
        func._mcp_tool for func in TOOLS_REGISTRY.values() if hasattr(func, "_mcp_tool")
    ]
    print(f"   Found {len(tools_list)} tools with metadata")

    if tools_list:
        print("✅ list_tools should work correctly")
    else:
        print("❌ list_tools would fail - no tools have metadata")


if __name__ == "__main__":
    asyncio.run(test_registry())
