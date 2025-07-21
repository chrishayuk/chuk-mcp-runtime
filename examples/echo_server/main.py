#!/usr/bin/env python
# examples/openai_compatibility_demo.py
"""
OpenAI compatibility demo with manual tool registration - demonstrates both dot notation
and OpenAI-compatible underscore notation tool registration.

This script:
1. Creates a proper configuration file with correct paths
2. Boots proxy servers with OpenAI compatibility enabled
3. Shows detailed debugging info about the proxy servers and tool registration
4. Manually registers tools to demonstrate OpenAI compatibility
5. Shows all registered tools (both dot and underscore variants)
6. Demonstrates using both naming styles
7. Shows what the OpenAI-compatible tool definitions would look like

To run:
    cd /path/to/chuk-mcp-runtime
    uv run examples/openai_compatibility_demo.py
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any
import tempfile

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("openai_compatibility_demo")

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Import the necessary modules
from chuk_mcp_runtime.server.config_loader import load_config, find_project_root
from chuk_mcp_runtime.proxy.manager import ProxyServerManager
from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY, mcp_tool

# Try to import OpenAI compatibility and ToolRegistryProvider
try:
    from chuk_mcp_runtime.common.openai_compatibility import OpenAIToolsAdapter
    from chuk_tool_processor.registry import ToolRegistryProvider
except ImportError as e:
    logger.error(f"Import error: {e}")
    ToolRegistryProvider = None
    OpenAIToolsAdapter = None

# Path to the example config template
CONFIG_TEMPLATE = os.path.join(
    os.path.dirname(__file__), "openai_compatible_config.yaml"
)


# Create a config file with correct paths
def create_test_config():
    # Check if the template exists
    if os.path.exists(CONFIG_TEMPLATE):
        with open(CONFIG_TEMPLATE, "r") as f:
            config_content = f.read()
    else:
        # Create config from scratch if template doesn't exist
        config_content = """
# examples/openai_compatible_config.yaml
proxy:
  enabled: true
  namespace: "proxy"
  openai_compatible: true  # Enable OpenAI compatibility
  keep_root_aliases: true  # Keep both dot and underscore formats available

mcp_servers:
  echo:
    type: "stdio" 
    command: "python"
    args: ["examples/echo_server/main.py"]  # Use full path from project root
