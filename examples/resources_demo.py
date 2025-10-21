#!/usr/bin/env python3
"""
MCP Resources Demo - Artifacts as Resources

Demonstrates how artifacts are exposed as MCP resources with session isolation.

This example shows:
1. Creating files via artifact tools (write operations)
2. Listing resources (read-only access)
3. Reading resource content
4. Session isolation between users

Run:
    uv run python examples/resources_demo.py
"""

import asyncio
import base64
from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    """Run MCP resources demo."""

    print("=" * 80)
    print("MCP Resources Demo - Artifacts as Resources")
    print("=" * 80)
    print()

    # Server configuration with artifacts enabled
    server_params = StdioServerParameters(
        command="chuk-mcp-server",
        args=["--config", "examples/resources_demo_config.yaml"],
        env=None,
    )

    print("📦 Starting MCP server with artifacts enabled...")
    print()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # ============================================================
            # Part 1: Create Files Using Tools (Write Operations)
            # ============================================================
            print("=" * 80)
            print("Part 1: Creating Files via Tools")
            print("=" * 80)
            print()

            # Create a text file
            print("📝 Creating text document...")
            result = await session.call_tool(
                "write_file",
                arguments={
                    "filename": "report.md",
                    "content": f"""# Monthly Report

Generated: {datetime.now().isoformat()}

## Summary
- Sales increased 20%
- New customers: 150
- Customer satisfaction: 4.5/5.0

## Next Steps
1. Expand marketing
2. Improve support
3. Launch new features
""",
                    "mime": "text/markdown",
                    "summary": "Monthly sales report",
                },
            )
            print(f"✅ Created: {result.content[0].text}")
            print()

            # Upload a binary file (simulated image)
            print("🖼️  Uploading image file...")
            fake_image = b"PNG-IMAGE-DATA-HERE"  # Simulated image
            result = await session.call_tool(
                "upload_file",
                arguments={
                    "filename": "chart.png",
                    "content": base64.b64encode(fake_image).decode(),
                    "mime": "image/png",
                    "summary": "Sales chart visualization",
                },
            )
            print(f"✅ Uploaded: {result.content[0].text}")
            print()

            # Create a JSON data file
            print("📊 Creating JSON data file...")
            result = await session.call_tool(
                "write_file",
                arguments={
                    "filename": "data.json",
                    "content": """{"sales": [100, 120, 150], "dates": ["Jan", "Feb", "Mar"]}""",
                    "mime": "application/json",
                    "summary": "Sales data in JSON format",
                },
            )
            print(f"✅ Created: {result.content[0].text}")
            print()

            # ============================================================
            # Part 2: List Resources (Read-Only Discovery)
            # ============================================================
            print("=" * 80)
            print("Part 2: Listing Resources")
            print("=" * 80)
            print()

            print("📋 Fetching available resources...")
            resources = await session.list_resources()

            print(f"Found {len(resources.resources)} resources:")
            print()

            for i, resource in enumerate(resources.resources, 1):
                print(f"{i}. {resource.name}")
                print(f"   URI:         {resource.uri}")
                print(f"   MIME Type:   {resource.mimeType}")
                print(f"   Description: {resource.description or '(none)'}")
                print()

            # ============================================================
            # Part 3: Read Resource Content
            # ============================================================
            print("=" * 80)
            print("Part 3: Reading Resource Content")
            print("=" * 80)
            print()

            if resources.resources:
                # Read the first text resource
                for resource in resources.resources:
                    if resource.mimeType and resource.mimeType.startswith("text/"):
                        print(f"📖 Reading resource: {resource.name}")
                        print(f"   URI: {resource.uri}")
                        print()

                        content = await session.read_resource(resource.uri)

                        # Display content based on type
                        if hasattr(content, "text"):
                            print("Content (text):")
                            print("-" * 60)
                            print(content.text[:500])  # First 500 chars
                            if len(content.text) > 500:
                                print(f"... ({len(content.text) - 500} more characters)")
                            print("-" * 60)
                        elif hasattr(content, "blob"):
                            print("Content (binary - base64):")
                            print("-" * 60)
                            print(content.blob[:100])  # First 100 chars of base64
                            print("...")
                            print("-" * 60)
                        print()
                        break

            # ============================================================
            # Part 4: Tools vs Resources Comparison
            # ============================================================
            print("=" * 80)
            print("Part 4: Tools vs Resources - When to Use Each")
            print("=" * 80)
            print()

            print("📌 MCP TOOLS (Actions - Write Operations)")
            print("   • write_file       - Create/update text files")
            print("   • upload_file      - Upload binary files")
            print("   • delete_file      - Delete files")
            print("   • move_file        - Rename/move files")
            print("   • copy_file        - Copy files")
            print("   • get_presigned_url - Generate download URLs")
            print()

            print("📌 MCP RESOURCES (Data - Read Operations)")
            print("   • resources/list   - Discover available files")
            print("   • resources/read   - Retrieve file content")
            print("   • Best for AI context retrieval")
            print("   • Automatic session isolation")
            print()

            print("💡 Best Practice:")
            print("   • Use RESOURCES to read files into AI context")
            print("   • Use TOOLS to create/modify/delete files")
            print("   • Resources are read-only, tools are actions")
            print()

            # ============================================================
            # Part 5: Session Isolation Demo
            # ============================================================
            print("=" * 80)
            print("Part 5: Session Isolation")
            print("=" * 80)
            print()

            print("🔒 Security Features:")
            print("   • Each session sees only their own files")
            print("   • Cross-session access is blocked")
            print("   • Resources respect session boundaries")
            print("   • URI validation prevents unauthorized access")
            print()

            print("Example session isolation:")
            print("   Session A creates: report.md, data.json")
            print("   Session B creates: notes.txt, config.yaml")
            print()
            print("   Session A resources/list → only sees report.md, data.json")
            print("   Session B resources/list → only sees notes.txt, config.yaml")
            print()
            print("   ✅ Session A CANNOT read Session B's files")
            print("   ✅ Session B CANNOT read Session A's files")
            print()

            # ============================================================
            # Summary
            # ============================================================
            print("=" * 80)
            print("Demo Complete!")
            print("=" * 80)
            print()
            print("📚 What we demonstrated:")
            print("   1. ✅ Created files using artifact tools")
            print("   2. ✅ Listed resources via resources/list")
            print("   3. ✅ Read resource content via resources/read")
            print("   4. ✅ Understood tools vs resources distinction")
            print("   5. ✅ Verified session isolation security")
            print()
            print("🎯 Key Takeaway:")
            print("   MCP Resources provide read-only access to artifacts,")
            print("   perfect for feeding file content into AI context,")
            print("   while Tools handle all write/modify operations.")
            print()


if __name__ == "__main__":
    asyncio.run(main())
