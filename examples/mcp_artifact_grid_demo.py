#!/usr/bin/env python3
"""
mcp_artifact_grid_demo.py
=========================

Grid-path & presign-URL sanity-check that goes **through the
chuk_mcp_runtime.artifacts wrapper** (so any existing MCP code keeps
working without touching chuk_artifacts directly).

• Works with either in-memory / filesystem back-ends or a real S3/MinIO
  bucket - decided entirely by your environment variables.

Relevant env vars
─────────────────
ARTIFACT_STORAGE_PROVIDER   memory | filesystem | s3
ARTIFACT_SESSION_PROVIDER   memory | redis
ARTIFACT_BUCKET             bucket name (for S3)
SANDBOX_ID                  sandbox namespace (default: "wrapper-demo")
# …plus the normal AWS_* / S3_ENDPOINT_URL vars for S3.
"""

import asyncio
import os
import textwrap
from datetime import datetime

# ← we import **the wrapper**, not chuk_artifacts directly
from chuk_mcp_runtime.artifacts import ArtifactStore
from dotenv import load_dotenv


def heading(txt: str) -> None:
    print(f"\n{txt}\n" + "─" * len(txt))


async def main() -> None:
    # ------------------------------------------------------------------ env
    load_dotenv()  # pick up AWS / MinIO creds, etc.

    storage_provider = os.getenv("ARTIFACT_STORAGE_PROVIDER", "memory")
    session_provider = os.getenv("ARTIFACT_SESSION_PROVIDER", "memory")
    bucket = os.getenv("ARTIFACT_BUCKET", "wrapper-demo")
    sandbox_id = os.getenv("SANDBOX_ID", "wrapper-demo")

    # ------------------------------------------------------------------ store
    store = ArtifactStore(
        storage_provider=storage_provider,
        session_provider=session_provider,
        bucket=bucket,
        sandbox_id=sandbox_id,
    )

    ok = await store.validate_configuration()
    provider_line = f"{storage_provider.upper()} / {session_provider.upper()}  →  {bucket}"
    heading(f"🔧  Using {provider_line}")
    print(textwrap.indent(str(ok), "   "))

    # ------------------------------------------------------------------ session
    session_id = await store.create_session(user_id="tester")
    heading("🆔  Session created")
    print("   ", session_id)

    # ------------------------------------------------------------------ store a couple of artefacts
    heading("💾  Storing artefacts")
    txt_id = await store.store(
        data=f"Hello @ {datetime.utcnow()}".encode(),
        mime="text/plain",
        summary="demo text file",
        filename="demo.txt",
        session_id=session_id,
    )
    png_id = await store.store(
        data=b"\x89PNG\r\n\x1a\n",  # tiny fake PNG header
        mime="image/png",
        summary="demo image",
        filename="demo.png",
        session_id=session_id,
    )
    print("   stored:", txt_id, png_id)

    # ------------------------------------------------------------------ grid helpers
    heading("🌐  GRID PATHS")
    canon = store.get_canonical_prefix(session_id)
    txt_key = store.generate_artifact_key(session_id, txt_id)
    png_key = store.generate_artifact_key(session_id, png_id)
    print(f"Session prefix  : {canon}")
    print(f"TXT artefact key: {txt_key}")
    print(f"PNG artefact key: {png_key}")

    # quick round-trip verify
    assert txt_key.startswith(canon) and png_key.startswith(canon)

    # ------------------------------------------------------------------ presign URLs
    heading("🔑  PRESIGNED URL CHECK")
    short_url = await store.presign_short(txt_id)
    # only meaningful for S3/MinIO - but print regardless
    print("short URL  :", short_url)

    # try to extract the object-key part out of the URL for a match check
    try:
        # URL looks like  https://host/bucket/key?sig…
        key_in_url = short_url.split(f"{bucket}/", 1)[1].split("?", 1)[0]
        print("key in URL :", key_in_url)
        print("helper key :", txt_key)
        print("MATCH?     :", key_in_url == txt_key)
    except Exception:
        print("URL parsing skipped (non-S3 provider)")

    # ------------------------------------------------------------------ tidy
    await store.delete(txt_id)
    await store.delete(png_id)
    await store.close()

    heading("🎉  DEMO COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
