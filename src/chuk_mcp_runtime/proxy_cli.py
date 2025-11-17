#!/usr/bin/env python
# chuk_mcp_runtime/proxy_cli.py
"""
proxy_cli.py
============

Launch the CHUK proxy layer from a YAML file, CLI arguments, or both.
Fully async-native implementation.

Examples
--------
# YAML only
chuk-mcp-proxy --config examples/proxy_config.yaml

# Args only (start a local echo server)
chuk-mcp-proxy --stdio echo2 --cwd /src/echo \
               --command uv --args run src/chuk_mcp_echo_server/main.py

# YAML + override (add remote SSE server)
chuk-mcp-proxy --config proxy_config.yaml \
               --sse weather --url https://api.example.com/sse/weather \
               --api-key $WEATHER_KEY

# Enable OpenAI-style names (underscores)
chuk-mcp-proxy --openai-compatible
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chuk_mcp_runtime.proxy.manager import ProxyServerManager
from chuk_mcp_runtime.server.config_loader import load_config
from chuk_mcp_runtime.server.logging_config import configure_logging
from chuk_mcp_runtime.types import MCPServerConfig, RuntimeConfig


# ─────────────────── CLI parsing ────────────────────
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Launch the CHUK proxy layer.")
    p.add_argument(
        "--config",
        metavar="FILE",
        help="YAML config file (optional - can be combined with flags below)",
    )

    # declare servers
    p.add_argument(
        "--stdio",
        action="append",
        metavar="NAME",
        help="add a local stdio MCP server (repeatable)",
    )
    p.add_argument(
        "--sse",
        action="append",
        metavar="NAME",
        help="add a remote SSE MCP server (repeatable)",
    )

    # stdio options
    p.add_argument(
        "--command",
        default="python",
        help="executable for stdio servers (default: python)",
    )
    p.add_argument("--cwd", default="", help="working directory for stdio server")
    p.add_argument("--args", nargs=argparse.REMAINDER, help="additional args for the stdio command")

    # sse options
    p.add_argument("--url", help="SSE base URL")
    p.add_argument("--api-key", help="SSE API key (or set API_KEY env var)")

    # proxy format option
    p.add_argument(
        "--openai-compatible",
        action="store_true",
        help="use OpenAI-compatible tool names (underscores)",
    )

    return p.parse_args()


# ───────────── configuration helpers ─────────────
def _empty_config() -> RuntimeConfig:
    config = RuntimeConfig()
    config.proxy.enabled = True
    config.proxy.namespace = "proxy"
    config.proxy.openai_compatible = False
    return config


def _merge_yaml(path: Path | None) -> RuntimeConfig:
    if not path:
        return _empty_config()
    if not path.exists():
        sys.exit(f"⚠️  Config file not found: {path}")
    return load_config([str(path)])


def _inject_stdio(cfg: RuntimeConfig, name: str, ns: argparse.Namespace) -> None:
    cfg.mcp_servers[name] = MCPServerConfig(
        command=ns.command,
        args=ns.args or [],
        env={},
        location=ns.cwd,
        type="stdio",
        enabled=True,
    )


def _inject_sse(cfg: RuntimeConfig, name: str, ns: argparse.Namespace) -> None:
    # SSE servers use a different pattern - no command/args needed
    cfg.mcp_servers[name] = MCPServerConfig(
        command="",  # SSE doesn't use command
        args=[],
        env={},
        type="sse",
        enabled=True,
        url=ns.url,
        api_key=ns.api_key or os.getenv("API_KEY", ""),
    )


# ─────────────────── async core ────────────────────
async def _async_main() -> None:
    args = _parse_args()

    # 1) YAML baseline (or empty)
    cfg = _merge_yaml(Path(args.config) if args.config else None)

    # 2) CLI overrides / additions
    cfg.proxy.openai_compatible = args.openai_compatible

    for name in args.stdio or []:
        _inject_stdio(cfg, name, args)
    for name in args.sse or []:
        _inject_sse(cfg, name, args)

    # 3) logging
    configure_logging(cfg.to_dict())

    # 4) start proxy layer
    proxy = ProxyServerManager(cfg.to_dict(), project_root=str(ROOT))
    await proxy.start_servers()

    try:
        running = ", ".join(proxy.running.keys()) or "— none —"
        print("Running servers :", running)

        tools = await proxy.get_all_tools()
        print("Wrapped tools   :", ", ".join(tools) or "— none —")

        # quick smoke-test
        if tools:
            first_tool_name = next(iter(tools))
            first_tool = tools[first_tool_name]
            res = await first_tool(message="Hello from proxy_cli!")
            print("Smoke-test call :", res)

        # block until Ctrl-C
        await asyncio.Event().wait()
    finally:
        await proxy.stop_servers()
        print("Proxy shut down.")


# ───────────── entry-point wrapper ─────────────
def cli() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
