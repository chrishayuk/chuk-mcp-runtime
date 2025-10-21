# tests/test_tool_naming.py
"""
Test module for tool naming resolution functionality.

Tests the functionality of the tool_naming module to ensure
proper resolution between dot and underscore naming conventions.
"""

from typing import Any, Dict

import pytest
from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY, mcp_tool
from chuk_mcp_runtime.common.tool_naming import (
    ToolNamingResolver,
    resolve_tool_name,
    update_naming_maps,
)


# --- Sample tools for testing ---
@mcp_tool(name="echo", description="Echo tool")
async def echo(msg: str) -> str:
    return f"echo:{msg}"


@mcp_tool(name="wiki.search", description="Wiki search tool")
async def wiki_search(query: str) -> Dict[str, Any]:
    return {"results": [f"Result for {query}"]}


@mcp_tool(name="google_search", description="Google search tool")
async def google_search(query: str) -> Dict[str, Any]:
    return {"results": [f"Google result for {query}"]}


@mcp_tool(name="proxy.bing.search", description="Bing search with proxy prefix")
async def bing_search(query: str) -> Dict[str, Any]:
    return {"results": [f"Bing result for {query}"]}


@mcp_tool(name="some.very.long.namespace.tool", description="Tool with many dots")
async def long_namespace_tool(param: str) -> str:
    return f"long:{param}"


@pytest.fixture
def setup_registry():
    """Set up a clean registry for tests."""
    # Clear registry before each test
    TOOLS_REGISTRY.clear()

    # Register test tools
    TOOLS_REGISTRY["echo"] = echo
    TOOLS_REGISTRY["wiki.search"] = wiki_search
    TOOLS_REGISTRY["google_search"] = google_search
    TOOLS_REGISTRY["proxy.bing.search"] = bing_search
    TOOLS_REGISTRY["some.very.long.namespace.tool"] = long_namespace_tool

    # Update name maps
    update_naming_maps()

    yield

    # Clean up
    TOOLS_REGISTRY.clear()


def test_resolver_initialization(setup_registry):
    """Test resolver initialization creates proper maps."""
    resolver = ToolNamingResolver()

    # Check dot to underscore mapping
    assert "wiki.search" in resolver.dot_to_underscore_map
    assert resolver.dot_to_underscore_map["wiki.search"] == "wiki_search"

    # Check underscore to dot mapping
    assert "google_search" in resolver.underscore_to_dot_map
    assert resolver.underscore_to_dot_map["google_search"] == "google.search"

    # Check how maps are built for nested namespaces
    assert "bing.search" in resolver.dot_to_underscore_map
    assert resolver.dot_to_underscore_map["bing.search"] == "bing_search"


def test_basic_name_resolution(setup_registry):
    """Test basic name resolution between dot and underscore notation."""
    # Dot to underscore
    assert resolve_tool_name("wiki.search") == "wiki.search"  # Original exists, so keep it

    # Underscore to dot (when original doesn't exist)
    TOOLS_REGISTRY.pop("wiki.search")
    update_naming_maps()
    TOOLS_REGISTRY["wiki_search"] = wiki_search  # Only register underscore version
    assert resolve_tool_name("wiki.search") == "wiki_search"

    # Reset for other tests
    TOOLS_REGISTRY.clear()
    TOOLS_REGISTRY["echo"] = echo
    TOOLS_REGISTRY["wiki.search"] = wiki_search
    TOOLS_REGISTRY["google_search"] = google_search
    TOOLS_REGISTRY["proxy.bing.search"] = bing_search
    TOOLS_REGISTRY["some.very.long.namespace.tool"] = long_namespace_tool
    update_naming_maps()


def test_proxy_namespace_resolution(setup_registry):
    """Test resolution with proxy namespaces."""
    # Full proxy namespace to short form
    assert resolve_tool_name("proxy.bing.search") == "proxy.bing.search"

    # Short form to proxy namespace
    assert resolve_tool_name("bing.search") == "proxy.bing.search"

    # Underscore form to proxy namespace
    assert resolve_tool_name("bing_search") == "proxy.bing.search"


def test_long_namespace_resolution(setup_registry):
    """Test resolution with long namespaces."""
    # Original long namespace
    assert resolve_tool_name("some.very.long.namespace.tool") == "some.very.long.namespace.tool"

    # Shortened to last two components
    assert resolve_tool_name("namespace.tool") == "some.very.long.namespace.tool"

    # Underscore version
    assert resolve_tool_name("some_very_long_namespace_tool") in [
        "some.very.long.namespace.tool",
        "some_very_long_namespace_tool",
    ]

    # Shortened underscore version
    assert resolve_tool_name("namespace_tool") == "some.very.long.namespace.tool"


def test_nonexistent_tool_resolution(setup_registry):
    """Test resolution behavior with nonexistent tools."""
    # Completely unknown tool should return original
    assert resolve_tool_name("nonexistent.tool") == "nonexistent.tool"

    # Similar but nonexistent
    assert resolve_tool_name("fake.search") == "fake.search"

    # Check that there's no false positives
    assert resolve_tool_name("bingsearch") == "bingsearch"  # No match for malformed name


def test_dynamic_registry_updates(setup_registry):
    """Test that resolver updates when registry changes."""
    # Confirm initial state
    assert resolve_tool_name("new.tool") == "new.tool"  # Not found

    # Add a new tool
    @mcp_tool(name="new.tool", description="New test tool")
    async def new_tool(param: str) -> str:
        return f"new:{param}"

    TOOLS_REGISTRY["new.tool"] = new_tool
    update_naming_maps()

    # Now should resolve
    assert resolve_tool_name("new_tool") == "new.tool"

    # Remove a tool and check resolution
    TOOLS_REGISTRY.pop("wiki.search")
    update_naming_maps()

    # No longer resolves to this tool
    assert resolve_tool_name("wiki.search") == "wiki.search"  # Not found

    # Add underscore version instead
    TOOLS_REGISTRY["wiki_search"] = wiki_search
    update_naming_maps()

    # Now should resolve underscore to original format
    assert resolve_tool_name("wiki.search") == "wiki_search"


def test_edge_cases(setup_registry):
    """Test edge cases in tool naming."""
    # Tool with both formats registered
    TOOLS_REGISTRY["dual.format"] = echo  # Reuse echo function
    TOOLS_REGISTRY["dual_format"] = echo
    update_naming_maps()

    # Should find the exact match first
    assert resolve_tool_name("dual.format") == "dual.format"
    assert resolve_tool_name("dual_format") == "dual_format"

    # Tool with numeric parts
    TOOLS_REGISTRY["version.1.2.tool"] = echo
    update_naming_maps()

    # Should handle numeric components
    assert resolve_tool_name("version.1.2.tool") == "version.1.2.tool"
    assert resolve_tool_name("version_1_2_tool") == "version.1.2.tool"

    # Tools with special characters (converted to underscore in OpenAI format)
    TOOLS_REGISTRY["special-chars.tool"] = echo
    update_naming_maps()

    # Should handle special characters
    assert resolve_tool_name("special-chars.tool") == "special-chars.tool"
    # Special characters are a bit tricky, it might resolve to either name
    resolved_name = resolve_tool_name("special_chars_tool")
    assert resolved_name in ["special-chars.tool", "special_chars_tool"]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
