"""Virtual filesystem middleware management for deep agents."""

from __future__ import annotations

from typing import Any, Dict, Optional


class VirtualFilesystemMiddlewareService:
    """Manage virtual filesystem middleware configuration.

    Simplified version that only handles the 3 essential config parameters:
    - enabled
    - long_term_memory
    - tool_token_limit_before_evict

    All security and mode-related configurations have been removed since
    the virtual filesystem is isolated from the host machine.
    """

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        """Initialize service with configuration dictionary.

        Args:
            config: Configuration dict from virtual_filesystem.json
        """
        self._config: Dict[str, Any] = config or {}

        # Load configuration
        self.enabled: bool = bool(self._config.get("enabled", True))
        self.long_term_memory: bool = bool(self._config.get("long_term_memory", False))
        self.tool_token_limit: Optional[int] = self._config.get("tool_token_limit_before_evict")

    def describe(self) -> Dict[str, Any]:
        """Return current configuration for debugging."""
        return {
            "enabled": self.enabled,
            "long_term_memory": self.long_term_memory,
            "tool_token_limit_before_evict": self.tool_token_limit,
        }

    def get_middleware_options(self) -> Dict[str, Any]:
        """Return options dict suitable for VirtualFilesystemMiddleware.__init__."""
        return {
            "long_term_memory": self.long_term_memory,
            "tool_token_limit_before_evict": self.tool_token_limit,
        }
