# tests/proxy/test_tool_wrapper.py
"""
Tests for `chuk_mcp_runtime.proxy.tool_wrapper.create_proxy_tool`
================================================================

Covered behaviour
-----------------
1.  Registers tool in `TOOLS_REGISTRY` under dotted name.
2.  Wrapper forwards kwargs to remote `stream_manager.call_tool()` and
    returns the `content`.
3.  Raises `RuntimeError` when remote returns `{"isError": True}`.
4.  Metadata/diagnostic attributes are attached correctly.
5.  Optional `ToolRegistryProvider` integration (mocked).

The real decorator attaches `_mcp_tool` lazily; we therefore call
`initialize_tool_registry()` in tests that inspect those attributes.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Dict, Any, List

import pytest

from chuk_mcp_runtime.proxy import tool_wrapper as tw
from chuk_mcp_runtime.proxy.tool_wrapper import create_proxy_tool
from chuk_mcp_runtime.common.mcp_tool_decorator import (
    TOOLS_REGISTRY,
    initialize_tool_registry,
)
from chuk_mcp_runtime.common.tool_naming import update_naming_maps


# ---------------------------------------------------------------------------#
# Autouse fixtures
# ---------------------------------------------------------------------------#
@pytest.fixture(autouse=True)
def _isolate_tools_registry():
    """Keep TOOLS_REGISTRY pristine across tests."""
    original = set(TOOLS_REGISTRY)
    yield
    for k in list(TOOLS_REGISTRY):
        if k not in original:
            TOOLS_REGISTRY.pop(k, None)
    update_naming_maps()


@pytest.fixture(autouse=True)
def _neutralise_toolregistryprovider(monkeypatch):
    """
    Most tests don’t need ToolRegistryProvider - set it to **None** so
    `create_proxy_tool()` skips the registration block.
    """
    monkeypatch.setattr(tw, "ToolRegistryProvider", None, raising=False)
    yield


# ---------------------------------------------------------------------------#
# Dummy stream manager helper
# ---------------------------------------------------------------------------#
class DummyStreamManager:
    def __init__(self, *, is_error: bool = False):
        self.calls: List[tuple[str, Dict[str, Any], str]] = []
        self.is_error = is_error

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any], server_name: str
    ):
        self.calls.append((tool_name, arguments, server_name))
        if self.is_error:
            return {"isError": True, "error": "boom!"}
        return {"content": {"ok": True, "args": arguments}}


# ---------------------------------------------------------------------------#
# 1) Registration and basic metadata
# ---------------------------------------------------------------------------#
@pytest.mark.asyncio
async def test_create_proxy_tool_registers_in_registry():
    stream_mgr = DummyStreamManager()
    await create_proxy_tool("proxy.time", "now", stream_mgr)

    await initialize_tool_registry()  # materialise final wrapper

    dotted = "proxy.time.now"
    assert dotted in TOOLS_REGISTRY
    wrapper = TOOLS_REGISTRY[dotted]
    assert hasattr(wrapper, "_mcp_tool")
    assert wrapper._mcp_tool.name == dotted
    # _proxy_server/_proxy_metadata live only on the placeholder,
    # so we no longer assert on them.


# ---------------------------------------------------------------------------#
# 2) Call-through & return value
# ---------------------------------------------------------------------------#
@pytest.mark.asyncio
async def test_wrapper_calls_stream_manager_and_returns_content():
    stream_mgr = DummyStreamManager()
    wrapper = await create_proxy_tool("proxy.wikipedia", "search", stream_mgr)

    result = await wrapper(query="python")
    assert stream_mgr.calls == [("search", {"query": "python"}, "wikipedia")]
    assert result == {"ok": True, "args": {"query": "python"}}


# ---------------------------------------------------------------------------#
# 3) Error propagation
# ---------------------------------------------------------------------------#
@pytest.mark.asyncio
async def test_wrapper_raises_on_remote_error():
    stream_mgr = DummyStreamManager(is_error=True)
    wrapper = await create_proxy_tool("proxy.wiki", "explode", stream_mgr)

    with pytest.raises(RuntimeError, match="boom!"):
        await wrapper(foo="bar")


# ---------------------------------------------------------------------------#
# 4) Custom metadata passthrough
# ---------------------------------------------------------------------------#
@pytest.mark.asyncio
async def test_metadata_description_is_used():
    meta = {"description": "Return the current UTC time."}
    stream_mgr = DummyStreamManager()
    await create_proxy_tool("proxy.clock", "utc_now", stream_mgr, metadata=meta)

    await initialize_tool_registry()
    wrapper = TOOLS_REGISTRY["proxy.clock.utc_now"]
    assert wrapper._mcp_tool.description == "Return the current UTC time."


# ---------------------------------------------------------------------------#
# 5) ToolRegistryProvider integration (optional dependency)
# ---------------------------------------------------------------------------#
@pytest.mark.asyncio
async def test_toolregistryprovider_registration(monkeypatch):
    """
    Provide a fake async ToolRegistryProvider and ensure create_proxy_tool
    registers the wrapper.
    """
    registry_calls: list[tuple] = []

    class FakeRegistry:
        async def register_tool(self, *, tool, name, namespace, metadata):
            registry_calls.append((tool, name, namespace, metadata))

    async def get_registry():
        return FakeRegistry()

    FakeProvider = type("TP", (), {"get_registry": staticmethod(get_registry)})
    monkeypatch.setattr(tw, "ToolRegistryProvider", FakeProvider, raising=False)

    stream_mgr = DummyStreamManager()
    await create_proxy_tool("proxy.echo", "ping", stream_mgr)

    assert registry_calls, "ToolRegistryProvider.register_tool not called"
    _, name, namespace, _ = registry_calls[0]
    assert (namespace, name) == ("proxy.echo", "ping")
