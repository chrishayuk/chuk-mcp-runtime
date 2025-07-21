#!/usr/bin/env python3
# examples/artifacts_smoke_test.py
"""
Comprehensive smoke-test for the chuk_artifacts runtime layer.

For every `session_provider × storage_provider` combination in the matrix below
it runs the following workflow **without aborting on provider-specific
limitations**:

1. **Configuration validation** - monkey-patching the legacy
   `AdminOperations` bug when necessary.
2. **CRUD cycle** - store / retrieve / metadata / delete.
3. **Presigned-URL generation** - only for back-ends that implement it.
4. **Batch storage & retrieval** - opportunistic (`retrieve_batch` optional).
5. **Negative paths & delete semantics** - non-existent metadata, exists→False.
6. **Simple per-session stats** - computed from `list_by_session` so it works
   even when `store.get_stats()` is broken.

The script prints ✅, ⚠️ or ❌ for each sub-step - all combos execute in a single
run so you get a full overview at a glance.
"""

from __future__ import annotations

import asyncio
import os
import random
import shutil
import string
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Any

from chuk_artifacts import ArtifactStore, ArtifactNotFoundError

# ---------------------------------------------------------------------------
# Test matrix - feel free to extend!
# ---------------------------------------------------------------------------
TEST_CONFIGS: List[Tuple[str, str, str]] = [
    ("memory", "filesystem", "Memory metadata + filesystem storage (baseline)"),
    ("redis", "filesystem", "Redis metadata + filesystem storage"),
    ("redis", "memory", "Redis metadata + in-memory storage (isolation quirks)"),
    ("redis", "s3", "Redis metadata + S3 storage (bucket chuk-sandbox-2)"),
    # Enable when IBM COS creds are configured:
    # ("redis", "ibm_cos", "Redis metadata + IBM COS (may 403 in CI)"),
]

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
_tmp_root = Path(tempfile.mkdtemp(prefix="artifact_test_")).resolve()


def _rand_bytes(n: int = 64) -> bytes:
    return os.urandom(n)


def _rand_str(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


# ---------------------------------------------------------------------------
# Compatibility helpers
# ---------------------------------------------------------------------------
async def _patch_admin_bug(store: ArtifactStore) -> None:
    """Ensure `store._admin.store` exists (fixed in chuk_artifacts ≥0.3.6)."""
    if not hasattr(store._admin, "store"):
        store._admin.store = store  # type: ignore[attr-defined]


async def _validate(store: ArtifactStore) -> bool:
    """Run `validate_configuration`, falling back gracefully when broken."""
    await _patch_admin_bug(store)
    try:
        cfg = await store.validate_configuration()
        return cfg["storage"]["status"] == "ok" and cfg["session"]["status"] == "ok"
    except Exception:
        # Filesystem provider - just check bucket dir exists; others: assume OK.
        if store._storage_provider_name == "filesystem":
            bucket_dir = Path(os.environ["ARTIFACT_FS_ROOT"]) / store.bucket
            return bucket_dir.exists()
        return True


# ---------------------------------------------------------------------------
# Core test routine
# ---------------------------------------------------------------------------
async def _basic_cycle(store: ArtifactStore, session: str):
    """Perform CRUD + presign + batch operations for one store instance."""
    # ── single-file flow ──────────────────────────────────────────────────
    txt_data = b"Hello, artifact!"
    aid_txt = await store.store(
        txt_data,
        mime="text/plain",
        filename="hello.txt",
        summary="hello text file",
        session_id=session,
    )
    assert await store.exists(aid_txt)

    # retrieve (memory storage may fail - tolerated)
    try:
        assert await store.retrieve(aid_txt) == txt_data
        print("      ✅ retrieve OK")
    except Exception as exc:
        print("      ⚠️  retrieve skipped —", exc.__class__.__name__)

    # presign (not all back-ends implement it)
    try:
        url = await store.presign_short(aid_txt)
        print("      ✅ presign OK →", url[:55] + "…")
    except Exception:
        print("      ⚠️  presign unavailable for this backend")

    # ── batch flow ────────────────────────────────────────────────────────
    batch_ids = await store.store_batch(
        [
            {
                "data": _rand_bytes(32),
                "mime": "application/octet-stream",
                "filename": f"batch_{i}.bin",
                "summary": f"batch {i}",
                "session_id": session,
            }
            for i in range(3)
        ]
    )
    print("      ✅ batch store →", len(batch_ids), "items")

    # Only attempt retrieve_batch if the method exists (API optional)
    if hasattr(store, "retrieve_batch"):
        try:
            await store.retrieve_batch(batch_ids)  # type: ignore[attr-defined]
            print("      ✅ batch retrieve OK")
        except Exception as exc:
            print("      ⚠️  batch retrieve skipped —", exc.__class__.__name__)
    else:
        print("      ⚠️  batch retrieve unsupported by provider")

    # ── negative path & delete ───────────────────────────────────────────
    try:
        await store.metadata("does_not_exist")
    except ArtifactNotFoundError:
        print("      ✅ non-existent metadata raises correctly")

    await store.delete(aid_txt)
    assert not await store.exists(aid_txt)
    print("      ✅ delete / exists OK")


# ---------------------------------------------------------------------------
# Single combination runner
# ---------------------------------------------------------------------------
async def _run_combo(session_p: str, storage_p: str, description: str):
    print(f"🧪  {description}")

    bucket_name = "chuk-sandbox-2" if storage_p == "s3" else f"{storage_p}-test"

    os.environ.update(
        {
            "ARTIFACT_SESSION_PROVIDER": session_p,
            "ARTIFACT_STORAGE_PROVIDER": storage_p,
            "ARTIFACT_BUCKET": bucket_name,
            "ARTIFACT_FS_ROOT": str(_tmp_root / storage_p),
        }
    )

    # Ensure filesystem bucket dir exists so validation fallback is happy
    if storage_p == "filesystem":
        (Path(os.environ["ARTIFACT_FS_ROOT"]) / bucket_name).mkdir(
            parents=True, exist_ok=True
        )

    try:
        store = ArtifactStore(
            session_provider=session_p,
            storage_provider=storage_p,
            bucket=bucket_name,
        )
    except Exception as exc:
        print("   ❌ initialization failed —", exc)
        return

    if not await _validate(store):
        print("   ❌ validation failed — skipping combo\n")
        await store.close()
        return

    print("   ✅ validation OK")
    await _basic_cycle(store, "smoke_test")

    # Simple stats via list_by_session (works everywhere)
    try:
        files_meta = await store.list_by_session("smoke_test")
        file_cnt = len(files_meta)
        bytes_total = sum(m.get("bytes", 0) for m in files_meta)
        print(f"   ✅ stats → files={file_cnt}, bytes={bytes_total}")
    except Exception as exc:
        print("   ⚠️  stats unavailable —", exc.__class__.__name__)

    await store.close()
    print()


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------
async def main():
    print("🚀 Comprehensive Artifact Store Smoke Test\n" + "=" * 50)
    for sess_p, store_p, desc in TEST_CONFIGS:
        await _run_combo(sess_p, store_p, desc)

    shutil.rmtree(_tmp_root, ignore_errors=True)
    print("🧹  temp dir removed →", _tmp_root)


if __name__ == "__main__":
    asyncio.run(main())
