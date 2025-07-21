#!/usr/bin/env python3
"""examples/session_e2e_demo.py

End-to-end demo that wires together **chuk_mcp_runtime**, **chuk_sessions**
and **chuk_artifacts** via the new *session bridge* - with full tool
registration just like the standalone artifacts demo.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

from chuk_mcp_runtime.server.config_loader import load_config
from chuk_mcp_runtime.session.session_bridge import (
    SessionContext,
    allocate_session,
    get_session_manager,
)
from chuk_mcp_runtime.tools import register_artifacts_tools, get_artifact_tools
from chuk_mcp_runtime.tools.artifacts_tools import (
    write_file,
    list_session_files,
    read_file,
    get_storage_stats,
)

# ───────────────────────── configuration helper ─────────────────────────
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="bridge_demo_")).resolve()
_ART_DIR = _TMP_ROOT / "artifacts"
_ALL_TOOLS = (
    "upload_file write_file read_file list_session_files delete_file list_directory "
    "copy_file move_file get_file_metadata get_storage_stats get_presigned_url"
).split()

_CFG_EXTRA: Dict[str, Any] = {
    "artifacts": {
        "storage_provider": "filesystem",
        "session_provider": "memory",
        "filesystem_root": str(_ART_DIR),
        "bucket": "bridge-demo",
        "tools": {"enabled": True, "tools": {t: {"enabled": True} for t in _ALL_TOOLS}},
    }
}


async def _enable_tools(cfg_extra: Dict[str, Any]) -> None:
    cfg = load_config(["config.yaml"], default_config={})
    cfg.update(cfg_extra)
    await register_artifacts_tools(cfg)


# ───────────────────────── helpers ─────────────────────────


def _banner(txt: str) -> None:  # prettier output
    print("\n" + txt)


def _extract_id(msg: str) -> str:
    """Return the artifact_id from write_file* style success messages."""
    m = re.search(r"artifact id:\s*([a-f0-9]{32})", msg, flags=re.I)
    return m.group(1) if m else msg  # fallback to raw msg if regex fails


# ───────────────────────── demo logic  ─────────────────────────


async def demo_filesystem_memory() -> None:
    """Filesystem + in-memory provider demo (earlier working version)."""
    print("Temp workspace:", _TMP_ROOT)

    # 1) enable artifact tools
    await _enable_tools(_CFG_EXTRA)
    print("✅ Tools enabled →", ", ".join(sorted(get_artifact_tools())))

    # 2) allocate sessions
    sid_alice = await allocate_session(user_id="alice", ttl_hours=1)
    sid_bob = await allocate_session(user_id="bob", ttl_hours=1)
    print(f"• Allocated sessions  →  alice={sid_alice}  |  bob={sid_bob}\n")

    # 3) Alice writes two files
    _banner("📝  Alice writes two files …")
    async with SessionContext(sid_alice):
        res1 = await write_file(
            content="# Alice Doc\n\nHello from Alice.",
            filename="docs/alice.md",
            mime="text/markdown",
            session_id=sid_alice,
        )
        res2 = await write_file(
            content='{"user":"alice","role":"admin"}',
            filename="config/alice.json",
            mime="application/json",
            session_id=sid_alice,
        )
        aid1, aid2 = _extract_id(res1), _extract_id(res2)
        print("   →", aid1)
        print("   →", aid2)
        print(
            "   Alice now has",
            len(await list_session_files(session_id=sid_alice)),
            "file(s)",
        )

    # 4) Bob writes one file
    _banner("📝  Bob writes a file …")
    async with SessionContext(sid_bob):
        resb = await write_file(
            content="# Bob Notes\n\n- task 1\n- task 2",
            filename="docs/bob.md",
            mime="text/markdown",
            session_id=sid_bob,
        )
        bid = _extract_id(resb)
        print("   →", bid)
        print(
            "   Bob now has",
            len(await list_session_files(session_id=sid_bob)),
            "file(s)",
        )

    # 5) Read documents back
    _banner("📖  Reading documents back …")
    async with SessionContext(sid_alice):
        txt = await read_file(aid1, as_text=True)
        print("   Alice reads:", txt.split("\n", 1)[0])
    async with SessionContext(sid_bob):
        txt = await read_file(bid, as_text=True)
        print("   Bob reads:  ", txt.split("\n", 1)[0])

    # 6) Stats for Alice
    _banner("📊  Storage stats (Alice)")
    stats = await get_storage_stats(session_id=sid_alice)
    print(
        f"   {stats['session_file_count']} file(s), {stats['session_total_bytes']} byte(s)\n",
    )

    # 7) cleanup
    await get_session_manager().cleanup_expired_sessions()
    shutil.rmtree(_TMP_ROOT)
    print("✅  Temp workspace cleaned - demo finished")


# ───────────────────────── redis + s3 variant ─────────────────────────


async def demo_redis_s3() -> None:
    """Same flow but using Redis for sessions and S3 (or MinIO) for storage."""
    print("\n🚀  Redis+S3 variant demo")

    # point the SessionManager to Redis
    os.environ["SESSION_PROVIDER"] = "redis"
    os.environ.setdefault("SESSION_REDIS_URL", "redis://localhost:6379/0")

    # S3 / MinIO creds from env or fallbacks (anonymous local MinIO for dev)
    os.environ["ARTIFACT_STORAGE_PROVIDER"] = "s3"
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "minioadmin")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "minioadmin")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")

    _s3_cfg: Dict[str, Any] = {
        "artifacts": {
            "storage_provider": "s3",
            "session_provider": "redis",
            "bucket": "bridge-demo",
            "tools": {
                "enabled": True,
                "tools": {t: {"enabled": True} for t in _ALL_TOOLS},
            },
        }
    }

    # enable tools against S3/Redis
    await _enable_tools(_s3_cfg)

    # allocate sessions (these go into Redis)
    sid_a = await allocate_session(user_id="redis-alice", ttl_hours=1)
    sid_b = await allocate_session(user_id="redis-bob", ttl_hours=1)
    print(f"   Sessions in Redis → {sid_a}, {sid_b}")

    # quick smoke-test write/read
    async with SessionContext(sid_a):
        res = await write_file(
            content="Hello S3 via Redis session",
            filename="hello.txt",
            session_id=sid_a,
        )
        aid = _extract_id(res)
        txt = await read_file(aid, as_text=True)
        print("   Round-trip ✓ - length:", len(txt))

    # cleanup (leave objects in bucket, only clean redis cache)
    await get_session_manager().cleanup_expired_sessions()
    print("✅  Redis+S3 flow finished - check bucket 'bridge-demo' for uploaded object")


# ───────────────────────── CLI glue  ─────────────────────────


async def _run():
    print("🚀  chuk_mcp_runtime × chuk_sessions end-to-end demo")
    await demo_filesystem_memory()
    await demo_redis_s3()


if __name__ == "__main__":
    asyncio.run(_run())
