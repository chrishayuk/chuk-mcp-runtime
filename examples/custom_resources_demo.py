#!/usr/bin/env python3
"""
Custom Resources Demo - @mcp_resource Decorator

Demonstrates how to create custom MCP resources using the @mcp_resource decorator.
Custom resources provide read-only access to application data, configuration,
system information, or any other data source.

Features:
- Static resources (fixed URIs)
- Dynamic resources (computed on-demand)
- Text and binary content
- Custom MIME types
- Async and sync functions

Run:
    uv run python examples/custom_resources_demo.py
"""

import asyncio
import json
import os
from datetime import datetime

from chuk_mcp_runtime.common.mcp_resource_decorator import (
    get_registered_resources,
    get_resource_function,
    mcp_resource,
)

# ============================================================================
# Example 1: Configuration Resources
# ============================================================================


@mcp_resource(
    uri="config://database",
    name="Database Configuration",
    description="Current database connection settings",
    mime_type="application/json",
)
async def get_database_config():
    """Return database configuration as JSON."""
    config = {
        "host": "localhost",
        "port": 5432,
        "database": "app_db",
        "pool_size": 10,
        "ssl_mode": "require",
    }
    return json.dumps(config, indent=2)


@mcp_resource(
    uri="config://app/settings",
    name="Application Settings",
    description="Application configuration and feature flags",
    mime_type="application/json",
)
def get_app_settings():
    """Return app settings (synchronous)."""
    settings = {
        "app_name": "MCP Demo App",
        "version": "1.0.0",
        "features": {
            "dark_mode": True,
            "notifications": True,
            "analytics": False,
        },
        "limits": {"max_upload_size": 10485760, "rate_limit": 1000},
    }
    return json.dumps(settings, indent=2)


# ============================================================================
# Example 2: System Information Resources
# ============================================================================


@mcp_resource(
    uri="system://info",
    name="System Information",
    description="Current system status and environment",
    mime_type="text/plain",
)
async def get_system_info():
    """Return system information."""
    info = f"""System Information
==================
Platform: {os.uname().sysname}
Node: {os.uname().nodename}
Release: {os.uname().release}
Machine: {os.uname().machine}

Process Info
============
PID: {os.getpid()}
Current Dir: {os.getcwd()}
User: {os.getenv('USER', 'unknown')}

Timestamp: {datetime.now().isoformat()}
"""
    return info


@mcp_resource(
    uri="system://env",
    name="Environment Variables",
    description="Selected environment variables",
    mime_type="text/plain",
)
def get_environment():
    """Return selected environment variables."""
    env_vars = ["PATH", "HOME", "USER", "SHELL"]
    lines = ["Environment Variables\n" + "=" * 40 + "\n"]

    for var in env_vars:
        value = os.getenv(var, "(not set)")
        lines.append(f"{var}: {value}\n")

    return "".join(lines)


# ============================================================================
# Example 3: Documentation Resources
# ============================================================================


@mcp_resource(
    uri="docs://api/overview",
    name="API Documentation",
    description="API endpoints and usage guide",
    mime_type="text/markdown",
)
async def get_api_docs():
    """Return API documentation in Markdown."""
    docs = """# API Documentation

## Authentication
All API requests require authentication via Bearer token:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

## Endpoints

### GET /api/users
List all users
- Query params: `limit`, `offset`
- Returns: Array of user objects

### POST /api/users
Create a new user
- Body: `{"name": "...", "email": "..."}`
- Returns: Created user object

### GET /api/users/{id}
Get user by ID
- Returns: User object or 404

## Rate Limiting
- 1000 requests per hour per API key
- Headers: `X-RateLimit-Remaining`, `X-RateLimit-Reset`
"""
    return docs


@mcp_resource(
    uri="docs://getting-started",
    name="Getting Started Guide",
    description="Quick start guide for new users",
    mime_type="text/markdown",
)
def get_getting_started():
    """Return getting started documentation."""
    return """# Getting Started

Welcome to the MCP Demo App!

## Installation
```bash
pip install mcp-demo-app
```

## Quick Start
```python
from mcp_demo import Client

client = Client(api_key="YOUR_KEY")
result = client.users.list()
print(result)
```

## Next Steps
1. Read the API documentation
2. Try the examples
3. Join our community
"""


