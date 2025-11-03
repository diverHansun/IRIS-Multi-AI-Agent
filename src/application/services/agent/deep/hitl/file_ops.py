"""File operation tracking and diff preview for HITL workflow.

This module provides file operation tracking with diff calculation for
real filesystem operations (write_real_file, edit_real_file).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from rich import box
from rich.panel import Panel
from rich.syntax import Syntax

FileOpStatus = Literal["pending", "success", "error"]


@dataclass
class FileOpMetrics:
    """Metrics for a file operation."""

    lines_read: int = 0
    lines_written: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    bytes_written: int = 0


@dataclass
class FileOperationRecord:
    """Track a single file operation."""

    tool_name: str
    tool_call_id: Optional[str]
    file_path: str
    physical_path: Optional[Path]
    args: Dict[str, Any] = field(default_factory=dict)
    status: FileOpStatus = "pending"
    error: Optional[str] = None

    before_content: Optional[str] = None
    after_content: Optional[str] = None
    diff: Optional[str] = None
    metrics: FileOpMetrics = field(default_factory=FileOpMetrics)


@dataclass
class ApprovalPreview:
    """Preview data for HITL approval."""

    title: str
    details: List[str]
    diff: Optional[str] = None
    diff_title: Optional[str] = None
    error: Optional[str] = None


def _safe_read(path: Path) -> Optional[str]:
    """Read file content safely, return None on failure."""
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None


def _count_lines(text: str) -> int:
    """Count lines in text."""
    if not text:
        return 0
    return len(text.splitlines())


def compute_unified_diff(
    before: str,
    after: str,
    display_path: str,
    *,
    max_lines: Optional[int] = 800,
) -> Optional[str]:
    """Compute unified diff between before and after content.

    Args:
        before: Content before modification
        after: Content after modification
        display_path: Path for display in diff header
        max_lines: Maximum lines to include in diff (None for unlimited)

    Returns:
        Unified diff string, or None if no changes
    """
    before_lines = before.splitlines()
    after_lines = after.splitlines()

    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"{display_path} (before)",
            tofile=f"{display_path} (after)",
            lineterm="",
        )
    )

    if not diff_lines:
        return None

    if max_lines is not None and len(diff_lines) > max_lines:
        truncated = diff_lines[: max_lines - 1]
        truncated.append("... (diff truncated)")
        return "\n".join(truncated)

    return "\n".join(diff_lines)


def resolve_physical_path(path_str: Optional[str]) -> Optional[Path]:
    """Convert file path to absolute physical path.

    Args:
        path_str: File path string (relative or absolute)

    Returns:
        Resolved absolute Path object, or None on error
    """
    if not path_str:
        return None

    try:
        path = Path(path_str)
        if path.is_absolute():
            return path.resolve()
        return (Path.cwd() / path).resolve()
    except (OSError, ValueError):
        return None


def format_display_path(path_str: Optional[str]) -> str:
    """Format path for display (show filename or relative path).

    Args:
        path_str: File path string

    Returns:
        Formatted path string for display
    """
    if not path_str:
        return "(unknown)"

    try:
        path = Path(path_str)
        if path.is_absolute():
            return path.name or str(path)
        return str(path)
    except (OSError, ValueError):
        return str(path_str)


def build_approval_preview(
    tool_name: str,
    args: Dict[str, Any],
) -> Optional[ApprovalPreview]:
    """Build preview for HITL approval.

    Args:
        tool_name: Name of the tool (write_real_file, edit_real_file)
        args: Tool arguments

    Returns:
        ApprovalPreview object with diff and details, or None if not applicable
    """
    if tool_name not in {"write_real_file", "edit_real_file"}:
        return None

    path_str = str(args.get("file_path") or args.get("path") or "")
    display_path = format_display_path(path_str)
    physical_path = resolve_physical_path(path_str)

    if tool_name == "write_real_file":
        content = str(args.get("content", ""))
        before = _safe_read(physical_path) if physical_path and physical_path.exists() else ""
        after = content

        diff = compute_unified_diff(before or "", after, display_path, max_lines=None)

        additions = 0
        if diff:
            additions = sum(
                1 for line in diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )

        total_lines = _count_lines(after)
        is_overwrite = bool(before)

        details = [
            f"File: {path_str}",
            "Action: Create new file" + (" (overwrites existing)" if is_overwrite else ""),
            f"Lines to write: {additions or total_lines}",
            f"Bytes to write: {len(after.encode('utf-8'))}",
        ]

        return ApprovalPreview(
            title=f"Write {display_path}",
            details=details,
            diff=diff,
            diff_title=f"Diff {display_path}",
        )

    if tool_name == "edit_real_file":
        if physical_path is None:
            return ApprovalPreview(
                title=f"Update {display_path}",
                details=[f"File: {path_str}", "Action: Replace text"],
                error="Unable to resolve file path.",
            )

        before = _safe_read(physical_path)
        if before is None:
            return ApprovalPreview(
                title=f"Update {display_path}",
                details=[f"File: {path_str}", "Action: Replace text"],
                error="Unable to read current file contents.",
            )

        old_string = str(args.get("old_string", ""))
        new_string = str(args.get("new_string", ""))
        replace_all = bool(args.get("replace_all", False))

        # Perform string replacement to predict after content
        if replace_all:
            after = before.replace(old_string, new_string)
            occurrences = before.count(old_string)
        else:
            after = before.replace(old_string, new_string, 1)
            occurrences = 1 if old_string in before else 0

        if occurrences == 0:
            return ApprovalPreview(
                title=f"Update {display_path}",
                details=[f"File: {path_str}", "Action: Replace text"],
                error="Old string not found in file.",
            )

        diff = compute_unified_diff(before, after, display_path, max_lines=None)

        additions = 0
        deletions = 0
        if diff:
            additions = sum(
                1 for line in diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            deletions = sum(
                1 for line in diff.splitlines()
                if line.startswith("-") and not line.startswith("---")
            )

        details = [
            f"File: {path_str}",
            f"Action: Replace text ({'all occurrences' if replace_all else 'single occurrence'})",
            f"Occurrences matched: {occurrences}",
            f"Lines changed: +{additions} / -{deletions}",
        ]

        return ApprovalPreview(
            title=f"Update {display_path}",
            details=details,
            diff=diff,
            diff_title=f"Diff {display_path}",
        )

    return None


class FileOpTracker:
    """Track file operations during agent execution."""

    def __init__(self) -> None:
        self.active: Dict[Optional[str], FileOperationRecord] = {}
        self.completed: List[FileOperationRecord] = []

    def start_operation(
        self,
        tool_name: str,
        args: Dict[str, Any],
        tool_call_id: Optional[str],
    ) -> None:
        """Register a file operation when tool call starts.

        Args:
            tool_name: Name of the tool (write_real_file, edit_real_file, bash)
            args: Tool arguments
            tool_call_id: Unique ID for this tool call
        """
        if tool_name not in {"write_real_file", "edit_real_file", "bash"}:
            return

        path_str = str(args.get("file_path") or args.get("path") or "")
        physical_path = resolve_physical_path(path_str)
        display_path = format_display_path(path_str)

        record = FileOperationRecord(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            file_path=path_str,
            physical_path=physical_path,
            args=args,
        )

        # Capture before_content for write/edit operations
        if tool_name in {"write_real_file", "edit_real_file"} and physical_path:
            record.before_content = _safe_read(physical_path) or ""

        self.active[tool_call_id] = record

    def complete_with_message(self, tool_message: Any) -> Optional[FileOperationRecord]:
        """Update operation record when tool completes.

        Args:
            tool_message: ToolMessage from agent execution

        Returns:
            Completed FileOperationRecord, or None if not tracked
        """
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
            self._finalize(record)
            return record

        record.status = "success"

        # For bash, just record success (no diff calculation)
        if record.tool_name == "bash":
            self._finalize(record)
            return record

        # For write/edit operations, calculate diff and metrics
        if record.physical_path:
            record.after_content = _safe_read(record.physical_path)

            if record.after_content is None:
                record.status = "error"
                record.error = "Could not read updated file content."
                self._finalize(record)
                return record

            # Calculate metrics
            record.metrics.lines_written = _count_lines(record.after_content)
            before_lines = _count_lines(record.before_content or "")

            # Calculate diff
            diff = compute_unified_diff(
                record.before_content or "",
                record.after_content,
                format_display_path(record.file_path),
                max_lines=None,
            )
            record.diff = diff

            if diff:
                additions = sum(
                    1 for line in diff.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
                deletions = sum(
                    1 for line in diff.splitlines()
                    if line.startswith("-") and not line.startswith("---")
                )
                record.metrics.lines_added = additions
                record.metrics.lines_removed = deletions
            elif record.tool_name == "write_real_file" and (record.before_content or "") == "":
                record.metrics.lines_added = record.metrics.lines_written

            record.metrics.bytes_written = len(record.after_content.encode("utf-8"))

            if record.diff is None and before_lines != record.metrics.lines_written:
                record.metrics.lines_added = max(
                    record.metrics.lines_written - before_lines, 0
                )

        self._finalize(record)
        return record

    def _finalize(self, record: FileOperationRecord) -> None:
        """Move record from active to completed."""
        self.completed.append(record)
        self.active.pop(record.tool_call_id, None)


def render_diff_block(diff: str, title: str, console) -> None:
    """Render diff in a Rich panel with syntax highlighting.

    Args:
        diff: Unified diff string
        title: Title for the panel
        console: Rich console instance
    """
    syntax = Syntax(diff, "diff", theme="monokai", line_numbers=False)
    panel = Panel(
        syntax,
        title=title,
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)


def render_file_operation(record: FileOperationRecord, console) -> None:
    """Render file operation result with metrics and diff.

    Args:
        record: Completed FileOperationRecord
        console: Rich console instance
    """
    if record.status == "error":
        console.print(f"\n[red]File operation failed: {record.file_path}[/red]")
        if record.error:
            console.print(f"[red]Error: {record.error}[/red]")
        return

    # Display operation summary with icon
    display_path = format_display_path(record.file_path)
    operation_icon = "\u2713"  # Checkmark
    console.print(f"\n[green]{operation_icon} File operation completed: {display_path}[/green]")

    # Display metrics for write/edit operations
    if record.tool_name in {"write_real_file", "edit_real_file"}:
        metrics = record.metrics

        # Build statistics lines
        stats_lines = []

        if metrics.lines_added or metrics.lines_removed:
            # Show detailed line changes
            change_summary = f"+{metrics.lines_added} / -{metrics.lines_removed}"
            stats_lines.append(f"  Lines changed: [green]+{metrics.lines_added}[/] / [red]-{metrics.lines_removed}[/]")
            stats_lines.append(f"  Total lines: {metrics.lines_written}")
        else:
            # New file or no changes
            stats_lines.append(f"  Lines written: {metrics.lines_written}")

        # Format bytes with human-readable units
        bytes_written = metrics.bytes_written
        if bytes_written >= 1024 * 1024:
            size_str = f"{bytes_written / (1024 * 1024):.2f} MB"
        elif bytes_written >= 1024:
            size_str = f"{bytes_written / 1024:.2f} KB"
        else:
            size_str = f"{bytes_written} bytes"
        stats_lines.append(f"  Size: {size_str}")

        # Display operation type
        op_type = "File created" if not record.before_content else "File modified"
        stats_lines.append(f"  Operation: {op_type}")

        console.print("[dim]" + "\n".join(stats_lines) + "[/dim]")

        # Display diff if available
        if record.diff:
            console.print()
            render_diff_block(record.diff, f"Diff {display_path}", console)
