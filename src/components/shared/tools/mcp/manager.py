import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import BaseTool, StructuredTool

from .config_loader import load_config, find_config_path
from .errors import MCPInitializationError, MCPNotAvailableError
from .tool_adapter import apply_naming_and_filter, schema_summary
from .types import ServerConfig

logger = logging.getLogger(__name__)


def _wrap_mcp_tool_with_error_handling(tool: BaseTool) -> BaseTool:
    """
    Wrap MCP tool with error handling to prevent conversation interruption.

    This wrapper catches exceptions from MCP tool execution (network errors,
    timeouts, server crashes) and returns error messages instead of raising
    exceptions, allowing Deep Agent conversations to continue gracefully.

    Design Principles:
        - KISS: Simple wrapper pattern, no complex error recovery logic
        - SRP: Single responsibility - convert exceptions to error messages
        - DRY: Unified error handling for all MCP tools

    Args:
        tool: Original MCP tool to wrap

    Returns:
        Wrapped tool that returns error messages instead of raising exceptions

    Error Handling:
        - asyncio.TimeoutError: MCP server response timeout
        - ConnectionError: Network connection failures
        - OSError: Process/socket errors (stdio transport)
        - Exception: All other unexpected errors

    Example Error Message:
        "[MCP ERROR] Tool 'firecrawl_map' failed: ConnectionError: Network unreachable.
        The tool may be temporarily unavailable. Please try again or use an alternative."
    """
    original_coroutine = tool.coroutine

    async def safe_ainvoke(**kwargs):
        """
        Safe async invocation wrapper with comprehensive error handling.

        Returns error message string on failure instead of raising exception.
        """
        try:
            if original_coroutine:
                return await original_coroutine(**kwargs)
            else:
                # Fallback to sync func if no coroutine (should not happen for MCP)
                logger.warning(
                    f"MCP tool '{tool.name}' has no coroutine, falling back to sync execution"
                )
                if tool.func:
                    # Run sync function in thread pool
                    return await asyncio.to_thread(tool.func, **kwargs)
                else:
                    raise RuntimeError(f"Tool {tool.name} has no callable implementation")

        except asyncio.TimeoutError as exc:
            # MCP server response timeout
            error_msg = (
                f"[MCP TIMEOUT] Tool '{tool.name}' execution timed out.\n"
                f"The MCP server may be slow or unresponsive.\n"
                f"Suggestions:\n"
                f"- Try again with a simpler request\n"
                f"- Check MCP server status\n"
                f"- Use an alternative tool if available"
            )
            logger.warning(f"MCP tool timeout: {tool.name}", exc_info=True)
            return error_msg

        except (ConnectionError, OSError) as exc:
            # Network connection failures or process errors
            error_msg = (
                f"[MCP CONNECTION ERROR] Tool '{tool.name}' connection failed.\n"
                f"Error details: {exc.__class__.__name__}: {exc}\n"
                f"Possible causes:\n"
                f"- Network connectivity issues\n"
                f"- MCP server not running or crashed\n"
                f"- Firewall blocking connection\n"
                f"Suggestions:\n"
                f"- Check your network connection\n"
                f"- Verify MCP server configuration in config/tools/mcp/mcp.toml\n"
                f"- Try restarting the application"
            )
            logger.warning(
                f"MCP tool connection error: {tool.name} - {exc.__class__.__name__}: {exc}",
                exc_info=True
            )
            return error_msg

        except Exception as exc:
            # All other unexpected errors
            error_msg = (
                f"[MCP ERROR] Tool '{tool.name}' execution failed.\n"
                f"Error type: {exc.__class__.__name__}\n"
                f"Error details: {exc}\n"
                f"The tool may be temporarily unavailable.\n"
                f"Suggestions:\n"
                f"- Try again later\n"
                f"- Use an alternative tool\n"
                f"- Check application logs for details"
            )
            logger.warning(
                f"MCP tool execution error: {tool.name} - {exc.__class__.__name__}: {exc}",
                exc_info=True
            )
            return error_msg

    # Create wrapped tool preserving original metadata
    # KISS principle: Use StructuredTool.from_function for simple wrapping
    return StructuredTool.from_function(
        name=tool.name,
        func=None,  # No sync version for MCP tools
        coroutine=safe_ainvoke,
        description=tool.description,
        args_schema=tool.args_schema,
    )


def _timedelta_to_milliseconds(value: Optional[timedelta]) -> Optional[int]:
    if value is None:
        return None
    return int(value.total_seconds() * 1000)


