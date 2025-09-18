import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import MCPConfig, ServerConfig, RetryConfig


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


def _expand_env_in_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    expanded: Dict[str, Any] = {}
    for k, v in mapping.items():
        if isinstance(v, str) and v.startswith("$"):
            expanded[k] = os.getenv(v[1:], "")
        else:
            expanded[k] = v
    return expanded


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
    candidates = [Path("config/mcp/mcp.toml"), Path("config/mcp/mcp.json")]
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
        transport = str(raw.get("transport", "stdio")).lower()
        command = str(raw.get("command", ""))
        args = list(raw.get("args", []) or [])
        cwd = raw.get("cwd", None)
        env = _expand_env_in_mapping(raw.get("env", {}) or {})
        include_tools = list(raw.get("include_tools", []) or [])
        exclude_tools = list(raw.get("exclude_tools", []) or [])
        rename_prefix = raw.get("rename_prefix", None)
        timeout_ms = raw.get("timeout_ms", None)

        # Only stdio in this phase
        if transport != "stdio":
            raise ValueError(f"Unsupported transport: {transport} (only 'stdio' is supported now)")
        if not command:
            raise ValueError(f"Server '{name}' requires a 'command'")

        servers[name] = ServerConfig(
            name=name,
            transport=transport,
            command=command,
            args=args,
            cwd=cwd,
            env=env,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
            rename_prefix=rename_prefix,
            timeout_ms=timeout_ms,
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

