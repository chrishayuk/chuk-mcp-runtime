#!/usr/bin/env python3
"""
Debug script to check session tools registration
"""

import asyncio
import sys
from pathlib import Path

# Add src to path so we can import the runtime
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from chuk_mcp_runtime.tools import (
    register_all_tools,
    get_all_tools_info,
    register_session_tools,
    register_artifacts_tools,
)
from chuk_mcp_runtime.tools.session_tools import (
    DEFAULT_SESSION_TOOLS_CONFIG,
    get_enabled_session_tools,
    configure_session_tools,
)
from chuk_mcp_runtime.tools.artifacts_tools import (
    DEFAULT_TOOL_CONFIG,
    get_enabled_tools as get_enabled_artifact_tools,
    configure_artifacts_tools,
)
from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY


async def main():
    print("🔍 Debug Tools Registration (Both Session and Artifacts)")
    print("=" * 60)

    # Clear registry to start fresh
    TOOLS_REGISTRY.clear()

    print("📋 DEFAULT CONFIGURATIONS:")
    print(
        f"   Session tools enabled by default: {DEFAULT_SESSION_TOOLS_CONFIG['enabled']}"
    )
    print(f"   Artifact tools enabled by default: {DEFAULT_TOOL_CONFIG['enabled']}")

    print("\n🧪 Testing with no configuration (should have no tools):")

    # Test with empty config
    empty_config = {}
    result = await register_all_tools(empty_config)
    print(f"   Registration results: {result}")
    print(f"   Tools in registry: {len(TOOLS_REGISTRY)}")

    # Clear for next test
    TOOLS_REGISTRY.clear()

    print("\n🔍 Checking session tool decorators directly:")
    from chuk_mcp_runtime.tools.session_tools import (
        get_current_session,
        set_session_context_tool,
        clear_session_context_tool,
    )

    test_tools = {
        "get_current_session": get_current_session,
        "set_session": set_session_context_tool,
        "clear_session": clear_session_context_tool,
    }

    for name, func in test_tools.items():
        print(f"   {name}:")
        print(f"     Has _mcp_tool: {'✅' if hasattr(func, '_mcp_tool') else '❌'}")
        print(f"     Has _needs_init: {'✅' if hasattr(func, '_needs_init') else '❌'}")
        if hasattr(func, "_mcp_tool"):
            print(f"     Tool name: {func._mcp_tool.name}")
        elif hasattr(func, "_needs_init"):
            print(f"     Needs init: {func._needs_init}")
            print(f"     Init name: {getattr(func, '_init_name', 'unknown')}")

    print("\n🧪 Testing with session tools enabled:")

    session_config = {
        "session_tools": {
            "enabled": True,
            "tools": {
                "get_current_session": {"enabled": True},
                "set_session": {"enabled": True},
                "clear_session": {"enabled": True},
            },
        }
    }

    session_result = await register_session_tools(session_config)
    print(f"   Session tools registration: {session_result}")
    print(
        f"   Session tools in registry: {len([t for t in TOOLS_REGISTRY if 'session' in t.lower()])}"
    )
    print(f"   Total tools in registry: {len(TOOLS_REGISTRY)}")

    # Clear for next test
    TOOLS_REGISTRY.clear()

    print("\n🧪 Testing with artifact tools enabled:")

    artifact_config = {
        "artifacts": {
            "enabled": True,
            "storage_provider": "memory",
            "tools": {
                "write_file": {"enabled": True},
                "read_file": {"enabled": True},
                "list_session_files": {"enabled": True},
            },
        }
    }

    try:
        artifact_result = await register_artifacts_tools(artifact_config)
        print(f"   Artifact tools registration: {artifact_result}")
        print(f"   Artifact tools in registry: {len(TOOLS_REGISTRY)}")
    except Exception as e:
        print(f"   Artifact tools registration failed: {e}")

    # Clear for final test
    TOOLS_REGISTRY.clear()

    print("\n🧪 Testing with both enabled:")

    full_config = {
        "session_tools": {
            "enabled": True,
            "tools": {
                "get_current_session": {"enabled": True},
                "set_session": {"enabled": True},
            },
        },
        "artifacts": {
            "enabled": True,
            "storage_provider": "memory",
            "tools": {"write_file": {"enabled": True}, "read_file": {"enabled": True}},
        },
    }

    all_results = await register_all_tools(full_config)
    print(f"   All tools registration: {all_results}")
    print(f"   Total tools in registry: {len(TOOLS_REGISTRY)}")

    print("\n📊 Final Registry Contents:")
    for tool_name in sorted(TOOLS_REGISTRY.keys()):
        tool = TOOLS_REGISTRY[tool_name]
        has_metadata = "✅" if hasattr(tool, "_mcp_tool") else "❌"
        tool_type = "🔐" if "session" in tool_name else "📁"
        print(f"   {tool_type} {has_metadata} {tool_name}")

    print(f"\n🎯 Summary:")
    print(
        f"   📁 Artifact tools: {len([t for t in TOOLS_REGISTRY if 'session' not in t])}"
    )
    print(
        f"   🔐 Session tools: {len([t for t in TOOLS_REGISTRY if 'session' in t or 'clear_session' in t])}"
    )
    print(f"   📊 Total tools: {len(TOOLS_REGISTRY)}")

    # Test tool info
    print(f"\n📋 Tool Info:")
    info = get_all_tools_info()
    print(f"   Categories: {info['categories']}")
    print(f"   Total enabled: {info['total_enabled']}")


if __name__ == "__main__":
    asyncio.run(main())
