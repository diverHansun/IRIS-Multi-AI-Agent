"""Session-scoped HITL preference tracking for deep agent streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Set


@dataclass
class SessionHITLManager:
    """Manage session-scoped Human-in-the-Loop preferences."""

    dangerous_tools: Set[str] = field(default_factory=set)
    tool_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    auto_approved_tools: Set[str] = field(default_factory=set)

    def is_auto_approved(self, tool_name: str) -> bool:
        """Return True if the tool has been auto-approved for this session."""
        return tool_name in self.auto_approved_tools

    def can_auto_approve(self, tool_name: str) -> bool:
        """Determine whether the tool supports auto-approval."""
        if tool_name in self.dangerous_tools:
            return False
        settings = self.tool_settings.get(tool_name)
        if settings is None:
            return True
        return settings.get("allow_auto_approve", True)

    def register_auto_approval(self, tool_name: str) -> None:
        """Persist auto-approval preference for the remainder of the session."""
        if not self.can_auto_approve(tool_name):
            msg = f"Tool '{tool_name}' cannot be auto-approved in this session."
            raise ValueError(msg)
        self.auto_approved_tools.add(tool_name)

    def clear(self) -> None:
        """Clear all session preferences."""
        self.auto_approved_tools.clear()

    def is_dangerous(self, tool_name: str) -> bool:
        """Return True if tool is flagged as dangerous."""
        return tool_name in self.dangerous_tools

    def get_tool_warning(self, tool_name: str) -> Optional[str]:
        """Fetch warning message configured for a tool, if any."""
        settings = self.tool_settings.get(tool_name)
        if not settings:
            return None
        warning = settings.get("warning_message")
        return str(warning) if warning else None

    def update_configuration(
        self,
        *,
        dangerous_tools: Iterable[str] | None = None,
        tool_settings: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        """Update dangerous tool list and tool settings."""
        if dangerous_tools is not None:
            self.dangerous_tools = {tool.strip() for tool in dangerous_tools}
        if tool_settings is not None:
            self.tool_settings = {key.strip(): value for key, value in tool_settings.items()}
        # Remove any auto-approved tools that are no longer allowed.
        self.auto_approved_tools = {
            tool for tool in self.auto_approved_tools if self.can_auto_approve(tool)
        }

    def export_preferences(self) -> Dict[str, Any]:
        """Return a snapshot of the current session preferences."""
        return {
            "auto_approved_tools": sorted(self.auto_approved_tools),
            "dangerous_tools": sorted(self.dangerous_tools),
            "tool_settings": self.tool_settings,
        }

