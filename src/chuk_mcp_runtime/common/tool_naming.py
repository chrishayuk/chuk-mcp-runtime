# chuk_mcp_runtime/common/tool_naming.py
"""
Tool naming compatibility module for CHUK MCP Runtime.

This module provides functionality to handle different tool naming conventions,
allowing clients to use either dot notation or underscore notation regardless
of how tools are registered in the server.
"""

from typing import Dict

from chuk_mcp_runtime.common.mcp_tool_decorator import TOOLS_REGISTRY
from chuk_mcp_runtime.server.logging_config import get_logger

logger = get_logger("chuk_mcp_runtime.common.tool_naming")


class ToolNamingResolver:
    """
    Resolves tool names between different conventions (dot vs underscore).
    Allows clients to use either format regardless of how tools are registered.
    """

    def __init__(self):
        """Initialize the tool naming resolver."""
        self.dot_to_underscore_map: Dict[str, str] = {}
        self.underscore_to_dot_map: Dict[str, str] = {}
        self.update_maps()

    def update_maps(self):
        """Update the internal maps based on the current TOOLS_REGISTRY."""
        # Clear existing maps
        self.dot_to_underscore_map.clear()
        self.underscore_to_dot_map.clear()

        # Build new maps
        for name in TOOLS_REGISTRY.keys():
            # For tools with dots (e.g., "proxy.wikipedia.search")
            if "." in name:
                # Get the last part after the last dot
                short_name = name.split(".")[-1]
                # Create server name from parts before the last dot
                server_prefix = ".".join(name.split(".")[:-1])

                # Standard format: server.tool (wikipedia.search)
                std_name = f"{server_prefix.split('.')[-1]}.{short_name}" if server_prefix else name
                # Underscore format: server_tool (wikipedia_search)
                underscore_name = (
                    f"{server_prefix.split('.')[-1]}_{short_name}"
                    if server_prefix
                    else name.replace(".", "_")
                )

                self.dot_to_underscore_map[std_name] = underscore_name
                self.underscore_to_dot_map[underscore_name] = std_name

            # For tools with underscores (e.g., "wikipedia_search")
            elif "_" in name:
                # Try to split into server and tool parts
                parts = name.split("_", 1)
                if len(parts) == 2:
                    server, tool = parts
                    dot_name = f"{server}.{tool}"

                    self.dot_to_underscore_map[dot_name] = name
                    self.underscore_to_dot_map[name] = dot_name

        logger.debug(f"Updated tool naming maps with {len(self.dot_to_underscore_map)} entries")

    def resolve_tool_name(self, name: str) -> str:
        """
        Resoalve a tool name to its registered form in TOOLS_REGISTRY.

        Args:
            name: The tool name to resolve (can be dot or underscore notation)

        Returns:
            The resolved tool name that exists in TOOLS_REGISTRY, or the original name if not found
        """
        # If the name is already in the registry, return it
        if name in TOOLS_REGISTRY:
            return name

        # Try to convert from dot to underscore notation
        if "." in name:
            # Check if we have a direct mapping
            if name in self.dot_to_underscore_map:
                resolved = self.dot_to_underscore_map[name]
                if resolved in TOOLS_REGISTRY:
                    return resolved

            # Try converting directly
            underscore_name = name.replace(".", "_")
            if underscore_name in TOOLS_REGISTRY:
                return underscore_name

            # If it has more than one dot, try the last two parts only
            if name.count(".") > 1:
                parts = name.split(".")
                simple_name = f"{parts[-2]}.{parts[-1]}"
                if simple_name in self.dot_to_underscore_map:
                    resolved = self.dot_to_underscore_map[simple_name]
                    if resolved in TOOLS_REGISTRY:
                        return resolved

                # Try with underscore
                simple_underscore = simple_name.replace(".", "_")
                if simple_underscore in TOOLS_REGISTRY:
                    return simple_underscore

        # Try to convert from underscore to dot notation
        elif "_" in name:
            # Check if we have a direct mapping
            if name in self.underscore_to_dot_map:
                resolved = self.underscore_to_dot_map[name]
                if resolved in TOOLS_REGISTRY:
                    return resolved

            # Try converting directly
            dot_name = name.replace("_", ".")
            if dot_name in TOOLS_REGISTRY:
                return dot_name

        # If all else fails, try to find a partial match
        for registered_name in TOOLS_REGISTRY.keys():
            # If the last part matches (ignoring prefix)
            reg_parts = registered_name.replace("_", ".").split(".")
            name_parts = name.replace("_", ".").split(".")

            if reg_parts[-1] == name_parts[-1] and (
                len(reg_parts) > 1 and len(name_parts) > 1 and reg_parts[-2] == name_parts[-2]
            ):
                return registered_name

        # No match found, return the original name
        return name


# Create a global instance
resolver = ToolNamingResolver()


def resolve_tool_name(name: str) -> str:
    """
    Resolve a tool name to its registered form in TOOLS_REGISTRY.

    Args:
        name: The tool name to resolve (can be dot or underscore notation)

    Returns:
        The resolved tool name that exists in TOOLS_REGISTRY, or the original name if not found
    """
    return resolver.resolve_tool_name(name)


def update_naming_maps():
    """Update the tool naming maps based on the current TOOLS_REGISTRY."""
    resolver.update_maps()
