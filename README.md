# CHUK MCP Runtime

[![PyPI](https://img.shields.io/pypi/v/chuk-mcp-runtime.svg)](https://pypi.org/project/chuk-mcp-runtime/)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)
![Official MCP SDK](https://img.shields.io/badge/built%20on-Official%20MCP%20SDK-blue)

A robust, production-ready runtime for the official Model Context Protocol (MCP) — adds proxying, session management, JWT auth, artifact storage, and progress notifications.

> ✅ **Continuously tested against the latest official MCP SDK releases** for guaranteed protocol compatibility.

---

**CHUK MCP Runtime extends the official MCP SDK**, adding a battle-tested runtime layer for real deployments — without modifying or re-implementing the protocol.

## Architecture

```
┌──────────────────────────┐
│  Client / Agent          │
│  (Claude, OpenAI, etc.)  │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  CHUK MCP Runtime        │
│  - Proxy Manager         │
│  - Session Manager       │
│  - Artifact Storage      │
│  - JWT Auth & Progress   │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  MCP SDK Servers & Tools │
│  (Official MCP Protocol) │
└──────────────────────────┘
```

## Why CHUK MCP Runtime?

- 🔌 **Multi-Server Proxy** - Connect multiple MCP servers through one unified endpoint
- 🔐 **Secure by Default** - All built-in tools disabled unless explicitly enabled
- 🌐 **Universal Connectivity** - stdio, SSE, and HTTP transports supported
- 🔧 **OpenAI Compatible** - Transform MCP tools into OpenAI function calling format
- 📊 **Progress Notifications** - Real-time progress reporting for long operations
- ⚡ **Production Features** - Session isolation, timeout protection, JWT auth, artifact storage

## Quick Start (30 seconds)

Run any official MCP server (like `mcp-server-time`) through the CHUK MCP Runtime proxy:

```bash
chuk-mcp-proxy --stdio time --command uvx -- mcp-server-time
```

That's it! You now have a running MCP proxy with tools like `proxy.time.get_current_time` (default 60s tool timeout).

> ℹ️ **Tip:** Everything after `--` is forwarded to the stdio child process (here: `mcp-server-time`).

> 💡 **Windows:** Install `uv` and use `uvx` from a shell with it on PATH, or replace `--command uvx -- mcp-server-time` with your Python launcher. Note that `mcp-server-time` may expose a Python module name like `mcp_server_time` depending on install method (e.g., `py -m mcp_server_time`).

### Hello World with Local Tools (10 seconds)

Create your first local MCP tool:

```python
# my_tools/tools.py
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool

@mcp_tool(name="greet", description="Say hi")
async def greet(name: str = "world") -> str:
    return f"Hello, {name}!"
```

```yaml
# config.yaml
server:
  type: "stdio"

mcp_servers:
  my_tools:
    enabled: true
    location: "./my_tools"
    tools:
      enabled: true
      module: "my_tools.tools"
```

```bash
# Run it (default 60s tool timeout)
chuk-mcp-server --config config.yaml
```

**Smoke test (stdio):**

```bash
# From a second terminal while chuk-mcp-server is running on stdio:
# Send tools/list over stdin and read stdout (minimal JSON-RPC roundtrip)
printf '%s\n' '{
  "jsonrpc":"2.0",
  "id": 1,
  "method":"tools/list",
  "params": {}
}'
```

## Installation

### Requirements
- Python 3.11+ (with `uv` recommended)
- On minimal distros/containers, install `tzdata` for timezone support
- (Optional) `jq` for pretty-printing JSON in curl examples

```bash
# Basic installation
uv pip install chuk-mcp-runtime

# With optional dependencies (installs dependencies for SSE/HTTP transports and development tooling)
uv pip install "chuk-mcp-runtime[websocket,dev]"

# Install tzdata for proper timezone support (containers, Alpine Linux)
uv pip install tzdata
```

## What Can You Build?

- **Multi-Server Gateway**: Expose multiple MCP servers (time, weather, GitHub, etc.) through one proxy
- **Enterprise MCP Services**: Add session management, artifact storage, and JWT auth to any MCP setup
- **OpenAI Bridge**: Transform any MCP server's tools into OpenAI-compatible function calls
- **Hybrid Architectures**: Run local Python tools alongside remote MCP servers
- **Progress-Aware Tools**: Build long-running operations with real-time client updates

## Table of Contents

- [Key Concepts](#key-concepts)
- [Configuration Reference](#configuration-reference)
- [Proxy Configuration Examples](#proxy-configuration-examples)
- [Creating Local Tools](#creating-local-mcp-tools)
- [Progress Notifications](#progress-notifications)
- [Built-in Tools](#built-in-tool-categories)
- [Security Model](#security-model)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Core Components Overview

| Component | Purpose |
|-----------|---------|
| **Proxy Manager** | Connects and namespaces multiple MCP servers |
| **Session Manager** | Maintains per-user state across tool calls |
| **Artifact Store** | Handles file persistence and isolation |
| **Auth & Security** | Adds JWT validation and sandboxing |
| **Progress Engine** | Sends real-time status updates to clients |

## Key Concepts

### Sessions

**Sessions** provide stateful context for multi-turn interactions with MCP tools. Each session:

- Has a unique identifier (session ID)
- Persists across multiple tool calls
- Can store metadata (user info, preferences, etc.)
- Controls access to artifacts (files) within the session scope
- Has an optional TTL (time-to-live) for automatic cleanup

**When to use sessions:**
- Multi-step workflows that need to maintain state
- User-specific file storage (isolate files per user)
- Long-running operations that span multiple requests
- Workflows requiring authentication/authorization context

**Example:**
```python
# Session-aware tool automatically gets current session context
@mcp_tool(name="save_user_file")
async def save_user_file(filename: str, content: str) -> str:
    # Files are automatically scoped to the current session
    # User A's "data.txt" is separate from User B's "data.txt"

    # Note: artifact_store is available via runtime context when artifacts are enabled
    from chuk_mcp_runtime.tools.artifacts_tools import artifact_store
    await artifact_store.write_file(filename, content)
    return f"Saved {filename} to session"
```

### Sandboxes

**Sandboxes** are isolated execution environments that contain one or more sessions. Think of them as:

- **Namespace** - Groups related sessions together
- **Deployment unit** - One sandbox per deployment/pod/instance
- **Isolation boundary** - Sessions in different sandboxes don't interact

**Sandbox ID** is set via:
1. Config file: `sessions.sandbox_id: "my-app"`
2. Environment variable: `MCP_SANDBOX_ID=my-app`
3. Auto-detected: Pod name in Kubernetes (`POD_NAME`)

**Use cases:**
```
Single-tenant app:     sandbox_id = "myapp"
Multi-tenant SaaS:     sandbox_id = "tenant-{customer_id}"
Development/staging:   sandbox_id = "dev-alice" | "staging"
Kubernetes pod:        sandbox_id = $POD_NAME (auto)
```

### Sessions vs Sandboxes

```
Sandbox: "production-app"
├── Session: user-alice-2024
│   ├── File: report.pdf
│   └── File: data.csv
├── Session: user-bob-2024
│   └── File: notes.txt
└── Session: background-job-123
    └── File: results.json

Different Sandbox: "staging-app"
└── (completely isolated from production)
```

### Artifacts

**Artifacts** are files managed by the runtime with:

- **Session isolation** - Files scoped to specific sessions
- **Storage backends** - Filesystem, S3, IBM Cloud Object Storage
- **Metadata tracking** - Size, timestamps, content type
- **Lifecycle management** - Auto-cleanup with session expiry

**Storage providers:**
- `filesystem` - Local disk (development, single-node)
- `s3` - AWS S3 (production, distributed)
- `ibm_cos` - IBM Cloud Object Storage (enterprise)

### Progress Notifications

**Progress notifications** enable real-time feedback for long-running operations:

- Client provides `progressToken` in request
- Tool calls `send_progress(current, total, message)`
- Runtime sends `notifications/progress` to client
- Client displays progress bar/status

**Perfect for:**
- File processing (10 of 50 files)
- API calls (fetching data batches)
- Multi-step workflows (step 3 of 5)
- Long computations (75% complete)

## Configuration Reference

Complete YAML configuration structure with all available options:

```yaml
# ============================================
# HOST CONFIGURATION
# ============================================
host:
  name: "my-mcp-server"           # Server name (for logging/identification)
  log_level: "INFO"                # Global log level: DEBUG, INFO, WARNING, ERROR

# ============================================
# SERVER TRANSPORT
# ============================================
server:
  type: "stdio"                    # Transport: stdio | sse | streamable-http
  auth: "bearer"                   # Optional: bearer (JWT) | none

# SSE-specific settings (when type: "sse")
sse:
  host: "0.0.0.0"                  # Listen address
  port: 8000                       # Listen port
  sse_path: "/sse"                 # SSE endpoint path
  message_path: "/messages/"       # Message submission path
  health_path: "/health"           # Health check path

# HTTP-specific settings (when type: "streamable-http")
streamable-http:
  host: "127.0.0.1"                # Listen address
  port: 3000                       # Listen port
  mcp_path: "/mcp"                 # MCP endpoint path
  json_response: true              # Enable JSON responses
  stateless: true                  # Stateless mode

# ============================================
# LOGGING CONFIGURATION
# ============================================
logging:
  level: "INFO"                    # Default log level
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  reset_handlers: true             # Reset existing handlers
  quiet_libraries: true            # Suppress noisy library logs

  # Per-logger overrides
  loggers:
    "chuk_mcp_runtime.proxy": "DEBUG"
    "chuk_mcp_runtime.tools": "INFO"

# ============================================
# TOOL CONFIGURATION
# ============================================
tools:
  registry_module: "chuk_mcp_runtime.common.mcp_tool_decorator"
  registry_attr: "TOOLS_REGISTRY"
  timeout: 60                      # Global tool timeout (seconds)

# ============================================
# SESSION MANAGEMENT
# ============================================
sessions:
  sandbox_id: "my-app"             # Sandbox identifier (deployment unit)
  default_ttl_hours: 24            # Session time-to-live

# Session tools (disabled by default)
session_tools:
  enabled: false                   # Master switch for session tools
  tools:
    get_current_session: {enabled: false}
    set_session: {enabled: false}
    clear_session: {enabled: false}
    list_sessions: {enabled: false}
    get_session_info: {enabled: false}
    create_session: {enabled: false}

# ============================================
# ARTIFACT STORAGE
# ============================================
artifacts:
  enabled: false                   # Master switch for artifacts
  storage_provider: "filesystem"   # filesystem | s3 | ibm_cos
  session_provider: "memory"       # memory | redis
  bucket: "my-artifacts"           # Storage bucket/directory name

  # Artifact tools (disabled by default)
  tools:
    upload_file: {enabled: false}
    write_file: {enabled: false}
    read_file: {enabled: false}
    list_session_files: {enabled: false}
    delete_file: {enabled: false}
    list_directory: {enabled: false}
    copy_file: {enabled: false}
    move_file: {enabled: false}
    get_file_metadata: {enabled: false}
    get_presigned_url: {enabled: false}
    get_storage_stats: {enabled: false}

# ============================================
# PROXY CONFIGURATION
# ============================================
proxy:
  enabled: false                   # Enable proxy mode
  namespace: "proxy"               # Tool name prefix (e.g., "proxy.time.get_time")
  keep_root_aliases: false         # Keep original tool names
  openai_compatible: false         # Use underscores (time_get_time)
  only_openai_tools: false         # Register only underscore versions

# ============================================
# MCP SERVERS (Local & Remote)
# ============================================
mcp_servers:
  # Local Python tools
  my_tools:
    enabled: true
    location: "./my_tools"         # Directory containing tool modules
    tools:
      enabled: true
      module: "my_tools.tools"     # Python module path

  # Remote stdio server
  time:
    enabled: true
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-time", "--local-timezone", "America/New_York"]
    cwd: "/optional/working/dir"   # Optional working directory

  # Remote SSE server
  weather:
    enabled: true
    type: "sse"
    url: "https://api.example.com/mcp"
    api_key: "your-api-key"        # Or set via API_KEY env var
```

### Configuration Priority

Settings are resolved in this order (highest to lowest):

1. **Command-line arguments** - `chuk-mcp-server --config custom.yaml`
2. **Environment variables** - `MCP_TOOL_TIMEOUT=120`
3. **Configuration file** - Values from YAML
4. **Default values** - Built-in defaults

### Minimal Configurations

**Stdio server with no sessions:**
```yaml
server:
  type: "stdio"
```

**SSE server (referenced in examples):**
```yaml
# sse_config.yaml
server:
  type: "sse"
  # For production: add auth: "bearer" and set JWT_SECRET_KEY

sse:
  host: "0.0.0.0"
  port: 8000
  sse_path: "/sse"
  message_path: "/messages/"
  health_path: "/health"
```

**Streamable HTTP server (referenced in examples):**
```yaml
# http_config.yaml
server:
  type: "streamable-http"
  # For production: add auth: "bearer" and set JWT_SECRET_KEY

streamable-http:
  host: "0.0.0.0"
  port: 3000
  mcp_path: "/mcp"
  json_response: true
  stateless: true
```

**Proxy only (no local tools):**
```yaml
proxy:
  enabled: true

mcp_servers:
  time:
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-time"]
```

**Full-featured with sessions:**
```yaml
server:
  type: "stdio"

sessions:
  sandbox_id: "prod"

session_tools:
  enabled: true
  tools:
    get_current_session: {enabled: true}
    create_session: {enabled: true}

artifacts:
  enabled: true
  storage_provider: "s3"
  tools:
    write_file: {enabled: true}
    read_file: {enabled: true}
```

## Proxy Configuration Examples

The proxy layer allows you to expose tools from multiple MCP servers through a unified interface.

### Simple Command Line Proxy

```bash
# Basic proxy with dot notation (proxy.time.get_current_time)
chuk-mcp-proxy --stdio time --command uvx -- mcp-server-time --local-timezone America/New_York

# Multiple stdio servers (--stdio is repeatable)
chuk-mcp-proxy --stdio time --command uvx -- mcp-server-time \
               --stdio weather --command uvx -- mcp-server-weather

# Multiple SSE servers (--sse is repeatable)
chuk-mcp-proxy \
  --sse analytics --url https://example.com/mcp --api-key "$API_KEY" \
  --sse metrics   --url https://metrics.example.com/mcp --api-key "$METRICS_API_KEY"

# OpenAI-compatible with underscore notation (time_get_current_time)
chuk-mcp-proxy --stdio time --command uvx -- mcp-server-time --openai-compatible

# Streamable HTTP server (serves MCP over HTTP)
chuk-mcp-server --config http_config.yaml  # See minimal config example below
```

> ⚠️ **Security:** For SSE/HTTP network transports, enable `server.auth: bearer` and set `JWT_SECRET_KEY`.

### Multiple Servers with Config File

```yaml
# proxy_config.yaml
proxy:
  enabled: true
  namespace: "proxy"

mcp_servers:
  time:
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-time", "--local-timezone", "America/New_York"]

  weather:
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-weather"]
```

```bash
chuk-mcp-proxy --config proxy_config.yaml
```

### OpenAI-Compatible Mode

```yaml
# openai_config.yaml
proxy:
  enabled: true
  namespace: "proxy"
  openai_compatible: true   # Enable underscore notation
  only_openai_tools: true   # Only register underscore-notation tools

mcp_servers:
  time:
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-time"]
```

```bash
chuk-mcp-proxy --config openai_config.yaml
```

**OpenAI-Compatible Naming Matrix:**

| Setting | Example Exposed Name |
|---------|---------------------|
| Default (dot notation) | `proxy.time.get_current_time` |
| `openai_compatible: true` | `time_get_current_time` |
| `openai_compatible: true` + `only_openai_tools: true` | Only underscore versions registered |

> **OpenAI-compatible mode** converts dots to underscores (e.g., `proxy.time.get_current_time` → `time_get_current_time`). Namespacing behavior is controlled by `openai_compatible` + `only_openai_tools`.

**OpenAI-compatible demo with HTTP:**

```bash
# Start proxy with OpenAI-compatible naming
chuk-mcp-proxy --stdio time --command uvx -- mcp-server-time --openai-compatible

# Call the underscore tool name over HTTP
curl -s http://127.0.0.1:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"time_get_current_time","arguments":{"timezone":"UTC"}}}'
```

### Name Aliasing in Proxy Mode

By default, tools are exposed under `proxy.<server>.<tool>`.
Set `keep_root_aliases: true` to also expose the original tool names (no `proxy.` prefix).
This is useful when migrating existing clients gradually. **Root aliases are great for gradual migration, but disable in multi-tenant prod to avoid collisions.**

```yaml
proxy:
  enabled: true
  namespace: "proxy"
  keep_root_aliases: true  # Also expose tools without proxy. prefix
```

With this setting enabled, `proxy.time.get_current_time` is available as both:
- `proxy.time.get_current_time` (namespaced)
- `get_current_time` (root alias)

### Tool Naming Interplay

**Complete naming matrix when options combine:**

| Setting Combination | Registered Names |
|---------------------|------------------|
| Default | `proxy.<server>.<tool>` |
| `keep_root_aliases: true` | `proxy.<server>.<tool>`, **and** `<tool>` |
| `openai_compatible: true` | `<server>_<tool>` |
| `openai_compatible: true` + `only_openai_tools: true` | `<server>_<tool>` **only** |
| `openai_compatible: true` + `keep_root_aliases: true` | `<server>_<tool>`, **and** `<tool>` |

> ⚠️ **Root aliases are un-namespaced.** Use with care in multi-server setups to avoid tool name collisions.

## Security Model

**IMPORTANT**: CHUK MCP Runtime follows a **secure-by-default** approach:

- **All built-in tools are disabled by default**
- Session management tools require explicit enablement
- Artifact storage tools require explicit enablement
- Tools must be individually enabled in configuration
- This prevents unexpected tool exposure and reduces attack surface

## Creating Local MCP Tools

### 1. Create a custom tool

```python
# my_tools/tools.py
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool

@mcp_tool(name="get_current_time", description="Get the current time in a timezone")
async def get_current_time(timezone: str = "UTC") -> str:
    """
    Get the current time in the specified timezone.

    Args:
        timezone: Target timezone (e.g., 'UTC', 'America/New_York')
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")

@mcp_tool(name="calculate_sum", description="Calculate the sum of two numbers", timeout=10)
async def calculate_sum(a: int, b: int) -> dict:
    """
    Calculate the sum of two numbers.

    Args:
        a: First number
        b: Second number
    """
    # ⚠️ PRODUCTION WARNING: Never use eval() for math operations - always validate
    # and compute directly as shown here. eval() is a security risk.
    result = a + b
    return {
        "operation": "addition",
        "operands": [a, b],
        "result": result
    }
```

### 2. Create a config file

```yaml
# config.yaml
host:
  name: "my-mcp-server"
  log_level: "INFO"

server:
  type: "stdio"

# Global tool settings
tools:
  registry_module: "chuk_mcp_runtime.common.mcp_tool_decorator"
  registry_attr: "TOOLS_REGISTRY"
  timeout: 60  # Default timeout for all tools

# Session management (optional - disabled by default)
sessions:
  sandbox_id: "my-app"
  default_ttl_hours: 24

# Session tools (disabled by default - must enable explicitly)
session_tools:
  enabled: true  # Must explicitly enable
  tools:
    get_current_session: {enabled: true}
    set_session: {enabled: true}
    clear_session: {enabled: true}
    create_session: {enabled: true}

# Artifact storage (disabled by default - must enable explicitly)
artifacts:
  enabled: true  # Must explicitly enable
  storage_provider: "filesystem"
  session_provider: "memory"
  bucket: "my-artifacts"
  tools:
    upload_file: {enabled: true}
    write_file: {enabled: true}
    read_file: {enabled: true}
    list_session_files: {enabled: true}
    delete_file: {enabled: true}
    get_file_metadata: {enabled: true}

# Local tool modules
mcp_servers:
  my_tools:
    enabled: true
    location: "./my_tools"
    tools:
      enabled: true
      module: "my_tools.tools"
```

### 3. Run the server

```bash
chuk-mcp-server --config config.yaml
```

## Built-in Tool Categories

CHUK MCP Runtime provides two categories of built-in tools that can be optionally enabled:

### Session Management Tools

**Status**: Disabled by default - must be explicitly enabled

Tools for managing session context and lifecycle:

- `get_current_session`: Get information about the current session
- `set_session`: Set the session context for operations  
- `clear_session`: Clear the current session context
- `list_sessions`: List all active sessions
- `get_session_info`: Get detailed session information
- `create_session`: Create a new session with metadata

**Enable in config**:
```yaml
session_tools:
  enabled: true
  tools:
    get_current_session: {enabled: true}
    set_session: {enabled: true}
    # ... enable other tools as needed
```

### Artifact Storage Tools

**Status**: Disabled by default - must be explicitly enabled

Tools for file storage and management within sessions:

- `upload_file`: Upload files with base64 content
- `write_file`: Create or update text files
- `read_file`: Read file contents
- `list_session_files`: List files in current session
- `delete_file`: Delete files
- `list_directory`: List directory contents
- `copy_file`: Copy files within session
- `move_file`: Move/rename files
- `get_file_metadata`: Get file metadata
- `get_presigned_url`: Generate presigned download URLs
- `get_storage_stats`: Get storage statistics

**Enable in config**:
```yaml
artifacts:
  enabled: true
  storage_provider: "filesystem"  # or "ibm_cos", "s3", etc.
  session_provider: "memory"      # or "redis"
  tools:
    upload_file: {enabled: true}
    write_file: {enabled: true}
    read_file: {enabled: true}
    # ... enable other tools as needed
```

## Tool Configuration

### Timeout Settings

CHUK MCP Runtime supports configurable timeouts for tools to handle long-running operations. The default timeout is **60 seconds** unless overridden.

```python
# Tool with custom timeout
@mcp_tool(
    name="api_call",
    description="Call external API", 
    timeout=30  # 30 second timeout
)
async def api_call(url: str) -> dict:
    """Call an external API with timeout protection."""
    # Implementation here
    pass
```

**Configuration priority** (highest to lowest):
1. Per-tool timeout in decorator: `@mcp_tool(timeout=30)`
2. Global timeout in config: `tools.timeout: 60`
3. Environment variable: `MCP_TOOL_TIMEOUT=60`
4. Default: 60 seconds

### Advanced Tool Features

Tools support:
- **Type hints** for automatic JSON schema generation
- **Docstring parsing** for parameter descriptions
- **Async execution** with timeout protection
- **Error handling** with graceful degradation
- **Session management** for stateful operations
- **Thread-safe initialization** with race condition protection
- **Progress notifications** for long-running operations

## Progress Notifications

CHUK MCP Runtime supports real-time progress notifications for long-running operations, allowing clients to display progress bars and status updates.

### How Progress Works

Progress notifications are sent over the MCP protocol using the `notifications/progress` message type. When a tool reports progress, the runtime automatically sends notifications to the client if:
1. The client provided a `progressToken` in the request
2. The tool uses the `send_progress()` function

> ℹ️ **Important:** Clients must send `_meta.progressToken` for progress to stream; otherwise updates are ignored by design.

### Using Progress in Tools

```python
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_runtime.server.request_context import send_progress

@mcp_tool(name="process_files", description="Process multiple files with progress")
async def process_files(file_paths: list[str]) -> dict:
    """
    Process multiple files and report progress.

    Args:
        file_paths: List of file paths to process
    """
    total = len(file_paths)
    results = []

    for i, path in enumerate(file_paths, 1):
        # Send progress update
        await send_progress(
            progress=i,
            total=total,
            message=f"Processing {path}"
        )

        # Do the actual work
        result = await process_file(path)
        results.append(result)
        await asyncio.sleep(0.5)  # Simulate work

    return {"processed": len(results), "results": results}
```

### Progress Patterns

**Step-based progress** (N of total):
```python
await send_progress(
    progress=5,
    total=10,
    message="Processing item 5 of 10"
)
```

**Percentage-based progress** (0.0 to 1.0):
```python
await send_progress(
    progress=0.75,
    total=1.0,
    message="75% complete"
)
```

**Multi-stage operations**:
```python
# Stage 1: Preparation
await send_progress(progress=1, total=3, message="Preparing data...")
await prepare_data()

# Stage 2: Processing
await send_progress(progress=2, total=3, message="Processing...")
await process_data()

# Stage 3: Finalizing
await send_progress(progress=3, total=3, message="Finalizing...")
await finalize()
```

### Client Integration

Progress notifications are automatically sent when clients include `progressToken` in the request metadata:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": 1,
  "params": {
    "name": "process_files",
    "arguments": {"file_paths": ["a.txt", "b.txt"]},
    "_meta": {
      "progressToken": "my-progress-123"
    }
  }
}
```

The client receives notifications like:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "my-progress-123",
    "progress": 1,
    "total": 2,
    "message": "Processing a.txt"
  }
}
```

### Examples

See complete working examples:
- `examples/progress_demo.py` - Basic progress reporting with visual output
- `examples/progress_e2e_demo.py` - Full end-to-end test over MCP protocol

### Testing Progress Support

Run the E2E demo to see progress in action:

```bash
cd examples
uv run python progress_e2e_demo.py
```

This demonstrates:
- Step-based progress (counting 1-10)
- Batch processing with progress
- Percentage-based progress (file download simulation)
- Visual progress bars in the terminal

## Running a Combined Local + Proxy Server

You can run a single server that provides both local tools and proxied remote tools:

```yaml
# combined_config.yaml
host:
  name: "combined-server"
  log_level: "INFO"

# Local server configuration
server:
  type: "stdio"

# Session management
sessions:
  sandbox_id: "combined-app"

# Enable session tools
session_tools:
  enabled: true
  tools:
    get_current_session: {enabled: true}
    create_session: {enabled: true}

# Enable artifact tools
artifacts:
  enabled: true
  storage_provider: "filesystem"
  tools:
    write_file: {enabled: true}
    read_file: {enabled: true}
    list_session_files: {enabled: true}

# Local tools
mcp_servers:
  local_tools:
    enabled: true
    location: "./my_tools"
    tools:
      enabled: true
      module: "my_tools.tools"

# Proxy configuration
proxy:
  enabled: true
  namespace: "proxy"
  openai_compatible: false
  
# Remote servers (managed by proxy)
mcp_servers:
  time:
    enabled: true
    type: "stdio"
    command: "uvx"
    args: ["mcp-server-time", "--local-timezone", "America/New_York"]
  
  echo:
    enabled: true
    type: "stdio"
    command: "python"
    args: ["examples/echo_server/main.py"]
```

Start the combined server:

```bash
chuk-mcp-server --config combined_config.yaml
```

## Transport Options

CHUK MCP Runtime supports multiple transport mechanisms:

### stdio (Standard Input/Output)
```yaml
server:
  type: "stdio"
```

### Server-Sent Events (SSE)
```yaml
server:
  type: "sse"
  auth: "bearer"  # Enable JWT authentication for network transports

sse:
  host: "0.0.0.0"
  port: 8000
  sse_path: "/sse"
  message_path: "/messages/"
  health_path: "/health"
```

> ⚠️ **Security:** When exposing network transports, enable `server.auth: bearer`, set `JWT_SECRET_KEY`, and run behind TLS (reverse proxy / ingress).

**Health check:**
```bash
curl -sf http://127.0.0.1:8000/health && echo "healthy"
```

**SSE message submission example:**
```bash
# Post a message to the SSE message endpoint
curl -s "http://127.0.0.1:8000/messages/" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"tools/call",
    "params":{"name":"proxy.time.get_current_time","arguments":{"timezone":"UTC"}}
  }'
```

**Kubernetes readiness/liveness probes:**
```yaml
# k8s probes (example)
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 2
  periodSeconds: 5
```

### Streamable HTTP
```yaml
server:
  type: "streamable-http"
  auth: "bearer"  # Enable JWT authentication for network transports

streamable-http:
  host: "127.0.0.1"
  port: 3000
  mcp_path: "/mcp"
  json_response: true
  stateless: true
```

> ⚠️ **Security:** When exposing network transports, enable `server.auth: bearer`, set `JWT_SECRET_KEY`, and run behind TLS (reverse proxy / ingress).

**Example: Call a tool over HTTP (stateless mode)**

```bash
# Call a tool via HTTP POST
curl -s http://127.0.0.1:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "proxy.time.get_current_time",
      "arguments": {"timezone": "UTC"},
      "_meta": {"progressToken": "curl-demo-1"}
    }
  }'
```

> If you enabled OpenAI-compatible mode, call `time_get_current_time` instead.

**Smoke test: List available tools**

```bash
# List available tools (verify wiring before calling)
curl -s http://127.0.0.1:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"tools/list",
    "params": {}
  }' | jq '.result.tools[].name'
```

## Security Features & Hardening

**Hardening checklist (production):**

- ✅ `server.auth: bearer` and `JWT_SECRET_KEY` set via a secrets manager
- ✅ Rotate JWT secrets; set `JWT_LEEWAY` for clock drift
- ✅ Disable tools you don't need (default is off — keep it that way)
- ✅ Use namespacing (avoid `keep_root_aliases` in multi-tenant prod)
- ✅ Set conservative `tools.timeout` and per-tool overrides
- ✅ Run behind TLS (reverse proxy / ingress)
- ✅ Add network ACLs; restrict SSE/HTTP exposure

### Authentication

**Quick JWT setup for development:**

```bash
# Generate a quick dev token (HS256) with 1h expiry
python - <<'PY'
import jwt, time
print(jwt.encode({"exp": int(time.time())+3600, "sub":"dev-user"}, "dev-secret", algorithm="HS256"))
PY
```

```yaml
# Server config (excerpt)
server:
  type: "streamable-http"
  auth: "bearer"
```

```bash
# Environment
export JWT_SECRET_KEY="dev-secret"
```

Then include the token in requests:

```bash
curl -H "Authorization: Bearer <token>" ...
```

### Tool Security
- All built-in tools disabled by default
- Granular per-tool enablement
- Session isolation for artifact storage
- Input validation on all tool parameters
- Timeout protection against runaway operations

## Environment Variables

Environment variables provide flexible configuration for different deployment scenarios. They **override config file values** but are **overridden by command-line arguments**.

### Core Configuration

| Variable | Purpose | Example | When to Use |
|----------|---------|---------|-------------|
| `CHUK_MCP_CONFIG_PATH` | Path to YAML config | `/etc/mcp/config.yaml` | Docker containers, systemd services |
| `CHUK_MCP_LOG_LEVEL` | Global log level | `DEBUG`, `INFO`, `WARNING` | Debugging, production |
| `MCP_TOOL_TIMEOUT` | Default tool timeout (seconds) | `120` | Long-running tools, slow networks |
| `TOOL_TIMEOUT` | Alternative timeout variable | `60` | Compatibility with other tools |

**Use case:**
```bash
# Override config file logging level for debugging
CHUK_MCP_LOG_LEVEL=DEBUG chuk-mcp-server --config prod.yaml
```

### Session & Sandbox Configuration

| Variable | Purpose | Example | When to Use |
|----------|---------|---------|-------------|
| `MCP_SANDBOX_ID` | Sandbox identifier | `prod-api`, `tenant-acme` | Multi-tenant, environment separation |
| `CHUK_SANDBOX_ID` | Alternative sandbox ID | `staging` | Legacy compatibility |
| `SANDBOX_ID` | Another alternative | `dev-alice` | Simplest form |
| `POD_NAME` | Kubernetes pod name | `api-deployment-abc123` | **Auto-detected in K8s** |

**Sandbox ID Resolution** (first match wins):
1. Config file: `sessions.sandbox_id`
2. `MCP_SANDBOX_ID` environment variable
3. `CHUK_SANDBOX_ID` environment variable
4. `SANDBOX_ID` environment variable
5. `POD_NAME` (Kubernetes auto-detection)
6. Default: `mcp-runtime-{timestamp}`

**Use cases:**
```bash
# Development: per-developer sandboxes
export MCP_SANDBOX_ID="dev-$USER"

# Production: multi-tenant SaaS
export MCP_SANDBOX_ID="tenant-${CUSTOMER_ID}"

# Kubernetes: automatic per-pod isolation
# POD_NAME is auto-detected, no config needed!
```

### Artifact Storage

| Variable | Purpose | Example | When to Use |
|----------|---------|---------|-------------|
| `ARTIFACT_STORAGE_PROVIDER` | Storage backend | `filesystem`, `s3`, `ibm_cos` | Switch backends per environment |
| `ARTIFACT_SESSION_PROVIDER` | Session tracking | `memory`, `redis` | Distributed deployments |
| `ARTIFACT_BUCKET` | Bucket/directory name | `prod-artifacts`, `/data/files` | Per-environment buckets |
| `ARTIFACT_FS_ROOT` | Filesystem storage path | `/var/lib/mcp` | Local storage location |

**Cloud Provider Credentials:**

**AWS S3:**
```bash
export ARTIFACT_STORAGE_PROVIDER=s3
export ARTIFACT_BUCKET=my-mcp-artifacts
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

**IBM Cloud Object Storage:**
```bash
export ARTIFACT_STORAGE_PROVIDER=ibm_cos
export ARTIFACT_BUCKET=mcp-prod
export IBM_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud
export IBM_COS_ACCESS_KEY_ID=...
export IBM_COS_SECRET_ACCESS_KEY=...
export IBM_COS_REGION=us-south
```

**Redis Session Provider** (for distributed/HA):
```bash
export ARTIFACT_SESSION_PROVIDER=redis
export SESSION_REDIS_URL=redis://localhost:6379/0

# Or individual components:
export SESSION_REDIS_HOST=redis.internal
export SESSION_REDIS_PORT=6379
export SESSION_REDIS_DB=0
export SESSION_REDIS_PASSWORD=secret
```

### Authentication

| Variable | Purpose | Example | When to Use |
|----------|---------|---------|-------------|
| `JWT_SECRET_KEY` | JWT signing secret | `your-256-bit-secret` | **Required for auth** |
| `JWT_ALGORITHM` | Signing algorithm | `HS256`, `RS256` | Default: HS256 |
| `JWT_ALLOWED_ALGORITHMS` | Accepted algorithms | `HS256,RS256` | Multi-algorithm support |
| `JWT_LEEWAY` | Clock drift tolerance (seconds) | `5` | Distributed systems |

**Use case:**
```bash
# Production: use secrets manager
export JWT_SECRET_KEY=$(cat /run/secrets/jwt_key)

# Development: simple secret
export JWT_SECRET_KEY="dev-secret-do-not-use-in-prod"
```

### Advanced: Distributed Deployments

For multi-node, hub-and-spoke architectures:

| Variable | Purpose | Example |
|----------|---------|---------|
| `HUB_ID` | Hub instance identifier | `hub-primary` |
| `HUB_URL` | Hub registration endpoint | `https://hub.internal/register` |
| `HUB_ADDR` | Hub communication address | `hub.internal:8080` |
| `HUB_TOKEN` | Hub authentication token | `eyJ...` |
| `POD_IP` | Pod IP for service discovery | `10.1.2.3` |
| `SBX_TRANSPORT` | Sandbox transport protocol | `http`, `grpc` |

**Typical setup:**
```bash
# Hub node
export HUB_ID=hub-us-east

# Worker nodes
export HUB_URL=https://hub.internal/api
export HUB_TOKEN=$HUB_AUTH_TOKEN
export POD_IP=$(hostname -i)
```

### Configuration Priority Summary

**Lowest → Highest Priority:**
```
Default values
    ↓
Config file (config.yaml)
    ↓
Environment variables (MCP_TOOL_TIMEOUT=120)
    ↓
Command-line arguments (--config custom.yaml)
```

> 💡 **Note:** Per-tool decorator timeout (`@mcp_tool(timeout=30)`) still beats all config/env settings.

**Example:**
```bash
# config.yaml has: tools.timeout: 60
# This overrides to 120:
MCP_TOOL_TIMEOUT=120 chuk-mcp-server --config config.yaml
```

### Example Environment Setup

```bash
# Basic configuration
export CHUK_MCP_LOG_LEVEL=INFO
export MCP_TOOL_TIMEOUT=60
export MCP_SANDBOX_ID=my-app

# Artifact storage with filesystem
export ARTIFACT_STORAGE_PROVIDER=filesystem
export ARTIFACT_FS_ROOT=/var/lib/mcp-artifacts

# Session management with Redis
export ARTIFACT_SESSION_PROVIDER=redis
export SESSION_REDIS_URL=redis://localhost:6379/0

# JWT authentication
export JWT_SECRET_KEY=your-secret-key-here

# Run the server
chuk-mcp-server --config config.yaml
```

### Docker Example

```dockerfile
FROM python:3.11-slim

# Install runtime
RUN pip install chuk-mcp-runtime

# Set environment variables
ENV CHUK_MCP_LOG_LEVEL=INFO
ENV MCP_TOOL_TIMEOUT=60
ENV ARTIFACT_STORAGE_PROVIDER=filesystem
ENV ARTIFACT_FS_ROOT=/app/artifacts
ENV MCP_SANDBOX_ID=docker-app

# Copy configuration
COPY config.yaml /app/config.yaml
WORKDIR /app

CMD ["chuk-mcp-server", "--config", "config.yaml"]
```

Environment variables take precedence in this order:
1. Command line arguments (highest)
2. Environment variables
3. Configuration file values
4. Default values (lowest)

## Command Reference

### chuk-mcp-proxy

```
chuk-mcp-proxy [OPTIONS]
```

Options:
- `--config FILE`: YAML config file (optional, can be combined with flags below)
- `--stdio NAME`: Add a local stdio MCP server (repeatable)
- `--sse NAME`: Add a remote SSE MCP server (repeatable)
- `--command CMD`: Executable for stdio servers (default: python)
- `--cwd DIR`: Working directory for stdio server
- `--args ...`: Additional args for the stdio command
- `--url URL`: SSE base URL
- `--api-key KEY`: SSE API key (or set API_KEY env var)
- `--openai-compatible`: Use OpenAI-compatible tool names (underscores)

### chuk-mcp-server

```
chuk-mcp-server [OPTIONS]
```

Options:
- `--config FILE`: YAML configuration file
- `-c FILE`: Short form of --config
- Environment variable: `CHUK_MCP_CONFIG_PATH`

## Troubleshooting

### Common Issues

**"Tool not found" errors**:
- Check that tools are properly enabled in configuration
- Verify tool registration in the specified module
- Ensure async function signatures are correct

**Session validation errors**:
- Verify session management is configured
- Check that session tools are enabled if using session features
- Ensure proper async/await usage in tool implementations

**Timeout errors**:
- Increase tool timeout settings
- Check for blocking operations in async tools
- Monitor resource usage during tool execution

### Common HTTP Error Shapes

**401 Unauthorized**: Missing/invalid `Authorization: Bearer <token>`.
Fix: set `server.auth: bearer` and export `JWT_SECRET_KEY`; include a valid JWT in requests.

**404 Not Found** (tool): The tool name isn't registered under the chosen naming scheme.
Fix: run `tools/list` and double-check `proxy` namespace, underscore vs dot, and `keep_root_aliases`.

**408/504 or timeout error**: Tool exceeded timeout.
Fix: raise `tools.timeout` or per-tool `@mcp_tool(timeout=...)`;  avoid blocking calls in async tools.

**422 Validation error**: Wrong arg types (schema is auto-generated from type hints).
Fix: confirm parameter names/types match the tool signature.

### Debug Logging

Enable detailed logging:

```yaml
logging:
  level: "DEBUG"
  loggers:
    "chuk_mcp_runtime.tools": "DEBUG"
    "chuk_mcp_runtime.session": "DEBUG"
    "chuk_mcp_runtime.proxy": "DEBUG"
```

## Examples

See the `examples/` directory for complete working examples:
- Basic tool creation
- Session management
- Artifact storage
- Proxy configurations
- Combined local + remote setups
- Progress notification demos

## Development

### Quick Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/chuk-mcp-runtime.git
cd chuk-mcp-runtime

# Install in development mode
make dev-install
# or: uv pip install -e ".[dev]"
```

### Available Make Commands

```bash
# Testing
make test              # Run tests
make coverage          # Generate coverage report (96% coverage)
make coverage-html     # Open HTML coverage report

# Code Quality
make lint              # Check code with ruff
make format            # Auto-format code
make typecheck         # Run mypy type checking
make check             # Run all checks (lint + typecheck + test)

# Cleaning
make clean             # Remove Python bytecode
make clean-build       # Remove build artifacts
make clean-test        # Remove test artifacts
make clean-all         # Deep clean everything

# Building & Publishing
make build             # Build distribution packages
make publish           # Publish to PyPI
make publish-test      # Publish to test PyPI
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/server/test_config_loader.py

# Run with coverage
make coverage

# Run tests in watch mode
uv run pytest-watch
```

### Code Quality Standards

The project maintains high quality standards:
- **96% test coverage** - All core modules fully tested
- **Type hints** - Full mypy type checking
- **Ruff linting** - Fast Python linter and formatter
- **Security** - No hardcoded credentials, secure defaults

> 🧠 Built and continuously tested against the latest [official MCP SDK](https://github.com/modelcontextprotocol), ensuring forward compatibility.

### Versioning & Compatibility

**Versioning:** SemVer. Continuously tested against the latest official MCP SDK.
**Breaking changes:** Only in `MAJOR` releases; see GitHub Releases for migration notes.

### Docker Compose (Development)

```yaml
# docker-compose.yml (dev)
services:
  mcp:
    image: python:3.11-slim
    command: ["bash","-lc","pip install chuk-mcp-runtime tzdata && chuk-mcp-server --config /app/config.yaml"]
    environment:
      JWT_SECRET_KEY: dev-secret
      CHUK_MCP_LOG_LEVEL: INFO
    ports:
      - "3000:3000"
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and checks (`make check`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Contribution Guidelines

- Maintain or improve test coverage (>90%)
- Follow existing code style (enforced by ruff)
- Add tests for new features
- Update documentation as needed
- Ensure all checks pass (`make check`)

## License

- **License:** MIT — see [LICENSE](./LICENSE)
- **Changelog:** Track releases and changes in [GitHub Releases](https://github.com/chrishayuk/chuk-mcp-runtime/releases)