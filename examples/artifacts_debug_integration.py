#!/usr/bin/env python3
"""examples/debug_integration.py  — *revised*

Step‑by‑step diagnostics for the **chuk_mcp_runtime × chuk_artifacts** tool‑chain.
This revision fixes the earlier _“Tool 'write_file' is disabled in configuration”_
error by **explicitly enabling all artifact tools** at runtime via a temporary
in‑memory configuration overlay (mirroring the approach used in
`examples/artifacts_e2e_demo.py`).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

# ─────────────────────────────── utilities ────────────────────────────────


def show_current_environment() -> None:
    """Print concise information about the current Python environment."""
    print("\n🐍 Python Environment Info")
    print("=" * 30)

    print(f"Python version: {sys.version.split()[0]}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {Path.cwd()}")

    print("\nPython path (first 5 entries):")
    for i, p in enumerate(sys.path[:5], 1):
        print(f"  {i}. {p}")
    if len(sys.path) > 5:
        print(f"  … and {len(sys.path) - 5} more")

    print("\nRelevant environment variables:")
    for var in ("PYTHONPATH", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV"):
        print(f"  {var}: {os.getenv(var, 'Not set')}")


def check_package_availability() -> Dict[str, bool]:
    """Attempt to import the critical packages and report availability."""
    print("\n🔍 Package Availability Check")
    print("=" * 35)

    pkgs = [
        ("chuk_mcp_runtime", "CHUK MCP Runtime"),
        ("chuk_artifacts", "CHUK Artifacts"),
        ("chuk_mcp_runtime.tools", "MCP Runtime Tools"),
        ("chuk_mcp_runtime.tools.artifacts_tools", "Artifacts Tools Integration"),
    ]

    results: Dict[str, bool] = {}
    for mod, desc in pkgs:
        try:
            __import__(mod)
            print(f"✅ {desc}: Available")
            results[mod] = True
        except ImportError as exc:
            print(f"❌ {desc}: Not available ({exc})")
            results[mod] = False
    return results


def check_specific_imports() -> bool:
    """Import various symbols to ensure the public API surface is intact."""
    print("\n🧪 Specific Import Testing")
    print("=" * 30)

    try:
        from chuk_artifacts import ArtifactStore  # type: ignore

        inst = ArtifactStore(
            storage_provider="memory",
            session_provider="memory",
            bucket="test",
        )
        print("✅ chuk_artifacts.ArtifactStore: OK →", inst.__class__.__name__)
        for meth in ("store", "retrieve", "list_by_session", "validate_configuration"):
            print(f"  • {meth.ljust(22)} :", "yes" if hasattr(inst, meth) else "MISSING")
    except Exception as exc:
        print(f"❌ chuk_artifacts import/usage failed: {exc}")
        return False

    try:
        from chuk_mcp_runtime.tools import ARTIFACT_TOOLS, ARTIFACTS_TOOLS_AVAILABLE  # type: ignore

        print("✅ chuk_mcp_runtime.tools import: OK")
        print("   Tools available flag:", ARTIFACTS_TOOLS_AVAILABLE)
        if ARTIFACTS_TOOLS_AVAILABLE:
            print("   Registered tools     :", len(ARTIFACT_TOOLS))
    except Exception as exc:
        print(f"❌ chuk_mcp_runtime.tools import failed: {exc}")
        return False
    return True


# ────────────────────── configuration helpers (NEW) ───────────────────────

_ALL_TOOLS = (
    "upload_file write_file read_file list_session_files delete_file list_directory "
    "copy_file move_file get_file_metadata get_storage_stats get_presigned_url"
).split()


def _build_cfg(fs_root: Path, bucket: str) -> Dict[str, Any]:
    """Return a minimal runtime‑config overlay enabling **all** artifact tools."""
    return {
        "artifacts": {
            "storage_provider": "filesystem",
            "session_provider": "memory",
            "filesystem_root": str(fs_root),
            "bucket": bucket,
            "tools": {
                "enabled": True,
                "tools": {t: {"enabled": True} for t in _ALL_TOOLS},
            },
        }
    }


async def _enable_artifact_tools(cfg_extra: Dict[str, Any]) -> None:
    """Merge *cfg_extra* into the runtime config and register tools."""
    from chuk_mcp_runtime.server.config_loader import load_config  # type: ignore
    from chuk_mcp_runtime.tools import register_artifacts_tools  # type: ignore

    base = load_config(["config.yaml"], default_config={})
    base.update(cfg_extra)
    await register_artifacts_tools(base)


# ───────────────────────── integration smoke test ─────────────────────────


async def test_basic_integration() -> bool:  # noqa: C901 - (complexity acceptable here)
    """End‑to‑end exercise of write/read etc. now that tools are enabled."""
    print("\n🔬 Basic Integration Test")
    print("=" * 28)

    from chuk_mcp_runtime.tools.artifacts_tools import (
        get_artifact_store,
        list_session_files,
        write_file,
    )

    # 1) Temp workspace + env vars
    tmp_root = Path(tempfile.mkdtemp(prefix="integration_test_")).resolve()
    os.environ.update(
        {
            "ARTIFACT_FS_ROOT": str(tmp_root),
            "ARTIFACT_STORAGE_PROVIDER": "filesystem",
            "ARTIFACT_SESSION_PROVIDER": "memory",
            "ARTIFACT_BUCKET": "integration-bucket",
        }
    )

    # 2) Register & enable *all* tools via config overlay
    await _enable_artifact_tools(_build_cfg(tmp_root, "integration-bucket"))
    print("✅ Artifact tools registered + enabled")

    # 3) Obtain store through helper (ensures consistency with config)
    store = await get_artifact_store()
    print("✅ get_artifact_store →", type(store).__name__)

    # 4) Smoke‑test write/list round‑trip
    res = await write_file(
        content="Hello Integration!",
        filename="hello.txt",
        session_id="test-session",
    )
    print("✅ write_file →", res.strip())

    files = await list_session_files(session_id="test-session")
    print("✅ list_session_files →", len(files), "file(s)")

    # 5) Validate configuration
    cfg_status = await store.validate_configuration()
    print("✅ validate_configuration →", cfg_status.get("storage", {}).get("status"))

    await store.close()
    shutil.rmtree(tmp_root, ignore_errors=True)
    print("🎉 Integration test completed successfully!")
    return True


# ───────────────────────────────── main ───────────────────────────────────


async def _main() -> None:
    print("🔧 CHUK MCP Runtime × chuk_artifacts Integration Debug (rev2)")
    print("=" * 65)

    show_current_environment()
    availability = check_package_availability()

    if not availability.get("chuk_artifacts"):
        print("\n⚠️  chuk_artifacts not installed → please run `pip install chuk-artifacts`.")
        return

    if not check_specific_imports():
        print("\n⚠️  Import test failed — aborting integration test.")
        return

    ok = await test_basic_integration()
    if ok:
        print("\n✅ All checks passed — runtime is ready to rock!")
    else:
        print("\n❌ Integration test failed — see logs above.")

    print("\nDebug complete — have a nice day! \N{SPARKLES}")


if __name__ == "__main__":
    asyncio.run(_main())
