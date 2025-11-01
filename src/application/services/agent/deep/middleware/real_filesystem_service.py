"""Real filesystem middleware management for deep agents."""

from __future__ import annotations

from typing import Any, Dict


class RealFilesystemMiddlewareService:
    """Expose status and runtime options for the real filesystem middleware."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        self._config: Dict[str, Any] = config or {}

        self.enabled: bool = bool(self._config.get("enabled", False))
        self.project_root = self._config.get("project_root")
        self.security = dict(self._config.get("security", {}))
        self.performance = dict(self._config.get("performance", {}))
        self.advanced = dict(self._config.get("advanced", {}))

    def describe(self) -> Dict[str, Any]:
        """Return user-facing metadata about the middleware configuration."""
        security = self.security or {}
        allowed_paths = security.get("allowed_paths") or []
        excluded_paths = security.get("excluded_paths") or []
        allowed_extensions = security.get("allowed_extensions") or []

        summary = {
            "enabled": self.enabled,
            "project_root": self.project_root,
            "allowed_paths": allowed_paths,
            "excluded_paths": excluded_paths,
            "allowed_extensions": allowed_extensions,
            "max_file_size": security.get("max_file_size"),
            "ignore_hidden_files": self.advanced.get("ignore_hidden_files", True),
        }
        return summary

    def get_middleware_options(self) -> Dict[str, Any]:
        """Return kwargs for RealFilesystemMiddleware."""
        return {
            "config": {
                "project_root": self.project_root,
                "security": self.security,
                "performance": self.performance,
                "advanced": self.advanced,
            }
        }
