# tests/common/test_mcp_decorator_coverage.py
"""
Targeted tests to improve mcp_tool_decorator coverage.
"""

from typing import Any, Dict, List

import pytest
from chuk_mcp_runtime.common.mcp_tool_decorator import (
    TOOLS_REGISTRY,
    execute_tool,
    get_tool_metadata,
    initialize_tool_registry,
    mcp_tool,
    scan_for_tools,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean registry before each test."""
    original = dict(TOOLS_REGISTRY)
    TOOLS_REGISTRY.clear()
    yield
    TOOLS_REGISTRY.clear()
    TOOLS_REGISTRY.update(original)


@pytest.mark.asyncio
async def test_tool_with_list_param():
    """Test tool with list parameter."""

    @mcp_tool(name="list_tool", description="Takes a list")
    async def list_tool(items: List[str]) -> int:
        """
        Process a list.

        Args:
            items: List of items
        """
        return len(items)

    result = await execute_tool("list_tool", items=["a", "b", "c"])
    assert result == 3


@pytest.mark.asyncio
async def test_tool_with_dict_param():
    """Test tool with dict parameter."""

    @mcp_tool(name="dict_tool", description="Takes a dict")
    async def dict_tool(config: Dict[str, Any]) -> str:
        """
        Process a config.

        Args:
            config: Configuration dictionary
        """
        return config.get("key", "default")

    result = await execute_tool("dict_tool", config={"key": "value"})
    assert result == "value"


@pytest.mark.asyncio
async def test_initialize_tool_registry():
    """Test registry initialization."""

    @mcp_tool(name="init_test", description="Test init")
    async def init_test():
        return "initialized"

    await initialize_tool_registry()
    assert "init_test" in TOOLS_REGISTRY


@pytest.mark.asyncio
async def test_get_tool_metadata_all():
    """Test getting all tool metadata."""

    @mcp_tool(name="meta_test", description="Metadata test")
    async def meta_test():
        """Tool for metadata testing."""
        return "result"

    metadata = await get_tool_metadata()
    assert isinstance(metadata, dict)
    assert "tools" in metadata or "meta_test" in str(metadata)


@pytest.mark.asyncio
async def test_get_tool_metadata_specific():
    """Test getting specific tool metadata."""

    @mcp_tool(name="specific_meta", description="Specific metadata")
    async def specific_meta():
        """Specific tool."""
        return "specific"

    metadata = await get_tool_metadata("specific_meta")
    assert metadata is not None


@pytest.mark.asyncio
async def test_scan_for_tools_empty():
    """Test scanning empty module list."""
    await scan_for_tools([])
    # Should not crash


@pytest.mark.asyncio
async def test_tool_with_bool_param():
    """Test tool with boolean parameter."""

    @mcp_tool(name="bool_tool", description="Takes bool")
    async def bool_tool(enabled: bool = True) -> str:
        """
        Boolean test.

        Args:
            enabled: Whether enabled
        """
        return "yes" if enabled else "no"

    result = await execute_tool("bool_tool", enabled=False)
    assert result == "no"


@pytest.mark.asyncio
async def test_tool_with_int_param():
    """Test tool with integer parameter."""

    @mcp_tool(name="int_tool", description="Takes int")
    async def int_tool(count: int) -> int:
        """
        Integer test.

        Args:
            count: Number to process
        """
        return count * 2

    result = await execute_tool("int_tool", count=5)
    assert result == 10


@pytest.mark.asyncio
async def test_tool_with_float_param():
    """Test tool with float parameter."""

    @mcp_tool(name="float_tool", description="Takes float")
    async def float_tool(value: float) -> float:
        """
        Float test.

        Args:
            value: Float value
        """
        return value * 1.5

    result = await execute_tool("float_tool", value=2.0)
    assert result == 3.0


@pytest.mark.asyncio
async def test_tool_with_multiple_params():
    """Test tool with multiple parameter types."""

    @mcp_tool(name="multi_tool", description="Multiple params")
    async def multi_tool(
        text: str, count: int = 1, enabled: bool = True, tags: List[str] = None
    ) -> Dict[str, Any]:
        """
        Multiple parameter test.

        Args:
            text: Text input
            count: Repeat count
            enabled: Whether enabled
            tags: Optional tags
        """
        return {"text": text, "count": count, "enabled": enabled, "tags": tags or []}

    result = await execute_tool("multi_tool", text="hello", count=3, enabled=False, tags=["a", "b"])
    assert result["text"] == "hello"
    assert result["count"] == 3
    assert result["enabled"] is False
    assert result["tags"] == ["a", "b"]


@pytest.mark.asyncio
async def test_tool_with_no_docstring():
    """Test tool without docstring."""

    @mcp_tool(name="no_doc", description="No docstring")
    async def no_doc(value: int):
        return value + 1

    result = await execute_tool("no_doc", value=10)
    assert result == 11


@pytest.mark.asyncio
async def test_tool_with_complex_return():
    """Test tool with complex return type."""

    @mcp_tool(name="complex_return", description="Complex return")
    async def complex_return() -> Dict[str, List[int]]:
        """Returns complex structure."""
        return {"numbers": [1, 2, 3], "values": [4, 5, 6]}

    result = await execute_tool("complex_return")
    assert "numbers" in result
    assert "values" in result


@pytest.mark.asyncio
async def test_tool_registry_persistence():
    """Test that tools remain in registry."""

    @mcp_tool(name="persist_test", description="Persistence test")
    async def persist_test():
        return "persistent"

    # Tool should be in registry
    assert "persist_test" in TOOLS_REGISTRY

    # Execute it
    result = await execute_tool("persist_test")
    assert result == "persistent"

    # Should still be in registry
    assert "persist_test" in TOOLS_REGISTRY
