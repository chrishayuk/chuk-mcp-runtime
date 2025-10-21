#!/usr/bin/env python
# examples/debug_metadata_test.py
"""
debug_metadata_test.py
---------------

Test different metadata formats to find what the registry accepts.
"""

import asyncio
from dataclasses import dataclass
from typing import List


async def test_metadata_formats():
    """Test different metadata formats with the registry."""

    print("=== Testing Metadata Formats ===\n")

    try:
        # Import the registry
        from chuk_tool_processor.registry import ToolRegistryProvider

        print("Successfully imported ToolRegistryProvider")

        # Get the registry
        registry = await ToolRegistryProvider.get_registry()
        print(f"Got registry instance: {type(registry).__name__}")

        # Create a simple tool class
        class SimpleTool:
            @staticmethod
            async def execute(message: str = "Hello"):
                return f"Echo: {message}"

        # Test different metadata formats
        test_cases = [
            ("None", None),
            ("Empty Dict", {}),
            ("Dict with description", {"description": "Test tool"}),
            ("Dict with tags", {"description": "Test tool", "tags": ["test"]}),
            (
                "Object with attributes",
                type("MetadataObj", (), {"description": "Test tool", "tags": ["test"]}),
            ),
        ]

        # Also create a dataclass
        @dataclass
        class ToolMetadata:
            description: str
            tags: List[str] = None

            def __post_init__(self):
                if self.tags is None:
                    self.tags = ["test"]

        test_cases.append(("Dataclass", ToolMetadata(description="Test tool")))

        # Try registering with each format
        for i, (name, metadata) in enumerate(test_cases):
            tool_name = f"test_tool_{i}"
            namespace = "metadata_test"

            try:
                print(f"\nTrying format: {name}")
                print(f"Metadata: {metadata}")

                await registry.register_tool(
                    tool=SimpleTool,
                    name=tool_name,
                    namespace=namespace,
                    metadata=metadata,
                )

                print(f"✅ Success! Registered tool with {name} metadata")

                # Check if we can retrieve the metadata
                try:
                    retrieved_metadata = await registry.get_metadata(tool_name, namespace)
                    print(f"Retrieved metadata: {retrieved_metadata}")

                    # Check attributes
                    if hasattr(retrieved_metadata, "description"):
                        print(f"  description: {retrieved_metadata.description}")
                    if hasattr(retrieved_metadata, "tags"):
                        print(f"  tags: {retrieved_metadata.tags}")
                except Exception as e:
                    print(f"Error retrieving metadata: {e}")

            except Exception as e:
                print(f"❌ Failed to register with {name} metadata: {e}")

        # List all tools to verify registration
        tools = await registry.list_tools()
        print(f"\nRegistered tools ({len(tools)}):")
        for ns, name in tools:
            print(f"  • {ns}.{name}")

    except Exception as e:
        print(f"Error during testing: {e}")


if __name__ == "__main__":
    asyncio.run(test_metadata_formats())
