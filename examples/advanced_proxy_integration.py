#!/usr/bin/env python
"""
examples/advanced_proxy_integration.py
--------------------------------------

Boot a ProxyServerManager directly, list wrapped tools, make one direct echo
call, then let you interactively echo messages until you press Ctrl-C or type
“exit”.

• Works with dot wrappers (default) or underscore wrappers when
  proxy.openai_compatible=true in the YAML or toggled below.
• Single asyncio event-loop, graceful Ctrl-C handling.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import traceback
from pathlib import Path
from typing import Dict, List

# ── project path -----------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chuk_mcp_runtime.proxy.manager import ProxyServerManager
from chuk_mcp_runtime.server.config_loader import find_project_root, load_config
from chuk_mcp_runtime.server.logging_config import configure_logging

HERE = Path(__file__).resolve().parent
CONFIG_YAML = HERE / "proxy_config.yaml"
if not CONFIG_YAML.exists():
    sys.exit(f"Config file not found: {CONFIG_YAML}")


# ───────────────────────── helpers ─────────────────────────
async def prompt_loop(echo_tool) -> None:
    print("\n=== Interactive mode === (type 'exit' to quit)\n")
    loop = asyncio.get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, lambda: input("> "))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in {"exit", "quit", "q"}:
            break
        try:
            result = await echo_tool(message=line)
            print("Result:", result)
        except Exception as exc:  # noqa: BLE001
            print("⚠️  Tool error:", exc)
            traceback.print_exc()


def pick_echo_tool(wrappers: Dict[str, callable]) -> tuple[str, callable]:
    for name, fn in wrappers.items():
        if "echo" in name.lower():
            return name, fn
    raise RuntimeError("No echo tool found in wrapped tools")


# ───────────────────────── main async ─────────────────────
async def main() -> None:
    # 1) load config & logging
    config = load_config([str(CONFIG_YAML)])
    configure_logging(config)

    # Toggle underscore aliases if desired
    # config.setdefault("proxy", {})["openai_compatible"] = True

    proxy = ProxyServerManager(config, find_project_root())

    # graceful Ctrl-C handling
    stop_event = asyncio.Event()

    def _on_sigint() -> None:
        if not stop_event.is_set():
            print("\nStopping… (Ctrl-C again to force)")
            stop_event.set()
        else:
            print("\nForce exiting!")
            os._exit(1)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_sigint)

    # 2) start proxy layer
    print("Booting proxy layer …")
    await proxy.start_servers()

    # 3) inventory
    running_servers: List[str] = list(proxy.running.keys())
    print(f"\nRunning servers: {', '.join(running_servers) or 'None'}")

    wrappers = proxy.get_all_tools()
    print(f"Wrapped tools   : {len(wrappers)}")
    for w in sorted(wrappers):
        print("  •", w)

    # 4) choose echo tool
    try:
        echo_name, echo_fn = pick_echo_tool(wrappers)
    except RuntimeError as exc:
        print(exc)
        await proxy.stop_servers()
        return

    print("\n=== Direct call ===")
    res = await echo_fn(message="Hello via direct call!")
    print("Result:", res)

    # 5) interactive prompt
    await prompt_loop(echo_fn)

    stop_event.set()
    await proxy.stop_servers()
    print("Proxy layer shut down cleanly.")


# ───────────────────────── entry point ─────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nForce-terminated by user.")
