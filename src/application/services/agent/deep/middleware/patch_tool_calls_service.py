"""Patch tool calls middleware metadata."""

from __future__ import annotations

from typing import Any, Dict


class PatchToolCallsService:
    """Provide basic status for patch tool calls middleware."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        self.enabled = bool(config.get("enabled", True)) if config else True

    def describe(self) -> Dict[str, Any]:
        return {"enabled": self.enabled}
