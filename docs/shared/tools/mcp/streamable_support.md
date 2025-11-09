## MCP Streamable HTTP Support Plan

This document describes how we will add official Streamable HTTP transport support to the MCP module while keeping existing agent call paths unchanged. The plan is aligned with `langchain-mcp-adapters` 0.1.11 and MCP SDK 1.13.x; no agent-side code changes are required.

### 1) Current MCP module architecture (as-is)

- Global tool loading
  - `GlobalMCPManager` loads config from `config/mcp/mcp.toml`, starts MCP clients, aggregates tools into a LangChain `BaseTool` list.
  - Tools are optionally prefixed/sanitized via `tool_adapter.apply_naming_and_filter`.
- Providers and unified manager
  - `MCPToolProvider` initializes `GlobalMCPManager` and returns the aggregated `BaseTool` list.
  - `UnifiedToolManager` composes multiple providers (SDK, MCP, Connector) and returns a single merged tool list to agents.
- Agent usage
  - Native LangChain agents: receive the tool list from `UnifiedToolManager`, then build `AgentExecutor` instances (ReAct or Tool Calling) with these tools.
  - Custom `zhipu_fcall_agent`: collects SDK/Connector tools, fetches MCP tools from `GlobalMCPManager`, converts them to model function schemas, and executes them in a function-calling loop.

Today only the `stdio` transport is enabled (local child processes). Streamable HTTP extends transports to remote HTTP(S) servers without changing how tools are consumed above the manager/provider layer.

