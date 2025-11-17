# tests/common/test_tool_naming_coverage.py
"""
Additional tests to improve tool_naming coverage.
"""

import pytest

from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY, mcp_tool
from chuk_mcp_runtime.common.tool_naming import resolve_tool_name, update_naming_maps


@pytest.fixture(autouse=True)
def setup_tools():
    """Set up test tools."""
    TOOLS_REGISTRY.clear()

    @mcp_tool(name="proxy.github.search", description="Search GitHub")
    async def github_search():
        return "github"

    @mcp_tool(name="github.search", description="Direct GitHub search")
    async def direct_search():
        return "direct"

    TOOLS_REGISTRY["proxy.github.search"] = github_search
    TOOLS_REGISTRY["github.search"] = direct_search
    update_naming_maps()

    yield

    TOOLS_REGISTRY.clear()


def test_resolve_tool_with_multiple_dots():
    """Test resolving tool names with multiple dots (proxy.github.search)."""
    # Should resolve to the full name
    result = resolve_tool_name("proxy.github.search")
    assert result == "proxy.github.search"


def test_resolve_tool_simple_name_from_multi_dot():
    """Test resolving using last two parts of multi-dot name."""
    # When looking up "github.search" it should find "github.search" directly
    result = resolve_tool_name("github.search")
    assert result == "github.search"


def test_resolve_tool_with_underscore_from_multi_dot():
    """Test resolving multi-dot name converted to underscore."""
    # Register the underscore version
    TOOLS_REGISTRY["github_search"] = TOOLS_REGISTRY["github.search"]
    update_naming_maps()

    # Should find github_search
    result = resolve_tool_name("github_search")
    assert result == "github_search"


def test_resolve_nonexistent_multi_dot_tool():
    """Test resolving non-existent multi-dot tool."""
    result = resolve_tool_name("nonexistent.multi.dot.tool")
    # Should return the original name if not found
    assert result == "nonexistent.multi.dot.tool"
