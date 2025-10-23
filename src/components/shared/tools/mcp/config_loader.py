import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .types import (
    MCPConfig,
    RetryConfig,
    ServerConfig,
    StreamableHTTPOptions,
    Transport,
)


def _read_toml(path: Path) -> Dict[str, Any]:
    try:
        # Python 3.11+
        import tomllib  # type: ignore
        with path.open("rb") as f:
            return tomllib.load(f)
    except ModuleNotFoundError:
        try:
            import tomli  # type: ignore
            with path.open("rb") as f:
                return tomli.load(f)
        except ModuleNotFoundError:
            raise RuntimeError(
                "TOML parser not available. Install 'tomli' for Python <3.11 or use JSON config."
            )


def _expand_env_in_string(value: str) -> str:
    """Expand environment variables in a string.
    
    Supports two formats:
    - $VAR_NAME - simple variable reference
    - ${VAR_NAME} - variable reference with braces
    
    Multiple variables in a single string are supported.
    Example: "https://api.example.com?key=$API_KEY&user=${USER_ID}"
    """
    import re
    
    # Expand ${VAR_NAME} format
    def replace_braced(match):
        var_name = match.group(1)
        return os.getenv(var_name, "")
    
    value = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', replace_braced, value)
    
    # Expand $VAR_NAME format (word boundary aware)
    def replace_simple(match):
        var_name = match.group(1)
        return os.getenv(var_name, "")
    
    value = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replace_simple, value)
    
    return value