References:
- What is MCP? [modelcontextprotocol.io/docs/getting-started/intro](https://modelcontextprotocol.io/docs/getting-started/intro)
- Understanding MCP servers (tools/resources/prompts): [modelcontextprotocol.io/docs/learn/server-concepts](https://modelcontextprotocol.io/docs/learn/server-concepts)

### 2) Dependencies & compatibility

- `langchain-mcp-adapters` **>= 0.1.11** (provides `StreamableHttpConnection` and Streamable HTTP session helpers).
- `mcp` SDK **>= 1.13.x** (ships the `streamablehttp_client` transport and session management utilities).
- Existing stdio configurations remain valid; Streamable HTTP is additive.

Callers mixing transports in one config must ensure they are running inside a virtual environment that carries the dependency versions above. If we upgrade the adapter in the future, update this section to note any breaking changes to configuration keys.

### 3) Configuration changes (Streamable HTTP)

Goal: support remote servers reachable over Streamable HTTP (single endpoint supporting POST and GET with SSE) while keeping the agent-facing API untouched.

#### 3.1 ServerConfig additions

`ServerConfig` gains optional fields that are only used when `transport == "streamable_http"`:

| Field | Type | Applies to | Notes |
| --- | --- | --- | --- |
| `url` | `str` | Streamable HTTP | Required; MCP endpoint accepting POST + GET (SSE) |
| `headers` | `dict[str, str]` | Streamable HTTP | Optional; env expansion supported (`$TOKEN`) |
| `options.timeout_ms` | `int` | Streamable HTTP | Optional; converted to `timeout` (HTTP request timeout) |
| `options.sse_read_timeout_ms` | `int` | Streamable HTTP | Optional; maps to `sse_read_timeout` |
| `options.terminate_on_close` | `bool` | Streamable HTTP | Optional; defaults to adapter behavior (`True`) |
| `options.insecure_skip_verify` | `bool` | Streamable HTTP | Optional; disables TLS verification via a custom `httpx` factory |

Existing stdio-specific fields (`command`, `args`, `cwd`, `env`, etc.) are still accepted but ignored when `transport` is Streamable HTTP.

#### 3.2 Config loader updates

- Allow `transport` values in `{"stdio", "streamable_http"}`.
- Validate required combinations:
  - `stdio` requires `command` (and implicitly `args`, defaulting to an empty list).
  - `streamable_http` requires `url`.
- Expand environment variables inside `headers` using the same logic as `env`.
- When `options.insecure_skip_verify` is true, record that detail so the manager can inject a custom `httpx.AsyncClient` with `verify=False` when building the adapter connection.
- Validation helpers should be transport-specific (`_validate_stdio`, `_validate_streamable_http`) to keep code clear and testable.

#### 3.3 Manager updates

- When constructing the dictionary passed to `MultiServerMCPClient`, branch per transport:
  - Stdio: continue forwarding `command`, `args`, `cwd`, `env` (existing behavior).
  - Streamable HTTP: supply `url`, `headers`, and map `options.*` to the adapter keys (`timeout`, `sse_read_timeout`, `terminate_on_close`). Inject `httpx_client_factory` when TLS verification must be skipped.
- Mask sensitive header values (e.g., `Authorization`) in status output; expose the header keys so operators know what is configured.
- Keep retries/backoff untouched; the adapter internally handles SSE GET after receiving the `notifications/initialized` event and automatically propagates `Mcp-Session-Id` and negotiated `MCP-Protocol-Version` headers.

### 4) Example configuration (`mcp.example.toml`)

Backwards-compatible example demonstrating mixed transports. The Streamable HTTP block references Gaode (Amap) MCP server endpoints - replace URL and headers with values from the official documentation: [https://lbs.amap.com/api/mcp-server/gettingstarted#s2](https://lbs.amap.com/api/mcp-server/gettingstarted#s2).

```toml
# Core (shared)
enabled = true
auto_start = true
prefer_mcp = true
namespace_strategy = "prefix"
default_prefix = "mcp_"

# --- Streamable HTTP (Gaode/Amap example) ---
[servers.remote-amap]
transport = "streamable_http"
url = "https://restapi.amap.com/mcp/v1"       # replace with the endpoint documented by Amap
rename_prefix = "amap:"
include_tools = ["place.search", "route.plan"]  # optional: limit the tool list

[servers.remote-amap.headers]
Authorization = "Bearer $AMAP_MCP_TOKEN"       # inject API credential via env var
X-Map-Key = "$AMAP_WEB_KEY"                    # reuse existing console key

[servers.remote-amap.options]
timeout_ms = 30000
sse_read_timeout_ms = 120000
terminate_on_close = true
insecure_skip_verify = false

# --- Existing stdio servers continue to work ---
[servers.filesystem]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "./data"]
rename_prefix = "fs:"
```

Notes:
- Environment variables in `headers` and `env` are expanded (e.g., `$AMAP_MCP_TOKEN`). Leave them unset to fall back to empty strings during validation - tests must cover this scenario.
- `timeout_ms` and `sse_read_timeout_ms` are expressed in milliseconds for consistency with existing retry/backoff options; the loader converts them to seconds (`timedelta`) before passing them to `langchain-mcp-adapters`.
- `insecure_skip_verify = true` is meant for local development or when connecting to self-signed endpoints. Production configs should omit it or set it to false.
- You can mix multiple stdio and Streamable HTTP servers; naming and include/exclude filters work the same way across transports.

### 5) Implementation guidelines

- **Transport scope**: officially support `stdio` and `streamable_http`. Do not implement legacy `http+sse` or WebSocket in this iteration.
- **Types**: extend `ServerConfig` with a typed `transport` (`Literal["stdio", "streamable_http"]`), add a `StreamableHTTPOptions` dataclass, and keep separate option fields to avoid leaking HTTP-only data into stdio configs.
- **Config loader**: isolate transport-specific validators, cover missing required fields, type mismatches, and unsupported keys in unit tests.
- **Manager**: build connection dictionaries via a helper to keep logic maintainable. Mask sensitive headers when recording status snapshots. Ensure the custom `httpx_client_factory` is only attached when necessary.
- **Testing**: add parameterized tests covering valid/invalid combinations for both transports, including env expansion, option mapping, and status redaction.
- **Backwards compatibility**: maintain current behavior when only stdio servers are configured. Ensure that `prefer_mcp`, namespace settings, and retry policies stay untouched.

### 6) Migration and testing checklist

1. Update `mcp.toml` (or `mcp.example.toml`) to add Streamable HTTP servers, ensuring credentials are provided via environment variables.
2. Verify dependency versions inside the virtual environment (`pip show langchain-mcp-adapters mcp`). Upgrade if versions are older than the minimum listed above.
3. Start the app and inspect MCP status command/endpoint:
   - Each server should display its `transport`, connection state, and tool count (headers redacted).
   - Total tool count should increase after remote servers connect.
4. Exercise tools via both agent paths:
   - LangChain ReAct/ToolCalling agents should list and execute the new tools.
   - `zhipu_fcall_agent` should surface the same tools in its model function schema.
5. Observe logs for timeouts or reconnection attempts. Adjust `timeout_ms` / `sse_read_timeout_ms` as needed; they map directly to the Streamable HTTP adapter parameters.
6. For Gaode/Amap specifically, confirm quota limits and API key validity through the official console before enabling the server in production.

### 7) Operational considerations

- **Reliability**
  - Remote transports introduce higher latency and potential network failures. Keep retry/backoff behavior in place and expose clear error messages in status output.
  - Streamable HTTP automatically opens an SSE stream after initialization; no additional heartbeats are needed, but timeouts should be tuned for long-running requests.
- **Security**
  - Prefer HTTPS endpoints. Reserve `insecure_skip_verify` for local testing when the endpoint uses self-signed certificates.
  - Avoid logging full header values. Redact sensitive data (`Authorization`, `X-API-KEY`, etc.) in both status and diagnostic logs.
- **Namespacing**
  - Use `rename_prefix` per server to prevent collisions and to make it obvious which backend a tool originates from.
- **Advanced options**
  - Future iterations may expose `auth` or `session_kwargs`. Document and test them when needed; for now they can be kept internal to prevent misconfiguration.

### 8) FAQ

- **Do agents need changes?**  
  No. Agents consume `BaseTool` lists; transport differences are handled inside the manager.

- **Does the manager need to send manual heartbeats or GET requests?**  
  No. `langchain-mcp-adapters` 0.1.11 automatically triggers the Streamable HTTP GET stream after receiving `notifications/initialized` and manages `Mcp-Session-Id` propagation.

- **Can we skip converting MCP tools to LangChain `BaseTool`?**  
  Not yet. We keep the adapter for compatibility. Native MCP execution paths can be added later without breaking this plan.

- **What about resources/prompts?**  
  The transport supports them too; this iteration focuses on tools. Resource/prompt UX can be layered on once the transport stabilizes.

### 9) References

- MCP Intro: [modelcontextprotocol.io/docs/getting-started/intro](https://modelcontextprotocol.io/docs/getting-started/intro)
- MCP Servers (tools/resources/prompts): [modelcontextprotocol.io/docs/learn/server-concepts](https://modelcontextprotocol.io/docs/learn/server-concepts)
- Official transport list: [modelcontextprotocol.io/specification/2025-06-18/basic/transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- Authorization guidance: [modelcontextprotocol.io/specification/2025-06-18/basic/authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
- Gaode (Amap) MCP quick start: [https://lbs.amap.com/api/mcp-server/gettingstarted#s2](https://lbs.amap.com/api/mcp-server/gettingstarted#s2)
