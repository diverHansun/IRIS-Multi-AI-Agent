"""Filesystem middleware management for deep agents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class FilesystemMiddlewareService:
    """Manage filesystem middleware configuration."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        self._config: Dict[str, Any] = config or {}
        self.enabled: bool = bool(self._config.get("enabled", True))
        self.default_mode: str = self._config.get("default_mode", "read_only")
        self.mode: str = self._config.get("mode", self.default_mode)
        self.long_term_memory: bool = bool(self._config.get("long_term_memory", False))
        self.tool_token_limit: Optional[int] = self._config.get("tool_token_limit_before_evict")
        self.modes: Dict[str, Any] = dict(self._config.get("modes", {}))
        self._mode_details: Dict[str, Any] = {}
        self._apply_mode(self.mode)

    def _apply_mode(self, mode: str) -> None:
        mode_config = self.modes.get(mode, {})
        security_source = mode_config.get("security", self._config.get("security", {}))
        self.allowed_paths: List[str] = list(security_source.get("allowed_paths", []))
        self.excluded_paths: List[str] = list(security_source.get("excluded_paths", []))
        self.max_file_size: int = int(security_source.get("max_file_size", 0))
        self.excluded_extensions: List[str] = list(security_source.get("excluded_extensions", []))
        self._mode_details = {
            "description": mode_config.get("description"),
            "requires_confirmation": mode_config.get("requires_confirmation"),
        }

    def set_mode(self, mode: str) -> None:
        if mode not in {"read_only", "ask_before_edit", "auto_edit"}:
            raise ValueError("Unsupported filesystem mode.")
        self.mode = mode
        self._config["mode"] = mode
        self._apply_mode(mode)

    def describe(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "default_mode": self.default_mode,
            "allowed_paths": self.allowed_paths,
            "excluded_paths": self.excluded_paths,
            "max_file_size": self.max_file_size,
            "excluded_extensions": self.excluded_extensions,
            "long_term_memory": self.long_term_memory,
            "modes": self.modes,
            "mode_details": self._mode_details,
            "tool_token_limit_before_evict": self.tool_token_limit,
        }
