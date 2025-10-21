#!/usr/bin/env python3
"""examples/artifacts_e2e_demo.py

Single, consolidated demo that *fully* exercises the chuk_mcp_runtime ↔︎
chuk_artifacts tool-chain and replaces the earlier three scripts.

Changes in this revision
------------------------
* **Robust `copy_file` ID extraction**- case-insensitive regex.
* **Graceful fallback for `get_storage_stats`**- works around the current
  `AdminOperations.store` attribute bug in `chuk_artifacts` ≤ 0.4.2 by
  computing the per-session totals from `list_session_files` when the
  built-in stats call fails.
* Tidier logging.
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

# ───────────────────────────── temp workspace + cfg ─────────────────────────
_TMP = Path(tempfile.mkdtemp(prefix="e2e_demo_")).resolve()
_ART = _TMP / "artifacts"
_ALL_TOOLS = (
    "upload_file write_file read_file list_session_files delete_file list_directory "
    "copy_file move_file get_file_metadata get_storage_stats get_presigned_url"
).split()
_CFG_EXTRA: Dict[str, Any] = {
    "artifacts": {
        "storage_provider": "filesystem",
        "session_provider": "memory",
        "filesystem_root": str(_ART),
        "bucket": "demo-files",
        "tools": {
            "enabled": True,
            "tools": {t: {"enabled": True} for t in _ALL_TOOLS},
        },
    }
}


# ───────────────────────── helper to enable tools ───────────────────────────
async def _enable_tools() -> None:
    from chuk_mcp_runtime.tools import register_artifacts_tools

    cfg = load_config(["config.yaml"], default_config={})
    cfg.update(_CFG_EXTRA)
    await register_artifacts_tools(cfg)


# ───────────────────────── demo per session ─────────────────────────────────
async def _demo_session(sid: str) -> None:
    from chuk_mcp_runtime.tools.artifacts_tools import (
        copy_file,
        get_file_metadata,
        list_session_files,
        read_file,
        write_file,
    )

    print(f"\n✨ Session {sid}")

    res_create = await write_file(
        content=f"Hello from {sid}!", filename="hello.txt", session_id=sid
    )
    aid = re.search(r"artifact id: (\w+)", res_create, flags=re.I).group(1)  # type: ignore[arg-type]
    print("  • write_file →", aid)

    txt = await read_file(aid, as_text=True, session_id=sid)
    print("  • read_file  →", txt)

    before = await list_session_files(session_id=sid)
    print("  • list_session_files →", len(before), "file(s)")

    res_copy = await copy_file(aid, new_filename="hello_backup.txt", session_id=sid)
    aid_copy = re.search(r"artifact id: (\w+)", res_copy, flags=re.I).group(1)  # type: ignore[arg-type]
    print("  • copy_file →", aid_copy)

    meta = await get_file_metadata(aid_copy, session_id=sid)
    print("  • get_file_metadata →", meta.get("bytes", "?"), "bytes")

    after = await list_session_files(session_id=sid)
    print("  • list_session_files →", len(after), "file(s) after copy")


# ───────────────────────── stats + optional presign ─────────────────────────
async def _safe_stats(sid: str) -> Dict[str, Any]:
    """Return stats dict; fall back to manual calc when provider API fails."""
    from chuk_mcp_runtime.tools.artifacts_tools import (
        get_storage_stats,
        list_session_files,
    )

    try:
        return await get_storage_stats(session_id=sid)
    except Exception:
        files = await list_session_files(session_id=sid)
        return {
            "session_id": sid,
            "session_file_count": len(files),
            "session_total_bytes": sum(f.get("bytes", 0) for f in files),
            "storage_provider": "filesystem (fallback)",
        }


async def _demo_stats(sid_a: str, sid_b: str) -> None:
    from chuk_mcp_runtime.tools.artifacts_tools import (
        get_presigned_url,
        list_session_files,
    )

    stats_a = await _safe_stats(sid_a)
    stats_b = await _safe_stats(sid_b)

    print("\n📊 Storage stats")
    for tag, st in ((sid_a, stats_a), (sid_b, stats_b)):
        print(f"   {tag}: {st['session_file_count']} file(s), {st['session_total_bytes']} bytes")

    # presign if backend supports it (not for filesystem)
    if stats_a.get("storage_provider") not in {"filesystem", "memory"}:
        first_id = (await list_session_files(session_id=sid_a))[0]["artifact_id"]
        url = await get_presigned_url(first_id, session_id=sid_a, expires_in="short")
        print("\n🔗 Presigned URL (short) →", url)


# ───────────────────────── main runner ──────────────────────────────────────
async def _run() -> None:
    print("🚀 End-to-End chuk_mcp_runtime × chuk_artifacts Demo")
    print("=" * 60)
    print("Temp workspace:", _TMP)

    _ART.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        {
            "ARTIFACT_FS_ROOT": str(_ART),
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_BUCKET": "demo-files",
        }
    )

    await _enable_tools()
    from chuk_mcp_runtime.tools import get_artifact_tools

    print("✅ Tools enabled →", ", ".join(sorted(get_artifact_tools())))

    await _demo_session("alpha")
    await _demo_session("beta")
    await _demo_stats("alpha", "beta")

    print("\n🎉 Demo completed successfully")


# ───────────────────────── CLI glue ─────────────────────────────────────────


def _cleanup() -> None:
    shutil.rmtree(_TMP, ignore_errors=True)
    for v in (
        "ARTIFACT_FS_ROOT",
        "ARTIFACT_STORAGE_PROVIDER",
        "ARTIFACT_SESSION_PROVIDER",
        "ARTIFACT_BUCKET",
    ):
        os.environ.pop(v, None)


def main() -> None:
    try:
        asyncio.run(_run())
    finally:
        _cleanup()
        print("\n✅ Temp resources cleaned- goodbye!")


if __name__ == "__main__":
    main()
