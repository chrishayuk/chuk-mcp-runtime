# tests/proxy/test_tool_wrapper_coverage.py
"""
Additional tests to improve tool_wrapper coverage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chuk_mcp_runtime.proxy.tool_wrapper import _tp_register, create_proxy_tool


@pytest.mark.asyncio
async def test_tp_register_with_no_register_tool_method():
    """Test _tp_register when registry doesn't have register_tool method."""
    # Create a mock registry without register_tool
    fake_registry = MagicMock(spec=[])  # No methods

    # Should not raise, just return early
    await _tp_register(
        fake_registry, name="test_tool", namespace="test", tool=lambda: None, metadata={}
    )
    # No assertions needed - just checking it doesn't crash


@pytest.mark.asyncio
async def test_tp_register_with_exception():
    """Test _tp_register when registry.register_tool raises exception."""
    # Create a mock registry that raises an exception
    fake_registry = MagicMock()
    fake_registry.register_tool = AsyncMock(side_effect=ValueError("Registration failed"))

    # Should catch the exception and log it (not raise)
    await _tp_register(
        fake_registry, name="test_tool", namespace="test", tool=lambda: None, metadata={}
    )
    # Should have attempted to call register_tool
    fake_registry.register_tool.assert_called_once()


@pytest.mark.asyncio
async def test_create_proxy_tool_basic():
    """Test basic create_proxy_tool functionality."""
    # Mock the stream manager
    mock_manager = MagicMock()
    mock_manager.call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": "result"}]}
    )

    # Mock metadata
    mock_metadata = {"name": "test_tool", "description": "Test", "inputSchema": {}}

    # Create tool without registry provider
    with patch("chuk_mcp_runtime.proxy.tool_wrapper.ToolRegistryProvider", None):
        tool = await create_proxy_tool(
            namespace="proxy",
            tool_name="test_tool",
            stream_manager=mock_manager,
            metadata=mock_metadata,
        )

        # Tool should be callable
        assert callable(tool)

        # Call the tool
        result = await tool()
        assert result == [{"type": "text", "text": "result"}]