def _build_insecure_httpx_factory() -> Callable[..., Any]:
    def factory(
        headers: Optional[Dict[str, str]] = None,
        timeout: Any = None,
        auth: Any = None,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("httpx is required for Streamable HTTP connections") from exc

        client_kwargs: Dict[str, Any] = {
            "follow_redirects": True,
            "verify": False,
        }
        if headers is not None:
            client_kwargs["headers"] = headers
        if timeout is not None:
            client_kwargs["timeout"] = timeout
        else:
            client_kwargs["timeout"] = httpx.Timeout(30.0)
        if auth is not None:
            client_kwargs["auth"] = auth

        return httpx.AsyncClient(**client_kwargs)

    return factory


class GlobalMCPManager:
    """Global singleton MCP manager.

    - Loads config from config/tools/mcp/mcp.toml (or JSON fallback)
    - Starts multiple MCP servers via langchain-mcp-adapters (stdio)
    - Exposes aggregated LangChain tools for all agents
    - Provides CLI status/tools/reload interfaces
    """

    _lock: Optional[asyncio.Lock] = None
    _initialized: bool = False
    _config: Optional[Any] = None
    _client: Any = None
    _tools: List[BaseTool] = []
    _status: Dict[str, Any] = {}
    _config_path: Optional[str] = None
    _last_reload: Optional[str] = None
    _deps_available: Optional[bool] = None

    @staticmethod
    def _build_connection_entry(server: ServerConfig) -> Dict[str, Any]:
        if server.transport == "stdio":
            entry: Dict[str, Any] = {
                "transport": server.transport,
                "command": server.command,
                "args": server.args,
            }
            if server.cwd:
                entry["cwd"] = server.cwd
            if server.env:
                entry["env"] = server.env
            return entry

        if not server.url:
            raise ValueError(f"Server '{server.name}' is missing 'url' for Streamable HTTP transport")

        entry = {
            "transport": server.transport,
            "url": server.url,
        }
        if server.headers:
            entry["headers"] = server.headers

        options = server.streamable_options
        if options.timeout is not None:
            entry["timeout"] = options.timeout
        if options.sse_read_timeout is not None:
            entry["sse_read_timeout"] = options.sse_read_timeout
        if options.terminate_on_close is not None:
            entry["terminate_on_close"] = options.terminate_on_close
        if options.insecure_skip_verify:
            entry["httpx_client_factory"] = _build_insecure_httpx_factory()

        return entry

    @staticmethod
    def _streamable_status_options(server: ServerConfig) -> Optional[Dict[str, Any]]:
        options = server.streamable_options
        summary: Dict[str, Any] = {}

        timeout_ms = _timedelta_to_milliseconds(options.timeout)
        if timeout_ms is not None:
            summary["timeout_ms"] = timeout_ms

        sse_timeout_ms = _timedelta_to_milliseconds(options.sse_read_timeout)
        if sse_timeout_ms is not None:
            summary["sse_read_timeout_ms"] = sse_timeout_ms

        if options.terminate_on_close is not None:
            summary["terminate_on_close"] = options.terminate_on_close

        if options.insecure_skip_verify:
            summary["insecure_skip_verify"] = True

        return summary or None

    @classmethod
    def _build_status_entry(cls, server: ServerConfig) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "name": server.name,
            "transport": server.transport,
            "status": "initializing",
            "tools_count": None,
            "last_error": None,
        }

        if server.transport == "stdio":
            entry["command"] = server.command
        else:
            entry["url"] = server.url
            if server.headers:
                entry["headers"] = {key: "***" for key in server.headers.keys()}
            options_summary = cls._streamable_status_options(server)
            if options_summary:
                entry["options"] = options_summary

        return entry

    @classmethod
    def _ensure_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _check_deps(cls) -> bool:
        if cls._deps_available is not None:
            return cls._deps_available
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: F401
            cls._deps_available = True
        except Exception:
            cls._deps_available = False
        return cls._deps_available

    @classmethod
    async def initialize(cls, force: bool = False) -> None:
        lock = cls._ensure_lock()
        async with lock:
            if cls._initialized and not force:
                return

            # load config
            cfg = load_config()
            cls._config = cfg
            cls._config_path = cfg.raw.get("__path__") if cfg and cfg.raw else None
            cls._status = {
                "enabled": bool(cfg.enabled),
                "config_path": cls._config_path,
                "servers": [],
                "tools_total": 0,
                "last_error": None,
            }

            # disabled
            if not cfg.enabled:
                cls._tools = []
                cls._client = None
                cls._initialized = True
                return

            # deps
            if not cls._check_deps():
                cls._status["last_error"] = (
                    "langchain-mcp-adapters not installed. Install it to enable MCP."
                )
                cls._tools = []
                cls._client = None
                cls._initialized = True
                return

            # build server config for MultiServerMCPClient
            server_config: Dict[str, Dict[str, Any]] = {}
            for name, sc in cfg.servers.items():
                server_config[name] = cls._build_connection_entry(sc)

            # Pre-populate status with configured servers for better diagnostics
            cls._status["servers"] = [
                cls._build_status_entry(sc)
                for sc in cfg.servers.values()
            ]

            # start client and get tools
            try:
                from langchain_mcp_adapters.client import MultiServerMCPClient

                cls._client = MultiServerMCPClient(server_config)
                # aggregated tools
                raw_tools: List[BaseTool] = await cls._client.get_tools()

                # naming/filtering (best-effort: apply per-server defaults not available => default_prefix)
                # Since the adapter returns aggregated tools, we apply default prefix at least.
                tools = apply_naming_and_filter(
                    raw_tools,
                    namespace_strategy=cfg.namespace_strategy,
                    default_prefix=cfg.default_prefix,
                )

                # Wrap all MCP tools with error handling to prevent conversation interruption
                # DRY principle: unified error handling for all MCP tools
                # This prevents network errors from interrupting Deep Agent conversations
                wrapped_tools = [_wrap_mcp_tool_with_error_handling(t) for t in tools]

                cls._tools = wrapped_tools

                # mark all configured servers as connected (per-server health is not exposed)
                for s in cls._status.get("servers", []):
                    s["status"] = "connected"

                cls._status["tools_total"] = len(cls._tools)
                cls._initialized = True
                cls._last_reload = datetime.utcnow().isoformat()
            except Exception as e:
                # Improve error visibility, especially for ExceptionGroup/TaskGroup failures
                def _format_exc(err: BaseException, depth: int = 0) -> str:
                    try:
                        from types import TracebackType  # noqa: F401
                    except Exception:
                        pass
                    prefix = "" if depth == 0 else "  " * depth
                    if hasattr(err, "exceptions") and isinstance(err, Exception):  # ExceptionGroup (py3.11+)
                        sub = getattr(err, "exceptions", [])
                        parts = [f"{prefix}{err.__class__.__name__}: {err}"]
                        for se in sub:
                            parts.append(_format_exc(se, depth + 1))
                        return "\n".join(parts)
                    return f"{prefix}{err.__class__.__name__}: {err}"

                cls._status["last_error"] = _format_exc(e)
                # mark servers as failed for better UX
                for s in cls._status.get("servers", []):
                    s["status"] = "failed"
                    s["last_error"] = "See top-level last_error"
                cls._tools = []
                cls._client = None
                cls._initialized = True

    @classmethod
    async def reload_config(cls) -> Dict[str, Any]:
        await cls.initialize(force=True)
        return {
            "enabled": bool(cls._config.enabled) if cls._config else False,
            "tools_total": len(cls._tools),
            "config_path": cls._config_path,
            "last_reload": cls._last_reload,
        }

    @classmethod
    def get_tools(cls) -> List[BaseTool]:
        # If not initialized and auto_start enabled, initialize lazily in a new loop if possible
        if not cls._initialized:
            cfg = load_config()
            if cfg.enabled and cfg.auto_start:
                try:
                    loop = asyncio.get_running_loop()
                    # schedule and wait synchronously is not possible here; return empty until explicit init
                except RuntimeError:
                    asyncio.run(cls.initialize())
        return cls._tools or []

    @classmethod
    def get_status(cls, verbose: bool = False) -> Dict[str, Any]:
        status = {
            "enabled": bool(cls._config.enabled) if cls._config else False,
            "initialized": cls._initialized,
            "config_path": cls._config_path,
            "tools_total": len(cls._tools),
            "servers": cls._status.get("servers", []),
            "last_error": cls._status.get("last_error"),
            "last_reload": cls._last_reload,
        }
        if verbose:
            status["tools"] = [schema_summary(t) for t in (cls._tools or [])]
        return status

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            try:
                await cls._client.close()
            except Exception:
                pass
        cls._client = None
        cls._initialized = False
        cls._tools = []
