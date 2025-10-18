import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import BaseTool

from .config_loader import load_config, find_config_path
from .errors import MCPInitializationError, MCPNotAvailableError
from .tool_adapter import apply_naming_and_filter, schema_summary
from .types import ServerConfig


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

    - Loads config from config/mcp/mcp.toml (or JSON fallback)
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

                cls._tools = tools

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
