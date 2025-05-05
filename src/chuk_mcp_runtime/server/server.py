# server.py
# -*- coding: utf-8 -*-
"""
CHUK MCP Server
===============

Core runtime for discovering tools and exposing them over MCP.  
Supports both built-in transports supplied by *mcp*:

* **STDIO** – great for CLI tools and editor integrations.
* **SSE**   – HTTP streaming via Starlette + Uvicorn.

Select the transport in *config["server"]["type"]* ("stdio" | "sse").
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from typing import Any, Callable, Dict, List, Optional, Union

# ── MCP runtime imports ──────────────────────────────────────────────
from mcp.server import Server
from mcp.server.stdio import stdio_server            # always available
from mcp.server.sse import SseServerTransport        # requires starlette + uvicorn

# For SSE server
from starlette.applications import Starlette
from starlette.routing import Route, Mount
import uvicorn

from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool

# ── Local runtime ────────────────────────────────────────────────────
from chuk_mcp_runtime.server.logging_config import get_logger


class MCPServer:
    """
    Manage tool discovery/registration and run the MCP server over the chosen
    transport (stdio | sse).
    """

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        config: Dict[str, Any],
        tools_registry: Optional[Dict[str, Callable]] = None,
    ):
        self.config = config
        self.logger = get_logger("chuk_mcp_runtime.server", config)
        self.server_name = config.get("host", {}).get("name", "generic-mcp")
        self.tools_registry = tools_registry or self._import_tools_registry()

    # ------------------------------------------------------------------ #
    # Tools discovery                                                    #
    # ------------------------------------------------------------------ #
    def _import_tools_registry(self) -> Dict[str, Callable]:
        tools_cfg = self.config.get("tools", {})
        module_path = tools_cfg.get(
            "registry_module", "chuk_mcp_runtime.common.mcp_tool_decorator"
        )
        attr_name = tools_cfg.get("registry_attr", "TOOLS_REGISTRY")

        try:
            mod = importlib.import_module(module_path)
            registry: Dict[str, Callable] = getattr(mod, attr_name, {})
        except (ImportError, AttributeError) as exc:
            self.logger.error("Failed to load TOOLS_REGISTRY from %s: %s", module_path, exc)
            registry = {}

        if registry:
            self.logger.debug(
                "Loaded %d tools: %s", len(registry), ", ".join(registry.keys())
            )
        else:
            self.logger.warning("No tools available")

        return registry

    # ------------------------------------------------------------------ #
    # Main entry                                                         #
    # ------------------------------------------------------------------ #
    async def serve(self, custom_handlers: Optional[Dict[str, Callable]] = None) -> None:
        import json
        
        server = Server(self.server_name)

        # ------------ list_tools --------------------------------------
        @server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                fn._mcp_tool  # type: ignore[attr-defined]
                for fn in self.tools_registry.values()
                if hasattr(fn, "_mcp_tool")
            ]

        # ------------ call_tool --------------------------------------
        @server.call_tool()
        async def call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
            if name not in self.tools_registry:
                raise ValueError(f"Tool not found: {name}")

            func = self.tools_registry[name]
            self.logger.debug("Executing %s with %s", name, arguments)

            result = func(**arguments)
            if inspect.isawaitable(result):
                result = await result

            # Already content objects?
            if isinstance(result, list) and all(
                isinstance(x, (TextContent, ImageContent, EmbeddedResource)) for x in result
            ):
                return result

            # Plain string → wrap
            if isinstance(result, str):
                return [TextContent(type="text", text=result)]

            # Fallback → JSON dump
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # ------------ optional extra handlers ------------------------
        if custom_handlers:
            for name, fn in custom_handlers.items():
                self.logger.debug("Adding custom handler: %s", name)
                setattr(server, name, fn)

        options = server.create_initialization_options()
        srv_type = self.config.get("server", {}).get("type", "stdio").lower()

        # ------------------------------------------------------------------ #
        # Transport selection                                                #
        # ------------------------------------------------------------------ #
        if srv_type == "stdio":
            self.logger.info("Starting MCP server on STDIO")
            async with stdio_server() as (r, w):
                await server.run(r, w, options)

        elif srv_type == "sse":
            self.logger.info("Starting MCP server over SSE")
            # Get SSE server configuration
            sse_config = self.config.get("sse", {})
            host = sse_config.get("host", "127.0.0.1")
            port = sse_config.get("port", 8000)
            sse_path = sse_config.get("sse_path", "/sse")
            msg_path = sse_config.get("message_path", "/messages")
            
            # Create the starlette app with routes
            from starlette.applications import Starlette
            from starlette.responses import JSONResponse, PlainTextResponse, Response
            from starlette.routing import Route
            from starlette.requests import Request
            import json
            
            # Create the SSE transport instance
            sse_transport = SseServerTransport(msg_path)
            
            async def handle_sse(request: Request):
                async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
                    await server.run(streams[0], streams[1], options)
                # Return empty response to avoid NoneType error
                return Response()
            
            routes = [
                Route("/sse", endpoint=handle_sse, methods=["GET"]),
                Mount("/messages/", app=sse_transport.handle_post_message),
            ]
            
            starlette_app = Starlette(routes=routes)
            
            # uvicorn.run(starlette_app, host="0.0.0.0", port=port)
            config = uvicorn.Config(starlette_app, host=host, port=port, log_level="info")
            uvicorn_server = uvicorn.Server(config)
            await uvicorn_server.serve()
            
            # A mapping to track active sessions
            # active_sessions = {}
            
            # ASGI handler functions (using the low-level interface)
            # async def handle_sse(scope, receive, send):
            #     """Handle SSE connections using the low-level ASGI interface"""
            #     if scope["type"] != "http":
            #         return
                
            #     # Get session_id from query params
            #     session_id = None
            #     query_string = scope.get("query_string", b"").decode("utf-8")
            #     if query_string:
            #         for param in query_string.split('&'):
            #             if '=' in param:
            #                 key, value = param.split('=', 1)
            #                 if key == "session_id":
            #                     session_id = value
                
            #     if not session_id:
            #         # Generate a session ID if none provided
            #         import uuid
            #         session_id = str(uuid.uuid4())
                
            #     self.logger.debug(f"New SSE connection with session_id: {session_id}")
                
            #     # Use the SSE transport to handle this connection
            #     async with sse_transport.connect_sse(scope, receive, send) as streams:
            #         # Store the session streams for later message delivery
            #         active_sessions[session_id] = streams
                    
            #         # Keep the connection open until client disconnects or error
            #         try:
            #             # Process incoming commands from the server
            #             # Create initialization options and pass them to run
            #             await server.run(streams[0], streams[1], options)
            #         except Exception as e:
            #             self.logger.error(f"Error in SSE session {session_id}: {e}")
            #         finally:
            #             # Clean up when the connection closes
            #             if session_id in active_sessions:
            #                 del active_sessions[session_id]
            #                 self.logger.debug(f"Closed SSE session: {session_id}")
            
            # async def handle_messages(scope, receive, send):
            #     """Handle incoming messages using the low-level ASGI interface"""
            #     if scope["type"] != "http":
            #         return
                
            #     # Process the request body
            #     request_body = b""
            #     more_body = True
                
            #     while more_body:
            #         message = await receive()
            #         request_body += message.get("body", b"")
            #         more_body = message.get("more_body", False)
                
            #     # Parse the JSON body
            #     try:
            #         body = json.loads(request_body.decode("utf-8"))
            #     except Exception as e:
            #         response = JSONResponse(
            #             {"error": f"Invalid JSON body: {str(e)}"},
            #             status_code=400
            #         )
            #         await response(scope, receive, send)
            #         return
                
            #     # Check for session_id
            #     session_id = None
                
            #     # Try to get session_id from the HTTP headers
            #     headers = dict(scope.get("headers", []))
            #     session_id_header = headers.get(b"x-session-id", b"").decode("utf-8")
            #     if session_id_header:
            #         session_id = session_id_header
                
            #     # If not in headers, try to get from the JSON payload
            #     if not session_id and "id" in body:
            #         session_id = body["id"]
                
            #     if not session_id:
            #         response = PlainTextResponse(
            #             "session_id is required",
            #             status_code=400
            #         )
            #         await response(scope, receive, send)
            #         return
                
            #     # Check if the session exists
            #     if session_id not in active_sessions:
            #         response = PlainTextResponse(
            #             f"No active session with id: {session_id}",
            #             status_code=404
            #         )
            #         await response(scope, receive, send)
            #         return
                
            #     # Forward the message to the correct session
            #     try:
            #         # Get the writer stream from the session
            #         _, writer = active_sessions[session_id]
                    
            #         # Create a custom object that matches the expected Pydantic model interface
            #         class PydanticLikeMessage:
            #             def __init__(self, data):
            #                 self.data = data
                            
            #             def model_dump_json(self, **kwargs):
            #                 return json.dumps(self.data)
                    
            #         # Wrap the message in our adapter class
            #         message_obj = PydanticLikeMessage(body)
            #         await writer.send(message_obj)
                    
            #         # Send success response
            #         response = JSONResponse({"success": True, "session_id": session_id})
            #         await response(scope, receive, send)
            #     except Exception as e:
            #         self.logger.error(f"Error handling message for session {session_id}: {e}")
            #         response = JSONResponse(
            #             {"error": str(e)},
            #             status_code=500
            #         )
            #         await response(scope, receive, send)
            
            # # Function to handle 404 errors
            # async def not_found(scope, receive, send):
            #     response = PlainTextResponse("Not Found", status_code=404)
            #     await response(scope, receive, send)
            
            # # Create app with routes
            # routes = [
            #     Route(sse_path, endpoint=handle_sse, methods=["GET"]),
            #     Route(msg_path, endpoint=handle_messages, methods=["POST"]),
            # ]
            
            # # Create an ASGI app that routes based on the path
            # async def app(scope, receive, send):
            #     if scope["type"] == "http":
            #         path = scope["path"]
            #         method = scope["method"]
                    
            #         # Route to the correct handler
            #         if path == sse_path and method == "GET":
            #             await handle_sse(scope, receive, send)
            #         elif path == msg_path and method == "POST":
            #             await handle_messages(scope, receive, send)
            #         else:
            #             await not_found(scope, receive, send)
            #     else:
            #         # Not an HTTP request
            #         await not_found(scope, receive, send)
            
            # # Start the uvicorn server
            # self.logger.info(f"Starting SSE server at http://{host}:{port} "
            #                  f"(SSE: {sse_path}, Messages: {msg_path})")
            
            # config = uvicorn.Config(
            #     app=app,
            #     host=host,
            #     port=port,
            #     log_level=sse_config.get("log_level", "info").lower(),
            #     access_log=sse_config.get("access_log", False),
            # )
            
            # server_instance = uvicorn.Server(config)
            # await server_instance.serve()
        else:
            raise ValueError(f"Unknown server type: {srv_type!r}")

    # ------------------------------------------------------------------ #
    # Helper utilities                                                   #
    # ------------------------------------------------------------------ #
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function at runtime (useful for tests)."""
        if not hasattr(func, "_mcp_tool"):
            self.logger.warning("Function %s lacks _mcp_tool metadata", func.__name__)
            return
        self.tools_registry[name] = func
        self.logger.debug("Registered tool: %s", name)

    def get_tool_names(self) -> List[str]:
        return list(self.tools_registry.keys())