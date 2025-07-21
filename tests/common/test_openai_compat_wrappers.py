# tests/test_openai_compat_wrappers.py
"""
OpenAI-compat wrapper bootstrap test.

We register a tool using dot notation (``wikipedia.search``), then run
``initialize_openai_compatibility()`` and verify that an underscore
alias (``wikipedia_search``) appears and behaves identically.
"""

from __future__ import annotations

import types
import sys
import pytest

from chuk_mcp_runtime.common.mcp_tool_decorator import (
    TOOLS_REGISTRY,
    mcp_tool,
    initialize_tool_registry,
)
from chuk_mcp_runtime.common.openai_compatibility import (
    initialize_openai_compatibility,
)
from chuk_mcp_runtime.common.tool_naming import update_naming_maps


# ── registry isolation ──────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(TOOLS_REGISTRY)
    TOOLS_REGISTRY.clear()
    yield
    TOOLS_REGISTRY.clear()
    TOOLS_REGISTRY.update(saved)
    update_naming_maps()


# ── safe stub for ToolRegistryProvider (awaitable) ───────────────────────
@pytest.fixture(autouse=True)
def _stub_toolregistryprovider(monkeypatch):
    class FakeRegistry:
        async def register_tool(self, *, tool, name, namespace, metadata):
            return None

        async def list_tools(self):
            return []

        async def get_tool(self, name, namespace):
            return None

        async def get_metadata(self, name, namespace):
            return None

    async def get_registry():
        return FakeRegistry()

    fake_mod = types.ModuleType("chuk_tool_processor.registry")
    fake_mod.ToolRegistryProvider = type(
        "TP", (), {"get_registry": staticmethod(get_registry)}
    )

    sys.modules.setdefault(
        "chuk_tool_processor", types.ModuleType("chuk_tool_processor")
    )
    sys.modules["chuk_tool_processor.registry"] = fake_mod
    monkeypatch.setitem(
        sys.modules["chuk_mcp_runtime.common.openai_compatibility"].__dict__,
        "ToolRegistryProvider",
        fake_mod.ToolRegistryProvider,
    )
    yield


# ── actual test ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dot_to_underscore_alias_creation():
    # 1) register a dot-notation tool
    @mcp_tool(name="wikipedia.search", description="dummy")
    async def dummy_tool(query: str):
        return f"dummy:{query}"

    await initialize_tool_registry()

    assert "wikipedia.search" in TOOLS_REGISTRY
    assert "wikipedia_search" not in TOOLS_REGISTRY

    # 2) run wrapper bootstrap
    await initialize_openai_compatibility()

    assert "wikipedia_search" in TOOLS_REGISTRY

    # 3) ensure alias delegates to original
    dot_result = await TOOLS_REGISTRY["wikipedia.search"](query="LLM")
    under_result = await TOOLS_REGISTRY["wikipedia_search"](query="LLM")
    assert dot_result == under_result == "dummy:LLM"
