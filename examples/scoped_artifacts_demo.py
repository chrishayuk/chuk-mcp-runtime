#!/usr/bin/env python3
"""
Scoped Artifacts Demo - Using chuk-artifacts v0.8 Storage Scopes

Demonstrates the three storage scopes:
- session: Ephemeral (expires with session)
- user: Persistent (survives sessions)
- sandbox: Shared (accessible to all users)

This example shows how chuk-mcp-runtime should leverage these scopes.
"""

import asyncio
import os

# Use memory providers for demo (no Redis required)
# IMPORTANT: Set these BEFORE importing chuk_artifacts
os.environ.setdefault("ARTIFACT_PROVIDER", "vfs-memory")
os.environ.setdefault("SESSION_PROVIDER", "memory")

from chuk_artifacts import ArtifactStore


async def demo_session_scope():
    """Demo: Session-scoped storage (ephemeral)."""
    print("\n" + "=" * 70)
    print("DEMO 1: Session-Scoped Storage (Ephemeral)")
    print("=" * 70)

    async with ArtifactStore() as store:
        # Create session-scoped file (expires with session)
        session_file = await store.store(
            data=b"Temporary work in progress...",
            mime="text/plain",
            summary="Session work file",
            filename="work.txt",
            user_id="alice",
            # scope="session" is the default - ephemeral
            ttl=900,  # 15 minutes
        )

        print(f"✅ Created session file: {session_file}")

        # Retrieve metadata
        meta = await store.metadata(session_file)
        print(f"   Scope: {meta.scope}")
        print(f"   Owner: {meta.owner_id or 'N/A'}")
        print(f"   TTL: {meta.ttl}s ({meta.ttl / 60:.1f} minutes)")
        print(f"   Session: {meta.session_id}")
        print()
        print("📝 Use case: Temporary files, caches, work in progress")
        print("⏰ Lifespan: Expires when session ends (15min - 24h)")


async def demo_user_scope():
    """Demo: User-scoped storage (persistent)."""
    print("\n" + "=" * 70)
    print("DEMO 2: User-Scoped Storage (Persistent)")
    print("=" * 70)

    async with ArtifactStore() as store:
        # Create user-scoped file (persists across sessions)
        user_file = await store.store(
            data=b"This is Alice's permanent document.",
            mime="application/pdf",
            summary="User's saved document",
            filename="documents/contract.pdf",
            user_id="alice",
            scope="user",  # ⭐ KEY: Persists across sessions!
            ttl=31536000,  # 1 year (effectively permanent)
        )

        print(f"✅ Created user file: {user_file}")

        # Retrieve metadata
        meta = await store.metadata(user_file)
        print(f"   Scope: {meta.scope}")
        print(f"   Owner: {meta.owner_id}")
        print(f"   TTL: {'No expiry' if meta.ttl > 31000000 else f'{meta.ttl}s'}")
        print(f"   Storage key: {meta.key}")
        print()

        # Demonstrate persistence: List user's files
        print("📁 All files for user 'alice':")
        user_files = await store.search(user_id="alice", scope="user")
        for f in user_files:
            print(f"   • {f.filename} ({f.mime})")
        print()
        print("📝 Use case: User documents, saved files, persistent data")
        print("⏰ Lifespan: Persists indefinitely (or 1 year default)")
        print("🔐 Access: Only the owning user can read/write")


async def demo_sandbox_scope():
    """Demo: Sandbox-scoped storage (shared)."""
    print("\n" + "=" * 70)
    print("DEMO 3: Sandbox-Scoped Storage (Shared)")
    print("=" * 70)

    async with ArtifactStore() as store:
        # Create sandbox-scoped file (shared across all users)
        sandbox_file = await store.store(
            data=b"Company logo - available to all users",
            mime="image/png",
            summary="Company logo template",
            filename="templates/logo.png",
            scope="sandbox",  # ⭐ KEY: Shared with everyone!
            ttl=31536000,  # 1 year (effectively permanent)
        )

        print(f"✅ Created sandbox file: {sandbox_file}")

        # Retrieve metadata
        meta = await store.metadata(sandbox_file)
        print(f"   Scope: {meta.scope}")
        print(f"   Owner: {meta.owner_id or 'None (shared)'}")
        print(f"   Storage key: {meta.key}")
        print()

        # List all sandbox resources
        print("📦 Shared sandbox resources:")
        sandbox_files = await store.search(scope="sandbox")
        for f in sandbox_files:
            print(f"   • {f.filename} ({f.mime})")
        print()
        print("📝 Use case: Templates, shared resources, system files")
        print("⏰ Lifespan: Persists indefinitely")
        print("🔐 Access: Read-only for users, admin writes only")


async def demo_scope_isolation():
    """Demo: Scope isolation and access control."""
    print("\n" + "=" * 70)
    print("DEMO 4: Scope Isolation & Access Control")
    print("=" * 70)

    async with ArtifactStore() as store:
        # Create files in different scopes for different users
        print("Creating files in different scopes...")
        print()

        # Alice's user file
        alice_doc = await store.store(
            data=b"Alice's private document",
            mime="text/plain",
            summary="Alice's private file",
            filename="alice_private.txt",
            user_id="alice",
            scope="user",
            ttl=31536000,
        )
        print(f"✅ Alice's user file: {alice_doc}")

        # Bob's user file
        bob_doc = await store.store(
            data=b"Bob's private document",
            mime="text/plain",
            summary="Bob's private file",
            filename="bob_private.txt",
            user_id="bob",
            scope="user",
            ttl=31536000,
        )
        print(f"✅ Bob's user file: {bob_doc}")

        # Shared sandbox file
        shared_template = await store.store(
            data=b"Shared template for everyone",
            mime="text/plain",
            summary="Shared template file",
            filename="shared_template.txt",
            scope="sandbox",
            ttl=31536000,
        )
        print(f"✅ Shared sandbox file: {shared_template}")
        print()

        # Demonstrate isolation
        print("🔐 Access Control:")
        print()

        # Alice can only see her files
        alice_files = await store.search(user_id="alice", scope="user")
        print(f"Alice's files ({len(alice_files)}):")
        for f in alice_files:
            print(f"   • {f.filename}")
        print()

        # Bob can only see his files
        bob_files = await store.search(user_id="bob", scope="user")
        print(f"Bob's files ({len(bob_files)}):")
        for f in bob_files:
            print(f"   • {f.filename}")
        print()

        # Everyone can see sandbox files
        sandbox_files = await store.search(scope="sandbox")
        print(f"Shared resources ({len(sandbox_files)}):")
        for f in sandbox_files:
            print(f"   • {f.filename}")


