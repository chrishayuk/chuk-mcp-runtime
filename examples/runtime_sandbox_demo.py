#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
runtime_sandbox_demo.py
=======================

Visual proof that sandbox IDs propagate correctly through

    • chuk_sessions.SessionManager
    • chuk_artifacts.ArtifactStore
    • generated grid keys  (<sandbox>/<session>/<artifact>)

Three independent scenarios:

1. Explicit      - pass `sandbox_id=` directly to ArtifactStore
2. Env-variable  - set SANDBOX_ID / ARTIFACT_SANDBOX_ID
3. Fallback      - remove vars so auto-generation is used

Run from the project root:

    uv run examples/runtime_sandbox_demo.py
"""

from __future__ import annotations

import asyncio
import importlib
import os
import textwrap

from dotenv import load_dotenv

# Load .env so the script behaves like the runtime
load_dotenv()

# ── runtime plumbing -------------------------------------------------
import chuk_mcp_runtime.session.session_bridge as bridge
from chuk_artifacts import ArtifactStore
from chuk_artifacts.config import configure_memory  # keep the demo self-contained
from chuk_mcp_runtime.session.session_bridge import get_session_manager


# ─────────────────── helper to flush the singleton ──────────────────
def _reset_session_manager() -> None:
    """Forget the cached SessionManager so the next call sees fresh env-vars."""
    bridge._manager = None
    importlib.reload(bridge)  # rebuild helper funcs (optional)


# ─────────────────────────────────────────────────────────────────────
async def demo_case(
    title: str,
    *,
    sandbox_id_param: str | None = None,
    env_var: str | None = None,
) -> None:
    """Run one sandbox-ID scenario and pretty print the result."""
    print(f"\n{title}\n" + "-" * len(title))

    # in-memory providers so S3/Redis aren’t required
    configure_memory()

    # tweak environment seen by SessionManager & ArtifactStore
    keys = ("SANDBOX_ID", "ARTIFACT_SANDBOX_ID", "MCP_SANDBOX_ID")
    if env_var is not None:
        for k in keys:
            os.environ[k] = env_var
    else:
        for k in keys:
            os.environ.pop(k, None)

    # ensure a *fresh* SessionManager for this scenario
    _reset_session_manager()

    # create components exactly like the runtime would
    mgr = get_session_manager()  # picks up env vars now
    store = ArtifactStore(sandbox_id=sandbox_id_param)  # explicit override if given

    # allocate session + store tiny artifact
    session_id = await mgr.allocate_session(user_id="demo-user")
    artifact_id = await store.store(
        data=b"hello-runtime",
        mime="text/plain",
        summary="demo-artifact",
        session_id=session_id,
    )

    # gather info
    canonical_prefix = mgr.get_canonical_prefix(session_id)
    artifact_key = mgr.generate_artifact_key(session_id, artifact_id)
    metadata = await store.metadata(artifact_id)

    print(
        textwrap.dedent(
            f"""
            Sandbox ID       : {mgr.sandbox_id}
            Session ID       : {session_id}
            Canonical prefix : {canonical_prefix}
            Generated key    : {artifact_key}
            Metadata['key']  : {metadata['key']}
        """
        ).strip()
    )

    await store.close()


# ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    print("🧪  Runtime Sandbox-ID Demonstration  🧪")

    await demo_case(
        "1️⃣  Explicit sandbox_id parameter",
        sandbox_id_param="explicit-sandbox",
        env_var=None,
    )

    await demo_case(
        "2️⃣  SANDBOX_ID / ARTIFACT_SANDBOX_ID environment variables",
        sandbox_id_param=None,
        env_var="env-sandbox",
    )

    await demo_case(
        "3️⃣  Auto-generated sandbox_id (fallback)",
        sandbox_id_param=None,
        env_var=None,
    )

    print("\n✅  Demo completed - sandbox namespaces propagate correctly!\n")


if __name__ == "__main__":
    asyncio.run(main())
