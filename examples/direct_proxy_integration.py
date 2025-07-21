#!/usr/bin/env python
# examples/direct_proxy_integration.py
"""
examples/direct_proxy_integration.py
------------------------------------

Spin up the full CHUK MCP Runtime ***with the proxy layer enabled*** by calling
`run_runtime()`.  The process blocks until you press <Ctrl-C>.

Highlights
~~~~~~~~~~
* Injects extra proxy settings via **default_config**.
* Lets `run_runtime()` handle graceful shutdown - no custom signal handling.
* Works with the new single-flag design
  (`proxy.openai_compatible = true | false`).
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── locate project root (one path tweak only) -------------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chuk_mcp_runtime.entry import run_runtime

# ── proxy_config.yaml lives right next to this script -----------------
CONFIG_YAML = Path(__file__).with_name("proxy_config.yaml")
if not CONFIG_YAML.exists():
    sys.exit(f"Config file not found: {CONFIG_YAML}")

if __name__ == "__main__":
    print("Starting CHUK MCP Runtime with proxy support …")
    print(f"Config file: {CONFIG_YAML}\nPress Ctrl-C to stop.\n")

    # Any tweaks you want in addition to the YAML (optional)
    default_cfg = {
        "proxy": {
            "enabled": True,  # explicit, but YAML already sets it
            # "openai_compatible": True,  # uncomment for underscore aliases
        }
    }

    try:
        # Blocks until Ctrl-C or an uncaught exception
        run_runtime(
            config_paths=[str(CONFIG_YAML)],
            default_config=default_cfg,
        )
    except KeyboardInterrupt:
        # run_runtime() logs shutdown; this is just extra UX sugar
        print("\nShutdown requested — goodbye!")
