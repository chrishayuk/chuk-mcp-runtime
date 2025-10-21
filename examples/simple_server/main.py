# examples/simple_server/main.py
"""
Example MCP Server Implementation

This demonstrates how to use the MCP runtime to create a simple server.
"""

import asyncio
import os
import sys
from typing import Any, Dict

# Add the parent directory to sys.path to import chuk_mcp_runtime
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.config_loader import load_config
from chuk_mcp_runtime.server.logging_config import configure_logging, get_logger
from chuk_mcp_runtime.server.server import MCPServer


# Define a simple tool using the decorator
@mcp_tool(name="echo", description="Echo back the input message")
def echo_tool(message: str) -> Dict[str, Any]:
    """
    Echo back the input message.

    Args:
        message: The message to echo.

    Returns:
        Dictionary with the echoed message.
    """
    return {"echo": message}


@mcp_tool(name="add", description="Add two numbers")
def add_tool(a: int, b: int) -> Dict[str, Any]:
    """
    Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        Dictionary with the sum.
    """
    return {"sum": a + b}


@mcp_tool(name="greet", description="Generate a greeting message")
def greet_tool(name: str, formal: bool = False) -> str:
    """
    Generate a greeting message.

    Args:
        name: Name to greet.
        formal: Whether to use a formal greeting.

    Returns:
        Greeting message.
    """
    if formal:
        return f"Good day, {name}. It is a pleasure to meet you."
    else:
        return f"Hey {name}! How's it going?"


async def main():
    """Run the example server."""
    # Load configuration
    config_file = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = load_config([config_file])

    # Configure logging
    configure_logging(config)
    logger = get_logger("chuk_example_server")

    # Create a tools registry with our defined tools
    tools_registry = {"echo": echo_tool, "add": add_tool, "greet": greet_tool}

    # Initialize and run the server
    logger.info("Starting example CHUK MCP server")
    server = MCPServer(config, tools_registry=tools_registry)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
