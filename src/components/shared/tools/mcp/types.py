from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetryConfig:
    max_retries: int = 2
    backoff_ms: int = 500


@dataclass
class ServerConfig:
    name: str
    transport: str = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    include_tools: List[str] = field(default_factory=list)
    exclude_tools: List[str] = field(default_factory=list)
    rename_prefix: Optional[str] = None
    timeout_ms: Optional[int] = None


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

