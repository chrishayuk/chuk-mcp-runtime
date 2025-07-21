#!/usr/bin/env python3
"""
Debug script to test the streaming tool in isolation
"""

import asyncio
import inspect
import sys
import os

# Add the project root to sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.common.mcp_tool_decorator import (
    mcp_tool,
    TOOLS_REGISTRY,
    initialize_tool_registry,
)


@mcp_tool(name="echo_stream", description="Echo words live", timeout=10)
async def echo_stream(text: str, delay: float = 0.20):
    """
    Echo words with a delay between each word.

    Args:
        text: The text to echo word by word
        delay: Delay between words in seconds
    """
    for word in text.split():
        await asyncio.sleep(delay)
        yield {"delta": word + " "}


async def test_streaming_tool():
    """Test the streaming tool directly"""
    print("Testing streaming tool directly...")

    # Initialize the tool registry
    await initialize_tool_registry()

    # Get the tool from registry
    tool_func = TOOLS_REGISTRY.get("echo_stream")
    if not tool_func:
        print("ERROR: Tool not found in registry")
        return

    print(f"Tool function: {tool_func}")
    print(f"Tool function type: {type(tool_func)}")
    print(f"Is async gen function: {inspect.isasyncgenfunction(tool_func)}")

    # Test calling the tool
    try:
        print("\n1. Testing direct call...")
        result = tool_func(text="Hello world", delay=0.1)
        print(f"Direct call result type: {type(result)}")
        print(f"Is async generator: {inspect.isasyncgen(result)}")

        if inspect.isasyncgen(result):
            print("\n2. Testing async iteration...")
            chunk_count = 0
            async for chunk in result:
                chunk_count += 1
                print(f"Chunk {chunk_count}: {chunk}")
            print(f"Total chunks: {chunk_count}")
        else:
            print("ERROR: Result is not an async generator!")

    except Exception as e:
        print(f"ERROR testing tool: {e}")
        import traceback

        traceback.print_exc()


async def test_original_function():
    """Test the original function before decoration"""
    print("\nTesting original function...")

    async def original_echo_stream(text: str, delay: float = 0.20):
        for word in text.split():
            await asyncio.sleep(delay)
            yield {"delta": word + " "}

    print(f"Original function type: {type(original_echo_stream)}")
    print(f"Is async gen function: {inspect.isasyncgenfunction(original_echo_stream)}")

    result = original_echo_stream(text="Hello world", delay=0.1)
    print(f"Original result type: {type(result)}")
    print(f"Is async generator: {inspect.isasyncgen(result)}")

    if inspect.isasyncgen(result):
        chunk_count = 0
        async for chunk in result:
            chunk_count += 1
            print(f"Original chunk {chunk_count}: {chunk}")
        print(f"Original total chunks: {chunk_count}")


if __name__ == "__main__":
    asyncio.run(test_original_function())
    asyncio.run(test_streaming_tool())
