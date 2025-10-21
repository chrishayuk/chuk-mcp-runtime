#!/usr/bin/env python3
"""
Debug script to test server execution flow for streaming tools
"""

import asyncio
import inspect
import os
import sys
import time

# Add the project root to sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from chuk_mcp_runtime.common.mcp_tool_decorator import (
    TOOLS_REGISTRY,
    initialize_tool_registry,
    mcp_tool,
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


async def simulate_server_execution():
    """Simulate how the server executes tools"""
    print("Simulating server execution...")

    # Initialize the tool registry
    await initialize_tool_registry()

    # Get the tool from registry
    tool_name = "echo_stream"
    func = TOOLS_REGISTRY.get(tool_name)
    if not func:
        print("ERROR: Tool not found in registry")
        return

    arguments = {"text": "Hello streaming world!", "delay": 0.1}
    timeout = 60.0

    print(f"Tool function: {func}")
    print(f"Is async gen function: {inspect.isasyncgenfunction(func)}")

    # Simulate the server's _execute_tool_with_timeout method
    try:
        print("\n=== Simulating _execute_tool_with_timeout ===")

        if inspect.isasyncgenfunction(func):
            print("Detected async generator function")

            # This is similar to what your server does
            agen = func(**arguments)
            print(f"Created async generator: {type(agen)}")
            print(f"Is async generator: {inspect.isasyncgen(agen)}")

            start = time.time()

            async def _streaming_wrapper():
                try:
                    chunk_count = 0
                    async for chunk in agen:
                        chunk_count += 1
                        print(f"Wrapper yielding chunk {chunk_count}: {chunk}")
                        # Check timeout on each chunk
                        if (time.time() - start) >= timeout:
                            await agen.aclose()
                            raise asyncio.TimeoutError(f"Streaming tool '{tool_name}' timed out")
                        yield chunk
                except Exception as e:
                    print(f"Error in streaming wrapper: {e}")
                    try:
                        await agen.aclose()
                    except Exception:
                        pass
                    raise e

            result = _streaming_wrapper()
            print(f"Wrapper result type: {type(result)}")
            print(f"Wrapper is async generator: {inspect.isasyncgen(result)}")

        else:
            print("Regular coroutine function")
            result = await asyncio.wait_for(func(**arguments), timeout=timeout)

        # Now simulate what happens in call_tool
        print("\n=== Simulating call_tool handling ===")

        if inspect.isasyncgen(result):
            print("Result is async generator, setting up content streaming")

            async def _to_content():
                try:
                    chunk_count = 0
                    async for part in result:
                        chunk_count += 1
                        print(f"Content processing chunk {chunk_count}: {part}")

                        # Simulate TextContent creation
                        if isinstance(part, dict) and "delta" in part:
                            content = {"type": "text", "text": part["delta"]}
                            print(f"Created TextContent: {content}")
                            yield content
                        else:
                            content = {"type": "text", "text": str(part)}
                            print(f"Created TextContent from other: {content}")
                            yield content

                    print(f"Content streaming completed, processed {chunk_count} chunks")
                except Exception as e:
                    print(f"Error in content streaming: {e}")
                    import traceback

                    traceback.print_exc()
                    yield {"type": "text", "text": f"Streaming error: {str(e)}"}

            content_generator = _to_content()
            print(f"Content generator type: {type(content_generator)}")
            print(f"Content generator is async gen: {inspect.isasyncgen(content_generator)}")

            # Try to consume it
            print("\n=== Consuming content generator ===")
            final_chunks = []
            async for content_chunk in content_generator:
                print(f"Final content chunk: {content_chunk}")
                final_chunks.append(content_chunk)

            print(f"Total final chunks: {len(final_chunks)}")

        else:
            print("Result is not async generator")
            print(f"Result: {result}")

    except Exception as e:
        print(f"ERROR in simulation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simulate_server_execution())