async def demo_cross_session_persistence():
    """Demo: User files persist across sessions."""
    print("\n" + "=" * 70)
    print("DEMO 5: Cross-Session Persistence")
    print("=" * 70)

    async with ArtifactStore() as store:
        print("Simulating multiple sessions for same user...")
        print()

        # Session 1: User creates document
        print("📱 Session 1 (mobile):")
        doc_id = await store.store(
            data=b"Document created on mobile",
            mime="text/plain",
            summary="Mobile notes",
            filename="notes.txt",
            user_id="alice",
            scope="user",  # Persists!
            ttl=31536000,  # 1 year (effectively permanent)
        )
        print(f"   ✅ Created: {doc_id}")
        print()

        # Session 2: User accesses from different device
        print("💻 Session 2 (desktop - different session):")
        # Can still retrieve the file!
        data = await store.retrieve(doc_id, user_id="alice")
        print(f"   ✅ Retrieved: {data.decode()}")
        print()

        # Session 3: User lists all their files
        print("🖥️  Session 3 (web - another session):")
        user_files = await store.search(user_id="alice", scope="user")
        print(f"   📁 User has {len(user_files)} file(s):")
        for f in user_files:
            print(f"      • {f.filename}")
        print()

        print("✨ Result: Files persist across all sessions for the same user!")


async def demo_mcp_use_cases():
    """Demo: Practical MCP use cases."""
    print("\n" + "=" * 70)
    print("DEMO 6: MCP Server Use Cases")
    print("=" * 70)

    async with ArtifactStore() as store:
        print("Practical examples for MCP servers:\n")

        # Use case 1: Code generation (session-scoped)
        print("1️⃣  Code Generation (session-scoped):")
        code_id = await store.store(
            data=b"def hello(): print('world')",
            mime="text/x-python",
            summary="Generated Python code",
            filename="generated.py",
            user_id="dev1",
            scope="session",  # Temporary
            ttl=900,
        )
        print(f"   Generated code: {code_id}")
        print("   Use: AI-generated code during conversation")
        print()

        # Use case 2: User's saved prompts (user-scoped)
        print("2️⃣  Saved Prompts (user-scoped):")
        prompt_id = await store.store(
            data=b"You are a helpful coding assistant...",
            mime="text/plain",
            summary="User custom prompt",
            filename="prompts/coding_assistant.txt",
            user_id="dev1",
            scope="user",  # Persistent
            ttl=31536000,  # 1 year (effectively permanent)
        )
        print(f"   Saved prompt: {prompt_id}")
        print("   Use: User's custom prompts, templates")
        print()

        # Use case 3: System templates (sandbox-scoped)
        print("3️⃣  System Templates (sandbox-scoped):")
        template_id = await store.store(
            data=b"# Project Template\n\n## Structure\n...",
            mime="text/markdown",
            summary="System template",
            filename="templates/project_template.md",
            scope="sandbox",  # Shared
            ttl=31536000,  # 1 year (effectively permanent)
        )
        print(f"   System template: {template_id}")
        print("   Use: Shared templates, boilerplate code")
        print()

        # Search examples
        print("4️⃣  Search & Discovery:")

        # Find user's Python files
        py_files = await store.search(user_id="dev1", scope="user", mime_prefix="text/x-python")
        print(f"   User's Python files: {len(py_files)}")

        # Find all templates
        templates = await store.search(scope="sandbox")
        print(f"   Available templates: {len(templates)}")


async def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("chuk-artifacts v0.8 - Storage Scopes Demo")
    print("=" * 70)

    await demo_session_scope()
    await demo_user_scope()
    await demo_sandbox_scope()
    await demo_scope_isolation()
    await demo_cross_session_persistence()
    await demo_mcp_use_cases()

    print("\n" + "=" * 70)
    print("Summary: Three Scopes for Three Use Cases")
    print("=" * 70)
    print("""
┌─────────────┬──────────────┬───────────────────┬─────────────────────┐
│ Scope       │ Lifetime     │ Access Control    │ Use Case            │
├─────────────┼──────────────┼───────────────────┼─────────────────────┤
│ session     │ Ephemeral    │ Session-isolated  │ Temp files, caches  │
│ user        │ Persistent   │ User-owned        │ Saved documents     │
│ sandbox     │ Shared       │ Read-only (users) │ Templates, resources│
└─────────────┴──────────────┴───────────────────┴─────────────────────┘

For MCP Servers:
- Use 'session' for: Generated code, temporary work, conversation artifacts
- Use 'user' for: Saved files, custom prompts, persistent documents
- Use 'sandbox' for: System templates, shared resources, boilerplate

Migration: All existing code defaults to 'session' scope (backward compatible)
    """)


if __name__ == "__main__":
    asyncio.run(main())
