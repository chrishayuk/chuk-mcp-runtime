#!/usr/bin/env python3
"""
Quick Clean GitHub Inspector
===========================

Simple solution that manually suppresses the noisy loggers.
"""

import asyncio
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv

# Load environment
load_dotenv()


def silence_noisy_loggers():
    """Manually set specific loggers to WARNING level."""
    noisy_loggers = [
        "chuk_mcp_runtime.proxy",
        "chuk_mcp_runtime.proxy.manager",
        "chuk_mcp_runtime.proxy.tool_wrapper",
        "chuk_tool_processor.mcp.stream_manager",
        "chuk_tool_processor.mcp.register",
        "chuk_tool_processor.mcp.setup_stdio",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


async def inspect_github_tools():
    """Get GitHub tools with minimal logging noise."""

    github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not github_token:
        print("❌ GITHUB_PERSONAL_ACCESS_TOKEN not set")
        return {}

    try:
        # Set up quiet logging BEFORE importing anything
        silence_noisy_loggers()

        from chuk_mcp_runtime.common.mcp_tool_decorator import (
            TOOLS_REGISTRY,
            initialize_tool_registry,
        )
        from chuk_mcp_runtime.proxy.manager import ProxyServerManager

        # Silence again after imports (some modules may reset logging)
        silence_noisy_loggers()

        # Configuration
        config = {
            "proxy": {
                "enabled": True,
                "namespace": "proxy",
                "openai_compatible": True,
            },
            "mcp_servers": {
                "github": {
                    "enabled": True,
                    "type": "stdio",
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-github"],
                    "location": "",
                }
            },
        }

        # Set environment
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token

        # Initialize
        await initialize_tool_registry()
        proxy_mgr = ProxyServerManager(config, project_root=os.getcwd())

        # Silence loggers one more time before the noisy startup
        silence_noisy_loggers()

        await proxy_mgr.start_servers()

        # Extract GitHub tools
        github_tools = {}
        for name, func in TOOLS_REGISTRY.items():
            if name.startswith("github_"):
                github_tools[name] = extract_tool_info(name, func)

        # Cleanup
        await proxy_mgr.stop_servers()

        return github_tools

    except Exception as e:
        print(f"❌ Error: {e}")
        return {}


def extract_tool_info(name: str, func) -> Dict[str, Any]:
    """Extract basic info from a tool."""
    info = {
        "name": name,
        "description": "No description available",
        "required_count": 0,
        "optional_count": 0,
    }

    if hasattr(func, "_mcp_tool"):
        tool_obj = func._mcp_tool
        info["description"] = getattr(tool_obj, "description", "No description")

        # Count parameters
        input_schema = getattr(tool_obj, "inputSchema", {})
        if isinstance(input_schema, dict):
            properties = input_schema.get("properties", {})
            required = set(input_schema.get("required", []))

            info["required_count"] = len(required)
            info["optional_count"] = len(properties) - len(required)

    return info


def print_clean_summary(tools: Dict[str, Any]):
    """Print a clean summary with full tools table."""

    if not tools:
        print("❌ No GitHub tools found")
        return

    print("\n🎉 GitHub Integration Success!")
    print("=" * 80)
    print(f"✅ {len(tools)} GitHub tools available")
    print("🔧 Tool naming: Underscore format (github_*)")
    print("📦 Ready to import from TOOLS_REGISTRY")

    # Print complete tools table
    print("\n📋 Complete GitHub Tools Table")
    print("=" * 80)
    print(f"{'Tool Name':<35} {'Req':<4} {'Opt':<4} {'Category':<12} {'Description':<25}")
    print("-" * 80)

    # Categorize and sort tools
    categorized_tools = categorize_tools(tools)

    for category in [
        "🏗️ Repository",
        "📁 Files",
        "🐛 Issues",
        "🔄 Pull Requests",
        "🔍 Search",
    ]:
        tool_list = categorized_tools.get(category, [])
        if tool_list:
            for tool_name in sorted(tool_list):
                tool_info = tools[tool_name]
                req_count = tool_info["required_count"]
                opt_count = tool_info["optional_count"]

                # Clean up category name for display
                cat_display = category.split(" ", 1)[1] if " " in category else category
                cat_display = cat_display[:12]  # Truncate if too long

                # Truncate description
                desc = tool_info["description"][:25]
                if len(tool_info["description"]) > 25:
                    desc = desc[:22] + "..."

                print(f"{tool_name:<35} {req_count:<4} {opt_count:<4} {cat_display:<12} {desc:<25}")

    # Quick stats summary
    print("\n📊 Summary by Category:")
    for category, tool_list in categorized_tools.items():
        if tool_list:
            print(f"   {category}: {len(tool_list)} tools")

    # Usage examples
    print("\n💡 Usage Examples:")
    print("```python")
    print("from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY")
    print()
    print("# Search repositories")
    print("repos = await TOOLS_REGISTRY['github_search_repositories'](query='python mcp')")
    print()
    print("# Get file contents")
    print("content = await TOOLS_REGISTRY['github_get_file_contents'](")
    print("    owner='microsoft', repo='vscode', path='README.md')")
    print()
    print("# Create an issue")
    print("issue = await TOOLS_REGISTRY['github_create_issue'](")
    print("    owner='myorg', repo='myrepo', title='Bug report', body='Description')")
    print("```")
    print("\n🚀 All 26 GitHub tools are ready to use!")


def categorize_tools(tools: Dict[str, Any]) -> Dict[str, list]:
    """Categorize tools by functionality."""

    categories = {
        "🏗️ Repository": [],
        "📁 Files": [],
        "🐛 Issues": [],
        "🔄 Pull Requests": [],
        "🔍 Search": [],
    }

    for tool_name in tools.keys():
        name_lower = tool_name.lower()

        if any(word in name_lower for word in ["search"]):
            categories["🔍 Search"].append(tool_name)
        elif any(word in name_lower for word in ["file", "content", "push"]):
            categories["📁 Files"].append(tool_name)
        elif any(word in name_lower for word in ["issue"]) and "pull" not in name_lower:
            categories["🐛 Issues"].append(tool_name)
        elif any(word in name_lower for word in ["pull", "pr", "review", "merge"]):
            categories["🔄 Pull Requests"].append(tool_name)
        elif (
            any(word in name_lower for word in ["repo", "fork", "branch", "commit"])
            and "pull" not in name_lower
        ):
            categories["🏗️ Repository"].append(tool_name)
        else:
            # Default to repository for uncategorized
            categories["🏗️ Repository"].append(tool_name)

    return categories


async def main():
    """Run the quick clean inspector."""

    print("🔍 Quick GitHub Tools Inspector")
    print("=" * 40)

    # Silence logging early
    silence_noisy_loggers()

    print("🔄 Checking GitHub MCP tools...")
    tools = await inspect_github_tools()

    print_clean_summary(tools)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
    except Exception as e:
        print(f"\n💥 Error: {e}")
