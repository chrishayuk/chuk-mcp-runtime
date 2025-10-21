# tests/common/test_mocks.py
"""
Common test mocks for CHUK MCP Runtime testing.

This module provides mock implementations used across multiple test files
to ensure consistent mocking behavior and avoid circular import issues.
"""

import asyncio
import json


# --- Async testing utilities ---
def run_async(coro):
    """Run an async coroutine in tests safely with a new event loop."""
    # Always create a new event loop to avoid 'already running' errors
    old_loop = None
    try:
        old_loop = asyncio.get_event_loop()
    except RuntimeError:
        pass

    # Create a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(coro)
    finally:
        # Clean up
        loop.close()
        if old_loop:
            asyncio.set_event_loop(old_loop)


class AsyncMock:
    """Mock class for async functions."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.call_count = 0
        self.call_args_list = []
        self.call_kwargs_list = []

    async def __call__(self, *args, **kwargs):
        self.call_count += 1
        self.call_args_list.append(args)
        self.call_kwargs_list.append(kwargs)
        return self.return_value


# --- Mock stream manager ---
class MockStreamManager:
    """Mock stream manager for testing proxy calls."""

    def __init__(self):
        self.call_history = []
        self.list_tools_results = {}

    async def list_tools(self, server_name):
        """Mock list_tools method."""
        self.call_history.append(("list_tools", server_name))
        return self.list_tools_results.get(server_name, [])

    async def call_tool(self, tool_name, arguments, server_name):
        """Mock call_tool method."""
        self.call_history.append(("call_tool", tool_name, arguments, server_name))
        return {
            "content": f"Mock response from {server_name}.{tool_name} with args {json.dumps(arguments)}",
            "isError": False,
        }

    async def close(self):
        """Mock close method."""
        self.call_history.append(("close",))
        return


# --- Mock server classes ---
class MockServerRegistry:
    """Mock server registry for testing."""

    def __init__(self, project_root, config):
        self.project_root = project_root
        self.config = config
        self.bootstrap_called = False

    async def load_server_components(self):
        """Nothing to load in tests."""
        self.bootstrap_called = True
        return {}


class MockMCPServer:
    """Mock MCP server for testing."""

    def __init__(self, config):
        self.config = config
        self.server_name = "mock-server"
        self.tools_registry = {}
        self.registered_tools = []
        self.serve_called = False

    async def register_tool(self, name, func):
        """Record registered tools."""
        self.registered_tools.append(name)
        self.tools_registry[name] = func

    async def serve(self, custom_handlers=None):
        """Record custom handlers and return."""
        self.serve_called = True
        self.custom_handlers = custom_handlers
        return


class DummyServerRegistry(MockServerRegistry):
    """Alias for MockServerRegistry."""

    pass


class DummyMCPServer(MockMCPServer):
    """Alias for MockMCPServer."""

    pass


# --- Mock proxy manager ---
class MockProxyServerManager:
    """Mock implementation for ProxyServerManager."""

    def __init__(self, config, project_root):
        self.config = config
        self.project_root = project_root

        # Extract required attributes from config
        proxy_config = config.get("proxy", {})
        self.enabled = proxy_config.get("enabled", False)
        self.ns_root = proxy_config.get("namespace", "proxy")
        self.openai_mode = proxy_config.get("openai_compatible", False)
        self.mcp_servers = config.get("mcp_servers", {})

        # Initialize state
        self.running = {}
        self.running_servers = {}  # Alias for compatibility with some tests
        self.stream_manager = None
        self.openai_wrappers = {}
        self.tools = {"proxy.test.tool": AsyncMock(return_value="Test result")}

    async def start_servers(self):
        """Mock start_servers implementation."""
        # Create running servers for each mcp_servers entry
        for server_name in self.mcp_servers or ["test"]:
            self.running[server_name] = {"wrappers": {}}
            self.running_servers[server_name] = {"wrappers": {}}

    async def stop_servers(self):
        """Mock stop_servers implementation."""
        self.running.clear()
        self.running_servers.clear()
        if self.stream_manager:
            await self.stream_manager.close()

    async def get_all_tools(self):
        """Mock get_all_tools implementation."""
        return self.tools

    async def call_tool(self, name, **kwargs):
        """Mock call_tool implementation with name resolution."""
        # Forward to stream manager if available
        if self.stream_manager:
            # Parse tool name
            server = "unknown"
            tool = name

            if "." in name:
                parts = name.split(".")
                if len(parts) >= 3 and parts[0] == self.ns_root:
                    server = parts[1]
                    tool = parts[2]
                elif len(parts) == 2:
                    server = parts[0]
                    tool = parts[1]
            elif "_" in name:
                parts = name.split("_", 1)
                server = parts[0]
                tool = parts[1] if len(parts) > 1 else "unknown"

            # Call the tool
            result = await self.stream_manager.call_tool(tool, kwargs, server)
            return result.get("content", f"Result from {server}.{tool}")

        # Simple mock response
        return f"Mock result from {name} with args {kwargs}"

    async def process_text(self, text):
        """Mock process_text implementation."""
        return [{"processed": True, "text": text}]


# --- Install our mock in the entry module ---
def install_mocks():
    """Install our mocks in the entry module and return the patched entry module."""
    try:
        import chuk_mcp_runtime.entry as entry

        # Install our mock class in the entry module
        entry.ProxyServerManager = MockProxyServerManager
        return entry
    except ImportError:
        # Return None if we can't import entry
        return None


# Auto-install when this module is imported
entry_module = install_mocks()