"""

    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    logger.info(f"Created config at {temp_path} with content:\n{config_content}")
    return temp_path


# Class to track registered tools for the demo
class ToolTracker:
    def __init__(self):
        self.dot_tools = []
        self.underscore_tools = []
        self.all_tools = {}

    def register_tool(self, name, func):
        """Register a tool in the tracker."""
        self.all_tools[name] = func
        if "." in name:
            self.dot_tools.append(name)
        elif "_" in name:
            self.underscore_tools.append(name)


# Manually register tools for the demo
def register_demo_tools() -> ToolTracker:
    """Manually register tools for the demo to demonstrate OpenAI compatibility."""
    tracker = ToolTracker()

    # Clear existing registry if needed
    # TOOLS_REGISTRY.clear()

    # Register the dot notation tool
    @mcp_tool(
        name="proxy.echo.echo", description="Echo back a message (dot notation version)"
    )
    async def echo_tool(message: str = "Hello"):
        """Echo back the provided message."""
        return {"message": f"Echo: {message}"}

    tracker.register_tool("proxy.echo.echo", echo_tool)

    # Register the OpenAI-compatible underscore version
    @mcp_tool(
        name="proxy_echo_echo",
        description="Echo back a message (OpenAI-compatible version)",
    )
    async def echo_tool_openai(message: str = "Hello"):
        """OpenAI-compatible echo tool."""
        return {"message": f"Echo (OpenAI version): {message}"}

    tracker.register_tool("proxy_echo_echo", echo_tool_openai)

    return tracker


async def main() -> None:
    # Print information about paths and environment
    logger.info(f"Script location: {__file__}")
    logger.info(f"Project root: {ROOT}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current directory: {os.getcwd()}")

    # Create the config file
    config_path = create_test_config()

    try:
        # Load configuration
        config = load_config([config_path])
        logger.info(f"Loaded config: {json.dumps(config, indent=2, default=str)}")

        # Ensure OpenAI compatibility is enabled
        config.setdefault("proxy", {})["openai_compatible"] = True
        config.setdefault("proxy", {})["keep_root_aliases"] = True

        # Print MCP servers from config
        logger.info(
            f"MCP servers in config: {list(config.get('mcp_servers', {}).keys())}"
        )

        # Check if the echo server main.py exists
        echo_server_main = os.path.join(ROOT, "examples", "echo_server", "main.py")
        if not os.path.exists(echo_server_main):
            logger.error(f"Echo server main.py not found: {echo_server_main}")
            print(f"⚠️ Echo server main.py not found: {echo_server_main}")
            return

        # Make the script executable just to be sure
        try:
            os.chmod(echo_server_main, 0o755)  # Set executable permissions
            logger.info(f"Made {echo_server_main} executable")
        except Exception as e:
            logger.warning(
                f"Could not set executable permissions on {echo_server_main}: {e}"
            )

        # 1. Start the proxy manager
        print("\n🚀 Starting proxy servers with OpenAI compatibility...\n")
        project_root = find_project_root()
        logger.info(f"Project root: {project_root}")

        proxy = ProxyServerManager(config, project_root)

        # Print initial state
        logger.info(f"Initial TOOLS_REGISTRY: {list(TOOLS_REGISTRY.keys())}")

        # Start the proxy
        try:
            await proxy.start_servers()
        except Exception as e:
            logger.error(f"Error starting proxy servers: {e}", exc_info=True)
            print(f"⚠️ Error starting proxy servers: {e}")

        try:
            # Print running servers
            logger.info(f"Running servers: {list(proxy.running_servers.keys())}")
            print(
                f"Running servers: {', '.join(proxy.running_servers.keys()) or 'None'}"
            )

            # 2. Get all tools from the proxy manager
            all_tools = proxy.get_all_tools()
            logger.info(f"All tools from proxy: {list(all_tools.keys())}")
            print(f"Found {len(all_tools)} tools from proxy.get_all_tools()")

            # Manually register tools for demonstration
            print("\n📝 Manually registering tools for demonstration...")
            tool_tracker = register_demo_tools()
            print(f"Registered {len(tool_tracker.all_tools)} demo tools")

            # 3. Display TOOLS_REGISTRY contents after manual registration
            logger.info(
                f"TOOLS_REGISTRY after registration: {list(TOOLS_REGISTRY.keys())}"
            )
            print(f"TOOLS_REGISTRY has {len(TOOLS_REGISTRY)} registered tools")

            # 4. Try to get ToolRegistryProvider if available
            if ToolRegistryProvider:
                registry = ToolRegistryProvider.get_registry()
                tool_list = list(registry.list_tools())
                logger.info(f"ToolRegistryProvider tools: {tool_list}")
                print(f"ToolRegistryProvider has {len(tool_list)} registered tools")

                # Use the tool tracker for display
                print("\n📋 Registered Tools:")
                print("\n🔹 Dot notation tools (original):")
                for tool in sorted(tool_tracker.dot_tools):
                    print(f"  • {tool}")

                print("\n🔹 Underscore notation tools (OpenAI-compatible):")
                for tool in sorted(tool_tracker.underscore_tools):
                    print(f"  • {tool}")
            else:
                logger.warning("ToolRegistryProvider not available")
                print("⚠️ ToolRegistryProvider not available")

            # 5. Display all manually registered tools
            print(f"\n🔧 Demo tools available: {len(tool_tracker.all_tools)}")
            for name in sorted(tool_tracker.all_tools.keys()):
                print(f"  • {name}")

            # 6. Try to execute a tool
            print("\n🧪 Testing tool execution:")
            try:
                # Test the dot notation tool
                dot_tool = TOOLS_REGISTRY.get("proxy.echo.echo")
                if dot_tool:
                    print(f"  • Testing dot notation tool: proxy.echo.echo")
                    result = dot_tool(message="Hello, dot notation!")
                    if hasattr(result, "__await__"):
                        result = await result
                    print(f"  • Result: {result}")

                # Test the underscore notation tool
                underscore_tool = TOOLS_REGISTRY.get("proxy_echo_echo")
                if underscore_tool:
                    print(f"  • Testing underscore notation tool: proxy_echo_echo")
                    result = underscore_tool(message="Hello, underscore notation!")
                    if hasattr(result, "__await__"):
                        result = await result
                    print(f"  • Result: {result}")

            except Exception as e:
                logger.error(f"Error executing tool: {e}", exc_info=True)
                print(f"  • ⚠️ Error executing tool: {e}")

            # 7. Generate OpenAI-compatible tool definitions if adapter is available
            if OpenAIToolsAdapter:
                try:
                    adapter = OpenAIToolsAdapter()
                    openai_tools = adapter.get_openai_tools_definition()

                    print(
                        f"\n📑 OpenAI-compatible tool definitions ({len(openai_tools)}):"
                    )
                    for i, tool in enumerate(openai_tools):
                        print(f"  Tool {i+1}: {tool['function']['name']}")
                        print(f"  Description: {tool['function']['description']}")
                except Exception as e:
                    logger.error(
                        f"Error generating OpenAI tool definitions: {e}", exc_info=True
                    )
                    print(f"⚠️ Error generating OpenAI tool definitions: {e}")

            print("\n✨ Demo complete!")

        except Exception as e:
            logger.error(f"Error during demo: {e}", exc_info=True)
            print(f"⚠️ Error during demo: {e}")
        finally:
            # Stop the proxy server
            try:
                await proxy.stop_servers()
                print("\n🛑 Proxy servers stopped.")
            except Exception as e:
                logger.error(f"Error stopping proxy servers: {e}", exc_info=True)
                print(f"⚠️ Error stopping proxy servers: {e}")
    finally:
        # Clean up temporary config
        try:
            os.unlink(config_path)
            logger.info(f"Removed temporary config file {config_path}")
        except Exception as e:
            logger.error(f"Error removing config file: {e}")


if __name__ == "__main__":
    asyncio.run(main())