def _expand_env_in_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Expand environment variables in a dictionary mapping."""
    expanded: Dict[str, Any] = {}
    for k, v in mapping.items():
        if isinstance(v, str):
            expanded[k] = _expand_env_in_string(v)
        else:
            expanded[k] = v
    return expanded


def _stringify_mapping(mapping: Dict[str, Any], field_name: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for k, v in mapping.items():
        if not isinstance(k, str) or not k:
            raise ValueError(f"{field_name} must use non-empty string keys")
        result[k] = "" if v is None else str(v)
    return result


def _coerce_optional_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if coerced < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return coerced


def _coerce_optional_bool(value: Any, field_name: str) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean")


def _parse_streamable_options(name: str, options: Dict[str, Any]) -> StreamableHTTPOptions:
    allowed_keys = {
        "timeout_ms",
        "sse_read_timeout_ms",
        "terminate_on_close",
        "insecure_skip_verify",
    }
    unexpected = sorted(set(options.keys()) - allowed_keys)
    if unexpected:
        joined = ", ".join(unexpected)
        raise ValueError(f"Server '{name}' has unsupported Streamable HTTP options: {joined}")

    timeout_ms = _coerce_optional_int(options.get("timeout_ms"), f"servers.{name}.options.timeout_ms")
    sse_timeout_ms = _coerce_optional_int(
        options.get("sse_read_timeout_ms"),
        f"servers.{name}.options.sse_read_timeout_ms",
    )
    terminate_on_close = _coerce_optional_bool(
        options.get("terminate_on_close"),
        f"servers.{name}.options.terminate_on_close",
    )

    insecure_skip_verify_raw = options.get("insecure_skip_verify")
    if insecure_skip_verify_raw is None:
        insecure_skip_verify = False
    elif isinstance(insecure_skip_verify_raw, bool):
        insecure_skip_verify = insecure_skip_verify_raw
    else:
        raise ValueError(
            f"servers.{name}.options.insecure_skip_verify must be a boolean",
        )

    return StreamableHTTPOptions(
        timeout=timedelta(milliseconds=timeout_ms) if timeout_ms is not None else None,
        sse_read_timeout=(
            timedelta(milliseconds=sse_timeout_ms) if sse_timeout_ms is not None else None
        ),
        terminate_on_close=terminate_on_close,
        insecure_skip_verify=insecure_skip_verify,
    )


def _parse_transport(raw_transport: Any, name: str) -> Transport:
    transport = str(raw_transport or "stdio").lower()
    if transport not in {"stdio", "streamable_http"}:
        raise ValueError(
            f"Unsupported transport '{transport}' for server '{name}' "
            "(supported transports: stdio, streamable_http)"
        )
    return cast(Transport, transport)


def _build_stdio_server(
    name: str,
    raw: Dict[str, Any],
    include_tools: List[str],
    exclude_tools: List[str],
    rename_prefix: Optional[str],
    timeout_ms: Optional[int],
) -> ServerConfig:
    command_raw = str(raw.get("command", "")).strip()
    if not command_raw:
        raise ValueError(f"Server '{name}' requires a 'command' when transport is 'stdio'")
    
    # Expand environment variables in command
    command = _expand_env_in_string(command_raw)

    args_raw = raw.get("args", []) or []
    if not isinstance(args_raw, (list, tuple)):
        raise ValueError(f"Server '{name}' expects 'args' to be a list when transport is 'stdio'")
    # Expand environment variables in args
    args = [_expand_env_in_string(str(arg)) for arg in args_raw]

    cwd_raw = raw.get("cwd", None)
    # Expand environment variables in cwd if present
    cwd = _expand_env_in_string(cwd_raw) if cwd_raw and isinstance(cwd_raw, str) else cwd_raw
    
    env_raw = raw.get("env", {}) or {}
    if not isinstance(env_raw, dict):
        raise ValueError(f"Server '{name}' expects 'env' to be a mapping when transport is 'stdio'")
    env = _expand_env_in_mapping(env_raw)
    env = _stringify_mapping(env, f"servers.{name}.env")

    return ServerConfig(
        name=name,
        transport="stdio",
        command=command,
        args=args,
        cwd=cwd,
        env=env,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        rename_prefix=rename_prefix,
        timeout_ms=timeout_ms,
    )


def _build_streamable_http_server(
    name: str,
    raw: Dict[str, Any],
    include_tools: List[str],
    exclude_tools: List[str],
    rename_prefix: Optional[str],
    timeout_ms: Optional[int],
) -> ServerConfig:
    url_raw = raw.get("url")
    if not isinstance(url_raw, str) or not url_raw:
        raise ValueError(f"Server '{name}' requires a non-empty 'url' when transport is 'streamable_http'")
    
    # Expand environment variables in URL
    url = _expand_env_in_string(url_raw)

    headers_raw = raw.get("headers", {}) or {}
    if not isinstance(headers_raw, dict):
        raise ValueError(f"Server '{name}' expects 'headers' to be a mapping when transport is 'streamable_http'")
    headers_expanded = _expand_env_in_mapping(headers_raw)
    headers = _stringify_mapping(headers_expanded, f"servers.{name}.headers")

    options_raw = raw.get("options", {}) or {}
    if not isinstance(options_raw, dict):
        raise ValueError(f"Server '{name}' expects 'options' to be a mapping when transport is 'streamable_http'")
    streamable_options = _parse_streamable_options(name, options_raw)

    return ServerConfig(
        name=name,
        transport="streamable_http",
        command="",
        args=[],
        cwd=None,
        env={},
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        rename_prefix=rename_prefix,
        timeout_ms=timeout_ms,
        url=url,
        headers=headers,
        streamable_options=streamable_options,
    )


def find_config_paths() -> List[Path]:
    """Find all available MCP config files (both TOML and JSON)"""
    paths = []
    
    # ENV override (if specified, only use that path)
    override = os.getenv("MCP_CONFIG_PATH")
    if override:
        p = Path(override)
        if p.exists():
            return [p]
        else:
            return []

    # Look for both TOML and JSON config files
    candidates = [Path("config/tools/mcp/mcp.toml"), Path("config/tools/mcp/mcp.json")]
    for candidate in candidates:
        if candidate.exists():
            paths.append(candidate)
    
    return paths


def find_config_path() -> Optional[Path]:
    """Backward compatibility function - returns the first available config file"""
    paths = find_config_paths()
    return paths[0] if paths else None


def _validate_and_build(config_dict: Dict[str, Any]) -> MCPConfig:
    enabled = bool(config_dict.get("enabled", False))
    auto_start = bool(config_dict.get("auto_start", False))
    prefer_mcp = bool(config_dict.get("prefer_mcp", True))
    namespace_strategy = str(config_dict.get("namespace_strategy", "prefix"))
    default_prefix = str(config_dict.get("default_prefix", "mcp:"))
    retry_dict = config_dict.get("retry", {}) or {}
    retry = RetryConfig(
        max_retries=int(retry_dict.get("max_retries", 2)),
        backoff_ms=int(retry_dict.get("backoff_ms", 500)),
    )

    servers_dict = config_dict.get("servers", {}) or {}
    servers: Dict[str, ServerConfig] = {}
    for name, raw in servers_dict.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Server '{name}' configuration must be a mapping")

        include_tools = list(raw.get("include_tools", []) or [])
        exclude_tools = list(raw.get("exclude_tools", []) or [])
        rename_prefix = raw.get("rename_prefix", None)
        timeout_ms = _coerce_optional_int(raw.get("timeout_ms"), f"servers.{name}.timeout_ms")

        transport = _parse_transport(raw.get("transport", "stdio"), name)

        if transport == "stdio":
            servers[name] = _build_stdio_server(
                name,
                raw,
                include_tools,
                exclude_tools,
                rename_prefix,
                timeout_ms,
            )
        else:
            servers[name] = _build_streamable_http_server(
                name,
                raw,
                include_tools,
                exclude_tools,
                rename_prefix,
                timeout_ms,
            )

    return MCPConfig(
        enabled=enabled,
        auto_start=auto_start,
        prefer_mcp=prefer_mcp,
        namespace_strategy=namespace_strategy,
        default_prefix=default_prefix,
        retry=retry,
        servers=servers,
        raw=config_dict,
    )


def _merge_configs(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple config dictionaries, with later configs overriding earlier ones"""
    if not configs:
        return {}
    
    # Start with the first config
    merged = configs[0].copy()
    
    # Merge subsequent configs
    for config in configs[1:]:
        # Merge top-level keys
        for key, value in config.items():
            if key == "servers" and "servers" in merged:
                # Merge servers dictionary
                merged["servers"].update(value)
            else:
                # Override other keys
                merged[key] = value
    
    return merged


def load_config(path: Optional[Path] = None) -> MCPConfig:
    """Load MCP configuration from file(s)"""
    if path:
        # Load single specified config file
        if path.suffix.lower() == ".toml":
            data = _read_toml(path)
        else:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        cfg = _validate_and_build(data)
        cfg.raw["__path__"] = str(path)
        return cfg
    
    # Load all available config files and merge them
    paths = find_config_paths()
    if not paths:
        # No config files; default disabled config
        return MCPConfig(enabled=False, auto_start=False)
    
    # Load all configs
    configs = []
    loaded_paths = []
    for p in paths:
        try:
            if p.suffix.lower() == ".toml":
                data = _read_toml(p)
            else:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            configs.append(data)
            loaded_paths.append(str(p))
        except Exception as e:
            # Log error but continue with other configs
            import logging
            logging.warning(f"Failed to load MCP config from {p}: {e}")
    
    # Merge configs
    merged_data = _merge_configs(configs)
    merged_data["__paths__"] = loaded_paths
    
    cfg = _validate_and_build(merged_data)
    # For backward compatibility, set __path__ to the first config file
    cfg.raw["__path__"] = loaded_paths[0] if loaded_paths else None
    cfg.raw["__paths__"] = loaded_paths
    return cfg
