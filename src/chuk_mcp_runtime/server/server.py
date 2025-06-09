# chuk_mcp_runtime/server/server.py
"""
CHUK MCP Server

* automatic session-ID injection for artifact tools
* optional bearer-token auth middleware
* transparent chuk_artifacts integration
* global **and per-tool** timeout support
* end-to-end **token streaming** for async-generator tools
* JSON concatenation fixing for tool parameters
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import time
import uuid
from inspect import (
    iscoroutinefunction,
    isasyncgenfunction,   # <-- NEW
    isasyncgen,          # <-- NEW
)
from typing import Any, Callable, Dict, List, Optional, Union

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, PlainTextResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from chuk_mcp_runtime.common.mcp_tool_decorator import (
    TOOLS_REGISTRY,
    initialize_tool_registry,
)
from chuk_mcp_runtime.common.tool_naming import resolve_tool_name, update_naming_maps
from chuk_mcp_runtime.common.verify_credentials import validate_token
from chuk_mcp_runtime.server.logging_config import get_logger
from chuk_mcp_runtime.session.session_management import (
    SessionError,
    clear_session_context,
    get_session_context,
    set_session_context,
)

# ─────────────────────────── Optional chuk_artifacts ──────────────────────────
try:
    from chuk_artifacts import ArtifactStore

    CHUK_ARTIFACTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    CHUK_ARTIFACTS_AVAILABLE = False
    ArtifactStore = None  # type: ignore

# ------------------------------------------------------------------------------
# JSON Concatenation Fix Utilities
# ------------------------------------------------------------------------------

def parse_tool_arguments(arguments: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse tool arguments, handling concatenated JSON strings.
    
    Handles cases like: {"text":"hello"}{"delay":0.5} -> {"text":"hello", "delay":0.5}
    """
    # If it's already a dict, return as-is (most common case)
    if isinstance(arguments, dict):
        return arguments
    
    # If it's None or empty, return empty dict
    if not arguments:
        return {}
    
    # Handle string arguments (where concatenation might occur)
    if isinstance(arguments, str):
        # First, try to parse as normal JSON
        try:
            parsed = json.loads(arguments)
            # If successful and it's a dict, return it
            if isinstance(parsed, dict):
                return parsed
            # If it's not a dict, wrap it
            return {"value": parsed}
        except json.JSONDecodeError:
            pass
        
        # If normal parsing failed, try to fix concatenated JSON
        if '}' in arguments and '{' in arguments:
            # Pattern to find }{ concatenations (with optional whitespace)
            pattern = r'\}\s*\{'
            if re.search(pattern, arguments):
                # Replace }{ with },{ to make it a valid JSON array
                array_str = '[' + re.sub(pattern, '},{', arguments) + ']'
                try:
                    # Parse as array of objects
                    objects = json.loads(array_str)
                    
                    # Merge all objects into one
                    merged = {}
                    for obj in objects:
                        if isinstance(obj, dict):
                            merged.update(obj)
                        else:
                            # If non-dict object in array, add with index
                            merged[f"value_{len(merged)}"] = obj
                    
                    return merged
                except json.JSONDecodeError:
                    # If parsing the array fails, fall through to string handling
                    pass
        
        # If all JSON parsing fails, treat as plain string
        return {"text": arguments}
    
    # For any other type, convert to string and wrap
    return {"value": str(arguments)}


# ------------------------------------------------------------------------------
# Authentication middleware
# ------------------------------------------------------------------------------
class AuthMiddleware(BaseHTTPMiddleware):
    """Simple bearer-token / cookie-based auth."""

    def __init__(self, app: ASGIApp, auth: Optional[str] = None, health_path: Optional[str] = "/health") -> None:
        super().__init__(app)
        self.auth = auth
        self.health_path = health_path

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if request.url.path == self.health_path and request.method == "GET":
            return await call_next(request)
    
        if self.auth != "bearer":
            return await call_next(request)

        token = None
        # 1) Authorization header
        if "Authorization" in request.headers:
            m = re.match(r"Bearer\s+(.+)", request.headers["Authorization"], re.I)
            if m:
                token = m.group(1)
        # 2) cookie fallback
        if not token:
            token = request.cookies.get("jwt_token")

        if not token:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)

        try:
            payload = await validate_token(token)
            request.scope["user"] = payload
        except HTTPException as exc:
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

        return await call_next(request)


# ------------------------------------------------------------------------------
# MCPServer
# ------------------------------------------------------------------------------

_ARTIFACT_RX = re.compile(
    r"\b("
    r"write_file|upload_file|read_file|delete_file|"
    r"list_session_files|list_directory|copy_file|move_file|"
    r"get_file_metadata|get_presigned_url|get_storage_stats"
    r")\b"
)