# ============================================================================
# Example 4: Binary Content Resources
# ============================================================================


@mcp_resource(
    uri="data://logo.png",
    name="Application Logo",
    description="Company logo in PNG format",
    mime_type="image/png",
)
async def get_logo():
    """Return binary logo data."""
    # Simulated PNG data (would be real image data in production)
    png_header = b"\x89PNG\r\n\x1a\n"
    fake_image_data = png_header + b"<fake-png-data-here>" * 100
    return fake_image_data


# ============================================================================
# Example 5: Dynamic/Computed Resources
# ============================================================================


@mcp_resource(
    uri="status://health",
    name="Health Status",
    description="Real-time application health check",
    mime_type="application/json",
)
async def get_health_status():
    """Return current health status (computed on each request)."""
    # Simulate health checks
    await asyncio.sleep(0.01)  # Simulate database ping

    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "database": "ok",
            "cache": "ok",
            "storage": "ok",
        },
        "uptime_seconds": 12345,
    }
    return json.dumps(health, indent=2)


@mcp_resource(
    uri="metrics://current",
    name="Current Metrics",
    description="Real-time application metrics",
    mime_type="application/json",
)
async def get_current_metrics():
    """Return current metrics."""
    import random

    metrics = {
        "requests_per_second": random.randint(100, 500),
        "active_connections": random.randint(10, 100),
        "memory_usage_mb": random.randint(256, 1024),
        "cpu_percent": round(random.uniform(10, 80), 2),
        "timestamp": datetime.now().isoformat(),
    }
    return json.dumps(metrics, indent=2)


# ============================================================================
# Demo Application
# ============================================================================


