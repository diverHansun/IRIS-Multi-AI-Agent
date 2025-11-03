"""File operation tracking for streaming mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

FileOpStatus = Literal["pending", "success", "error"]


@dataclass
class FileOperationRecord:
    """Track a single file operation during streaming."""

    tool_name: str
    tool_call_id: Optional[str]
    args: Dict[str, Any] = field(default_factory=dict)
    status: FileOpStatus = "pending"
    error: Optional[str] = None


class FileOpTracker:
    """Track file operations during agent execution."""

    def __init__(self) -> None:
        self.active: Dict[Optional[str], FileOperationRecord] = {}
        self.completed: list[FileOperationRecord] = []

    def start_operation(
        self, tool_name: str, args: Dict[str, Any], tool_call_id: Optional[str]
    ) -> None:
        """Register a new file operation when tool call starts."""
        if tool_name not in {"read_file", "write_file", "edit_file"}:
            return

        record = FileOperationRecord(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            args=args,
        )
        self.active[tool_call_id] = record

    def complete_with_message(self, tool_message: Any) -> Optional[FileOperationRecord]:
        """Update operation record when tool completes."""
        tool_call_id = getattr(tool_message, "tool_call_id", None)
        record = self.active.get(tool_call_id)
        if record is None:
            return None

        content = tool_message.content
        if isinstance(content, list):
            content_parts = []
            for item in content:
                if isinstance(item, str):
                    content_parts.append(item)
                else:
                    content_parts.append(str(item))
            content_text = "\n".join(content_parts)
        else:
            content_text = str(content) if content is not None else ""

        status = getattr(tool_message, "status", "success")
        if status != "success" or content_text.lower().startswith("error"):
            record.status = "error"
            record.error = content_text
        else:
            record.status = "success"

        self._finalize(record)
        return record

    def _finalize(self, record: FileOperationRecord) -> None:
        """Move record from active to completed."""
        self.completed.append(record)
        self.active.pop(record.tool_call_id, None)
