from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional, Literal


@dataclass
class RetryConfig:
    max_retries: int = 2
    backoff_ms: int = 500


@dataclass
class StreamableHTTPOptions:
    timeout: Optional[timedelta] = None
    sse_read_timeout: Optional[timedelta] = None
    terminate_on_close: Optional[bool] = None
    insecure_skip_verify: bool = False


Transport = Literal["stdio", "streamable_http"]


@dataclass
class ServerConfig:
    name: str
    transport: Transport = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    include_tools: List[str] = field(default_factory=list)
    exclude_tools: List[str] = field(default_factory=list)
    rename_prefix: Optional[str] = None
    timeout_ms: Optional[int] = None
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    streamable_options: StreamableHTTPOptions = field(default_factory=StreamableHTTPOptions)


@dataclass
class MCPConfig:
    enabled: bool = False
    auto_start: bool = False
    prefer_mcp: bool = True
    namespace_strategy: str = "prefix"  # or "none"
    default_prefix: str = "mcp:"
    retry: RetryConfig = field(default_factory=RetryConfig)
    servers: Dict[str, ServerConfig] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)  # keep original
