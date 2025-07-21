# chuk_mcp_runtime/main.py
"""
Main entry point for the CHUK MCP Runtime.

This module provides a simple entry point for running the CHUK MCP Runtime
with both local tools and proxy support.
"""

from chuk_mcp_runtime.entry import main

if __name__ == "__main__":
    # Launch the runtime with both local tools and proxy support
    main()
