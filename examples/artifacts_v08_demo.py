#!/usr/bin/env python3
"""
Demo: chuk-artifacts v0.8 Integration

Shows three ways to use artifact storage:
1. General tools with scope parameter (backward compatible)
2. Explicit session tools (ephemeral)
3. Explicit user tools (persistent)
"""

import asyncio
import os

from chuk_artifacts import ArtifactStore


async def demo():
    """Demonstrate all three patterns."""
    print("=" * 70)
    print("chuk-artifacts v0.8 - Three Tool Patterns")
    print("=" * 70)
    print()

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    async with ArtifactStore(sandbox_id="demo") as store:
        # ============================================================
        # Pattern 1: General tools with scope (backward compatible)
        # ============================================================
        print("Pattern 1: General Tools (scope parameter)")
        print("-" * 70)

        # Default is session scope (backward compatible)
        session_file = await store.store(
            data=b"Temporary data",
            filename="temp.txt",
            mime="text/plain",
            summary="Session file",
            # scope="session" is default
        )
        print(f"✓ store (default scope=session): {session_file}")

        # Can explicitly use user scope
        user_file = await store.store(
            data=b"Permanent data",
            filename="perm.txt",
            mime="text/plain",
            summary="User file",
            user_id="alice",
            scope="user",
        )
        print(f"✓ store (scope=user): {user_file}")
        print()

        # ============================================================
        # Pattern 2: Explicit session tools (clear intent)
        # ============================================================
        print("Pattern 2: Explicit Session Tools (ephemeral)")
        print("-" * 70)

        # These would call write_session_file/upload_session_file
        # which internally call write_file/upload_file with scope="session"
        print("✓ write_session_file() - always ephemeral")
        print("✓ upload_session_file() - always ephemeral")
        print("✓ list_session_files() - only shows session files")
        print()

        # ============================================================
        # Pattern 3: Explicit user tools (persistent)
        # ============================================================
        print("Pattern 3: Explicit User Tools (persistent)")
        print("-" * 70)

        # These would call write_user_file/upload_user_file
        # which internally call write_file/upload_file with scope="user"
        print("✓ write_user_file() - always persistent")
        print("✓ upload_user_file() - always persistent")
        print("✓ list_user_files() - only shows user files")
        print()

        # ============================================================
        # Show metadata difference
        # ============================================================
        print("Metadata Comparison:")
        print("-" * 70)

        session_meta = await store.metadata(session_file)
        print(f"Session file: scope={session_meta.scope}, ttl={session_meta.ttl}s")

        user_meta = await store.metadata(user_file)
        print(
            f"User file:    scope={user_meta.scope}, ttl={user_meta.ttl}s, owner={user_meta.owner_id}"
        )
        print()

        # ============================================================
        # Summary
        # ============================================================
        print("=" * 70)
        print("Summary: Choose Your Pattern")
        print("=" * 70)
        print("""
1. General Tools (Flexible):
   - write_file(scope="session")  # Default, backward compatible
   - write_file(scope="user")     # Explicit persistent

2. Explicit Session Tools (Clear Intent):
   - write_session_file()  # Always ephemeral
   - upload_session_file() # Always ephemeral

3. Explicit User Tools (Clear Intent):
   - write_user_file()  # Always persistent
   - upload_user_file() # Always persistent

Recommendation:
- Use explicit tools for clarity (write_session_file, write_user_file)
- Use general tools for flexibility (write_file with scope param)
- Default scope is "session" for backward compatibility
        """)


if __name__ == "__main__":
    asyncio.run(demo())
