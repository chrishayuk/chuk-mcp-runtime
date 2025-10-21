#!/usr/bin/env python
# examples/debug_registry_test.py
"""
debug_registry_test.py
--------------

A minimal test to identify the exact issue with tool registration.
"""

import asyncio


async def test_registry():
    """Test the registry with different approaches."""
    try:
        # Import the registry
        from chuk_tool_processor.registry import ToolRegistryProvider

        print("Successfully imported ToolRegistryProvider")

        # Get the registry
        registry = await ToolRegistryProvider.get_registry()
        print(f"Got registry instance: {type(registry).__name__}")

        # Create a simple tool
        class SimpleTool:
            @staticmethod
            async def execute(text: str = "Hello"):
                return f"Echo: {text}"

        # Try to register with different patterns
        print("\n=== Testing Different Registration Patterns ===")

        # Pattern 1: Tool only
        try:
            print("\nPattern 1: Tool only")
            await registry.register_tool(SimpleTool)
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Pattern 2: Tool and name
        try:
            print("\nPattern 2: Tool and name")
            await registry.register_tool(SimpleTool, "test_tool_2")
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Pattern 3: Tool, name, namespace
        try:
            print("\nPattern 3: Tool, name, namespace")
            await registry.register_tool(SimpleTool, "test_tool_3", "test")
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Pattern A: Named parameters - tool only
        try:
            print("\nPattern A: Named parameters - tool only")
            await registry.register_tool(tool=SimpleTool)
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Pattern B: Named parameters - tool and name
        try:
            print("\nPattern B: Named parameters - tool and name")
            await registry.register_tool(tool=SimpleTool, name="test_tool_B")
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Pattern C: Named parameters - tool, name, namespace
        try:
            print("\nPattern C: Named parameters - tool, name, namespace")
            await registry.register_tool(tool=SimpleTool, name="test_tool_C", namespace="test")
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Pattern D: Named parameters - all parameters
        try:
            print("\nPattern D: Named parameters - all parameters")
            await registry.register_tool(
                tool=SimpleTool,
                name="test_tool_D",
                namespace="test",
                metadata={"description": "Test tool"},
            )
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")

        # List all registered tools
        print("\n=== Registered Tools ===")
        tools = await registry.list_tools()
        for ns, name in tools:
            print(f"  • {ns}.{name}")

    except Exception as e:
        print(f"Error during test: {e}")


if __name__ == "__main__":
    asyncio.run(test_registry())