class MCPServer:
    """Central MCP server with session & artifact-store support."""

    # ------------------------------------------------------------------ #
    # Construction & helpers                                             #
    # ------------------------------------------------------------------ #

    def __init__(
        self,
        config: Dict[str, Any],
        tools_registry: Optional[Dict[str, Callable]] = None,
    ) -> None:
        self.config = config
        self.logger = get_logger("chuk_mcp_runtime.server", config)

        self.server_name = config.get("host", {}).get("name", "generic-mcp")
        self.tools_registry = tools_registry or TOOLS_REGISTRY
        self.current_session: Optional[str] = None
        self.artifact_store: Optional[ArtifactStore] = None

        # Tool timeout configuration
        self.tool_timeout = self._get_tool_timeout()
        self.logger.info("Tool timeout configured: %.1fs (global default)", self.tool_timeout)

        update_naming_maps()  # make sure resolve_tool_name works

    # ..........................................................................
    # timeout helpers
    # ..........................................................................

    def _get_tool_timeout(self) -> float:
        """Pick global timeout from config/env with sane fall-back."""
        timeout_sources = [
            self.config.get("tools", {}).get("timeout"),
            self.config.get("tool_timeout"),
            os.getenv("MCP_TOOL_TIMEOUT"),
            os.getenv("TOOL_TIMEOUT"),
            60.0,  # default
        ]
        for t in timeout_sources:
            if t is not None:
                try:
                    return float(t)
                except (ValueError, TypeError):
                    continue
        return 60.0

    # ..........................................................................
    # artifact store (unchanged)
    # ..........................................................................

    async def _setup_artifact_store(self) -> None:
        if not CHUK_ARTIFACTS_AVAILABLE:
            self.logger.info("chuk_artifacts not installed – file tools disabled")
            return

        cfg = self.config.get("artifacts", {})
        storage = cfg.get(
            "storage_provider", os.getenv("ARTIFACT_STORAGE_PROVIDER", "filesystem")
        )
        session = cfg.get(
            "session_provider", os.getenv("ARTIFACT_SESSION_PROVIDER", "memory")
        )
        bucket = cfg.get(
            "bucket", os.getenv("ARTIFACT_BUCKET", f"mcp-{self.server_name}")
        )

        # filesystem root (only when storage == filesystem)
        if storage == "filesystem":
            fs_root = cfg.get(
                "filesystem_root",
                os.getenv(
                    "ARTIFACT_FS_ROOT",
                    os.path.expanduser(f"~/.chuk_mcp_artifacts/{self.server_name}"),
                ),
            )
            os.environ["ARTIFACT_FS_ROOT"] = fs_root  # chuk_artifacts honours this

        try:
            self.artifact_store = ArtifactStore(
                storage_provider=storage, session_provider=session, bucket=bucket
            )
            status = await self.artifact_store.validate_configuration()
            if (
                status["session"]["status"] == "ok"
                and status["storage"]["status"] == "ok"
            ):
                self.logger.info("Artifact store ready: %s/%s → %s", storage, session, bucket)
            else:
                self.logger.warning("Artifact-store config issues: %s", status)
        except Exception as exc:  # pragma: no cover
            self.logger.error("Artifact-store init failed: %s", exc)
            self.artifact_store = None

    async def _import_tools_registry(self) -> Dict[str, Callable]:
        mod = self.config.get("tools", {}).get(
            "registry_module", "chuk_mcp_runtime.common.mcp_tool_decorator"
        )
        attr = self.config.get("tools", {}).get("registry_attr", "TOOLS_REGISTRY")

        try:
            m = importlib.import_module(mod)
            if iscoroutinefunction(getattr(m, "initialize_tool_registry", None)):
                await m.initialize_tool_registry()
            registry: Dict[str, Callable] = getattr(m, attr, {})
        except Exception as exc:
            self.logger.error("Unable to import tool registry: %s", exc)
            registry = {}

        update_naming_maps()
        return registry

    # ------------------------------------------------------------------ #
    # Session helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _inject_session_context(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Auto-add `session_id` for artifact helpers."""
        if _ARTIFACT_RX.search(tool_name) and "session_id" not in args:
            if not self.current_session:
                self.current_session = (
                    f"mcp-session-{int(time.time())}-{uuid.uuid4().hex[:8]}"
                )
                self.logger.info("Auto-created session: %s", self.current_session)
            args = {**args, "session_id": self.current_session}
        return args

    # ------------------------------------------------------------------ #
    # Tool execution with timeout & streaming                            #
    # ------------------------------------------------------------------ #

    async def _execute_tool_with_timeout(
        self, func: Callable, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """
        Execute a tool.

        * Coroutine tools → awaited with asyncio.wait_for()
        * Async-generator tools → streamed, still respecting timeout
        """
        timeout = getattr(func, "_tool_timeout", None) or self.tool_timeout

        # ── async-generator branch ───────────────────────────────────────────
        if isasyncgenfunction(func):
            agen = func(**arguments)  # create generator
            start = time.time()

            async def _wrapper():
                nonlocal start
                try:
                    async for chunk in agen:
                        yield chunk
                        if (time.time() - start) >= timeout:
                            raise asyncio.TimeoutError()
                finally:
                    await agen.aclose()

            return _wrapper()  # caller will iterate

        # ── classic coroutine branch ─────────────────────────────────────────
        try:
            self.logger.debug("Executing tool '%s' (timeout %.1fs)", tool_name, timeout)
            return await asyncio.wait_for(func(**arguments), timeout=timeout)
        except asyncio.TimeoutError:
            raise ValueError(f"Tool '{tool_name}' timed out after {timeout:.1f}s")

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    async def serve(self, custom_handlers: Optional[Dict[str, Callable]] = None) -> None:
        """Boot the MCP server (stdio or SSE) and serve forever."""
        await self._setup_artifact_store()

        if not self.tools_registry:
            self.tools_registry = await self._import_tools_registry()

        await initialize_tool_registry()
        update_naming_maps()

        server = Server(self.server_name)

        # ----------------------------- list_tools ----------------------------- #

        @server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools with robust error handling."""
            try:
                self.logger.info("list_tools called – %d tools total", len(self.tools_registry))
                
                tools = []
                for tool_name, func in self.tools_registry.items():
                    try:
                        if hasattr(func, "_mcp_tool"):
                            tool_obj = func._mcp_tool
                            
                            # Verify the tool object is valid
                            if hasattr(tool_obj, 'name') and hasattr(tool_obj, 'description'):
                                tools.append(tool_obj)
                                self.logger.debug("Added tool to list: %s", tool_obj.name)
                            else:
                                self.logger.warning("Tool %s has invalid _mcp_tool object: %s", 
                                                tool_name, tool_obj)
                        else:
                            self.logger.warning("Tool %s missing _mcp_tool attribute", tool_name)
                            
                    except Exception as e:
                        self.logger.error("Error processing tool %s: %s", tool_name, e)
                        continue
                
                self.logger.info("Returning %d valid tools", len(tools))
                return tools
                
            except Exception as e:
                self.logger.error("Error in list_tools: %s", e)
                import traceback
                self.logger.error("Full traceback: %s", traceback.format_exc())
                # Return empty list rather than crashing
                return []

        # ----------------------------- call_tool ----------------------------- #
        @server.call_tool()
        async def call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
            """Execute a tool with JSON concatenation fixing and streaming workaround."""
            try:
                # Fix concatenated JSON in arguments FIRST
                original_args = arguments
                if arguments:
                    if isinstance(arguments, (str, dict)):
                        arguments = parse_tool_arguments(arguments)
                        
                        # Log if we had to fix anything
                        if arguments != original_args:
                            self.logger.info("Fixed concatenated JSON arguments for '%s': %s -> %s", 
                                           name, original_args, arguments)

                self.logger.debug("call_tool called with name='%s', arguments=%s", name, arguments)
                registry = self.tools_registry

                # ── name resolution ───────────────────────────────────────────────
                resolved = name if name in registry else resolve_tool_name(name)
                if resolved not in registry:
                    matches = [
                        k
                        for k in registry
                        if k.endswith(f"_{name}") or k.endswith(f".{name}")
                    ]
                    if len(matches) == 1:
                        resolved = matches[0]
                if resolved not in registry:
                    raise ValueError(f"Tool not found: {name}")

                func = registry[resolved]
                self.logger.debug("Resolved tool '%s' to function: %s", name, func)

                # ── auto-inject session_id for artifact helpers ──────────────────
                arguments = await self._inject_session_context(resolved, arguments)
                is_artifact_tool = _ARTIFACT_RX.search(resolved) is not None

                # ── execute (with timeout / streaming) ───────────────────────────
                if self.current_session:
                    set_session_context(self.current_session)

                self.logger.debug("About to execute tool '%s'", resolved)
                result = await self._execute_tool_with_timeout(func, resolved, arguments)
                self.logger.debug("Tool execution completed, result type: %s", type(result))

                # Did the tool change the session?
                new_ctx = get_session_context()
                if new_ctx and new_ctx != self.current_session:
                    self.current_session = new_ctx

                # ── streaming path: collect all chunks to work around MCP library bug ────────────────────
                if isasyncgen(result):
                    self.logger.debug("Tool returned async generator, collecting all chunks for '%s'", resolved)
                    
                    collected_chunks = []
                    chunk_count = 0
                    
                    try:
                        async for part in result:
                            chunk_count += 1
                            self.logger.debug("Collecting streaming chunk %d for '%s': %s", chunk_count, resolved, part)
                            
                            # Convert to TextContent
                            if isinstance(part, (TextContent, ImageContent, EmbeddedResource)):
                                collected_chunks.append(part)
                            elif isinstance(part, str):
                                collected_chunks.append(TextContent(type="text", text=part))
                            elif isinstance(part, dict) and "delta" in part:
                                collected_chunks.append(TextContent(type="text", text=part["delta"]))
                            else:
                                collected_chunks.append(TextContent(
                                    type="text", text=json.dumps(part, ensure_ascii=False)
                                ))
                        
                        self.logger.debug("Collected %d chunks for '%s'", chunk_count, resolved)
                        
                        # Return all chunks as a single response
                        if collected_chunks:
                            return collected_chunks
                        else:
                            return [TextContent(type="text", text="No output from streaming tool")]
                            
                    except Exception as e:
                        self.logger.error("Error collecting streaming chunks for '%s': %s", resolved, e)
                        return [TextContent(type="text", text=f"Streaming error: {str(e)}")]

                # ── non-streaming path (finish like before) ───────────────────────
                self.logger.debug("Tool returned non-streaming result for '%s'", resolved)
                
                if is_artifact_tool:
                    wrapped = (
                        {**result, "session_id": self.current_session}
                        if isinstance(result, dict)
                        and "content" in result
                        and "isError" in result
                        else {
                            "session_id": self.current_session,
                            "content": result,
                            "isError": False,
                        }
                    )
                    result = wrapped

                if (
                    isinstance(result, list)
                    and all(
                        isinstance(r, (TextContent, ImageContent, EmbeddedResource))
                        for r in result
                    )
                ):
                    return result

                if isinstance(result, str):
                    return [TextContent(type="text", text=result)]

                # everything else → JSON string
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
            except Exception as e:
                self.logger.error("Error in call_tool for '%s': %s", name, e)
                import traceback
                self.logger.error("Full traceback: %s", traceback.format_exc())
                return [TextContent(type="text", text=f"Tool execution error: {str(e)}")]
                
        # ------------------------------------------------------------------ #
        # transport bootstrapping (stdio / SSE)                             #
        # ------------------------------------------------------------------ #
        opts = server.create_initialization_options()
        mode = self.config.get("server", {}).get("type", "stdio")

        if mode == "stdio":
            self.logger.info(
                "Starting MCP (stdio) – global timeout %.1fs …", self.tool_timeout
            )
            async with stdio_server() as (r, w):
                await server.run(r, w, opts)

        elif mode == "sse":
            cfg = self.config.get("sse", {})
            host, port = cfg.get("host", "0.0.0.0"), cfg.get("port", 8000)
            sse_path, msg_path, health_path = cfg.get("sse_path", "/sse"), cfg.get("message_path", "/messages/"), cfg.get("health_path", "/health")
            transport = SseServerTransport(msg_path)

            async def _handle_sse(request: Request):
                async with transport.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    await server.run(streams[0], streams[1], opts)
                return Response()
            
            async def health(request):
                return PlainTextResponse("OK")

            app = Starlette(
                routes=[
                    Route(sse_path, _handle_sse, methods=["GET"]),
                    Mount(msg_path, app=transport.handle_post_message),
                    Route(health_path, health, methods=["GET"]),
                ],
                middleware=[
                    Middleware(
                        AuthMiddleware,
                        auth=self.config.get("server", {}).get("auth"),
                        health_path=health_path,
                    )
                ],
            )
            self.logger.info(
                "Starting MCP (SSE) on %s:%s – global timeout %.1fs …",
                host,
                port,
                self.tool_timeout,
            )
            await uvicorn.Server(
                uvicorn.Config(app, host=host, port=port, log_level="info")
            ).serve()
        else:
            raise ValueError(f"Unknown server type: {mode}")

    # ------------------------------------------------------------------ #
    # Misc administrative helpers                                        #
    # ------------------------------------------------------------------ #

    async def register_tool(self, name: str, func: Callable) -> None:
        if not hasattr(func, "_mcp_tool"):
            self.logger.warning("Function %s lacks _mcp_tool metadata", func.__name__)
            return
        self.tools_registry[name] = func
        update_naming_maps()

    async def get_tool_names(self) -> List[str]:
        return list(self.tools_registry)

    # session getters / setters -----------------------------------------

    def set_session(self, session_id: str) -> None:
        self.current_session = session_id
        set_session_context(session_id)

    def get_current_session(self) -> Optional[str]:
        return self.current_session

    def get_artifact_store(self) -> Optional[ArtifactStore]:
        return self.artifact_store

    async def close(self) -> None:
        if self.artifact_store:
            try:
                await self.artifact_store.close()
            except Exception as exc:  # pragma: no cover
                self.logger.warning("Error closing artifact store: %s", exc)