async def main():
    """Run the custom resources demo."""

    print("=" * 80)
    print("Custom MCP Resources Demo - @mcp_resource Decorator")
    print("=" * 80)
    print()

    # ========================================================================
    # Part 1: List All Registered Resources
    # ========================================================================
    print("=" * 80)
    print("Part 1: Registered Resources")
    print("=" * 80)
    print()

    resources = get_registered_resources()
    print(f"Found {len(resources)} custom resources:")
    print()

    for i, resource in enumerate(resources, 1):
        print(f"{i}. {resource.name}")
        print(f"   URI:         {resource.uri}")
        print(f"   MIME Type:   {resource.mimeType}")
        print(f"   Description: {resource.description}")
        print()

    # ========================================================================
    # Part 2: Read Specific Resources
    # ========================================================================
    print("=" * 80)
    print("Part 2: Reading Resources")
    print("=" * 80)
    print()

    # Read database config
    print("📖 Reading config://database")
    print("-" * 60)
    db_config_func = get_resource_function("config://database")
    if db_config_func:
        content = await db_config_func()
        print(content)
    print()

    # Read system info
    print("📖 Reading system://info")
    print("-" * 60)
    system_info_func = get_resource_function("system://info")
    if system_info_func:
        content = await system_info_func()
        print(content[:300])  # First 300 chars
        print("...")
    print()

    # Read API docs
    print("📖 Reading docs://api/overview")
    print("-" * 60)
    api_docs_func = get_resource_function("docs://api/overview")
    if api_docs_func:
        content = await api_docs_func()
        print(content[:400])  # First 400 chars
        print("...")
    print()

    # Read health status (dynamic)
    print("📖 Reading status://health (dynamic - computed on each call)")
    print("-" * 60)
    health_func = get_resource_function("status://health")
    if health_func:
        # Call it twice to show it's dynamic
        content1 = await health_func()
        await asyncio.sleep(0.1)
        content2 = await health_func()

        print("First call:")
        print(content1)
        print("\nSecond call (notice timestamp changes):")
        print(content2)
    print()

    # Read binary resource
    print("📖 Reading data://logo.png (binary content)")
    print("-" * 60)
    logo_func = get_resource_function("data://logo.png")
    if logo_func:
        binary_data = await logo_func()
        print(f"Binary data type: {type(binary_data)}")
        print(f"Size: {len(binary_data)} bytes")
        print(f"First 20 bytes: {binary_data[:20]}")
    print()

    # ========================================================================
    # Part 3: Resource Types Summary
    # ========================================================================
    print("=" * 80)
    print("Part 3: Resource Types Summary")
    print("=" * 80)
    print()

    print("✅ Static Resources (cached/config data)")
    print("   • config://database - Database settings")
    print("   • config://app/settings - App configuration")
    print("   • docs://api/overview - API documentation")
    print()

    print("✅ Dynamic Resources (computed on each request)")
    print("   • status://health - Current health status")
    print("   • metrics://current - Real-time metrics")
    print()

    print("✅ System Resources (environment/system info)")
    print("   • system://info - System information")
    print("   • system://env - Environment variables")
    print()

    print("✅ Binary Resources (images, files)")
    print("   • data://logo.png - Binary image data")
    print()

    # ========================================================================
    # Part 4: Use Cases
    # ========================================================================
    print("=" * 80)
    print("Part 4: Custom Resources Use Cases")
    print("=" * 80)
    print()

    print("💡 When to use @mcp_resource:")
    print()
    print("1. Configuration & Settings")
    print("   - Expose app config to AI agents")
    print("   - Feature flags and environment settings")
    print("   - API keys/endpoints (non-sensitive)")
    print()

    print("2. Documentation & Help")
    print("   - API documentation")
    print("   - Code examples")
    print("   - Schema definitions")
    print()

    print("3. System Information")
    print("   - Health checks")
    print("   - Metrics and statistics")
    print("   - Environment info")
    print()

    print("4. Dynamic Content")
    print("   - Live data feeds")
    print("   - Computed results")
    print("   - Real-time status")
    print()

    print("5. Static Assets")
    print("   - Templates")
    print("   - Schema files")
    print("   - Reference data")
    print()

    # ========================================================================
    # Part 5: Resources vs Tools vs Artifacts
    # ========================================================================
    print("=" * 80)
    print("Part 5: Resources vs Tools vs Artifacts")
    print("=" * 80)
    print()

    print("📌 CUSTOM RESOURCES (@mcp_resource)")
    print("   • Read-only access to application data")
    print("   • Defined by functions (sync or async)")
    print("   • Can be static or dynamic")
    print("   • No session isolation (global)")
    print("   • Examples: config, docs, system info")
    print()

    print("📌 ARTIFACT RESOURCES (from artifact store)")
    print("   • Read-only access to user files")
    print("   • Session-isolated (users see only their files)")
    print("   • Created via tools (write_file, upload_file)")
    print("   • URI scheme: artifact://{id}")
    print("   • Examples: uploaded documents, generated reports")
    print()

    print("📌 TOOLS (@mcp_tool)")
    print("   • Actions that modify state")
    print("   • Can read/write/delete")
    print("   • May have side effects")
    print("   • Examples: write_file, send_email, create_user")
    print()

    print("💡 Architecture:")
    print("   ┌──────────────────────────────────────┐")
    print("   │         MCP Server                    │")
    print("   ├──────────────────────────────────────┤")
    print("   │  Custom Resources  │  Artifact Res.  │")
    print("   │  (app data)        │  (user files)   │")
    print("   │        ↓           │        ↓         │")
    print("   │   resources/list   │  resources/list │")
    print("   │   resources/read   │  resources/read │")
    print("   ├────────────────────┴──────────────────┤")
    print("   │  Tools (write_file, upload_file, ...) │")
    print("   └───────────────────────────────────────┘")
    print()

    # ========================================================================
    # Summary
    # ========================================================================
    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print()
    print("📚 What we demonstrated:")
    print("   1. ✅ Created custom resources with @mcp_resource")
    print("   2. ✅ Listed all registered resources")
    print("   3. ✅ Read text and binary resource content")
    print("   4. ✅ Showed static vs dynamic resources")
    print("   5. ✅ Understood use cases and best practices")
    print()
    print("🎯 Key Takeaways:")
    print("   • Custom resources expose read-only app/system data")
    print("   • Use @mcp_resource decorator on functions")
    print("   • Resources can be static or computed dynamically")
    print("   • Different from tools (actions) and artifacts (user files)")
    print("   • Perfect for config, docs, system info, metrics")
    print()


if __name__ == "__main__":
    asyncio.run(main())
