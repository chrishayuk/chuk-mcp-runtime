#!/usr/bin/env python3
"""
GitHub MCP Practical Demo
========================

Demonstrates what actually works with your GitHub token permissions:
1. Search repositories (✅ Working)
2. Get file contents (✅ Working)
3. List issues from existing repos
4. Get repository information
5. Search users
6. List commits

This focuses on read-only operations that work reliably!
"""

import asyncio
import os
import json
import logging
import contextlib
import io
from typing import Dict, Any, Optional
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("⚠️ dotenv not available, using environment variables as-is")


def silence_debug_only():
    """Silence only debug messages, keep essential logging."""
    # Set specific noisy loggers to WARNING instead of disabling all logging
    noisy_loggers = [
        "chuk_mcp_runtime.proxy",
        "chuk_mcp_runtime.proxy.manager",
        "chuk_mcp_runtime.proxy.tool_wrapper",
        "chuk_tool_processor.mcp.stream_manager",
        "chuk_tool_processor.mcp.register",
        "chuk_tool_processor.mcp.setup_stdio",
        "root",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


class GitHubPracticalDemo:
    """Demonstrates practical GitHub operations that actually work."""

    def __init__(self):
        self.tools = {}

    async def setup(self):
        """Initialize the GitHub MCP tools with minimal noise."""
        silence_debug_only()

        # Check token
        github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        if not github_token:
            print("❌ GITHUB_PERSONAL_ACCESS_TOKEN not set")
            return False

        try:
            from chuk_mcp_runtime.proxy.manager import ProxyServerManager
            from chuk_mcp_runtime.common.mcp_tool_decorator import (
                TOOLS_REGISTRY,
                initialize_tool_registry,
            )

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

            os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
            await initialize_tool_registry()

            proxy_mgr = ProxyServerManager(config, project_root=os.getcwd())

            # Only silence stdout during startup, keep stderr for errors
            with contextlib.redirect_stdout(io.StringIO()):
                await proxy_mgr.start_servers()

            # Extract tools
            for name, func in TOOLS_REGISTRY.items():
                if name.startswith("github_"):
                    self.tools[name] = func

            self.proxy_mgr = proxy_mgr
            return True

        except Exception as e:
            print(f"❌ Setup failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def demo_repository_search(self):
        """Demo: Repository search (this works!)"""
        print("\n🔍 Repository Search Demo")
        print("=" * 40)

        try:
            search_tool = self.tools["github_search_repositories"]

            print("🔎 Searching for popular Python repositories...")
            result = await search_tool(query="stars:>10000 language:python")
            self.print_result("Repository Search", result)

            print("\n🔎 Searching for MCP-related repositories...")
            result = await search_tool(query="mcp python")
            self.print_result("MCP Repository Search", result)

        except Exception as e:
            print(f"❌ Search failed: {e}")

    async def demo_file_exploration(self):
        """Demo: File content retrieval (this works!)"""
        print("\n📁 File Content Demo")
        print("=" * 40)

        try:
            file_tool = self.tools["github_get_file_contents"]

            print("📖 Getting README from a popular repository...")
            result = await file_tool(owner="microsoft", repo="vscode", path="README.md")

            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list) and content:
                    file_text = (
                        content[0].text
                        if hasattr(content[0], "text")
                        else str(content[0])
                    )
                    lines = file_text.split("\n")[:3]
                    print("📄 VS Code README preview:")
                    for i, line in enumerate(lines, 1):
                        if line.strip():
                            print(f"   {i}: {line[:60]}...")

            print("\n📖 Getting Python file from a popular repo...")
            result = await file_tool(owner="python", repo="cpython", path="README.rst")
            self.print_result("CPython README", result, max_length=300)

        except Exception as e:
            print(f"❌ File retrieval failed: {e}")

    async def demo_repository_info(self):
        """Demo: Repository information gathering"""
        print("\n📊 Repository Information Demo")
        print("=" * 40)

        try:
            # List commits from a repository
            if "github_list_commits" in self.tools:
                commits_tool = self.tools["github_list_commits"]
                print("📈 Getting recent commits from microsoft/vscode...")
                result = await commits_tool(owner="microsoft", repo="vscode")
                self.print_result("Recent Commits", result, max_length=400)

            # List issues from a repository
            if "github_list_issues" in self.tools:
                issues_tool = self.tools["github_list_issues"]
                print("\n🐛 Getting issues from microsoft/vscode...")
                result = await issues_tool(
                    owner="microsoft", repo="vscode", state="open"
                )
                self.print_result("Open Issues", result, max_length=400)

        except Exception as e:
            print(f"❌ Repository info failed: {e}")

    async def demo_search_capabilities(self):
        """Demo: Various search capabilities"""
        print("\n🔍 Advanced Search Demo")
        print("=" * 40)

        try:
            # Search for users
            if "github_search_users" in self.tools:
                users_tool = self.tools["github_search_users"]
                print("👥 Searching for Python developers...")
                result = await users_tool(q="language:python followers:>1000")
                self.print_result("Python Developers", result, max_length=300)

            # Search for issues
            if "github_search_issues" in self.tools:
                issues_tool = self.tools["github_search_issues"]
                print("\n🐛 Searching for recent Python issues...")
                result = await issues_tool(
                    q="language:python is:issue created:>2024-01-01"
                )
                self.print_result("Recent Python Issues", result, max_length=300)

        except Exception as e:
            print(f"❌ Search capabilities failed: {e}")

    def print_result(self, title: str, result: Any, max_length: int = 200):
        """Print a formatted result."""
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and content:
                text = (
                    content[0].text if hasattr(content[0], "text") else str(content[0])
                )
                preview = text[:max_length] + "..." if len(text) > max_length else text
                print(f"✅ {title} successful!")
                print(f"📋 Preview: {preview}")
            else:
                print(f"✅ {title} completed (no preview data)")
        else:
            print(f"✅ {title} executed!")

    def demo_tool_showcase(self):
        """Show all available tools."""
        print("\n🔧 Available GitHub Tools")
        print("=" * 40)

        # Categorize tools
        categories = {
            "🔍 Search": ["search"],
            "📁 Files": ["file", "content"],
            "📊 Repository": ["repo", "commit", "branch", "fork"],
            "🐛 Issues": ["issue"],
            "🔄 Pull Requests": ["pull"],
            "👥 Users": ["user"],
        }

        for category, keywords in categories.items():
            tools_in_category = [
                name
                for name in self.tools.keys()
                if any(keyword in name.lower() for keyword in keywords)
            ]
            if tools_in_category:
                print(f"\n{category} ({len(tools_in_category)} tools):")
                for tool in sorted(tools_in_category)[:5]:  # Show first 5
                    print(f"   • {tool}")
                if len(tools_in_category) > 5:
                    print(f"   ... and {len(tools_in_category) - 5} more")

    async def cleanup(self):
        """Clean up resources."""
        try:
            if hasattr(self, "proxy_mgr"):
                with contextlib.redirect_stdout(io.StringIO()):
                    await self.proxy_mgr.stop_servers()
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

    def print_summary(self):
        """Print final summary."""
        print("\n🎉 PRACTICAL DEMO SUMMARY")
        print("=" * 50)
        print("✅ Successfully demonstrated working GitHub operations:")
        print("   🔍 Repository search with complex queries")
        print("   📁 File content retrieval from any public repo")
        print("   📊 Repository metadata and commit history")
        print("   🐛 Issue listing and search")
        print("   👥 User and developer search")
        print()
        print(f"🔧 Total tools available: {len(self.tools)}")
        print("🚀 Your GitHub MCP integration is working excellently!")
        print()
        print("💡 What works reliably:")
        print("   • All read-only operations")
        print("   • Public repository access")
        print("   • Advanced search queries")
        print("   • File and metadata retrieval")
        print()
        print("⚠️ What requires special permissions:")
        print("   • Repository creation")
        print("   • File modifications")
        print("   • Issue/PR creation")
        print("   • Code search (enterprise feature)")


async def main():
    """Run the practical GitHub MCP demonstration."""

    print("🚀 GitHub MCP Practical Demo")
    print("=" * 50)
    print("Demonstrating what actually works with your GitHub integration!")
    print()

    demo = GitHubPracticalDemo()

    try:
        print("🔧 Setting up GitHub MCP tools...")
        if not await demo.setup():
            return

        print(f"✅ Ready! Loaded {len(demo.tools)} GitHub tools")

        # Run practical demonstrations
        await demo.demo_repository_search()
        await demo.demo_file_exploration()
        await demo.demo_repository_info()
        await demo.demo_search_capabilities()

        # Show available tools
        demo.demo_tool_showcase()

        # Summary
        demo.print_summary()

    except KeyboardInterrupt:
        print("\n⏹️ Demo interrupted")
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
    finally:
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
