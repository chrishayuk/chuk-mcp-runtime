#!/usr/bin/env python
# examples/inspect_registry.py
"""
inspect_registry.py
---------------------------

Inspect the API of the ToolRegistryProvider to determine the correct method signatures,
with improved error handling for the metadata parameter.
"""

import asyncio
import inspect
import sys
from typing import Any, Dict, List, Set


async def inspect_registry_api():
    """
    Inspect the API of the ToolRegistryProvider and display detailed information
    about the methods available for tool registration.
    """
    try:
        # Import the registry
        from chuk_tool_processor.registry import ToolRegistryProvider

        print("Successfully imported ToolRegistryProvider")

        # Get the registry
        registry = await ToolRegistryProvider.get_registry()
        print(f"Got registry instance: {type(registry).__name__}")

        # Display available methods
        methods = [
            attr
            for attr in dir(registry)
            if callable(getattr(registry, attr)) and not attr.startswith("_")
        ]
        print(f"\nAvailable public methods ({len(methods)}):")
        for method in sorted(methods):
            print(f"  • {method}")

        # Detailed info on registration methods
        registration_methods = [
            m
            for m in methods
            if any(term in m.lower() for term in ["register", "add", "create"])
        ]

        print(f"\nRegistration methods ({len(registration_methods)}):")
        for method_name in registration_methods:
            method = getattr(registry, method_name)
            sig = inspect.signature(method)
            is_async = inspect.iscoroutinefunction(method)

            print(f"\n  • {method_name}{'[async]' if is_async else ''}:")
            print(f"    Signature: {sig}")

            # Get parameter details
            param_details = []
            for name, param in sig.parameters.items():
                param_type = (
                    param.annotation
                    if param.annotation != inspect.Parameter.empty
                    else "Any"
                )
                default = (
                    ""
                    if param.default == inspect.Parameter.empty
                    else f" = {param.default}"
                )
                param_details.append(f"{name}: {param_type}{default}")

            print(f"    Parameters:")
            for detail in param_details:
                print(f"      - {detail}")

            if method.__doc__:
                doc = method.__doc__.strip()
                print(
                    f"    Docstring: {doc[:60]}..."
                    if len(doc) > 60
                    else f"    Docstring: {doc}"
                )

        # Check for tool listing methods
        listing_methods = [
            m
            for m in methods
            if any(term in m.lower() for term in ["list", "get_all", "find"])
        ]

        print(f"\nTool listing methods ({len(listing_methods)}):")
        for method_name in listing_methods:
            method = getattr(registry, method_name)
            sig = inspect.signature(method)
            is_async = inspect.iscoroutinefunction(method)

            print(f"  • {method_name}{'[async]' if is_async else ''}: {sig}")

        # Try to list tools as an example
        try:
            tools = await registry.list_tools()
            print(f"\nExisting tools: {len(tools)}")
            for ns, name in tools:
                try:
                    metadata = await registry.get_metadata(name, ns)
                    description = (
                        getattr(metadata, "description", "No description")
                        if metadata
                        else "No metadata"
                    )
                    print(f"  • {ns or 'default'}.{name}: {description}")
                except Exception as e:
                    print(f"  • {ns or 'default'}.{name}: Error getting metadata: {e}")
        except Exception as e:
            print(f"Error listing tools: {e}")

        # Test for a ProxyTool class example with proper error handling
        print("\nExample of creating a ProxyTool class:")

        class SampleProxyTool:
            """Sample proxy tool for testing."""

            @staticmethod
            async def execute(message: str = "Hello"):
                """Execute the sample tool."""
                return f"Echo: {message}"

        # Try to register the sample tool - using named parameters only
        try:
            # Check if register_tool exists
            if hasattr(registry, "register_tool"):
                sig = inspect.signature(registry.register_tool)
                print(f"Will try registry.register_tool with signature: {sig}")

                # Use named parameters only
                metadata_dict = {
                    "description": "Sample echo tool",
                    "tags": ["test", "echo"],
                }

                try:
                    # Try with all parameters named
                    print("Registering with all named parameters")
                    await registry.register_tool(
                        tool=SampleProxyTool,
                        name="sample_echo",
                        namespace="sample",
                        metadata=metadata_dict,
                    )
                    print("✅ Success! Registered tool with all named parameters")
                except Exception as e:
                    print(f"❌ Failed with all named parameters: {e}")

                    try:
                        # Try without metadata
                        print("Registering without metadata")
                        await registry.register_tool(
                            tool=SampleProxyTool,
                            name="sample_echo2",
                            namespace="sample",
                        )
                        print("✅ Success! Registered tool without metadata")
                    except Exception as e2:
                        print(f"❌ Failed without metadata: {e2}")

                        try:
                            # Try with minimal parameters
                            print("Registering with minimal parameters")
                            await registry.register_tool(
                                tool=SampleProxyTool, name="sample_echo3"
                            )
                            print("✅ Success! Registered tool with minimal parameters")
                        except Exception as e3:
                            print(f"❌ Failed with minimal parameters: {e3}")

            else:
                print("registry.register_tool not found")

        except Exception as e:
            print(f"Error registering sample tool: {e}")

        # List tools again to see what worked
        try:
            tools = await registry.list_tools()
            print(f"\nRegistered tools after test ({len(tools)}):")
            for ns, name in tools:
                print(f"  • {ns}.{name}")
        except Exception as e:
            print(f"Error listing tools: {e}")

    except Exception as e:
        print(f"Error during inspection: {e}")


if __name__ == "__main__":
    asyncio.run(inspect_registry_api())
