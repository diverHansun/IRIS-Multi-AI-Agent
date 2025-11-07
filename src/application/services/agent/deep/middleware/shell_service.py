"""Shell middleware management for deep agents."""

from __future__ import annotations

from typing import Any, Dict


class ShellMiddlewareService:
    """Service layer for shell middleware configuration management."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        """
        Initialize shell middleware service.

        Args:
            config: Configuration dictionary
        """
        self._config: Dict[str, Any] = config or {}

        self.enabled: bool = bool(self._config.get("enabled", False))
        self.workspace_root = self._config.get("workspace_root", ".")
        self.shell_type = self._config.get("shell_type", "cmd")
        self.command_timeout = float(self._config.get("command_timeout", 30.0))
        self.startup_timeout = float(self._config.get("startup_timeout", 10.0))
        self.termination_timeout = float(self._config.get("termination_timeout", 5.0))
        self.max_output_lines = int(self._config.get("max_output_lines", 100))
        self.max_output_bytes = int(self._config.get("max_output_bytes", 1048576))
        self.environment = dict(self._config.get("environment", {}))
        self.startup_commands = list(self._config.get("startup_commands", []))

    def describe(self) -> Dict[str, Any]:
        """
        Return user-facing metadata about the middleware configuration.

        Returns:
            Configuration summary
        """
        return {
            "enabled": self.enabled,
            "workspace_root": self.workspace_root,
            "shell_type": self.shell_type,
            "command_timeout": self.command_timeout,
            "startup_timeout": self.startup_timeout,
            "termination_timeout": self.termination_timeout,
            "max_output_lines": self.max_output_lines,
            "max_output_bytes": self.max_output_bytes,
            "has_environment": bool(self.environment),
            "startup_commands_count": len(self.startup_commands),
        }

    def get_middleware_config(self) -> Dict[str, Any]:
        """
        Return configuration dictionary for ShellToolMiddleware.

        Returns:
            Configuration dict compatible with build_shell_config
        """
        return {
            "enabled": self.enabled,
            "workspace_root": self.workspace_root,
            "shell_type": self.shell_type,
            "command_timeout": self.command_timeout,
            "startup_timeout": self.startup_timeout,
            "termination_timeout": self.termination_timeout,
            "max_output_lines": self.max_output_lines,
            "max_output_bytes": self.max_output_bytes,
            "environment": self.environment,
            "startup_commands": self.startup_commands,
        }
